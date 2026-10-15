"""NO-MODO-XBOX-TUDO-FUNCIONA-01 — a ponte do `mira.set` leva o toque e a inclinação.

A resposta de 28/09/2026 (~16h50) pôs na aba 02 os chips «Cursor | Botões» do touchpad e
«Inclinação» embaixo de cada analógico. A «Inclinação» virou o lado do Analógico Virtual
em 08/10 (`test_o_analogico_virtual_e_um_so.py`), e o «Cursor | Botões» saiu com o desenho
do todo de 15/10/2026, que pôs no lugar o interruptor «Ligado | Desligado» do touchpad
(`test_o_touchpad_liga_e_desliga_na_aba_controles.py`). O gesto `toque` saiu com ele.

Fica a ponte (`ipc_bridge.mira_set_detalhado`): ela leva os dois campos ao daemon, e os
chamadores de hoje (o Analógico Virtual e a Calibrar) mandam o mesmo corpo de antes.

Endereços de rádio: a faixa SINTÉTICA da casa (``aa:bb:cc``), nunca um OUI real.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

_P1, _P2, _P4 = "aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:04"


def _ponte_que_anota(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Any]]:
    from hefesto_dualsense4unix.app import ipc_bridge

    pedidos: list[tuple[str, Any]] = []

    def _safe_call(method: str, params: Any = None) -> tuple[bool, Any]:
        pedidos.append((method, params))
        return True, {"status": "ok"}

    monkeypatch.setattr(ipc_bridge, "_safe_call", _safe_call)
    return pedidos


def test_a_ponte_leva_os_dois_campos(monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: tire o `payload["toque"]` da ponte e o segundo caso reprova."""
    from hefesto_dualsense4unix.app import ipc_bridge

    pedidos = _ponte_que_anota(monkeypatch)
    ipc_bridge.mira_set_detalhado(inclinacao="analogico_direito", uniq=_P4)
    ipc_bridge.mira_set_detalhado(toque="zonas", uniq=_P2)
    ipc_bridge.mira_set_detalhado(toque="nenhum", uniq=_P2)
    assert pedidos == [
        ("mira.set", {"inclinacao": "analogico_direito", "uniq": _P4}),
        ("mira.set", {"toque": "zonas", "uniq": _P2}),
        ("mira.set", {"toque": "nenhum", "uniq": _P2}),
    ]


def test_os_chamadores_de_hoje_mandam_o_mesmo_corpo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Mira e a Calibrar não mandam os campos novos sem pedir."""
    from hefesto_dualsense4unix.app import ipc_bridge

    pedidos = _ponte_que_anota(monkeypatch)
    ipc_bridge.mira_set_detalhado(ligada=True, uniq=_P1)
    ipc_bridge.mira_set_detalhado(sensibilidade=9, uniq=_P1)
    assert ipc_bridge.mira_set_detalhado(uniq=_P1) is None
    assert pedidos == [
        ("mira.set", {"ligada": True, "uniq": _P1}),
        ("mira.set", {"sensibilidade": 9, "uniq": _P1}),
    ]
    padrao = inspect.signature(ipc_bridge.mira_set_detalhado).parameters
    assert padrao["inclinacao"].default is None
    assert padrao["toque"].default is None
