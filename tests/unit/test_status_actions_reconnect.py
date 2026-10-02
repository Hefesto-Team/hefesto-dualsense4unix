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


