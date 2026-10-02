"""Lugar vazio diz `P2 • Desconectado`, e não um travessão mudo."""

from __future__ import annotations

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import (
    IDENTIDADE_DO_LUGAR,
    PONTO_DO_ROTULO,
    SEM_NINGUEM_AQUI,
    TODOS_OS_LUGARES,
    TRAVESSAO,
)

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
    """A cura não pode virar "inventar valor para quem não está aqui"."""
    carga = pacotes.apagar_os_lugares_sem_dono(_carga_com_um_controle(), com_dono=("p1",))
    assert carga["colunas"]["p2"][campo] == TRAVESSAO


def test_o_lugar_ocupado_nao_e_tocado() -> None:
    """Quem está na mesa continua com o que a aba escreveu."""
    carga = pacotes.apagar_os_lugares_sem_dono(_carga_com_um_controle(), com_dono=("p1",))
    assert carga["colunas"]["p1"] == COLUNA_VIVA


def test_aba_sem_a_chave_nao_ganha_chave_nova() -> None:
    """`chaves` é a união do que a PRÓPRIA carga trouxe — nada nasce aqui."""
    carga = {"colunas": {"p1": {"forca": "balanceado"}}}
    saida = pacotes.apagar_os_lugares_sem_dono(carga, com_dono=("p1",))
    assert IDENTIDADE_DO_LUGAR not in saida["colunas"]["p2"]


def test_a_frase_e_a_mesma_do_desenho() -> None:
    """A palavra tem UM dono — senão a casa fica com duas versões dela."""
    from pathlib import Path
    raiz = Path(__file__).resolve().parents[2]
    fonte = (raiz / "src/hefesto_dualsense4unix/interface/aba05.py").read_text(
        encoding="utf-8")
    assert f'</span> {SEM_NINGUEM_AQUI}</div>' in fonte, (
        "o gerador da aba 05 deixou de usar a mesma palavra do "
        "`SEM_NINGUEM_AQUI` — as colunas de desenho e as escritas passariam a "
        "dizer coisas diferentes sobre o mesmo estado")
