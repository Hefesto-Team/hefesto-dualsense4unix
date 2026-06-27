"""Subsystems resilientes (FEAT-DAEMON-RESILIENT-SUBSYSTEMS-01).

Um subsystem que falha ao iniciar (dep nativa ausente, porta em uso, permissão
negada) é isolado em `_failed_subsystems` e o daemon segue rodando — poll/IPC/
perfis sobrevivem a um subsystem quebrado, em vez de o boot inteiro morrer.
"""
from __future__ import annotations

import asyncio

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.testing import FakeController


def _state() -> ControllerState:
    return ControllerState(
        battery_pct=80, l2_raw=0, r2_raw=0, connected=True,
        transport="usb", buttons_pressed=frozenset(),
    )


def _config(**over: object) -> DaemonConfig:
    base: dict[str, object] = dict(
        poll_hz=200, auto_reconnect=False, udp_enabled=False, autoswitch_enabled=False,
        mouse_emulation_enabled=False, keyboard_emulation_enabled=False,
        ps_button_action="none", mic_button_toggles_system=False,
    )
    base.update(over)
    return DaemonConfig(**base)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_failing_subsystem_does_not_kill_daemon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.load_paused_state", lambda: False
    )
    fc = FakeController(transport="usb", states=[_state()])
    bus = EventBus()
    store = StateStore()
    daemon = Daemon(controller=fc, bus=bus, store=store, config=_config(ipc_enabled=True))

    async def _boom() -> None:
        raise RuntimeError("ipc explodiu no start")

    monkeypatch.setattr(daemon, "_start_ipc", _boom)

    run_task = asyncio.create_task(daemon.run())
    # Espera deterministicamente o 1º tick do poll antes de parar — sob carga e
    # com cobertura (--cov) no CI um sleep fixo de 0.1s pode não bastar (flaky).
    for _ in range(500):
        if store.counter("poll.tick") >= 1:
            break
        await asyncio.sleep(0.01)
    daemon.stop()
    await run_task

    # O IPC falhou e foi isolado; o daemon NÃO morreu (poll seguiu rodando).
    assert "ipc" in daemon._failed_subsystems
    assert "explodiu" in daemon._failed_subsystems["ipc"]
    assert store.counter("poll.tick") >= 1
