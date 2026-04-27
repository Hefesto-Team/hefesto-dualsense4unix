"""Testes de `HefestoApp.quit_app` (BUG-MULTI-INSTANCE-01).

Verifica que 'Sair' no tray encerra o daemon via systemctl --user stop.

Abordagem: importamos `HefestoApp` lazy dentro de cada teste pois o módulo
`hefesto_dualsense4unix.app.app` puxa `gi.repository.GdkPixbuf`, que nem todo ambiente de
CI tem. Quando ausente, o teste é pulado.
"""
from __future__ import annotations

import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _load_app_module():
    try:
        import hefesto_dualsense4unix.app.app as app_mod
    except ImportError as exc:
        pytest.skip(f"gi/GdkPixbuf indisponível: {exc}")
    return app_mod


class _InstantThread:
    """Stub de threading.Thread que executa target() síncrono em start().

    Preserva a assinatura esperada (target, daemon kwarg) mas roda na
    thread principal pra facilitar asserts nos testes. quit_app dispara
    `_shutdown_backend` em thread daemon; usar este stub vira execução
    in-line.
    """

    def __init__(self, target=None, daemon=False, **_kw):
        self._target = target

    def start(self) -> None:
        if self._target is not None:
            self._target()


def _make_quit_stub(app_mod, tray=None):
    stub = SimpleNamespace(_quitting=False, tray=tray)
    stub._shutdown_backend = lambda: app_mod.HefestoApp._shutdown_backend(stub)
    return stub


def test_quit_app_chama_systemctl_stop(monkeypatch):
    app_mod = _load_app_module()

    fake_run = MagicMock(return_value=SimpleNamespace(returncode=0, stdout="", stderr=""))
    fake_main_quit = MagicMock()

    monkeypatch.setattr(app_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(app_mod.Gtk, "main_quit", fake_main_quit)
    monkeypatch.setattr(app_mod.threading, "Thread", _InstantThread)

    stub = _make_quit_stub(app_mod)
    app_mod.HefestoApp.quit_app(stub)

    fake_run.assert_called_once()
    args, kwargs = fake_run.call_args
    cmd = args[0] if args else kwargs.get("args")
    assert cmd == ["systemctl", "--user", "stop", "hefesto-dualsense4unix.service"]
    assert kwargs.get("check") is False
    assert kwargs.get("timeout") == 5
    fake_main_quit.assert_called_once()
    assert stub._quitting is True


def test_quit_app_sobrevive_a_systemctl_ausente(monkeypatch):
    app_mod = _load_app_module()

    def _raise(*_a, **_kw):
        raise FileNotFoundError("systemctl")

    fake_main_quit = MagicMock()

    monkeypatch.setattr(app_mod.subprocess, "run", _raise)
    monkeypatch.setattr(app_mod.Gtk, "main_quit", fake_main_quit)
    monkeypatch.setattr(app_mod.threading, "Thread", _InstantThread)

    stub = _make_quit_stub(app_mod)
    app_mod.HefestoApp.quit_app(stub)
    fake_main_quit.assert_called_once()


def test_quit_app_para_tray(monkeypatch):
    app_mod = _load_app_module()

    fake_run = MagicMock(return_value=SimpleNamespace(returncode=0))
    fake_main_quit = MagicMock()
    fake_tray = MagicMock()

    monkeypatch.setattr(app_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(app_mod.Gtk, "main_quit", fake_main_quit)
    monkeypatch.setattr(app_mod.threading, "Thread", _InstantThread)

    stub = _make_quit_stub(app_mod, tray=fake_tray)
    app_mod.HefestoApp.quit_app(stub)

    fake_tray.stop.assert_called_once()


def test_quit_app_sobrevive_a_timeout(monkeypatch):
    app_mod = _load_app_module()

    def _timeout(*_a, **_kw):
        raise subprocess.TimeoutExpired(cmd="systemctl", timeout=5)

    fake_main_quit = MagicMock()

    monkeypatch.setattr(app_mod.subprocess, "run", _timeout)
    monkeypatch.setattr(app_mod.Gtk, "main_quit", fake_main_quit)
    monkeypatch.setattr(app_mod.threading, "Thread", _InstantThread)

    stub = _make_quit_stub(app_mod)
    app_mod.HefestoApp.quit_app(stub)
    fake_main_quit.assert_called_once()


def test_quit_app_main_quit_antes_do_cleanup(monkeypatch):
    """Invariante crítico: Gtk.main_quit é chamado ANTES de tray.stop /
    systemctl pra que o processo encerre mesmo se o cleanup travar
    (D-Bus sem StatusNotifierWatcher robusto)."""
    app_mod = _load_app_module()

    call_order: list[str] = []

    def _record_quit() -> None:
        call_order.append("main_quit")

    fake_tray = MagicMock()
    fake_tray.stop.side_effect = lambda: call_order.append("tray_stop")

    fake_run = MagicMock(
        side_effect=lambda *_a, **_kw: (
            call_order.append("systemctl"),
            SimpleNamespace(returncode=0),
        )[1]
    )

    monkeypatch.setattr(app_mod.Gtk, "main_quit", _record_quit)
    monkeypatch.setattr(app_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(app_mod.threading, "Thread", _InstantThread)

    stub = _make_quit_stub(app_mod, tray=fake_tray)
    app_mod.HefestoApp.quit_app(stub)

    assert call_order[0] == "main_quit"
    assert "tray_stop" in call_order
    assert "systemctl" in call_order
