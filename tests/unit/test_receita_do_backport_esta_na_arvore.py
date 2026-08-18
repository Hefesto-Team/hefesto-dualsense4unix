"""A receita do backport do BlueZ tem de morar na ÁRVORE, não num ramo arquivado.

Defeito medido em 11/08/2026, na auditoria de "o que só existe nesta máquina":

O `install.sh` e o `doctor.sh` mandavam quem estivesse sem o backport rodar
`git show arquivo/processo-pre-1.0:docs/process/estudos/...` — um ramo que não
aparece em `git branch -a`. Pior: `install.sh:1638` já citava o documento pelo
caminho da árvore, **como se ele estivesse aqui**, e ele não estava.

O efeito prático é o pior possível para o objetivo dela de levar o produto para
outro PC: numa máquina limpa o `apt` só oferece o bluez 5.72, o `doctor` REPROVA
(piso 5.79) e a mensagem de erro aponta para um lugar que a pessoa não tem como
alcançar. O único FAIL que uma máquina limpa levaria no caminho `native`, e ele
vinha com uma instrução impossível de seguir.

A MORDIDA, provada em 11/08/2026
================================
Renomeado `docs/process/estudos/2026-07-19-estudo-bluez-backport-onda-r.md`,
`test_a_receita_do_backport_existe_na_arvore` reprova. Trocada a mensagem do
`install.sh` de volta para `git show arquivo/processo-pre-1.0:`,
`test_o_install_nao_manda_para_ramo_arquivado` reprova. Idem no `doctor.sh` com
o seu próprio caso. Desfeitas as três, verde.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.conftest import arvore_congelada

#: O documento que o `install.sh` e o `doctor.sh` mandam ler quando falta o
#: backport. O nome é citado nos dois, então mudá-lo quebra os dois.
RECEITA = Path("docs/process/estudos/2026-07-19-estudo-bluez-backport-onda-r.md")

#: A forma que NÃO pode voltar: instrução que só funciona para quem tem o ramo
#: arquivado no clone — ou seja, praticamente ninguém numa máquina nova.
#:
#: O casamento é feito só em linha EXECUTÁVEL. Um comentário que cita a forma
#: antiga para explicar o que foi curado é exatamente o que a casa manda
#: escrever (não se apaga decisão medida), e reprová-lo seria castigar a
#: honestidade — o defeito que a PORTAO-VIVO-01 nomeia.
PADRAO_DE_RAMO_ARQUIVADO = re.compile(r"git\s+show\s+arquivo/")


def _linhas_executaveis(texto: str) -> list[str]:
    """As linhas do script sem as de comentário puro."""
    return [ln for ln in texto.splitlines() if not ln.lstrip().startswith("#")]


def _raiz() -> Path:
    """A raiz para ler os SCRIPTS: a cópia congelada da sessão.

    `docs/` NÃO está em `_CONGELAR` (tests/conftest.py) — a foto cobre só o que
    uma bancada de shell executa. Por isso o caso do documento lê da árvore de
    trabalho, e só os scripts leem daqui.
    """
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
    # Não basta existir: tem de conter a receita de fato. Um arquivo vazio ou
    # um resumo sem os comandos passaria num teste de existência e falharia na
    # mão de quem precisa.
    assert "dpkg-buildpackage" in texto, (
        "a receita existe mas não traz o comando de build; quem seguir não chega aos .deb"
    )
    assert "mk-build-deps" in texto, "a receita não diz como instalar as dependências de build"


@pytest.mark.parametrize("arquivo", ["install.sh", "scripts/doctor.sh"])
def test_o_install_nao_manda_para_ramo_arquivado(arquivo):
    """Nenhum dos dois pode instruir por `git show arquivo/...`.

    Vale para os dois pelo mesmo motivo, e por isso são o mesmo caso: cada um
    é a única mensagem que a pessoa vê no momento em que precisa da receita.
    """
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
