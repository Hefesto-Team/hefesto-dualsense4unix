"""Lugar vazio diz `P2 • Desconectado`, e não um travessão mudo.

MEDIDO NA TELA EM 05/09/2026, fotografando a aba Vibração com UM controle na
bancada: três colunas igualmente vazias, e só uma delas calada.

===========  ==========================  ===================================
coluna       o que aparecia              por quê
===========  ==========================  ===================================
P2           ``—``                       TEM endereço (``data-hef=
                                         "identidade"``), então o piloto
                                         escrevia o travessão por cima
P3, P4       ``P3 • Desconectado``       são DESENHO — ninguém escreve nelas,
                                         e a frase do gerador sobrevivia
===========  ==========================  ===================================

O TRAVESSÃO CONTINUA CERTO PARA O RESTO DA COLUNA. *"Isto eu não sei"* é a
resposta honesta para o volume de um controle que não está aqui. Mas a
IDENTIDADE do lugar não é desconhecida: o lugar é o P2, e ele está
desconectado. Isso se sabe — e a tela já sabia dizer em dois dos quatro.

A MORDIDA: apague o `if IDENTIDADE_DO_LUGAR in chaves:` de
`pacotes.apagar_os_lugares_sem_dono` e :func:`test_o_lugar_sem_ninguem_se_nomeia` reprova —
o travessão volta a cobrir a identidade.
"""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import (
    IDENTIDADE_DO_LUGAR,
    PONTO_DO_ROTULO,
    SEM_NINGUEM_AQUI,
    TODOS_OS_LUGARES,
    TRAVESSAO,
)

#: UMA COLUNA DE VERDADE, com a identidade e mais dois campos quaisquer. Os
#: dois "quaisquer" existem para provar que a cura NÃO os alcança.
COLUNA_VIVA = {IDENTIDADE_DO_LUGAR: "P1 • Cosmic Red",
               "forca": "balanceado", "motor-forte": "100"}


def _carga_com_um_controle() -> dict:
    return {"colunas": {"p1": dict(COLUNA_VIVA)}}


@pytest.mark.parametrize("pref", sorted(TODOS_OS_LUGARES - {"p1"}))
def test_o_lugar_sem_ninguem_se_nomeia(pref: str) -> None:
    """Cada lugar vazio diz o SEU número e a palavra, não um travessão."""
    carga = pacotes.apagar_os_lugares_sem_dono(_carga_com_um_controle(), com_dono=("p1",))
    esperado = f"P{pref[1:]} {PONTO_DO_ROTULO} {SEM_NINGUEM_AQUI}"
    assert carga["colunas"][pref][IDENTIDADE_DO_LUGAR] == esperado, (
        f"a coluna do {pref.upper()} não diz que está vazia — um travessão "
        "mudo ao lado de duas colunas que dizem `Desconectado` é a tela "
        "discordando de si mesma na mesma linha")


@pytest.mark.parametrize("campo", ["forca", "motor-forte"])
def test_o_resto_da_coluna_continua_travessao(campo: str) -> None:
    """A cura não pode virar "inventar valor para quem não está aqui".

    O travessão é a resposta honesta para o que NÃO se sabe. Só a identidade
    do lugar sai da regra, porque só ela é conhecida.
    """
    carga = pacotes.apagar_os_lugares_sem_dono(_carga_com_um_controle(), com_dono=("p1",))
    assert carga["colunas"]["p2"][campo] == TRAVESSAO


def test_o_lugar_ocupado_nao_e_tocado() -> None:
    """Quem está na mesa continua com o que a aba escreveu."""
    carga = pacotes.apagar_os_lugares_sem_dono(_carga_com_um_controle(), com_dono=("p1",))
    assert carga["colunas"]["p1"] == COLUNA_VIVA


def test_aba_sem_a_chave_nao_ganha_chave_nova() -> None:
    """`chaves` é a união do que a PRÓPRIA carga trouxe — nada nasce aqui.

    Uma aba que não emite `identidade` não pode passar a emitir por causa
    desta cura: o piloto escreveria num endereço que a página não tem, e o
    contador de campos pintados mentiria para cima.
    """
    carga = {"colunas": {"p1": {"forca": "balanceado"}}}
    saida = pacotes.apagar_os_lugares_sem_dono(carga, com_dono=("p1",))
    assert IDENTIDADE_DO_LUGAR not in saida["colunas"]["p2"]


def test_a_frase_e_a_mesma_do_desenho() -> None:
    """A palavra tem UM dono — senão a casa fica com duas versões dela.

    O gerador da aba 05 escreve `P{j} • Desconectado` nas colunas que são
    desenho puro (P3 e P4). Se as duas frases divergirem, a tela mostra as
    duas lado a lado e ninguém vê.
    """
    from pathlib import Path
    raiz = Path(__file__).resolve().parents[2]
    fonte = (raiz / "src/hefesto_dualsense4unix/interface/aba05.py").read_text(
        encoding="utf-8")
    assert f'</span> {SEM_NINGUEM_AQUI}</div>' in fonte, (
        "o gerador da aba 05 deixou de usar a mesma palavra do "
        "`SEM_NINGUEM_AQUI` — as colunas de desenho e as escritas passariam a "
        "dizer coisas diferentes sobre o mesmo estado")
