"""Testes do Daemon (lifecycle + poll loop)."""
from __future__ import annotations

import asyncio

import pytest

from hefesto.core.controller import ControllerState
from hefesto.core.events import EventBus, EventTopic
from hefesto.daemon.lifecycle import (
    BATTERY_DEBOUNCE_SEC,
    Daemon,
    DaemonConfig,
)
from hefesto.daemon.state_store import StateStore
from hefesto.testing import FakeController


def _mk_states(n: int, transport: str = "usb") -> list[ControllerState]:
    return [
        ControllerState(
            battery_pct=80,
            l2_raw=i % 256,
            r2_raw=(255 - i) % 256,
            connected=True,
            transport=transport,  # type: ignore[arg-type]
        )
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_poll_loop_gera_state_update_e_para_no_stop():
    fc = FakeController(transport="usb", states=_mk_states(20))
    bus = EventBus()
    store = StateStore()
    daemon = Daemon(
        controller=fc,
        bus=bus,
        store=store,
        config=DaemonConfig(
            poll_hz=120, auto_reconnect=False,
            ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False,
        ),
    )

    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.05)
    state_queue = bus.subscribe(EventTopic.STATE_UPDATE)
    await asyncio.sleep(0.15)
    daemon.stop()
    await run_task

    assert store.counter("poll.tick") >= 5
    assert state_queue.qsize() >= 1


@pytest.mark.asyncio
async def test_connected_event_publicado_no_start():
    fc = FakeController(transport="bt", states=_mk_states(3, "bt"))
    bus = EventBus()
    daemon = Daemon(
        controller=fc, bus=bus,
        config=DaemonConfig(
            poll_hz=60, auto_reconnect=False,
            ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False,
        ),
    )

    queue = bus.subscribe(EventTopic.CONTROLLER_CONNECTED)
    run_task = asyncio.create_task(daemon.run())
    payload = await asyncio.wait_for(queue.get(), timeout=1.0)
    daemon.stop()
    await run_task

    assert payload == {"transport": "bt"}


@pytest.mark.asyncio
async def test_battery_debounce_dispara_no_primeiro_read():
    fc = FakeController(
        transport="usb",
        states=[
            ControllerState(battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb"),
            ControllerState(battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb"),
            ControllerState(battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb"),
        ],
    )
    bus = EventBus()
    store = StateStore()
    cfg = DaemonConfig(
        poll_hz=120, auto_reconnect=False,
        ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False,
    )
    daemon = Daemon(controller=fc, bus=bus, store=store, config=cfg)

    queue = bus.subscribe(EventTopic.BATTERY_CHANGE)
    run_task = asyncio.create_task(daemon.run())

    first = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert first == 80

    await asyncio.sleep(0.05)
    daemon.stop()
    await run_task

    # Bateria não mudou: min-interval (100ms) + elapsed < 5s impede novo disparo
    assert store.counter("battery.change.emitted") == 1


@pytest.mark.asyncio
async def test_battery_dispara_quando_delta_pct():
    states = [
        ControllerState(battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb"),
    ]
    for _ in range(30):
        states.append(
            ControllerState(battery_pct=79, l2_raw=0, r2_raw=0, connected=True, transport="usb")
        )
    fc = FakeController(transport="usb", states=states)
    bus = EventBus()
    store = StateStore()
    cfg = DaemonConfig(
        poll_hz=60, auto_reconnect=False,
        ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False,
    )
    daemon = Daemon(controller=fc, bus=bus, store=store, config=cfg)

    queue = bus.subscribe(EventTopic.BATTERY_CHANGE)
    run_task = asyncio.create_task(daemon.run())

    first = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert first == 80

    second = await asyncio.wait_for(queue.get(), timeout=2.0)
    assert second == 79

    daemon.stop()
    await run_task


@pytest.mark.asyncio
async def test_stop_idempotente():
    fc = FakeController(transport="usb", states=_mk_states(5))
    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=60, auto_reconnect=False,
            ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False,
        ),
    )
    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.03)
    daemon.stop()
    daemon.stop()  # segundo stop é noop
    await run_task


@pytest.mark.asyncio
async def test_daemon_desconecta_no_shutdown():
    fc = FakeController(transport="usb", states=_mk_states(5))
    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=60, auto_reconnect=False,
            ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False,
        ),
    )
    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.03)
    assert fc.is_connected() is True
    daemon.stop()
    await run_task
    assert fc.is_connected() is False


def test_battery_debounce_constants_coerentes_com_adr008():
    # Sanidade cross-regra: ADR-008 + V2-17 exige 1%, 5s, min 100ms
    from hefesto.daemon.lifecycle import (
        BATTERY_DELTA_THRESHOLD_PCT,
        BATTERY_MIN_INTERVAL_SEC,
    )

    assert BATTERY_DELTA_THRESHOLD_PCT == 1
    assert BATTERY_DEBOUNCE_SEC == 5.0
    assert BATTERY_MIN_INTERVAL_SEC == 0.1
