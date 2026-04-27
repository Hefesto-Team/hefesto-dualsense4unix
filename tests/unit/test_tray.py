"""Testes do TrayController com gi mockado (W5.4)."""
from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.integrations.tray import (
    APP_ID,
    ICON_NAME,
    TrayController,
    probe_gi_availability,
)


def test_constantes():
    assert APP_ID == "hefesto-dualsense4unix-tray"
    assert ICON_NAME == "input-gaming"


def test_probe_gi_availability_sem_gi(monkeypatch: pytest.MonkeyPatch):
    import builtins

    real_import = builtins.__import__

    def blocked(name: str, *args, **kwargs):
        if name == "gi":
            raise ImportError("gi bloqueado pra teste")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    ok, msg = probe_gi_availability()
    assert ok is False
    assert "PyGObject" in msg


def test_tray_controller_start_retorna_false_sem_gi(monkeypatch: pytest.MonkeyPatch):
    import builtins

    real_import = builtins.__import__

    def blocked(name: str, *args, **kwargs):
        if name == "gi":
            raise ImportError("gi bloqueado pra teste")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    ctrl = TrayController()
    assert ctrl.is_available() is False
    assert ctrl.start() is False


def _setup_fake_gi(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock]:
    """Instala mocks de `gi` e `gi.repository` no sys.modules."""
    fake_gtk = MagicMock()
    fake_gtk.Menu.return_value = MagicMock()
    fake_gtk.MenuItem.return_value = MagicMock()
    fake_gtk.SeparatorMenuItem.return_value = MagicMock()

    fake_indicator_enum = MagicMock()
    fake_indicator_enum.IndicatorStatus.ACTIVE = "active"
    fake_indicator_enum.IndicatorStatus.PASSIVE = "passive"
    fake_indicator_enum.IndicatorCategory.APPLICATION_STATUS = "app_status"
    fake_indicator_enum.Indicator.new = MagicMock(return_value=MagicMock(
        set_status=MagicMock(),
        set_menu=MagicMock(),
    ))

    fake_repository = MagicMock()
    fake_repository.Gtk = fake_gtk
    fake_repository.AyatanaAppIndicator3 = fake_indicator_enum
    fake_repository.AppIndicator3 = fake_indicator_enum

    fake_gi = ModuleType("gi")
    fake_gi.require_version = MagicMock()  # type: ignore[attr-defined]
    fake_gi.repository = fake_repository  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "gi", fake_gi)
    monkeypatch.setitem(sys.modules, "gi.repository", fake_repository)

    return fake_gtk, fake_repository


def test_probe_gi_availability_com_gi_mockado(monkeypatch: pytest.MonkeyPatch):
    _setup_fake_gi(monkeypatch)
    ok, msg = probe_gi_availability()
    assert ok is True
    assert "ok" in msg


def test_tray_start_cria_indicador_e_menu(monkeypatch: pytest.MonkeyPatch):
    fake_gtk, _fake_repo = _setup_fake_gi(monkeypatch)
    ctrl = TrayController()
    assert ctrl.start() is True
    assert ctrl._indicator is not None
    assert ctrl._menu is not None
    fake_gtk.Menu.assert_called()


def test_tray_update_status(monkeypatch: pytest.MonkeyPatch):
    _setup_fake_gi(monkeypatch)
    ctrl = TrayController()
    ctrl.start()
    ctrl.update_status("Bat 50%")
    ctrl._status_item.set_label.assert_called_with("Bat 50%")


def test_tray_update_profiles(monkeypatch: pytest.MonkeyPatch):
    fake_gtk, _ = _setup_fake_gi(monkeypatch)
    ctrl = TrayController()
    ctrl.start()

    calls: list[str] = []
    ctrl.update_profiles(["shooter", "driving"], on_select=calls.append)
    # Deve ter criado 2 MenuItem novos (um por perfil)
    # Contamos as chamadas a MenuItem do gtk: 1 pra status, 1 open_tui, 1 quit, 2 perfis = 5
    assert fake_gtk.MenuItem.call_count >= 2
    assert len(ctrl._profile_items) == 2


def test_tray_stop_marca_passive(monkeypatch: pytest.MonkeyPatch):
    _setup_fake_gi(monkeypatch)
    ctrl = TrayController()
    ctrl.start()
    assert ctrl._indicator is not None
    ctrl.stop()
    assert ctrl._indicator is None
