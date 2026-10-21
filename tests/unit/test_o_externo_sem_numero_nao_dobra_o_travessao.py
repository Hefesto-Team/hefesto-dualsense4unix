"""A tela mostra no máximo quatro controles: o externo sem número de jogador não ganha cartão.

Medido em 20/10/2026 no piloto das dez abas: com os quatro DualSense ligados, o externo fica sem
lugar de co-op, o daemon manda `player_slot: null`, e a 01 e a 08 ganhavam um quinto cartão,
«Controle — Nintendo». A A-TELA-MOSTRA-NO-MAXIMO-QUATRO-CONTROLES-01 tira o cartão: só o externo
que ocupa um lugar livre (com número) aparece, os DualSense primeiro.

MORDIDA: devolva `externos_na_mesa` sem o filtro do `slot_of` (a lista inteira) e os testes do
teto reprovam nas duas abas, no cabo e no rádio.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from pacotes import Contexto
from pacotes import a01_jogar, a08_conexoes

from hefesto_dualsense4unix.app.actions.home_actions import (
    _format_external_title,
    externos_na_mesa,
)

NINTENDO = {"vid": "057e", "pid": "2009", "name": "Pro Controller"}
VIVO: dict[str, Any] = {
    "connected": True, "native_mode": False,
    "gamepad_emulation": {"enabled": True, "flavor": "dualsense"}, "paused": False,
}
CARTAO = {a01_jogar: 'class="ext-cartao"', a08_conexoes: 'class="ext-linha"'}


def _cartoes(pacote: Any, externos: list[dict[str, Any]]) -> int:
    ctx = Contexto(state=dict(VIVO), mesa=[], conectados=[], externos=externos)
    return pacote._html_dos_externos(ctx).count(CARTAO[pacote])


@pytest.mark.parametrize("pacote", [a01_jogar, a08_conexoes], ids=["01", "08"])
@pytest.mark.parametrize("bus", ["usb", "bluetooth"])
def test_quatro_dualsense_e_um_externo_sem_numero_dao_quatro_cartoes(pacote: Any, bus: str) -> None:
    """A prova da D-2010-A-TELA-MOSTRA-NO-MAXIMO-QUATRO-CONTROLES."""
    externo = {**NINTENDO, "bus": bus, "player_slot": None}
    assert 4 + _cartoes(pacote, [externo]) == 4


@pytest.mark.parametrize("pacote", [a01_jogar, a08_conexoes], ids=["01", "08"])
@pytest.mark.parametrize("bus", ["usb", "bluetooth"])
def test_tres_dualsense_e_o_externo_com_numero_4_dao_quatro_cartoes(pacote: Any, bus: str) -> None:
    externo = {**NINTENDO, "bus": bus, "player_slot": 4}
    assert 3 + _cartoes(pacote, [externo]) == 4


def test_a_lista_da_mesa_so_leva_quem_tem_numero() -> None:
    """O dono é `externos_na_mesa`: o piloto (`hefesto_vivo`) e as duas abas passam por ele."""
    com, sem = {**NINTENDO, "player_slot": 3}, {**NINTENDO, "player_slot": None}
    assert externos_na_mesa({"external": [com, sem]}) == [com]
    assert externos_na_mesa(None, [sem]) == []


def test_com_numero_o_titulo_de_sempre() -> None:
    titulo = _format_external_title({**NINTENDO, "bus": "usb", "player_slot": 3})
    assert titulo.startswith("Controle 3 — ")
    assert titulo.count("—") == 1
