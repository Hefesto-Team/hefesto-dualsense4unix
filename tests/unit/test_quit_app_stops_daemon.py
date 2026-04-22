"""Testes de `HefestoApp.quit_app` (BUG-MULTI-INSTANCE-01).

Verifica que 'Sair' no tray encerra o daemon via systemctl --user stop.

Abordagem: importamos `HefestoApp` lazy dentro de cada teste pois o módulo
`hefesto.app.app` puxa `gi.repository.GdkPixbuf`, que nem todo ambiente de
CI tem. Quando ausente, o teste é pulado.
"""
from __future__ import annotations

import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _load_app_module():
    try:
        import hefesto.app.app as app_mod
    except ImportError as exc:
        pytest.skip(f"gi/GdkPixbuf indisponível: {exc}")
    return app_mod


def test_quit_app_chama_systemctl_stop(monkeypatch):
    app_mod = _load_app_module()

    fake_run = MagicMock(return_value=SimpleNamespace(returncode=0, stdout="", stderr=""))
    fake_main_quit = MagicMock()

    monkeypatch.setattr(app_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(app_mod.Gtk, "main_quit", fake_main_quit)

    stub = SimpleNamespace(_quitting=False, tray=None)
    app_mod.HefestoApp.quit_app(stub)

    fake_run.assert_called_once()
    args, kwargs = fake_run.call_args
    cmd = args[0] if args else kwargs.get("args")
    assert cmd == ["systemctl", "--user", "stop", "hefesto.service"]
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

    stub = SimpleNamespace(_quitting=False, tray=None)
    app_mod.HefestoApp.quit_app(stub)
    fake_main_quit.assert_called_once()


def test_quit_app_para_tray(monkeypatch):
    app_mod = _load_app_module()

    fake_run = MagicMock(return_value=SimpleNamespace(returncode=0))
    fake_main_quit = MagicMock()
    fake_tray = MagicMock()

    monkeypatch.setattr(app_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(app_mod.Gtk, "main_quit", fake_main_quit)

    stub = SimpleNamespace(_quitting=False, tray=fake_tray)
    app_mod.HefestoApp.quit_app(stub)

    fake_tray.stop.assert_called_once()


def test_quit_app_sobrevive_a_timeout(monkeypatch):
    app_mod = _load_app_module()

    def _timeout(*_a, **_kw):
        raise subprocess.TimeoutExpired(cmd="systemctl", timeout=5)

    fake_main_quit = MagicMock()

    monkeypatch.setattr(app_mod.subprocess, "run", _timeout)
    monkeypatch.setattr(app_mod.Gtk, "main_quit", fake_main_quit)

    stub = SimpleNamespace(_quitting=False, tray=None)
    app_mod.HefestoApp.quit_app(stub)
    fake_main_quit.assert_called_once()
