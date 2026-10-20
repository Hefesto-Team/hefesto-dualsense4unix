"""O título do cartão de um externo sem número de jogador não dobra o travessão.

Medido em 20/10/2026 no piloto das dez abas (O-EXTERNO-SEM-NUMERO-NAO-DOBRA-O-TRAVESSAO-01):
com os quatro DualSense ligados, o externo fica sem lugar de co-op, o daemon manda
`player_slot: null`, e o cartão da 01 e da 08 dizia «Controle — — Nintendo».
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.app.actions.home_actions import _format_external_title

NINTENDO = {"vid": "057e", "pid": "2009", "bus": "bluetooth", "name": "Pro Controller"}


@pytest.mark.parametrize("bus", ["usb", "bluetooth"])
def test_sem_numero_o_titulo_tem_um_travessao_so(bus: str) -> None:
    """A prova da D-2010-O-EXTERNO-SEM-NUMERO-TEM-UM-TRAVESSAO, no cabo e no rádio."""
    titulo = _format_external_title({**NINTENDO, "bus": bus, "player_slot": None})
    assert "— —" not in titulo
    assert titulo.count("—") == 1
    assert titulo.startswith("Controle — ")


def test_com_numero_o_titulo_de_sempre() -> None:
    titulo = _format_external_title({**NINTENDO, "player_slot": 3})
    assert titulo.startswith("Controle 3 — ")
    assert titulo.count("—") == 1
