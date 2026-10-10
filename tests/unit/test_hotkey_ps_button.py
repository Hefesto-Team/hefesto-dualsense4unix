"""Testes do PS solo (FEAT-HOTKEY-STEAM-01)."""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import steam_launch_options as slo
from hefesto_dualsense4unix.integrations import steam_launcher
from hefesto_dualsense4unix.integrations.hotkey_daemon import HotkeyConfig, HotkeyManager


def test_ps_solo_dispara_no_release_sem_combo():
    fired: list[str] = []
    mgr = HotkeyManager(on_ps_solo=lambda: fired.append("solo"))

    assert mgr.observe(["ps"], now=0.0) is None
    assert fired == []
    result = mgr.observe([], now=0.05)
    assert result == "ps_solo"
    assert fired == ["solo"]


def test_ps_solo_dispara_mesmo_apos_hold_longo():
    """PS segurado sozinho por muito tempo e entao solto ainda conta como solo."""
    fired: list[str] = []
    mgr = HotkeyManager(on_ps_solo=lambda: fired.append("solo"))
    for t in (0.0, 0.2, 0.4, 0.6):
        mgr.observe(["ps"], now=t)
    assert fired == []
    assert mgr.observe([], now=0.65) == "ps_solo"
    assert fired == ["solo"]


def test_ps_solo_suprimido_quando_combo_dispara():
    fired_next: list[str] = []
    fired_solo: list[str] = []
    mgr = HotkeyManager(
        on_next=lambda: fired_next.append("n"),
        on_ps_solo=lambda: fired_solo.append("solo"),
    )
    mgr.observe(["ps", "dpad_up"], now=0.0)
    mgr.observe(["ps", "dpad_up"], now=0.2)
    mgr.observe(["ps"], now=0.25)
    mgr.observe([], now=0.3)
    assert fired_next == ["n"]
    assert fired_solo == []


def test_ps_solo_nao_dispara_sem_callback():
    mgr = HotkeyManager()
    mgr.observe(["ps"], now=0.0)
    assert mgr.observe([], now=0.05) == "ps_solo"


def test_ps_solo_nao_dispara_se_ps_nunca_foi_pressionado():
    fired: list[str] = []
    mgr = HotkeyManager(on_ps_solo=lambda: fired.append("solo"))
    mgr.observe([], now=0.0)
    mgr.observe(["cross"], now=0.1)
    mgr.observe([], now=0.2)
    assert fired == []


def test_ps_solo_readiepara_em_novo_press():
    fired: list[str] = []
    mgr = HotkeyManager(on_ps_solo=lambda: fired.append("solo"))
    mgr.observe(["ps"], now=0.0)
    mgr.observe([], now=0.05)
    mgr.observe(["ps"], now=0.10)
    mgr.observe([], now=0.15)
    assert fired == ["solo", "solo"]


def test_long_press_desligado_por_default():
    """Default novo (FEAT-EMULATION-GAMEMODE-COMBO-01): ps_long_press_ms=0 →"""
    fired: list[str] = []
    mgr = HotkeyManager(on_ps_long_press=lambda: fired.append("long"))
    assert mgr.observe(["ps"], now=0.0) is None
    assert mgr.observe(["ps"], now=2.0) is None
    assert fired == []


def test_long_press_dispara_apos_threshold():
    """Com ps_long_press_ms>0 (gesto reativado), segurar o PS >= threshold dispara"""
    fired: list[str] = []
    mgr = HotkeyManager(
        on_ps_long_press=lambda: fired.append("long"),
        config=HotkeyConfig(ps_long_press_ms=1000),
    )
    assert mgr.observe(["ps"], now=0.0) is None
    assert mgr.observe(["ps"], now=0.5) is None
    assert fired == []
    assert mgr.observe(["ps"], now=1.0) == "ps_long_press"
    assert fired == ["long"]
    assert mgr.observe(["ps"], now=1.2) is None
    assert fired == ["long"]


def test_long_press_suprime_ps_solo_no_release():
    """Após o long-press disparar, o release do PS NÃO abre a Steam (ps_solo)."""
    solo: list[str] = []
    longp: list[str] = []
    mgr = HotkeyManager(
        on_ps_solo=lambda: solo.append("solo"),
        on_ps_long_press=lambda: longp.append("long"),
        config=HotkeyConfig(ps_long_press_ms=1000),
    )
    mgr.observe(["ps"], now=0.0)
    mgr.observe(["ps"], now=1.0)
    assert mgr.observe([], now=1.1) is None
    assert longp == ["long"]
    assert solo == []


def test_toque_curto_no_ps_ainda_abre_steam():
    """Toque curto (< threshold) segue disparando ps_solo (Steam) — sem regressão."""
    solo: list[str] = []
    longp: list[str] = []
    mgr = HotkeyManager(
        on_ps_solo=lambda: solo.append("solo"),
        on_ps_long_press=lambda: longp.append("long"),
    )
    mgr.observe(["ps"], now=0.0)
    assert mgr.observe([], now=0.1) == "ps_solo"
    assert solo == ["solo"]
    assert longp == []


def test_long_press_suprimido_por_combo():
    """PS+D-pad (combo) não dispara long-press mesmo segurando muito tempo."""
    longp: list[str] = []
    nextp: list[str] = []
    mgr = HotkeyManager(
        on_next=lambda: nextp.append("n"),
        on_ps_long_press=lambda: longp.append("long"),
    )
    mgr.observe(["ps", "dpad_up"], now=0.0)
    mgr.observe(["ps", "dpad_up"], now=0.2)
    mgr.observe(["ps", "dpad_up"], now=1.5)
    assert longp == []
    assert nextp == ["n"]


def test_long_press_threshold_configuravel():
    """ps_long_press_ms configuravel via HotkeyConfig."""
    from hefesto_dualsense4unix.integrations.hotkey_daemon import HotkeyConfig

    fired: list[str] = []
    mgr = HotkeyManager(
        on_ps_long_press=lambda: fired.append("long"),
        config=HotkeyConfig(ps_long_press_ms=300),
    )
    mgr.observe(["ps"], now=0.0)
    assert mgr.observe(["ps"], now=0.35) == "ps_long_press"
    assert fired == ["long"]


@pytest.fixture(autouse=True)
def _reset_missing_warning():
    steam_launcher._reset_missing_warning_for_tests()
    yield
    steam_launcher._reset_missing_warning_for_tests()


def test_open_or_focus_steam_sem_porta_nenhuma_avisa_uma_vez(monkeypatch, caplog):
    """Nem ``steam`` nem ``xdg-open``: a porta recusa sem abrir, e o aviso sai uma vez."""
    caplog.set_level("WARNING")
    monkeypatch.setattr(slo, "processos_da_steam", lambda *a, **k: [])
    monkeypatch.setattr(slo, "ha_porta_de_reabrir", lambda: False)

    def _reabrir_proibido(**_k: Any) -> bool:
        raise AssertionError("sem porta nenhuma, nada se reabre")

    monkeypatch.setattr(slo, "reopen_steam", _reabrir_proibido)
    assert steam_launcher.open_or_focus_steam() is False
    assert steam_launcher.open_or_focus_steam() is False


def test_open_or_focus_steam_nunca_levanta(monkeypatch):
    """Se o dono explode, a porta devolve False e não propaga ao fio do gesto."""
    monkeypatch.setattr(slo, "processos_da_steam", lambda *a, **k: [])
    monkeypatch.setattr(slo, "ha_porta_de_reabrir", lambda: True)

    def _bomba(**_k: Any) -> bool:
        raise RuntimeError("o dono morreu")

    monkeypatch.setattr(slo, "reopen_steam", _bomba)
    assert steam_launcher.open_or_focus_steam() is False


def test_daemon_config_ps_button_defaults():
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

    cfg = DaemonConfig()
    assert cfg.ps_button_action == "steam"
    assert cfg.ps_button_command == []


def test_start_hotkey_manager_instancia_e_chama_steam(monkeypatch):
    """Daemon._start_hotkey_manager() cria HotkeyManager; on_ps_solo chama steam."""
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.integrations import steam_launcher as _sl
    from hefesto_dualsense4unix.testing import FakeController

    called: list[str] = []
    monkeypatch.setattr(_sl, "open_or_focus_steam", lambda **_kw: called.append("steam") or True)

    fc = FakeController(transport="usb", states=[])
    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(ps_button_action="steam"),
    )
    daemon._start_hotkey_manager()

    assert daemon._hotkey_manager is not None
    daemon._hotkey_manager.on_ps_solo()
    assert daemon._hotkey_manager.on_ps_solo.esperar(5.0)
    assert called == ["steam"]


def test_start_hotkey_manager_none_nao_chama_steam(monkeypatch):
    """ps_button_action='none' → on_ps_solo não chama nenhum launcher."""
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.integrations import steam_launcher as _sl
    from hefesto_dualsense4unix.testing import FakeController

    called: list[str] = []
    monkeypatch.setattr(_sl, "open_or_focus_steam", lambda **_kw: called.append("steam") or True)

    fc = FakeController(transport="usb", states=[])
    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(ps_button_action="none"),
    )
    daemon._start_hotkey_manager()
    daemon._hotkey_manager.on_ps_solo()
    assert daemon._hotkey_manager.on_ps_solo.esperar(5.0)

    assert called == []


def test_set_emulation_suppressed_toggle_e_set(monkeypatch):
    """set_emulation_suppressed faz toggle (None) e set explicito (bool)."""
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.testing import FakeController

    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.desktop_notifications.notify_emulation_suppressed",
        lambda _s: True,
    )
    daemon = Daemon(controller=FakeController(transport="usb", states=[]), config=DaemonConfig())

    assert daemon._emulation_suppressed is False
    assert daemon.set_emulation_suppressed() is True
    assert daemon._emulation_suppressed is True
    assert daemon.set_emulation_suppressed() is False
    assert daemon.set_emulation_suppressed(True) is True
    assert daemon.set_emulation_suppressed(True) is True
    assert daemon.set_emulation_suppressed(False) is False


def test_start_hotkey_manager_long_press_toggla_modo_jogo(monkeypatch):
    """on_ps_long_press do HotkeyManager alterna daemon._emulation_suppressed."""
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.testing import FakeController

    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.desktop_notifications.notify_emulation_suppressed",
        lambda _s: True,
    )
    daemon = Daemon(controller=FakeController(transport="usb", states=[]), config=DaemonConfig())
    daemon._start_hotkey_manager()

    assert daemon._hotkey_manager.on_ps_long_press is not None
    assert daemon._emulation_suppressed is False
    daemon._hotkey_manager.on_ps_long_press()
    assert daemon._emulation_suppressed is True
    daemon._hotkey_manager.on_ps_long_press()
    assert daemon._emulation_suppressed is False
