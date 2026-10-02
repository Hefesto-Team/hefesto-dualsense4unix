"""A receita do backport do BlueZ tem de morar na ÁRVORE, não num ramo arquivado."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.conftest import arvore_congelada

RECEITA = Path("docs/usage/receita-backport-bluez.md")

PADRAO_DE_RAMO_ARQUIVADO = re.compile(r"git\s+show\s+arquivo/")


def _linhas_executaveis(texto: str) -> list[str]:
    """As linhas do script sem as de comentário puro."""
    return [ln for ln in texto.splitlines() if not ln.lstrip().startswith("#")]


def _raiz() -> Path:
    """A raiz para ler os SCRIPTS: a cópia congelada da sessão."""
    return arvore_congelada()


def _raiz_do_repo() -> Path:
    return Path(__file__).resolve().parents[2]


def test_a_receita_do_backport_existe_na_arvore():
    """O arquivo tem de estar no disco, versionado, não num ramo arquivado."""
    caminho = _raiz_do_repo() / RECEITA
    assert caminho.is_file(), (
        f"{RECEITA} não está na árvore. O install.sh e o doctor.sh mandam lê-la "
        "quando o backport falta; sem ela, quem levar o produto para outro PC "
        "recebe uma instrução que não tem como seguir."
    )
    texto = caminho.read_text(encoding="utf-8")
    assert "dpkg-buildpackage" in texto, (
        "a receita existe mas não traz o comando de build; quem seguir não chega aos .deb"
    )
    assert "mk-build-deps" in texto, "a receita não diz como instalar as dependências de build"


@pytest.mark.parametrize("arquivo", ["install.sh", "scripts/doctor.sh"])
def test_o_install_nao_manda_para_ramo_arquivado(arquivo):
    """Nenhum dos dois pode instruir por `git show arquivo/...`."""
    texto = (_raiz() / arquivo).read_text(encoding="utf-8")
    achados = [ln for ln in _linhas_executaveis(texto) if PADRAO_DE_RAMO_ARQUIVADO.search(ln)]
    assert not achados, (
        f"{arquivo} manda o usuário para um ramo arquivado ({achados}). "
        "Numa máquina limpa esse ramo não existe no clone, e a instrução é impossível "
        f"de seguir. Aponte para {RECEITA}, que está na árvore."
    )


@pytest.mark.parametrize("arquivo", ["install.sh", "scripts/doctor.sh"])
def test_os_dois_apontam_para_a_receita_pelo_caminho_da_arvore(arquivo):
    """Além de não apontar para o ramo, têm de apontar para o lugar certo."""
    texto = (_raiz() / arquivo).read_text(encoding="utf-8")
    assert RECEITA.name in texto, (
        f"{arquivo} não cita {RECEITA.name}; quem ficar sem o backport não sabe para onde ir"
    )
