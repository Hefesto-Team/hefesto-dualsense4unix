"""Testes do HotkeyManager."""
from __future__ import annotations

from hefesto_dualsense4unix.integrations.hotkey_daemon import (
    DEFAULT_BUFFER_MS,
    HotkeyConfig,
    HotkeyManager,
)


def test_combo_nao_dispara_antes_do_buffer():
    fired = []
    mgr = HotkeyManager(on_next=lambda: fired.append("next"))

    # t=0: pressiona combo
    assert mgr.observe(["ps", "dpad_up"], now=0.0) is None
    assert fired == []

    # t=0.1s: ainda dentro do buffer (150ms)
    assert mgr.observe(["ps", "dpad_up"], now=0.1) is None
    assert fired == []


def test_combo_dispara_apos_buffer():
    fired = []
    mgr = HotkeyManager(on_next=lambda: fired.append("next"))

    mgr.observe(["ps", "dpad_up"], now=0.0)
    result = mgr.observe(["ps", "dpad_up"], now=0.2)  # >150ms
    assert result == "next"
    assert fired == ["next"]


def test_combo_so_dispara_uma_vez_enquanto_segurado():
    fired = []
    mgr = HotkeyManager(on_next=lambda: fired.append("n"))
    mgr.observe(["ps", "dpad_up"], now=0.0)
    mgr.observe(["ps", "dpad_up"], now=0.2)
    mgr.observe(["ps", "dpad_up"], now=0.3)
    mgr.observe(["ps", "dpad_up"], now=0.5)
    assert fired == ["n"]


def test_combo_pode_redisparar_apos_release():
    fired = []
    mgr = HotkeyManager(on_next=lambda: fired.append("n"))
    mgr.observe(["ps", "dpad_up"], now=0.0)
    mgr.observe(["ps", "dpad_up"], now=0.2)
    # solta
    mgr.observe([], now=0.25)
    mgr.observe(["ps", "dpad_up"], now=0.3)
    mgr.observe(["ps", "dpad_up"], now=0.5)
    assert fired == ["n", "n"]


def test_combo_prev_separado():
    hits = {"next": 0, "prev": 0}
    mgr = HotkeyManager(
        on_next=lambda: hits.__setitem__("next", hits["next"] + 1),
        on_prev=lambda: hits.__setitem__("prev", hits["prev"] + 1),
    )
    mgr.observe(["ps", "dpad_down"], now=0.0)
    mgr.observe(["ps", "dpad_down"], now=0.2)
    assert hits == {"next": 0, "prev": 1}


def test_botao_solo_nao_dispara():
    fired = []
    mgr = HotkeyManager(on_next=lambda: fired.append("n"))
    for t in (0.0, 0.1, 0.2, 0.3):
        mgr.observe(["ps"], now=t)
    assert fired == []


def test_passthrough_repassa_fora_de_emulation():
    mgr = HotkeyManager()
    assert mgr.should_passthrough(["ps", "dpad_up"], emulation_active=False) is True


def test_passthrough_bloqueia_combo_em_emulation():
    mgr = HotkeyManager()
    assert mgr.should_passthrough(["ps", "dpad_up"], emulation_active=True) is False


def test_passthrough_permite_botao_solo_em_emulation():
    mgr = HotkeyManager()
    assert mgr.should_passthrough(["cross"], emulation_active=True) is True


def test_passthrough_respeita_config_override():
    mgr = HotkeyManager(
        config=HotkeyConfig(passthrough_in_emulation=True)
    )
    assert mgr.should_passthrough(["ps", "dpad_up"], emulation_active=True) is True


def test_config_customizado():
    mgr = HotkeyManager(
        config=HotkeyConfig(buffer_ms=50, next_profile=("l1", "r1"))
    )
    fired = []
    mgr.on_next = lambda: fired.append("n")
    mgr.observe(["l1", "r1"], now=0.0)
    mgr.observe(["l1", "r1"], now=0.08)  # 80ms > buffer de 50ms
    assert fired == ["n"]


def test_default_buffer_configuracao():
    assert DEFAULT_BUFFER_MS == 150  # V3-2
    cfg = HotkeyConfig()
    assert cfg.buffer_ms == 150
