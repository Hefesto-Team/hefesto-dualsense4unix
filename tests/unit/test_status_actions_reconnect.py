"""Máquina de estado do reconnect do header (UX-RECONNECT-01).

Testa transições INITIAL/ONLINE → RECONNECTING → OFFLINE e o caminho de
volta (RECONNECTING → ONLINE, OFFLINE → ONLINE) sem acoplar a GTK: usamos
fakes leves que imitam apenas a API mínima consumida pelos renderers.
"""
from __future__ import annotations

import sys
import types
from typing import Any

import pytest


# GTK é import-by-side-effect no módulo real; para testes em CI sem display
# injetamos stubs em `gi.repository` antes do import. Isso evita requerer Xvfb
# para testar lógica pura de transição de estado.
def _install_gi_stubs() -> None:
    if "gi" in sys.modules and hasattr(sys.modules["gi"], "require_version"):
        try:
            # Se o gi real já funciona (ambiente com GTK), não mexe.
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
    glib_mod.timeout_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.timeout_add_seconds = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]

    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GLib"] = glib_mod


_install_gi_stubs()

from hefesto.app.actions.status_actions import StatusActionsMixin  # noqa: E402
from hefesto.app.constants import RECONNECT_FAIL_THRESHOLD  # noqa: E402


class _FakeLabel:
    def __init__(self) -> None:
        self.markup: str | None = None
        self.text: str | None = None

    def set_markup(self, markup: str) -> None:
        self.markup = markup

    def set_text(self, text: str) -> None:
        self.text = text

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
    assert "conectado via usb" in header.markup
    assert "#2d8" in header.markup  # verde canônico


def test_first_failure_moves_to_reconnecting(host: _Host) -> None:
    host._update_reconnect_state(None)
    assert host._reconnect_state == "reconnecting"
    assert host._consecutive_failures == 1
    header = host.builder.get_object("header_connection")
    assert "tentando reconectar" in header.markup
    assert "◐" in header.markup  # U+25D0, não emoji
    assert "#d90" in header.markup  # laranja canônico


def test_threshold_failures_moves_to_offline(host: _Host) -> None:
    for _ in range(RECONNECT_FAIL_THRESHOLD):
        host._update_reconnect_state(None)
    assert host._reconnect_state == "offline"
    assert host._consecutive_failures == RECONNECT_FAIL_THRESHOLD
    header = host.builder.get_object("header_connection")
    assert "daemon offline" in header.markup
    assert "○" in header.markup  # U+25CB
    assert "#d33" in header.markup  # vermelho canônico


def test_reconnecting_to_online_recovers(host: _Host) -> None:
    host._update_reconnect_state(None)
    host._update_reconnect_state(None)
    assert host._reconnect_state == "reconnecting"

    host._update_reconnect_state({"connected": True, "transport": "bt"})
    assert host._reconnect_state == "online"
    assert host._consecutive_failures == 0
    header = host.builder.get_object("header_connection")
    assert "conectado via bt" in header.markup


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
    assert "◐" in header.markup
    # Defesa contra regressão: blocos de emoji coloridos não podem aparecer.
    for char in header.markup:
        assert ord(char) < 0x1F000, f"emoji encontrado: {char!r}"


# "A consistência é a virtude do burro." — Oscar Wilde.
