"""Garante que _evdev.snapshot() é chamado exatamente 1x por tick no poll loop."""
from __future__ import annotations

import asyncio
from typing import Any, ClassVar
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.testing import FakeController


def _mk_states(n: int) -> list[ControllerState]:
    return [
        ControllerState(
            battery_pct=80,
            l2_raw=0,
            r2_raw=0,
            connected=True,
            transport="usb",
        )
        for _ in range(n)
    ]


class _FakeSnap:
    """Snapshot evdev mínimo para testes."""

    buttons_pressed: ClassVar[list[str]] = []


class _FakeSnapComBotoes:
    """Snapshot evdev com botões pré-definidos."""

    buttons_pressed: ClassVar[list[str]] = ["cross", "ps"]


@pytest.mark.asyncio
async def test_snapshot_chamado_exatamente_uma_vez_por_tick_sem_consumidores():
    """Com evdev disponível mas sem mouse nem hotkey ativos, snapshot() deve ser"""
    n_ticks = 10
    call_counter: list[int] = []

    fc = FakeController(transport="usb", states=_mk_states(n_ticks * 4))
    mock_evdev = MagicMock()
    mock_evdev.is_available.return_value = True
    mock_evdev.snapshot.side_effect = lambda: (call_counter.append(1) or _FakeSnap())
    fc._evdev = mock_evdev

    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
        ),
    )

    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.15)
    daemon.stop()
    await run_task

    ticks = daemon.store.counter("poll.tick")
    assert ticks >= n_ticks, f"poll.tick esperado >= {n_ticks}, obtido {ticks}"
    assert len(call_counter) == ticks, (
        f"snapshot() chamado {len(call_counter)}x para {ticks} ticks "
        f"(esperado 1:1 — sem duplicatas)"
    )


@pytest.mark.asyncio
async def test_snapshot_chamado_exatamente_uma_vez_por_tick_com_hotkey_e_mouse(
    monkeypatch: pytest.MonkeyPatch,
):
    """Com hotkey_manager E mouse_device ativos, snapshot() deve ser chamado"""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.0
    )
    n_ticks = 10
    call_counter: list[int] = []

    fc = FakeController(transport="usb", states=_mk_states(n_ticks * 4))
    mock_evdev = MagicMock()
    mock_evdev.is_available.return_value = True
    mock_evdev.snapshot.side_effect = lambda: (call_counter.append(1) or _FakeSnap())
    fc._evdev = mock_evdev

    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
        ),
    )

    from hefesto_dualsense4unix.integrations.hotkey_daemon import HotkeyManager

    daemon._hotkey_manager = HotkeyManager()

    dispatch_calls: list[Any] = []
    mock_mouse = MagicMock()
    mock_mouse.dispatch.side_effect = lambda **kw: dispatch_calls.append(kw)
    daemon._mouse_device = mock_mouse

    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.15)
    daemon.stop()
    await run_task

    ticks = daemon.store.counter("poll.tick")
    assert ticks >= n_ticks, f"poll.tick esperado >= {n_ticks}, obtido {ticks}"

    assert len(call_counter) == ticks, (
        f"snapshot() chamado {len(call_counter)}x para {ticks} ticks "
        f"(esperado 1:1 — refactor A-09 falhou se > ticks)"
    )

    assert len(dispatch_calls) == ticks, (
        f"mouse.dispatch chamado {len(dispatch_calls)}x para {ticks} ticks"
    )


@pytest.mark.asyncio
async def test_snapshot_nao_chamado_quando_evdev_indisponivel():
    """Se evdev.is_available() retorna False, snapshot() não deve ser chamado."""
    n_ticks = 5
    call_counter: list[int] = []

    fc = FakeController(transport="usb", states=_mk_states(n_ticks * 4))
    mock_evdev = MagicMock()
    mock_evdev.is_available.return_value = False
    mock_evdev.snapshot.side_effect = lambda: call_counter.append(1)
    fc._evdev = mock_evdev

    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
        ),
    )

    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.10)
    daemon.stop()
    await run_task

    assert len(call_counter) == 0, (
        f"snapshot() foi chamado {len(call_counter)}x mesmo com is_available=False"
    )


@pytest.mark.asyncio
async def test_snapshot_excecao_retorna_frozenset_vazio():
    """Se snapshot() lança exceção, _evdev_buttons_once retorna frozenset() vazio"""
    n_ticks = 5
    fc = FakeController(transport="usb", states=_mk_states(n_ticks * 4))
    mock_evdev = MagicMock()
    mock_evdev.is_available.return_value = True
    mock_evdev.snapshot.side_effect = RuntimeError("evdev explodiu")
    fc._evdev = mock_evdev

    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
        ),
    )

    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.10)
    daemon.stop()
    await run_task

    ticks = daemon.store.counter("poll.tick")
    assert ticks >= n_ticks, (
        f"poll loop parou precocemente ({ticks} ticks) após exceção no evdev"
    )


@pytest.mark.asyncio
async def test_botoes_passados_ao_hotkey_manager_e_ao_mouse(
    monkeypatch: pytest.MonkeyPatch,
):
    """Botões retornados por _evdev_buttons_once devem chegar ao hotkey_manager.observe"""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.0
    )
    n_ticks = 5

    fc = FakeController(transport="usb", states=_mk_states(n_ticks * 4))
    mock_evdev = MagicMock()
    mock_evdev.is_available.return_value = True
    mock_evdev.snapshot.return_value = _FakeSnapComBotoes()
    fc._evdev = mock_evdev

    hotkey_observes: list[frozenset[str]] = []

    from hefesto_dualsense4unix.integrations.hotkey_daemon import HotkeyManager

    _orig_observe = HotkeyManager.observe

    def _spy_observe(self: Any, pressed: Any, *, now: Any = None, de: Any = None) -> Any:
        assert de is None, f"o laço leu um controle que o FakeController não tem: {de}"
        hotkey_observes.append(frozenset(pressed))
        return _orig_observe(self, pressed, now=now, de=de)

    monkeypatch.setattr(HotkeyManager, "observe", _spy_observe)

    dispatch_buttons: list[frozenset[str]] = []
    mock_mouse = MagicMock()
    mock_mouse.dispatch.side_effect = lambda **kw: dispatch_buttons.append(
        kw.get("buttons", frozenset())
    )

    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
        ),
    )
    daemon._mouse_device = mock_mouse

    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.10)
    daemon.stop()
    await run_task

    ticks = daemon.store.counter("poll.tick")
    assert ticks >= n_ticks

    observe_esperado = frozenset(["cross", "ps"])
    dispatch_esperado = frozenset(["cross"])
    assert hotkey_observes, "hotkey_manager.observe nunca foi chamado"
    assert all(b == observe_esperado for b in hotkey_observes), (
        f"hotkey_manager recebeu botões incorretos: {hotkey_observes[:3]!r}"
    )
    assert dispatch_buttons, "mouse.dispatch nunca foi chamado"
    assert all(b == dispatch_esperado for b in dispatch_buttons), (
        f"mouse.dispatch recebeu botões incorretos (ps deve ser latchado): "
        f"{dispatch_buttons[:3]!r}"
    )
