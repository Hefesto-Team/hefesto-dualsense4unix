"""FEAT-DSX-MULTI-CONTROLLER-01 — surfacing de N controles no tray e na GUI.

O `daemon.state_full` passou a expor um bloco `controllers` (um item por
controle físico, com `transport` e `is_primary`). Tray, aba Status e janela
compacta mostram "N controles (BT + USB)" quando há 2+. Estes testes cobrem a
lógica de formatação (pura), incluindo a degradação graciosa para daemon antigo
sem o bloco e para falha de IPC.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock


def _state(*controllers: dict[str, Any]) -> dict[str, Any]:
    return {"connected": True, "transport": "bt", "controllers": list(controllers)}


def _make_tray(on_state: Any) -> Any:
    from hefesto_dualsense4unix.app.tray import AppTray

    return AppTray(
        on_show_window=MagicMock(),
        on_quit=MagicMock(),
        on_list_profiles=MagicMock(return_value=[]),
        on_switch_profile=MagicMock(return_value=True),
        on_state=on_state,
    )


def test_status_connected_controllers_filtra_e_ordena() -> None:
    from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin

    state = _state(
        {"connected": True, "transport": "bt", "is_primary": True},
        {"connected": False, "transport": "usb"},
        {"connected": True, "transport": "usb"},
    )
    conectados = StatusActionsMixin._connected_controllers(state)
    assert [c["transport"] for c in conectados] == ["bt", "usb"]


def test_status_connected_controllers_daemon_antigo() -> None:
    from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin

    assert StatusActionsMixin._connected_controllers({"connected": True}) == []


class _FakeBox:
    """Box fake que conta show()/hide() do seletor de botões."""

    def __init__(self) -> None:
        self.shown = 0
        self.hidden = 0

    def show(self) -> None:
        self.shown += 1

    def hide(self) -> None:
        self.hidden += 1

    def get_children(self) -> list[Any]:
        return []

    def remove(self, _child: Any) -> None:
        pass


