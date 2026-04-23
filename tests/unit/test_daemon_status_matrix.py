"""Testes da matriz de estados do daemon (BUG-DAEMON-STATUS-MISMATCH-01).

Cobre `_daemon_status()` com monkeypatch das 3 fontes:
  1. `_systemctl_oneline` — retorna is-active e is-enabled.
  2. `_read_daemon_pid` — retorna o pid lido do arquivo.
  3. `is_alive` via single_instance — retorna se o pid esta vivo.

As 4 combinacoes principais da matriz:
  A. systemd active + processo vivo   → online_systemd
  B. systemd inactive + processo vivo → online_avulso
  C. systemd active + processo morto  → iniciando
  D. systemd inactive + processo morto → offline

Adicionalmente verifica o estado `online_systemd` com enabled=enabled
e que `_set_daemon_status_markup` pinta o label correto.

Usa stubs gi para rodar em CI sem display GTK.
"""
from __future__ import annotations

import sys
import types
from typing import Any


def _install_gi_stubs() -> None:
    """Instala stubs minimos de gi.repository para rodar sem GTK real."""
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

import pytest  # noqa: E402

import hefesto.utils.single_instance as si_mod  # noqa: E402
from hefesto.app.actions.daemon_actions import DaemonActionsMixin  # noqa: E402

# ---------------------------------------------------------------------------
# Host mínimo para exercitar _daemon_status sem Builder real
# ---------------------------------------------------------------------------


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

    def set_visible(self, v: bool) -> None:
        self.visible = v


class _Host(DaemonActionsMixin):
    """Host mínimo que permite monkeypatch de _systemctl_oneline e _read_daemon_pid."""

    def __init__(self) -> None:
        self._daemon_autostart_guard = False
        self._daemon_autostart_attempts = 0
        # Widgets fake para _set_daemon_status_markup e _refresh_daemon_view.
        self._label = _FakeLabelObj()
        self._sw = _FakeSwitchObj()
        self._btn_migrate = _FakeButtonObj()

    def _get(self, widget_id: str) -> Any:
        if widget_id == "daemon_status_label":
            return self._label
        if widget_id == "daemon_autostart_switch":
            return self._sw
        if widget_id == "btn_migrate_to_systemd":
            return self._btn_migrate
        if widget_id == "daemon_status_text":
            return _FakeTextViewObj()
        return None

    # Stub de _systemctl_status_text para não chamar subprocess real.
    def _systemctl_status_text(self, _unit: str) -> str:
        return "(stub)"


# ---------------------------------------------------------------------------
# Testes da matriz de estados
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "systemd_active, process_alive, expected_status",
    [
        (True, True, "online_systemd"),    # A: systemd + processo vivo
        (False, True, "online_avulso"),    # B: avulso
        (True, False, "iniciando"),        # C: systemd active, processo ausente
        (False, False, "offline"),         # D: tudo morto
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


def test_online_systemd_com_enabled_exibe_autostart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Label mostra '+ auto-start' quando systemd active + enabled."""
    host = _Host()

    def _fake_oneline(args: list[str]) -> str:
        if "is-active" in args:
            return "active"
        if "is-enabled" in args:
            return "enabled"
        return ""

    monkeypatch.setattr(host, "_systemctl_oneline", _fake_oneline)
    monkeypatch.setattr(host, "_read_daemon_pid", lambda: 99)
    monkeypatch.setattr(si_mod, "is_alive", lambda _pid: True)

    host._set_daemon_status_markup("online_systemd", "enabled")

    assert "auto-start" in host._label.markup
    assert "#2d8" in host._label.markup


def test_offline_label_vermelho(monkeypatch: pytest.MonkeyPatch) -> None:
    """Label 'Offline' usa cor vermelha (#d33) e glifo circulo vazio."""
    host = _Host()
    host._set_daemon_status_markup("offline", "disabled")

    assert "#d33" in host._label.markup
    assert "Offline" in host._label.markup
    # Glifo circulo vazio (U+25CB) deve estar presente.
    assert "○" in host._label.markup or "○" in host._label.markup


def test_online_avulso_label_amarelo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Label 'Online (processo avulso)' usa cor amarela (#ca0)."""
    host = _Host()
    host._set_daemon_status_markup("online_avulso", "disabled")

    assert "#ca0" in host._label.markup
    assert "avulso" in host._label.markup


def test_botao_migrate_visivel_apenas_em_avulso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """btn_migrate_to_systemd fica visivel apenas no estado online_avulso."""
    host = _Host()

    # Estado online_avulso: botao deve ficar visivel.
    def _fake_oneline_avulso(args: list[str]) -> str:
        if "is-active" in args:
            return "inactive"
        if "is-enabled" in args:
            return "disabled"
        return ""

    monkeypatch.setattr(host, "_systemctl_oneline", _fake_oneline_avulso)
    monkeypatch.setattr(host, "_read_daemon_pid", lambda: 777)
    monkeypatch.setattr(si_mod, "is_alive", lambda _pid: True)

    host._refresh_daemon_view()

    assert host._btn_migrate.visible is True

    # Estado offline: botao deve ficar oculto.
    monkeypatch.setattr(host, "_read_daemon_pid", lambda: None)
    monkeypatch.setattr(si_mod, "is_alive", lambda _pid: False)

    host._refresh_daemon_view()

    assert host._btn_migrate.visible is False
