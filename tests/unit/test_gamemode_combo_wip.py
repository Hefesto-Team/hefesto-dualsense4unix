"""Cobertura do WIP de modo-jogo / combo (estava sem teste no caminho-estrela)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.integrations.hotkey_daemon import (
    DEFAULT_COMBO_GAMEMODE,
    HotkeyConfig,
    HotkeyManager,
)


def test_latch_forma_e_segura_ate_soltar() -> None:
    """PS+Options forma o combo; soltar o PS antes do Options NÃO libera o"""
    hm = HotkeyManager()
    assert hm.combo_buttons_active({"ps", "options"}) == frozenset({"ps", "options"})
    assert hm.combo_buttons_active({"options"}) == frozenset({"options"})
    assert hm.combo_buttons_active(set()) == frozenset()
    assert hm.combo_buttons_active({"options"}) == frozenset()


def test_options_sozinho_nunca_bloqueia() -> None:
    hm = HotkeyManager()
    assert hm.combo_buttons_active({"options"}) == frozenset()


def test_sem_ps_nao_bloqueia_nada() -> None:
    hm = HotkeyManager()
    assert hm.combo_buttons_active({"cross", "square"}) == frozenset()


def test_combo_gamemode_dispara_on_ps_long_press() -> None:
    calls: list[str] = []
    hm = HotkeyManager(on_ps_long_press=lambda: calls.append("toggle"))
    assert hm.observe({"ps", "options"}, now=0.0) is None
    fired = hm.observe({"ps", "options"}, now=0.2)
    assert fired == "gamemode"
    assert calls == ["toggle"]


def test_default_combo_gamemode_e_ps_options() -> None:
    assert DEFAULT_COMBO_GAMEMODE == ("ps", "options")


def test_combo_gamemode_funciona_com_long_press_desligado() -> None:
    """Config da Vitória: ps_long_press_ms=0 (modo-jogo só por combo)."""
    calls: list[str] = []
    hm = HotkeyManager(
        on_ps_long_press=lambda: calls.append("toggle"),
        config=HotkeyConfig(ps_long_press_ms=0),
    )
    hm.observe({"ps", "options"}, now=0.0)
    fired = hm.observe({"ps", "options"}, now=0.2)
    assert fired == "gamemode"
    assert calls == ["toggle"]


def test_ps_long_press_zero_nao_alterna_em_hold() -> None:
    calls: list[str] = []
    hm = HotkeyManager(
        on_ps_long_press=lambda: calls.append("toggle"),
        on_ps_solo=lambda: calls.append("steam"),
        config=HotkeyConfig(ps_long_press_ms=0),
    )
    hm.observe({"ps"}, now=0.0)
    hm.observe({"ps"}, now=2.0)
    assert "toggle" not in calls, "long-press desligado não deve alternar no hold"
    hm.observe(set(), now=2.05)

    assert calls == [], "hold de 2 s passa do teto de 700 ms: não é toque curto"

    hm.observe({"ps"}, now=10.0)
    hm.observe(set(), now=10.2)
    assert calls == ["steam"], "PS solo deve abrir a Steam no release curto"


def test_ps_solo_toque_curto_abre_steam() -> None:
    calls: list[str] = []
    hm = HotkeyManager(on_ps_solo=lambda: calls.append("steam"))
    hm.observe({"ps"}, now=0.0)
    hm.observe(set(), now=0.1)
    assert calls == ["steam"]


def test_suppress_faz_flush_dos_devices(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.testing import FakeController

    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.desktop_notifications."
        "notify_emulation_suppressed",
        lambda *_a, **_k: None,
    )

    daemon = Daemon(controller=FakeController(transport="usb"), config=DaemonConfig())
    kbd = MagicMock()
    mouse = MagicMock()
    daemon._keyboard_device = kbd
    daemon._mouse_device = mouse

    new_state = daemon.set_emulation_suppressed(True)

    assert new_state is True
    kbd.dispatch.assert_called_once_with(frozenset())
    mouse.dispatch.assert_called_once_with(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=0, buttons=frozenset()
    )


def test_unsuppress_nao_faz_flush(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.testing import FakeController

    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.desktop_notifications."
        "notify_emulation_suppressed",
        lambda *_a, **_k: None,
    )

    daemon = Daemon(controller=FakeController(transport="usb"), config=DaemonConfig())
    daemon._emulation_suppressed = True
    kbd = MagicMock()
    mouse = MagicMock()
    daemon._keyboard_device = kbd
    daemon._mouse_device = mouse

    new_state = daemon.set_emulation_suppressed(False)

    assert new_state is False
    kbd.dispatch.assert_not_called()
    mouse.dispatch.assert_not_called()
