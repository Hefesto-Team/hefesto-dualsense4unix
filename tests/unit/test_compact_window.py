"""Testes do FEAT-COMPACT-WINDOW-FALLBACK-01 (surrogate de tray COSMIC).

Padrão: stubs gi/Gtk/Gdk para rodar sem display real (igual ao
test_status_actions_reconnect.py). Foca em comportamento observável:
- `is_enabled()` respeita env var.
- `_render_state` produz markup correto para online/offline/sem device.
- Profile button popula popup menu com lista IPC.
"""
from __future__ import annotations

import sys
import types

import pytest


def _install_gi_stubs() -> None:
    """Stubs mínimos de gi.repository para rodar sem GTK real (CI/headless)."""
    if "gi" in sys.modules and hasattr(sys.modules["gi"], "require_version"):
        try:
            from gi.repository import Gtk  # noqa: F401
            return
        except Exception:
            pass

    gi_mod = types.ModuleType("gi")

    def _require_version(_name: str, _ver: str) -> None:
        return None

    gi_mod.require_version = _require_version  # type: ignore[attr-defined]
    repo_mod = types.ModuleType("gi.repository")
    gtk_mod = types.ModuleType("gi.repository.Gtk")
    gdk_mod = types.ModuleType("gi.repository.Gdk")
    glib_mod = types.ModuleType("gi.repository.GLib")

    # Gtk stubs mínimos para o import-time class definitions.
    # Inclui o superset usado por outros testes (DrawingArea, GObject, Align,
    # Grid, etc) porque a ordem de coleta do pytest pode fazer o stub deste
    # módulo ser registrado primeiro em sys.modules — sem cobertura ampla,
    # test_status_actions_reconnect/test_profiles_gui_sync quebram em coleção.
    gtk_mod.Builder = object  # type: ignore[attr-defined]
    gtk_mod.Window = object  # type: ignore[attr-defined]
    gtk_mod.WindowType = type("WindowType", (), {"TOPLEVEL": 0})  # type: ignore[attr-defined]
    gtk_mod.Button = object  # type: ignore[attr-defined]
    gtk_mod.Label = object  # type: ignore[attr-defined]
    gtk_mod.Box = object  # type: ignore[attr-defined]
    gtk_mod.Grid = object  # type: ignore[attr-defined]
    gtk_mod.DrawingArea = object  # type: ignore[attr-defined]
    gtk_mod.Menu = object  # type: ignore[attr-defined]
    gtk_mod.MenuItem = type("MenuItem", (), {})  # type: ignore[attr-defined]
    gtk_mod.SeparatorMenuItem = object  # type: ignore[attr-defined]
    gtk_mod.TextView = object  # type: ignore[attr-defined]
    gtk_mod.TextBuffer = object  # type: ignore[attr-defined]
    gtk_mod.ToggleButton = object  # type: ignore[attr-defined]
    gtk_mod.Orientation = type(
        "Orientation", (), {"HORIZONTAL": 0, "VERTICAL": 1}
    )  # type: ignore[attr-defined]
    gtk_mod.Switch = object  # type: ignore[attr-defined]
    gtk_mod.ComboBoxText = object  # type: ignore[attr-defined]
    gtk_mod.Align = type("Align", (), {"CENTER": 0, "START": 1, "END": 2, "FILL": 3})  # type: ignore[attr-defined]
    gtk_mod.IconTheme = type("IconTheme", (), {"get_default": staticmethod(lambda: None)})  # type: ignore[attr-defined]
    gtk_mod.PositionType = type("PositionType", (), {"LEFT": 0, "RIGHT": 1, "TOP": 2, "BOTTOM": 3})  # type: ignore[attr-defined]
    # GObject stub (alguns mixins importam GObject diretamente).
    gobject_mod = types.ModuleType("gi.repository.GObject")
    gobject_mod.SignalFlags = type("SignalFlags", (), {"RUN_LAST": 0})  # type: ignore[attr-defined]
    gobject_mod.TYPE_NONE = 0  # type: ignore[attr-defined]
    gobject_mod.GObject = object  # type: ignore[attr-defined]
    repo_mod.GObject = gobject_mod  # type: ignore[attr-defined]
    sys.modules["gi.repository.GObject"] = gobject_mod
    gdk_mod.Gravity = type("Gravity", (), {"SOUTH_EAST": 0, "SOUTH_WEST": 1, "NORTH_WEST": 2})  # type: ignore[attr-defined]
    glib_mod.idle_add = lambda fn, *a, **kw: fn(*a, **kw)  # type: ignore[attr-defined]
    glib_mod.timeout_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.timeout_add_seconds = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.source_remove = lambda *_a, **_kw: None  # type: ignore[attr-defined]

    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.Gdk = gdk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]
    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.Gdk"] = gdk_mod
    sys.modules["gi.repository.GLib"] = glib_mod


_install_gi_stubs()

from hefesto_dualsense4unix.app.compact_window import (  # noqa: E402
    ENV_OPT_OUT,
    CompactWindow,
    is_enabled,
)


class _FakeLabel:
    def __init__(self) -> None:
        self.markup: str | None = None

    def set_markup(self, markup: str) -> None:
        self.markup = markup

    def set_xalign(self, _v: float) -> None:
        pass


def _mk_window() -> CompactWindow:
    """Cria CompactWindow sem buildar GTK; injeta labels fake direto."""
    cw = CompactWindow(
        on_show_window=lambda: None,
        on_quit=lambda: None,
        on_list_profiles=lambda: [],
        on_switch_profile=lambda _name: True,
        on_state=lambda: None,
    )
    cw._status_label = _FakeLabel()  # type: ignore[assignment]
    cw._battery_label = _FakeLabel()  # type: ignore[assignment]
    return cw


# ---------------------------------------------------------------------------
# is_enabled() / env var opt-out
# ---------------------------------------------------------------------------


def test_is_enabled_default_true(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem env var setada, compact window é auto-on."""
    monkeypatch.delenv(ENV_OPT_OUT, raising=False)
    assert is_enabled() is True


def test_is_enabled_opt_out_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """HEFESTO_DUALSENSE4UNIX_COMPACT_WINDOW=0 desativa."""
    monkeypatch.setenv(ENV_OPT_OUT, "0")
    assert is_enabled() is False


def test_is_enabled_outros_valores_continuam_ligado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Apenas '0' explícito desliga (1, true, qualquer outro => on)."""
    monkeypatch.setenv(ENV_OPT_OUT, "1")
    assert is_enabled() is True
    monkeypatch.setenv(ENV_OPT_OUT, "yes")
    assert is_enabled() is True


# ---------------------------------------------------------------------------
# _render_state — markup por cenário
# ---------------------------------------------------------------------------


def test_render_state_online_pinta_glyph_verde_e_transport() -> None:
    cw = _mk_window()
    cw._render_state(
        {
            "connected": True,
            "transport": "bt",
            "active_profile": "fps",
            "battery_pct": 75,
        }
    )
    assert cw._status_label is not None
    markup = cw._status_label.markup or ""
    assert "&#9679;" in markup  # U+25CF NCR
    assert "#2d8" in markup
    assert "BT" in markup
    assert "fps" in markup
    assert cw._battery_label is not None
    assert "75" in (cw._battery_label.markup or "")


def test_render_state_offline_pinta_glyph_vermelho() -> None:
    cw = _mk_window()
    cw._render_state(None)
    assert cw._status_label is not None
    markup = cw._status_label.markup or ""
    assert "&#9675;" in markup  # U+25CB NCR
    assert "#d33" in markup
    assert "offline" in markup.lower()


def test_render_state_controller_disconnected_pinta_glyph_vermelho() -> None:
    cw = _mk_window()
    cw._render_state(
        {
            "connected": False,
            "transport": "usb",
            "active_profile": "fallback",
            "battery_pct": None,
        }
    )
    assert cw._status_label is not None
    markup = cw._status_label.markup or ""
    assert "&#9675;" in markup
    assert "desconectado" in markup.lower()


def test_render_state_battery_invalida_mostra_traco() -> None:
    cw = _mk_window()
    cw._render_state(
        {
            "connected": True,
            "transport": "bt",
            "active_profile": "x",
            "battery_pct": "n/d",  # tipo inválido — deve cair no else
        }
    )
    assert cw._battery_label is not None
    assert "—" in (cw._battery_label.markup or "")
