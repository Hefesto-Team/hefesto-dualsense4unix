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


# --------------------------------------------------------------------------
# Seletor de alvo — botões segmentados (sem popup; imune ao bug do cosmic-comp)
# --------------------------------------------------------------------------


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


def _mixin_with_selector(monkeypatch: Any) -> tuple[Any, list[Any], list[int]]:
    from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin

    obj = StatusActionsMixin.__new__(StatusActionsMixin)
    obj._target_combo = _FakeBox()
    obj._target_combo_rows = []
    obj._target_combo_updating = False
    obj._target_combo_visible = False
    obj._target_combo_active = -1
    obj._target_buttons = []
    rebuilds: list[Any] = []
    actives: list[int] = []
    # Evita criar GtkRadioButton de verdade (precisaria de display).
    monkeypatch.setattr(
        StatusActionsMixin,
        "_rebuild_target_buttons",
        lambda self, box, rows: rebuilds.append(rows),
    )
    monkeypatch.setattr(
        StatusActionsMixin,
        "_set_target_active",
        lambda self, pos: actives.append(pos),
    )
    return obj, rebuilds, actives


def test_seletor_idempotente_nao_reconstroi(monkeypatch: Any) -> None:
    """Refresh repetido com o MESMO estado não reconstrói os botões nem re-mostra."""
    obj, rebuilds, _actives = _mixin_with_selector(monkeypatch)
    state = _state(
        {"index": 0, "connected": True, "transport": "bt", "is_primary": True},
        {"index": 1, "connected": True, "transport": "usb"},
    )
    state["output_target_index"] = None

    obj._refresh_controller_target_combo(state)  # 1ª: reconstrói + mostra
    assert len(rebuilds) == 1
    assert obj._target_combo.shown == 1

    for _ in range(5):
        obj._refresh_controller_target_combo(state)
    assert len(rebuilds) == 1  # não reconstruiu de novo
    assert obj._target_combo.shown == 1  # não re-mostrou


def test_short_target_label() -> None:
    from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin

    f = StatusActionsMixin._short_target_label
    assert f("Todos os controles") == "Todos"
    assert f("Controle 1 — BT") == "1 · BT"
    assert f("Controle 2 — USB") == "2 · USB"


def test_render_pausa_enquanto_popup_aberto(monkeypatch: Any) -> None:
    """Com um popup aberto (grab GTK ativo), os renders NÃO tocam widgets.

    É o que impede o re-layout a 10 Hz (sticks tremendo) de fechar o popup
    (BUG-COMBO-POPUP-FLICKER-02).
    """
    from hefesto_dualsense4unix.app.actions import status_actions as sa

    obj = sa.StatusActionsMixin.__new__(sa.StatusActionsMixin)
    toques: list[str] = []
    obj._get = lambda name: toques.append(name) or None  # type: ignore[attr-defined,assignment]

    # Popup aberto → _popup_is_open() True → render retorna sem tocar nada.
    # (mockamos o helper direto p/ não depender do estado global do Gtk nos testes)
    monkeypatch.setattr(sa.StatusActionsMixin, "_popup_is_open", staticmethod(lambda: True))
    obj._render_live_state({"connected": True})
    obj._render_slow_state({"connected": True})
    assert toques == []


def test_seletor_some_com_menos_de_dois(monkeypatch: Any) -> None:
    obj, _rebuilds, _actives = _mixin_with_selector(monkeypatch)
    obj._target_combo_visible = True
    state = _state({"index": 0, "connected": True, "transport": "usb", "is_primary": True})
    obj._refresh_controller_target_combo(state)
    assert obj._target_combo.hidden == 1
    assert obj._target_combo_visible is False
    # Repetir não re-esconde (idempotente).
    obj._refresh_controller_target_combo(state)
    assert obj._target_combo.hidden == 1
