"""Testes do primeiro refresh do status do daemon no bootstrap da GUI."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("status do daemon no primeiro frame")

import sys
import types
from typing import Any


def _install_gi_stubs() -> None:
    """Stubs mínimos de gi.repository para rodar sem GTK real."""
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

    class _FakeWindow:
        pass

    gtk_mod.Builder = object  # type: ignore[attr-defined]
    gtk_mod.Window = _FakeWindow  # type: ignore[attr-defined]
    gtk_mod.Button = object  # type: ignore[attr-defined]
    gtk_mod.Switch = object  # type: ignore[attr-defined]
    gtk_mod.Label = object  # type: ignore[attr-defined]
    gtk_mod.TextView = object  # type: ignore[attr-defined]
    gtk_mod.TextBuffer = object  # type: ignore[attr-defined]
    gtk_mod.MessageDialog = object  # type: ignore[attr-defined]
    gtk_mod.MessageType = object  # type: ignore[attr-defined]
    gtk_mod.ButtonsType = object  # type: ignore[attr-defined]
    glib_mod.idle_add = lambda fn, *a, **kw: fn(*a, **kw) or 0  # type: ignore[attr-defined]
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
    def __init__(self) -> None:
        self.active: bool = False

    def set_active(self, v: bool) -> None:
        self.active = v


class _FakeButtonObj:
    def __init__(self) -> None:
        self.visible: bool = False
        self.sensitive: bool = True
        self.tooltip: str = ""

    def set_visible(self, v: bool) -> None:
        self.visible = v

    def set_sensitive(self, v: bool) -> None:
        self.sensitive = v

    def set_tooltip_text(self, t: str) -> None:
        self.tooltip = t


class _ImmediateExecutor:
    """Executor síncrono — roda o worker na mesma thread, imediatamente."""

    def submit(self, fn: Any, *args: Any, **kwargs: Any) -> None:
        fn(*args, **kwargs)


class _Host(DaemonActionsMixin):
    """Host mínimo com widgets fake e executor síncrono."""

    def __init__(self) -> None:
        self._daemon_autostart_guard = False
        self._daemon_autostart_attempts = 0
        self._label = _FakeLabelObj()
        self._sw = _FakeSwitchObj()
        self._btn_migrate = _FakeButtonObj()
        self._btn_restart = _FakeButtonObj()

    def _get(self, widget_id: str) -> Any:
        if widget_id == "daemon_status_label":
            return self._label
        if widget_id == "daemon_autostart_switch":
            return self._sw
        if widget_id == "btn_migrate_to_systemd":
            return self._btn_migrate
        if widget_id == "btn_restart_daemon":
            return self._btn_restart
        if widget_id == "daemon_status_text":
            return _FakeTextViewObj()
        return None

    def _systemctl_status_text(self, _unit: str) -> str:
        return "(stub status text)"


def _patch_installer_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Faz `ServiceInstaller().detect_installed_unit()` retornar None."""
    from hefesto_dualsense4unix.daemon import service_install

    class _FakeInstaller:
        def detect_installed_unit(self) -> Any:
            return None

    monkeypatch.setattr(service_install, "ServiceInstaller", _FakeInstaller)


def _patch_executor_immediate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Faz `_get_executor()` devolver um executor síncrono."""
    from hefesto_dualsense4unix.app import ipc_bridge

    monkeypatch.setattr(ipc_bridge, "_get_executor", lambda: _ImmediateExecutor())
    from hefesto_dualsense4unix.app.actions import daemon_actions

    monkeypatch.setattr(daemon_actions, "_get_executor", lambda: _ImmediateExecutor())

    def _eager_idle_add(fn: Any, *args: Any, **kwargs: Any) -> int:
        fn(*args, **kwargs)
        return 0

    monkeypatch.setattr(daemon_actions.GLib, "idle_add", _eager_idle_add)


def test_find_repo_file_resolve_raiz_do_repo() -> None:
    """BUG-GUI-REPO-ROOT-OFFBYONE-01 (H3 da auditoria): _find_repo_file achava"""
    host = _Host()
    found = host._find_repo_file("scripts/install_snd_quirk.sh")
    assert found is not None, "não resolveu — _find_repo_file quebrado (parents errado)"
    assert found.name == "install_snd_quirk.sh"
    assert found.is_file()
    assert host._find_repo_file("run.sh") is not None
