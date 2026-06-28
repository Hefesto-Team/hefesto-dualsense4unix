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


# --------------------------------------------------------------------------
# Tray — _controllers_suffix
# --------------------------------------------------------------------------


def _make_tray(on_state: Any) -> Any:
    from hefesto_dualsense4unix.app.tray import AppTray

    return AppTray(
        on_show_window=MagicMock(),
        on_quit=MagicMock(),
        on_list_profiles=MagicMock(return_value=[]),
        on_switch_profile=MagicMock(return_value=True),
        on_state=on_state,
    )


def test_tray_suffix_dois_controles() -> None:
    tray = _make_tray(
        lambda: _state(
            {"connected": True, "transport": "bt", "is_primary": True},
            {"connected": True, "transport": "usb"},
        )
    )
    assert tray._controllers_suffix() == " · 2 controles (BT + USB)"


def test_tray_suffix_um_controle_vazio() -> None:
    tray = _make_tray(
        lambda: _state({"connected": True, "transport": "usb", "is_primary": True})
    )
    assert tray._controllers_suffix() == ""


def test_tray_suffix_ignora_desconectados() -> None:
    tray = _make_tray(
        lambda: _state(
            {"connected": True, "transport": "bt", "is_primary": True},
            {"connected": False, "transport": "usb"},
        )
    )
    assert tray._controllers_suffix() == ""


def test_tray_suffix_sem_on_state() -> None:
    tray = _make_tray(None)
    assert tray._controllers_suffix() == ""


def test_tray_suffix_daemon_antigo_sem_bloco() -> None:
    # Daemon antigo: state_full sem a chave `controllers`.
    tray = _make_tray(lambda: {"connected": True, "transport": "usb"})
    assert tray._controllers_suffix() == ""


def test_tray_suffix_tolera_excecao_de_ipc() -> None:
    def _boom() -> dict[str, Any]:
        raise RuntimeError("daemon offline")

    tray = _make_tray(_boom)
    assert tray._controllers_suffix() == ""


def test_tray_suffix_estado_none() -> None:
    tray = _make_tray(lambda: None)
    assert tray._controllers_suffix() == ""


# --------------------------------------------------------------------------
# Aba Status — helpers estáticos
# --------------------------------------------------------------------------


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


def test_status_controllers_transports_label() -> None:
    from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin

    conectados = [
        {"connected": True, "transport": "bt", "is_primary": True},
        {"connected": True, "transport": "usb"},
    ]
    assert StatusActionsMixin._controllers_transports(conectados) == "BT + USB"
