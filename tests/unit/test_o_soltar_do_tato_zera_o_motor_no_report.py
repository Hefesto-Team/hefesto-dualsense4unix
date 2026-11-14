"""O soltar do tato zera o motor no report (O-SOLTAR-DO-TATO-ZERA-O-MOTOR-NO-REPORT-01).

O padrão de pé no motor de cada controle da mesa misturada (um a quatro, cabo e rádio, com e sem
ponte, Pro e 8BitDo em qualquer posição, na máscara DualSense e na Xbox) e, no meio dele, o modo
que cala (Nativo) ou o jogo que fecha: a última escrita de cada controle, em toda saída que o
padrão ligou, é o zero. Roda o ``TatoVivo``, o ``AtuadorDosMotores``, a saída de produção e o
``AltoFalanteSubsystem`` do produto; só o tocador, o report e o motor do nó são dublês.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from tests.unit.test_o_gatilho_toca_o_tipo_no_lado_dele import (
    CABO,
    NATIVO,
    OITO_BITDO,
    P,
    PRO,
    RADIO_COM_PONTE,
    RADIO_SEM_PONTE,
    SONY,
    XBOX,
    _Mesa,
    _pad,
)

MESAS = {
    "1 cabo": ({P[0]: CABO}, {}),
    "1 rádio": ({P[0]: RADIO_SEM_PONTE}, {}),
    "4 cabos": (dict.fromkeys(P, CABO), {}),
    "3 cabos e 1 rádio": ({P[0]: CABO, P[1]: CABO, P[2]: CABO, P[3]: RADIO_SEM_PONTE}, {}),
    "2 e 2, rádio na frente": (
        {P[0]: RADIO_SEM_PONTE, P[1]: CABO, P[2]: RADIO_COM_PONTE, P[3]: CABO}, {}),
    "1 cabo e 3 rádios": (
        {P[0]: RADIO_COM_PONTE, P[1]: RADIO_SEM_PONTE, P[2]: CABO, P[3]: RADIO_SEM_PONTE}, {}),
    "4 rádios": (dict.fromkeys(P, RADIO_SEM_PONTE), {}),
    "Pro e 8BitDo no meio": (
        {P[0]: CABO, P[1]: RADIO_SEM_PONTE, P[2]: RADIO_SEM_PONTE, P[3]: CABO},
        {P[1]: PRO, P[3]: OITO_BITDO}),
}


def _ultimas(mesa: _Mesa, uniq: str) -> list[tuple[int, int]]:
    """A última escrita de cada saída que tocou este controle."""
    tocador = mesa.tocadores.get(uniq)
    saidas = [
        list(tocador.lados) if tocador is not None else [],
        [(forte, fraco) for u, fraco, forte in mesa.backend.rumble if u == uniq],
        [(forte, fraco) for u, fraco, forte in mesa.no if u == uniq],
    ]
    return [saida[-1] for saida in saidas if saida]


def _o_soltar(mesa: _Mesa, como: str) -> None:
    if como == NATIVO:
        mesa.daemon.is_native_mode = lambda: True
    else:
        mesa.jogo_aberto = False


@pytest.mark.parametrize("chip", [SONY, XBOX])
@pytest.mark.parametrize("como", [NATIVO, "jogo_fechou"])
@pytest.mark.parametrize("nome", list(MESAS))
def test_o_soltar_no_meio_do_padrao_zera_todo_motor_da_mesa(
    nome: str, como: str, chip: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    conexoes, familias = MESAS[nome]
    mesa = _Mesa(monkeypatch, chip=chip, conexoes=dict(conexoes), familias=dict(familias),
                 primario=next(iter(conexoes)))
    for uniq in conexoes:
        if uniq in familias:
            mesa.pads[uniq] = mesa.daemon._coop_manager._players[uniq].vpad = _pad(chip)
        mesa.tipos[uniq] = "tranco"
        mesa.evento(uniq, tv.LADO_ESQUERDO)
    mesa.correr(0.05)
    for uniq in conexoes:
        assert any(e or d for e, d in _ultimas(mesa, uniq)), f"{uniq} não ligou o motor"
    _o_soltar(mesa, como)
    mesa.correr(0.2, desde=0.06)
    for uniq in conexoes:
        assert _ultimas(mesa, uniq) and all(
            par == (0, 0) for par in _ultimas(mesa, uniq)), f"{uniq} ficou com o motor de pé"
    assert not mesa.motor.pendentes
