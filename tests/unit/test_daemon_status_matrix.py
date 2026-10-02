"""Testes da matriz de estados do daemon (BUG-DAEMON-STATUS-MISMATCH-01)."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("a matriz do estado do daemon na janela")

import sys
import types
from typing import Any


def _install_gi_stubs() -> None:
    """Instala stubs minimos de gi.repository para rodar sem GTK real."""
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

    class _FakeLabel:
        def __init__(self) -> None:
            self._markup: str = ""
            self._tooltip: str = ""

        def set_markup(self, markup: str) -> None:
            self._markup = markup

        def set_tooltip_text(self, tooltip: str) -> None:
            self._tooltip = tooltip

        def set_visible(self, _v: bool) -> None:
            pass

    class _FakeSwitch:
        def set_active(self, _v: bool) -> None:
            pass

    class _FakeButton:
        def set_sensitive(self, _v: bool) -> None:
            pass

        def set_tooltip_text(self, _t: str) -> None:
            pass

        def set_visible(self, _v: bool) -> None:
            pass

    class _FakeTextView:
        def get_buffer(self) -> _FakeBuffer:
            return _FakeBuffer()

        def scroll_to_mark(self, *_a: Any, **_kw: Any) -> None:
            pass

        def scroll_to_iter(self, *_a: Any, **_kw: Any) -> None:
            pass

    class _FakeBuffer:
        def set_text(self, _t: str) -> None:
            pass

        def get_end_iter(self) -> None:
            return None  # type: ignore[return-value]

        def create_mark(self, *_a: Any) -> None:
            return None  # type: ignore[return-value]

        def delete_mark(self, _m: Any) -> None:
            pass

    class _FakeWindow:
        pass

    gtk_mod.Builder = object  # type: ignore[attr-defined]
    gtk_mod.Window = _FakeWindow  # type: ignore[attr-defined]
    gtk_mod.Button = _FakeButton  # type: ignore[attr-defined]
    gtk_mod.Switch = _FakeSwitch  # type: ignore[attr-defined]
    gtk_mod.Label = _FakeLabel  # type: ignore[attr-defined]
    gtk_mod.TextView = _FakeTextView  # type: ignore[attr-defined]
    gtk_mod.TextBuffer = _FakeBuffer  # type: ignore[attr-defined]
    gtk_mod.MessageDialog = object  # type: ignore[attr-defined]
    gtk_mod.MessageType = object  # type: ignore[attr-defined]
    gtk_mod.ButtonsType = object  # type: ignore[attr-defined]
    glib_mod.idle_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.timeout_add = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    glib_mod.timeout_add_seconds = lambda *_a, **_kw: 0  # type: ignore[attr-defined]
    repo_mod.Gtk = gtk_mod  # type: ignore[attr-defined]
    repo_mod.GLib = glib_mod  # type: ignore[attr-defined]

    sys.modules["gi"] = gi_mod
    sys.modules["gi.repository"] = repo_mod
    sys.modules["gi.repository.Gtk"] = gtk_mod
    sys.modules["gi.repository.GLib"] = glib_mod


_install_gi_stubs()

import pytest

import hefesto_dualsense4unix.utils.single_instance as si_mod
from hefesto_dualsense4unix.app.actions.daemon_actions import DaemonActionsMixin


class _FakeBufferObj:
    def set_text(self, _t: str) -> None:
        pass

    def get_end_iter(self) -> None:
        return None  # type: ignore[return-value]

    def create_mark(self, *_a: Any) -> None:
        return None  # type: ignore[return-value]

    def delete_mark(self, _m: Any) -> None:
        pass


class _FakeTextViewObj:
    def get_buffer(self) -> _FakeBufferObj:
        return _FakeBufferObj()

    def scroll_to_mark(self, *_a: Any, **_kw: Any) -> None:
        pass

    def scroll_to_iter(self, *_a: Any, **_kw: Any) -> None:
        pass


class _FakeLabelObj:
    def __init__(self) -> None:
        self.markup: str = ""
        self.tooltip: str = ""

    def set_markup(self, markup: str) -> None:
        self.markup = markup

    def set_tooltip_text(self, tooltip: str) -> None:
        self.tooltip = tooltip


class _FakeSwitchObj:
    def set_active(self, _v: bool) -> None:
        pass


class _FakeButtonObj:
    def __init__(self) -> None:
        self.visible: bool = False
        self.sensitive: bool | None = None
        self.tooltip: str = ""

    def set_visible(self, v: bool) -> None:
        self.visible = v

    def set_sensitive(self, v: bool) -> None:
        self.sensitive = v

    def set_tooltip_text(self, t: str) -> None:
        self.tooltip = t


class _Host(DaemonActionsMixin):
    """Host mínimo que permite monkeypatch de _systemctl_oneline e _read_daemon_pid."""

    def __init__(self) -> None:
        self._daemon_autostart_guard = False
        self._daemon_autostart_attempts = 0
        self._label = _FakeLabelObj()
        self._sw = _FakeSwitchObj()
        self._btn_migrate = _FakeButtonObj()
        self._btn_start = _FakeButtonObj()
        self._btn_stop = _FakeButtonObj()

    def _get(self, widget_id: str) -> Any:
        if widget_id == "daemon_status_label":
            return self._label
        if widget_id == "daemon_autostart_switch":
            return self._sw
        if widget_id == "btn_migrate_to_systemd":
            return self._btn_migrate
        if widget_id == "daemon_start_button":
            return self._btn_start
        if widget_id == "daemon_stop_button":
            return self._btn_stop
        if widget_id == "daemon_status_text":
            return _FakeTextViewObj()
        return None

    def _systemctl_status_text(self, _unit: str) -> str:
        return "(stub)"


@pytest.mark.parametrize(
    "systemd_active, process_alive, expected_status",
    [
        (True, True, "online_systemd"),
        (False, True, "online_avulso"),
        (True, False, "iniciando"),
        (False, False, "offline"),
    ],
)
def test_daemon_status_matriz(
    monkeypatch: pytest.MonkeyPatch,
    systemd_active: bool,
    process_alive: bool,
    expected_status: str,
) -> None:
    """_daemon_status() retorna o estado correto para cada combinacao da matriz."""
    host = _Host()

    def _fake_oneline(args: list[str]) -> str:
        if "is-active" in args:
            return "active" if systemd_active else "inactive"
        if "is-enabled" in args:
            return "enabled"
        return ""

    monkeypatch.setattr(host, "_systemctl_oneline", _fake_oneline)

    pid_val: int | None = 12345 if process_alive else None
    monkeypatch.setattr(host, "_read_daemon_pid", lambda: pid_val)
    monkeypatch.setattr(si_mod, "is_alive", lambda pid: process_alive)

    result = host._daemon_status()
    assert result == expected_status


class _TextViewQueGuarda:
    """Dublê de `daemon_status_text` que LEMBRA o que foi escrito."""

    def __init__(self) -> None:
        self.texto: str = ""

    def get_buffer(self) -> Any:
        return self

    def set_text(self, t: str) -> None:
        self.texto = t

    def get_end_iter(self) -> None:
        return None

    def create_mark(self, *_a: Any) -> None:
        return None

    def delete_mark(self, _m: Any) -> None:
        pass

    def scroll_to_mark(self, *_a: Any, **_kw: Any) -> None:
        pass

    def scroll_to_iter(self, *_a: Any, **_kw: Any) -> None:
        pass


class _HostComPainel(_Host):
    def __init__(self) -> None:
        super().__init__()
        self._painel = _TextViewQueGuarda()

    def _get(self, widget_id: str) -> Any:
        if widget_id == "daemon_status_text":
            return self._painel
        return super()._get(widget_id)


