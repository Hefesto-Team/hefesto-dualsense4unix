"""Máquina de estado do reconnect do header (UX-RECONNECT-01)."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("status_actions: o reconectar da janela")

import sys
import types
from typing import Any

import pytest


def _install_gi_stubs() -> None:
    existente = sys.modules.get("gi")
    if existente is None or getattr(existente, "__spec__", None) is not None:
        try:
            import gi

            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk  # noqa: F401

            return
        except Exception:  # pragma: no cover — ambientes sem GTK
            pass

    gi_mod = types.ModuleType("gi")

    def _require_version(_name: str, _ver: str) -> None:
        return None

    gi_mod.require_version = _require_version  # type: ignore[attr-defined]
    repo_mod = types.ModuleType("gi.repository")
    gtk_mod = types.ModuleType("gi.repository.Gtk")
    glib_mod = types.ModuleType("gi.repository.GLib")

    class _FakeBuilder:
        pass

    class _FakeWindow:
        pass

    gtk_mod.Builder = _FakeBuilder  # type: ignore[attr-defined]
    gtk_mod.Window = _FakeWindow  # type: ignore[attr-defined]
    gtk_mod.Button = object  # type: ignore[attr-defined]
    gtk_mod.ComboBoxText = object  # type: ignore[attr-defined]
    gtk_mod.Switch = object  # type: ignore[attr-defined]
    gtk_mod.TextView = object  # type: ignore[attr-defined]
    gtk_mod.TextBuffer = object  # type: ignore[attr-defined]
    gtk_mod.DrawingArea = object  # type: ignore[attr-defined]
    gtk_mod.Box = object  # type: ignore[attr-defined]
    gtk_mod.Grid = object  # type: ignore[attr-defined]
    gtk_mod.Label = object  # type: ignore[attr-defined]
    gtk_mod.Align = type("Align", (), {"CENTER": 0})  # type: ignore[attr-defined]
    glib_mod.timeout_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.timeout_add_seconds = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.idle_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]

    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GLib"] = glib_mod


_install_gi_stubs()

from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin
from hefesto_dualsense4unix.app.constants import RECONNECT_FAIL_THRESHOLD


class _FakeLabel:
    def __init__(self) -> None:
        self.markup: str | None = None
        self.text: str | None = None
        self.visible: bool | None = None

    def set_markup(self, markup: str) -> None:
        self.markup = markup

    def set_text(self, text: str) -> None:
        self.text = text

    def set_visible(self, value: bool) -> None:
        self.visible = value

    def set_fraction(self, _frac: float) -> None:  # pragma: no cover
        pass


class _FakeBar(_FakeLabel):
    def set_fraction(self, _frac: float) -> None:
        pass


class _FakeBuilder:
    def __init__(self) -> None:
        self._widgets: dict[str, Any] = {}

    def get_object(self, wid: str) -> Any:
        if wid not in self._widgets:
            self._widgets[wid] = (
                _FakeBar() if "bar" in wid else _FakeLabel()
            )
        return self._widgets[wid]


class _Host(StatusActionsMixin):
    """Host mínimo para exercitar a máquina de estado sem janela real."""

    def __init__(self) -> None:
        self.builder = _FakeBuilder()
        self._reconnect_state = "online"
        self._consecutive_failures = 0


@pytest.fixture
def host() -> _Host:
    return _Host()


def test_initial_state_is_online(host: _Host) -> None:
    assert host._reconnect_state == "online"
    assert host._consecutive_failures == 0


def test_ipc_success_keeps_online_and_zeroes_counter(host: _Host) -> None:
    host._consecutive_failures = 2
    host._reconnect_state = "reconnecting"

    host._update_reconnect_state({"connected": True, "transport": "usb"})

    assert host._reconnect_state == "online"
    assert host._consecutive_failures == 0
    header = host.builder.get_object("header_connection")
    assert header.markup is not None
    assert "Conectado Via" in header.markup
    assert "#50fa7b" in header.markup


def test_first_failure_moves_to_reconnecting(host: _Host) -> None:
    host._update_reconnect_state(None)
    assert host._reconnect_state == "reconnecting"
    assert host._consecutive_failures == 1
    header = host.builder.get_object("header_connection")
    assert "Tentando Reconectar" in header.markup
    assert "&#9680;" in header.markup
    assert "#ffb86c" in header.markup


def test_threshold_failures_moves_to_offline(host: _Host) -> None:
    for _ in range(RECONNECT_FAIL_THRESHOLD):
        host._update_reconnect_state(None)
    assert host._reconnect_state == "offline"
    assert host._consecutive_failures == RECONNECT_FAIL_THRESHOLD
    header = host.builder.get_object("header_connection")
    assert "Hefesto desligado" in header.markup
    assert "&#9675;" in header.markup
    assert "#ff5555" in header.markup


def test_reconnecting_to_online_recovers(host: _Host) -> None:
    host._update_reconnect_state(None)
    host._update_reconnect_state(None)
    assert host._reconnect_state == "reconnecting"

    host._update_reconnect_state({"connected": True, "transport": "bt"})
    assert host._reconnect_state == "online"
    assert host._consecutive_failures == 0
    header = host.builder.get_object("header_connection")
    assert "Conectado Via BT" in header.markup


def test_offline_to_online_recovers(host: _Host) -> None:
    for _ in range(RECONNECT_FAIL_THRESHOLD + 2):
        host._update_reconnect_state(None)
    assert host._reconnect_state == "offline"

    host._update_reconnect_state({"connected": True, "transport": "usb"})
    assert host._reconnect_state == "online"
    assert host._consecutive_failures == 0


def test_reconnecting_markup_uses_geometric_shape_not_emoji(host: _Host) -> None:
    """Garante U+25D0 (Geometric Shape) — nunca emojis coloridos."""
    host._update_reconnect_state(None)
    header = host.builder.get_object("header_connection")
    assert "&#9680;" in header.markup
    for char in header.markup:
        assert ord(char) < 0x1F000, f"emoji encontrado: {char!r}"


def test_initial_poll_fallback_pinta_header_quando_nenhum_poll_sucedeu(
    host: _Host,
) -> None:
    """Sem nenhum poll bem-sucedido, fallback aciona transição para offline acionável."""
    host._first_poll_succeeded = False

    result = host._check_initial_poll_fallback()

    assert result is False
    header = host.builder.get_object("header_connection")
    assert "Desconectado" in header.markup
    assert "aba Sistema" in header.markup
    # media o mundo de ontem"*.  # (noqa-acento: verbo medir, imperfeito)
    assert '"Reiniciar"' in header.markup
    assert "#ff5555" in header.markup
    assert host._reconnect_state == "offline"
    daemon_label = host.builder.get_object("status_daemon")
    assert "Sem resposta" in (daemon_label.text or "")


def test_initial_poll_fallback_no_op_quando_poll_ja_sucedeu(host: _Host) -> None:
    """Se algum poll já foi OK, o fallback não sobrescreve o header."""
    host._first_poll_succeeded = True
    header = host.builder.get_object("header_connection")
    header.markup = "<span foreground='#50fa7b'> Conectado Via USB</span>"

    result = host._check_initial_poll_fallback()

    assert result is False
    assert "Conectado Via USB" in header.markup
    assert host._reconnect_state != "offline" or host._consecutive_failures == 0


def test_idle_add_callbacks_sao_one_shot(monkeypatch: pytest.MonkeyPatch) -> None:
    """install_status_polling registra wrappers one-shot em idle_add (não busy-loop)."""
    from hefesto_dualsense4unix.app.actions import status_actions as mod

    idle_calls: list[Any] = []
    monkeypatch.setattr(
        mod.GLib, "idle_add", lambda fn, *args: idle_calls.append((fn, args)) or 0
    )
    monkeypatch.setattr(mod.GLib, "timeout_add", lambda *_a, **_kw: 0)
    monkeypatch.setattr(mod.GLib, "timeout_add_seconds", lambda *_a, **_kw: 0)

    host = object.__new__(StatusActionsMixin)

    def _no_slot(_id: str) -> None:
        return None

    host._get = _no_slot  # type: ignore[attr-defined]
    host._tick_live_state = lambda: True  # type: ignore[attr-defined]
    host._tick_profile_state = lambda: True  # type: ignore[attr-defined]

    StatusActionsMixin.install_status_polling(host)

    assert len(idle_calls) >= 2
    for fn, _args in idle_calls[:2]:
        assert fn() is False


