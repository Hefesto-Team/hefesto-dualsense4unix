"""Regressão BUG-VALIDAR-ACENTUACAO-FIX-GLYPHS-03.

Defesa em camadas (pre-pass + post-pass) contra strip de glyphs Unicode
permitidos por ADR-011. Complementa `test_validar_acentuacao_glyphs.py`
(camada 1) com cenários de defense-in-depth: linha inteira com glyph
nunca é tocada e, mesmo que tocada, pós-verificação reverte se glyph
sumir.

Cenários cobertos:
- BLACK CIRCLE / WHITE CIRCLE em linha com palavra-alvo do dicionário
  (pre-pass pula a linha).
- Par malicioso `_CORRECOES[glyph] = ""` injetado para 5 codepoints
  reportados (●○◐△□).
- Glyph dentro de docstring `.py`.
- D-pad arrows (↑↓←→) em legenda.
- Face buttons (triangulo, circulo, quadrado) — todos em ranges ADR-011.
- White-box: post-pass reverte se filtro camada 1 falhar (monkeypatch).
- White-box: pre-pass pula linha inteira (palavra-alvo permanece intacta).
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


class TestPrePassPulaLinhaComGlyph:
    """Pre-pass: linhas com glyph protegido nunca são corrigidas."""

    def test_validar_acentuacao_preserva_glyph_pontuado(
        self, tmp_path: Path
    ) -> None:
        """Linha com `●` + palavra-alvo do dicionário é pulada inteira.

        Comportamento intencional: o custo de um falso negativo (palavra
        sem acento na linha do glyph) é menor que o custo do strip.
        """
        arq = tmp_path / "exemplo.py"
        glyph = chr(0x25CF)  # BLACK CIRCLE
        # `funcao` está no dicionário _CORRECOES; sem o pre-pass seria
        # corrigido para `função`. Com o pre-pass, a linha sai intacta.
        conteudo = f'msg = "{glyph} funcao status atual"\n'
        arq.write_text(conteudo, encoding="utf-8")

        validator.corrigir_arquivo(arq, tmp_path)

        final = arq.read_text(encoding="utf-8")
        assert glyph in final, "glyph BLACK CIRCLE deve sobreviver"
        assert "funcao" in final, (
            "pre-pass deve pular a linha inteira: palavra-alvo permanece"
        )

    def test_validar_acentuacao_preserva_dpad_arrows(
        self, tmp_path: Path
    ) -> None:
        """D-pad arrows (↑↓←→) — codepoints U+2191/93/90/92 — sobrevivem."""
        arq = tmp_path / "exemplo.py"
        arrows = chr(0x2191) + chr(0x2193) + chr(0x2190) + chr(0x2192)
        conteudo = f'legend = "D-pad ({arrows}) — direcao"\n'
        arq.write_text(conteudo, encoding="utf-8")

        validator.corrigir_arquivo(arq, tmp_path)

        final = arq.read_text(encoding="utf-8")
        for arrow in arrows:
            assert arrow in final, f"arrow U+{ord(arrow):04X} deve sobreviver"

    def test_validar_acentuacao_preserva_face_buttons(
        self, tmp_path: Path
    ) -> None:
        """Face buttons △ ○ □ — todos em UNICODE_ALLOWED_RANGES."""
        arq = tmp_path / "exemplo.py"
        triangulo = chr(0x25B3)
        circulo = chr(0x25CB)
        quadrado = chr(0x25A1)
        conteudo = (
            f'mapping = "{triangulo} {circulo} {quadrado} configuracao"\n'
        )
        arq.write_text(conteudo, encoding="utf-8")

        validator.corrigir_arquivo(arq, tmp_path)

        final = arq.read_text(encoding="utf-8")
        assert triangulo in final, "U+25B3 △ deve sobreviver"
        assert circulo in final, "U+25CB ○ deve sobreviver"
        assert quadrado in final, "U+25A1 □ deve sobreviver"

    def test_validar_acentuacao_preserva_glyph_em_docstring(
        self, tmp_path: Path
    ) -> None:
        """Glyph em docstring `.py` é preservado pelo pre-pass."""
        arq = tmp_path / "modulo.py"
        glyph = chr(0x25CF)
        conteudo = (
            "def status():\n"
            f'    """Retorna {glyph} ativo na funcao."""\n'
            "    return True\n"
        )
        arq.write_text(conteudo, encoding="utf-8")

        validator.corrigir_arquivo(arq, tmp_path)

        final = arq.read_text(encoding="utf-8")
        assert glyph in final, "glyph dentro da docstring deve sobreviver"


class TestParMaliciosoBloqueado:
    """Mesmo com par malicioso em _CORRECOES, glyph sobrevive."""

    @pytest.mark.parametrize(
        "codepoint,name",
        [
            (0x25CF, "BLACK CIRCLE"),
            (0x25CB, "WHITE CIRCLE"),
            (0x25D0, "CIRCLE WITH LEFT HALF BLACK"),
            (0x25B3, "WHITE UP-POINTING TRIANGLE"),
            (0x25A1, "WHITE SQUARE"),
        ],
    )
    def test_validar_acentuacao_preserva_glyph_em_par_malicioso(
        self,
        tmp_path: Path,
        codepoint: int,
        name: str,
    ) -> None:
        """Cinco codepoints reportados na regressão sobrevivem com par malicioso.

        Variante explícita de `test_par_malicioso_bloqueado` (já existente em
        `_glyphs.py`) cobrindo cada um dos 5 glyphs reportados na 3a
        reprodução do strip ADR-011.
        """
        import re

        arq = tmp_path / "exemplo.md"
        glyph = chr(codepoint)
        arq.write_text(f"{glyph} linha de teste\n", encoding="utf-8")

        original_correcoes = dict(validator._CORRECOES)
        original_patterns = dict(validator._PATTERNS)

        try:
            validator._CORRECOES[glyph] = ""
            validator._PATTERNS[glyph] = re.compile(glyph)

            validator.corrigir_arquivo(arq, tmp_path)

            final = arq.read_text(encoding="utf-8")
            assert glyph in final, (
                f"U+{codepoint:04X} {name} deveria sobreviver com par malicioso"
            )
        finally:
            validator._CORRECOES.clear()
            validator._CORRECOES.update(original_correcoes)
            validator._PATTERNS.clear()
            validator._PATTERNS.update(original_patterns)


class TestPostPassReverteSeGlyphPerdido:
    """White-box: post-pass detecta perda e reverte."""

    def test_post_pass_reverte_se_glyph_perdido(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Simula falha das camadas 1+2 (pre-pass) e confirma que post-pass age.

        Estratégia: o pre-pass usa `_contem_glyph_protegido(linha)` antes
        do loop de pares. Se monkeypatcharmos a função para retornar False
        durante a fase pre-pass + camada 1, mas True na fase post-pass,
        forçamos exatamente o cenário hipotético do post-pass.

        Implementação prática: counter via closure que retorna False nas
        primeiras N invocações e True depois — assim pre-pass e filtro
        camada 1 deixam passar, mas o post-pass detecta a perda.
        """
        import re

        arq = tmp_path / "exemplo.md"
        glyph = chr(0x25CF)
        # Linha com glyph + texto que casa par malicioso.
        arq.write_text(f"{glyph} alvo\n", encoding="utf-8")

        original_correcoes = dict(validator._CORRECOES)
        original_patterns = dict(validator._PATTERNS)
        original_contem = validator._contem_glyph_protegido

        chamadas: list[str] = []

        def contem_falso_nas_primeiras_2(texto: str) -> bool:
            chamadas.append(texto)
            # Pre-pass (1a chamada com `linha`) e filtro camada 1 (chamadas
            # com slices) retornam False — passa direto. Post-pass usa
            # `linha` original e `nova` — neste momento queremos comportamento
            # verdadeiro para detectar perda.
            if len(chamadas) <= 2:
                return False
            return original_contem(texto)

        try:
            validator._CORRECOES["alvo"] = ""
            validator._PATTERNS["alvo"] = re.compile(
                r"(?<![A-Za-z0-9_])alvo(?![A-Za-z0-9_])"
            )
            monkeypatch.setattr(
                validator,
                "_contem_glyph_protegido",
                contem_falso_nas_primeiras_2,
            )

            # Cenário: pre-pass deixa passar (1a chamada → False), filtro
            # camada 1 deixa passar (2a chamada com slice → False), aplica
            # substituição "alvo" → "" (linha vira `<glyph> `). O glyph
            # sobrevive nesta substituição específica (estamos removendo
            # "alvo", não o glyph), então post-pass NÃO precisa reverter.
            # Para forçar reversão de fato, a substituição precisa REMOVER
            # o glyph. Trocamos o par para mapear o próprio glyph.
            validator._CORRECOES.clear()
            validator._CORRECOES.update(original_correcoes)
            validator._CORRECOES[glyph] = ""
            validator._PATTERNS.clear()
            validator._PATTERNS.update(original_patterns)
            validator._PATTERNS[glyph] = re.compile(glyph)

            validator.corrigir_arquivo(arq, tmp_path)

            final = arq.read_text(encoding="utf-8")
            assert glyph in final, (
                "post-pass deveria detectar perda do glyph e reverter a linha"
            )
            captured = capsys.readouterr()
            assert "[ADR-011 POST]" in captured.err, (
                "post-pass deve emitir warning [ADR-011 POST] em stderr"
            )
        finally:
            validator._CORRECOES.clear()
            validator._CORRECOES.update(original_correcoes)
            validator._PATTERNS.clear()
            validator._PATTERNS.update(original_patterns)


class TestPrePassWhiteBox:
    """Pre-pass white-box: verifica comportamento intencional."""

    def test_pre_pass_pula_linha_inteira(self, tmp_path: Path) -> None:
        """Palavra-alvo na mesma linha do glyph permanece intocada.

        Documenta a `Decisao de design` da sprint: pre-pass é conservador.
        Linhas com glyph não recebem fix de acento — usuário corrige
        manualmente se necessário.
        """
        arq = tmp_path / "exemplo.py"
        glyph = chr(0x25CF)
        # Múltiplas palavras-alvo do dicionário na mesma linha.
        conteudo = (
            f'msg = "{glyph} funcao validacao configuracao comunicacao"\n'
        )
        arq.write_text(conteudo, encoding="utf-8")

        subs_count = validator.corrigir_arquivo(arq, tmp_path)

        final = arq.read_text(encoding="utf-8")
        assert subs_count == 0, "pre-pass deve impedir qualquer substituição"
        assert "funcao" in final
        assert "validacao" in final
        assert "configuracao" in final
        assert "comunicacao" in final
        assert glyph in final
