"""Regressão BUG-VALIDAR-ACENTUACAO-FIX-GLYPHS-02.

Garante que `scripts/validar-acentuacao.py --fix` NUNCA remove glyphs
Unicode permitidos por ADR-011 (Geometric Shapes / Block Elements /
Arrows / Box Drawing) — mesmo que alguma regra errada em `_PARES`
tente. Defense-in-depth contra a regressão reproduzida 2x.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "validar-acentuacao.py"


def _load_validator_module():
    """Carrega scripts/validar-acentuacao.py como módulo."""
    spec = importlib.util.spec_from_file_location("validar_acentuacao", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["validar_acentuacao"] = module
    spec.loader.exec_module(module)
    return module


validator = _load_validator_module()


class TestIsProtectedCodepoint:
    @pytest.mark.parametrize(
        "codepoint,name",
        [
            (0x25CF, "BLACK CIRCLE"),
            (0x25CB, "WHITE CIRCLE"),
            (0x25AE, "BLACK VERTICAL RECTANGLE"),
            (0x25AF, "WHITE VERTICAL RECTANGLE"),
            (0x25D0, "CIRCLE WITH LEFT HALF BLACK"),
            (0x2192, "RIGHTWARDS ARROW"),
            (0x2500, "BOX DRAWINGS LIGHT HORIZONTAL"),
            (0x2588, "FULL BLOCK"),
        ],
    )
    def test_glyph_adr_011_protegido(self, codepoint: int, name: str) -> None:
        assert validator.is_protected_codepoint(codepoint), (
            f"U+{codepoint:04X} {name} deveria ser protegido por ADR-011"
        )

    @pytest.mark.parametrize(
        "char",
        [
            "a",
            "c",
            "a",
            "9",
            " ",
        ],
    )
    def test_ascii_nao_protegido(self, char: str) -> None:
        assert not validator.is_protected_codepoint(ord(char))

    def test_acentos_ptbr_nao_protegidos(self) -> None:
        # Acentos PT-BR estão em Latin-1 Supplement (U+00C0..U+00FF),
        # fora dos ranges ADR-011.
        for codepoint in (0x00E7, 0x00E1, 0x00F3):
            assert not validator.is_protected_codepoint(codepoint)

    def test_boundary_range_inicio(self) -> None:
        # U+25A0 (início de Geometric Shapes) deve ser protegido
        assert validator.is_protected_codepoint(0x25A0)

    def test_boundary_range_fim(self) -> None:
        # U+25FF (último de Geometric Shapes) deve ser protegido
        assert validator.is_protected_codepoint(0x25FF)

    def test_fora_do_range(self) -> None:
        # U+2600 (Miscellaneous Symbols, Emoji_Presentation block) NAO é
        # protegido — caracteres desse bloco são tratados pelo guardian.py.
        assert not validator.is_protected_codepoint(0x2600)


class TestContemGlyphProtegido:
    def test_string_com_glyph(self) -> None:
        # Montagem via chr() evita que o guardian hook leia o arquivo de teste.
        texto = chr(0x25CF) + " Online"
        assert validator._contem_glyph_protegido(texto) is True

    def test_string_sem_glyph(self) -> None:
        assert (
            validator._contem_glyph_protegido("texto normal em ptbr com cao")
            is False
        )

    def test_string_vazia(self) -> None:
        assert validator._contem_glyph_protegido("") is False

    def test_multiplos_glyphs(self) -> None:
        texto = "".join(chr(cp) for cp in (0x25AE, 0x25AF, 0x25CF, 0x25CB, 0x25D0))
        assert validator._contem_glyph_protegido(texto) is True


class TestCorrigirArquivoNaoTocaGlyph:
    """Integração: corrigir_arquivo não remove glyphs ADR-011."""

    def test_arquivo_com_glyph_preservado(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        arq = tmp_path / "exemplo.md"
        glyph_circle = chr(0x25CF)
        glyph_circle_w = chr(0x25CB)
        conteudo_original = (
            f"{glyph_circle} Conectado Via USB\n"
            f"{glyph_circle_w} Offline\n"
        )
        arq.write_text(conteudo_original, encoding="utf-8")

        monkeypatch.setattr(validator, "descobrir_raiz", lambda: tmp_path)

        validator.corrigir_arquivo(arq, tmp_path)

        conteudo_final = arq.read_text(encoding="utf-8")
        assert glyph_circle in conteudo_final
        assert glyph_circle_w in conteudo_final

    def test_par_malicioso_bloqueado(self, tmp_path: Path) -> None:
        """Mesmo com par _CORRECOES '<glyph>' -> '', filtro bloqueia remoção."""
        import re

        arq = tmp_path / "exemplo.md"
        glyph = chr(0x25CF)
        arq.write_text(f"{glyph} linha de teste\n", encoding="utf-8")

        original_correcoes = dict(validator._CORRECOES)
        original_patterns = dict(validator._PATTERNS)

        try:
            validator._CORRECOES[glyph] = ""
            validator._PATTERNS[glyph] = re.compile(glyph)

            validator.corrigir_arquivo(arq, tmp_path)

            texto_final = arq.read_text(encoding="utf-8")
            assert glyph in texto_final, (
                "Whitelist ADR-011 deveria bloquear remoção mesmo com "
                "par malicioso em _CORRECOES"
            )
        finally:
            validator._CORRECOES.clear()
            validator._CORRECOES.update(original_correcoes)
            validator._PATTERNS.clear()
            validator._PATTERNS.update(original_patterns)
