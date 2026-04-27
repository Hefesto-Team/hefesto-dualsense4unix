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


# --- Testes de AppTray (app/tray.py) — CLUSTER-TRAY-POLISH-01 -------------

def _setup_fake_gi_for_apptray(monkeypatch: pytest.MonkeyPatch):
    """Aparelha mocks de gi para `app/tray.py`.

    `app/tray.py` importa `GLib, Gtk` do `gi.repository` no topo do módulo.
    Cada `Gtk.MenuItem(...)` precisa retornar uma instância nova (rastreável)
    para que os testes possam validar `set_use_underline` e labels.
    """
    fake_gtk = MagicMock()

    created_menu_items: list[MagicMock] = []

    def _make_menu_item(label: str = "", **_kw):
        item = MagicMock(name=f"MenuItem({label!r})")
        item._label = label
        item.set_use_underline = MagicMock()
        item.set_sensitive = MagicMock()
        item.set_label = MagicMock()
        item.connect = MagicMock()
        created_menu_items.append(item)
        return item

    fake_gtk.MenuItem.side_effect = _make_menu_item
    fake_gtk.MenuItem.new_with_label = MagicMock(
        side_effect=lambda label: _make_menu_item(label=label)
    )
    fake_gtk.Menu.return_value = MagicMock()
    fake_gtk.SeparatorMenuItem.return_value = MagicMock()
    fake_gtk.IconTheme.get_default.return_value = None  # cai no fallback

    fake_glib = MagicMock()

    fake_indicator_enum = MagicMock()
    fake_indicator_enum.IndicatorStatus.ACTIVE = "active"
    fake_indicator_enum.IndicatorStatus.PASSIVE = "passive"
    fake_indicator_enum.IndicatorCategory.APPLICATION_STATUS = "app_status"
    fake_indicator_enum.Indicator.new = MagicMock(
        return_value=MagicMock(
            set_status=MagicMock(),
            set_menu=MagicMock(),
            set_title=MagicMock(),
        )
    )

    fake_repository = MagicMock()
    fake_repository.Gtk = fake_gtk
    fake_repository.GLib = fake_glib
    fake_repository.AyatanaAppIndicator3 = fake_indicator_enum
    fake_repository.AppIndicator3 = fake_indicator_enum

    fake_gi = ModuleType("gi")
    fake_gi.require_version = MagicMock()  # type: ignore[attr-defined]
    fake_gi.repository = fake_repository  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "gi", fake_gi)
    monkeypatch.setitem(sys.modules, "gi.repository", fake_repository)

    return fake_gtk, created_menu_items


def _make_apptray():
    """Importa AppTray ja aparelhado com os mocks instalados."""
    from hefesto_dualsense4unix.app.tray import AppTray

    tray = AppTray(
        on_show_window=MagicMock(),
        on_quit=MagicMock(),
        on_list_profiles=MagicMock(return_value=[]),
        on_switch_profile=MagicMock(return_value=True),
    )
    return tray


def _patch_apptray_module(monkeypatch: pytest.MonkeyPatch, fake_gtk, fake_glib_module=None):
    """Substitui Gtk/GLib já importados em `hefesto_dualsense4unix.app.tray`.

    Necessário porque o módulo já fez `from gi.repository import GLib, Gtk` no
    topo — patchar `sys.modules` não basta para rebindings já feitos.
    """
    import hefesto_dualsense4unix.app.tray as apptray_mod

    monkeypatch.setattr(apptray_mod, "Gtk", fake_gtk)
    if fake_glib_module is not None:
        monkeypatch.setattr(apptray_mod, "GLib", fake_glib_module)
    # probe_gi_availability vira sempre OK (já que gi mockado).
    monkeypatch.setattr(apptray_mod, "probe_gi_availability", lambda: (True, "ok"))


def test_apptray_render_profiles_remove_placeholder_inicial(monkeypatch: pytest.MonkeyPatch):
    """TRAY-LOADING-ZOMBIE-01: nenhum item residual com label '(carregando)'.

    Após `start()` (que agora chama `_render_profiles([])`) e depois um
    `_render_profiles([{"name": "X"}])`, validar que nenhum dos items
    criados ficou com label '(carregando)' permanente.
    """
    fake_gtk, created = _setup_fake_gi_for_apptray(monkeypatch)
    _patch_apptray_module(monkeypatch, fake_gtk, MagicMock())

    tray = _make_apptray()
    assert tray.start() is True

    # Após start, deve haver "(nenhum perfil)" controlado por _profile_menu_items.
    labels_em_lista = [it._label for it in tray._profile_menu_items]
    assert labels_em_lista == ["(nenhum perfil)"], (
        f"start deve popular submenu via _render_profiles([]); achei {labels_em_lista}"
    )

    # Render de perfis reais.
    tray._render_profiles([{"name": "perfil_a", "active": True}])

    # Nenhum item criado pelo módulo pode ter label '(carregando)'.
    labels_carregando = [it._label for it in created if it._label == "(carregando)"]
    assert labels_carregando == [], (
        f"nenhum item zumbi com '(carregando)' permitido; achei {labels_carregando}"
    )

    # _profile_menu_items reflete o último render (1 perfil).
    final_labels = [it._label for it in tray._profile_menu_items]
    assert final_labels == ["> perfil_a"], (
        f"_profile_menu_items deve refletir o render atual; achei {final_labels}"
    )


def test_apptray_render_profiles_aplica_use_underline_false(monkeypatch: pytest.MonkeyPatch):
    """TRAY-UNDERSCORE-MNEMONIC-01: perfil com `_` recebe set_use_underline(False)."""
    fake_gtk, _created = _setup_fake_gi_for_apptray(monkeypatch)
    _patch_apptray_module(monkeypatch, fake_gtk, MagicMock())

    tray = _make_apptray()
    tray.start()
    tray._render_profiles([{"name": "meu_perfil", "active": False}])

    perfil_item = next(
        (it for it in tray._profile_menu_items if it._label == "meu_perfil"),
        None,
    )
    assert perfil_item is not None, "item para 'meu_perfil' deve existir"
    perfil_item.set_use_underline.assert_called_once_with(False)


def test_apptray_render_perfil_vazio_aplica_use_underline_false(monkeypatch: pytest.MonkeyPatch):
    """TRAY-UNDERSCORE-MNEMONIC-01 (defensivo): '(nenhum perfil)' também recebe."""
    fake_gtk, _created = _setup_fake_gi_for_apptray(monkeypatch)
    _patch_apptray_module(monkeypatch, fake_gtk, MagicMock())

    tray = _make_apptray()
    tray.start()
    # `start` já chama `_render_profiles([])` — basta inspecionar.

    nenhum_item = next(
        (it for it in tray._profile_menu_items if it._label == "(nenhum perfil)"),
        None,
    )
    assert nenhum_item is not None
    nenhum_item.set_use_underline.assert_called_once_with(False)
