"""BG-BASES-01 (26/08/2026) — *cinco listas respondiam "onde estão os scripts"*."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `app.actions.emulation_actions`, que carrega o GTK")

from hefesto_dualsense4unix.utils import repo_files


LITERAIS_DE_LISTA_A_MAO = (
    "/usr/share/",
    "/usr/local/share/",
    "/app/share/",
    "parents[",
)

MODULOS_CONVERTIDOS = (
    "app/actions/daemon_actions.py",
    "app/actions/emulation_actions.py",
    "cli/cmd_mic.py",
)

RAIZ_DO_PACOTE = Path(repo_files.__file__).resolve().parent.parent


def _linhas_de_docstring(arvore: ast.AST) -> set[int]:
    """As linhas que EXPLICAM, para não confundi-las com as que executam."""
    linhas: set[int] = set()
    for no in ast.walk(arvore):
        if not isinstance(
            no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        corpo = getattr(no, "body", [])
        if (
            corpo
            and isinstance(corpo[0], ast.Expr)
            and isinstance(corpo[0].value, ast.Constant)
            and isinstance(corpo[0].value.value, str)
        ):
            alvo = corpo[0]
            linhas.update(range(alvo.lineno, (alvo.end_lineno or alvo.lineno) + 1))
    return linhas


def _codigo_de(fonte: str) -> list[tuple[int, str]]:
    """As linhas de CÓDIGO de um fonte: sem docstring e sem comentário."""
    docs = _linhas_de_docstring(ast.parse(fonte))
    saida: list[tuple[int, str]] = []
    for numero, linha in enumerate(fonte.splitlines(), start=1):
        if numero in docs:
            continue
        texto = linha.strip()
        if not texto or texto.startswith("#"):
            continue
        saida.append((numero, texto))
    return saida


class TestNenhumaListaAMaoSobreviveu:

    @pytest.mark.parametrize("relativo", MODULOS_CONVERTIDOS)
    def test_o_modulo_inteiro_nao_guarda_uma_segunda_lista(
        self, relativo: str
    ) -> None:
        """A constante de módulo é a porta dos fundos, e ela fica fechada."""
        caminho = RAIZ_DO_PACOTE / relativo
        suspeitas = [
            f"{relativo}:{numero}: {texto}"
            for numero, texto in _codigo_de(caminho.read_text(encoding="utf-8"))
            for literal in LITERAIS_DE_LISTA_A_MAO
            if literal in texto
        ]

        assert not suspeitas, (
            "um caminho de instalação foi escrito à mão fora de "
            "`utils/repo_files.py`:\n  " + "\n  ".join(suspeitas)
        )


class TestAListaDeBases:
    def test_a_busca_unica_conhece_as_seis_bases(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """As seis, e cada uma é um formato de instalação MEDIDO."""
        prefixo = tmp_path / "prefixo"
        casa = tmp_path / "casa"
        monkeypatch.setattr(sys, "prefix", str(prefixo))
        monkeypatch.setenv("XDG_DATA_HOME", str(casa))

        bases = [str(b) for b in repo_files.bases_de_instalacao()]
        nome = repo_files.NOME_NO_SHARE
        esperadas = {
            "a raiz do checkout": str(Path(repo_files.__file__).resolve().parents[3]),
            "o prefixo do wheel (AppImage, venv, Nix)": str(
                prefixo / "share" / nome
            ),
            "o Flatpak": f"/app/share/{nome}",
            "o share do usuário (pip --user)": str(casa / nome),
            "o pacote do sistema (.deb, Arch, Fedora)": f"/usr/share/{nome}",
            "a instalação manual em /usr/local": f"/usr/local/share/{nome}",
        }

        faltando = {
            porque: caminho
            for porque, caminho in esperadas.items()
            if caminho not in bases
        }
        assert not faltando, (
            "a busca única deixou de olhar para um formato de instalação:\n  "
            + "\n  ".join(f"{p}: {c}" for p, c in faltando.items())
            + f"\n\nolhou só para: {bases}"
        )

    def test_a_raiz_do_checkout_e_a_raiz_mesmo(self) -> None:
        """BUG-GUI-REPO-ROOT-OFFBYONE-01: contar um `parents` a menos aponta"""
        primeira = repo_files.bases_de_instalacao()[0]

        assert (primeira / "src" / "hefesto_dualsense4unix").is_dir(), (
            f"a primeira base é {primeira}, que não é a raiz do checkout"
        )


