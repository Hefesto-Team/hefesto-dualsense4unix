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


@pytest.mark.asyncio
async def test_poll_loop_emits_button_down_up_on_diff():
    """Publica BUTTON_DOWN/UP ao diff entre ticks (INFRA-BUTTON-EVENTS-01).

    Tick 1: cross pressionado  -> BUTTON_DOWN cross.
    Tick 2: cross + circle     -> BUTTON_DOWN circle (cross mantido, sem UP).
    Tick 3: nenhum pressionado -> BUTTON_UP cross, BUTTON_UP circle.
    Total esperado: 3 DOWN (cross, circle) + 2 UP (circle, cross por ordem sorted).
    """
    states = [
        ControllerState(
            battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb",
            buttons_pressed=frozenset({"cross"}),
        ),
        ControllerState(
            battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb",
            buttons_pressed=frozenset({"cross", "circle"}),
        ),
        ControllerState(
            battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb",
            buttons_pressed=frozenset(),
        ),
    ]
    fc = FakeController(transport="usb", states=states)
    bus = EventBus()
    store = StateStore()
    cfg = DaemonConfig(
        poll_hz=120, auto_reconnect=False,
        ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False,
    )
    daemon = Daemon(controller=fc, bus=bus, store=store, config=cfg)

    down_queue = bus.subscribe(EventTopic.BUTTON_DOWN)
    up_queue = bus.subscribe(EventTopic.BUTTON_UP)

    run_task = asyncio.create_task(daemon.run())
    # Aguarda processamento dos 3 ticks (120Hz → ~25ms por tick)
    await asyncio.sleep(0.15)
    daemon.stop()
    await run_task

    # Coleta eventos publicados
    down_events = []
    while not down_queue.empty():
        down_events.append(await down_queue.get())
    up_events = []
    while not up_queue.empty():
        up_events.append(await up_queue.get())

    down_buttons = [e["button"] for e in down_events]
    up_buttons = [e["button"] for e in up_events]

    # cross DOWN no tick 1; circle DOWN no tick 2
    assert "cross" in down_buttons
    assert "circle" in down_buttons
    # circle UP e cross UP no tick 3
    assert "cross" in up_buttons
    assert "circle" in up_buttons

    # Contadores no store refletem emissões
    assert store.counter("button.down.emitted") >= 2
    assert store.counter("button.up.emitted") >= 2

    # Payloads corretos
    for ev in down_events:
        assert ev["pressed"] is True
    for ev in up_events:
        assert ev["pressed"] is False


@pytest.mark.asyncio
async def test_poll_loop_emits_mic_btn_down_up():
    """Mic button via ControllerState.buttons_pressed gera BUTTON_DOWN/UP (INFRA-MIC-HID-01).

    FakeController com mic_btn alternando entre ticks produz sequência correta.
    """
    states = [
        ControllerState(
            battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb",
            buttons_pressed=frozenset({"mic_btn"}),
        ),
        ControllerState(
            battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb",
            buttons_pressed=frozenset(),
        ),
    ]
    fc = FakeController(transport="usb", states=states)
    bus = EventBus()
    store = StateStore()
    cfg = DaemonConfig(
        poll_hz=120, auto_reconnect=False,
        ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False,
    )
    daemon = Daemon(controller=fc, bus=bus, store=store, config=cfg)

    down_queue = bus.subscribe(EventTopic.BUTTON_DOWN)
    up_queue = bus.subscribe(EventTopic.BUTTON_UP)

    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.1)
    daemon.stop()
    await run_task

    down_events = []
    while not down_queue.empty():
        down_events.append(await down_queue.get())
    up_events = []
    while not up_queue.empty():
        up_events.append(await up_queue.get())

    down_buttons = [e["button"] for e in down_events]
    up_buttons = [e["button"] for e in up_events]

    assert "mic_btn" in down_buttons
    assert "mic_btn" in up_buttons

    # Verificar payloads
    mic_down = next((e for e in down_events if e["button"] == "mic_btn"), None)
    mic_up = next((e for e in up_events if e["button"] == "mic_btn"), None)
    assert mic_down is not None and mic_down["pressed"] is True
    assert mic_up is not None and mic_up["pressed"] is False


@pytest.mark.asyncio
async def test_poll_loop_no_event_when_buttons_unchanged():
    """Nenhum evento publicado se buttons_pressed não muda (idempotência — critério 5)."""
    state_base = ControllerState(
        battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb",
        buttons_pressed=frozenset({"cross"}),
    )
    # 10 ticks com mesmo conjunto — deve gerar exatamente 1 DOWN na transição
    # vazio -> {cross} e nenhum UP
    states = [state_base] * 10
    fc = FakeController(transport="usb", states=states)
    bus = EventBus()
    store = StateStore()
    cfg = DaemonConfig(
        poll_hz=120, auto_reconnect=False,
        ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False,
    )
    daemon = Daemon(controller=fc, bus=bus, store=store, config=cfg)

    down_queue = bus.subscribe(EventTopic.BUTTON_DOWN)
    up_queue = bus.subscribe(EventTopic.BUTTON_UP)

    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.15)
    daemon.stop()
    await run_task

    down_count = down_queue.qsize()
    up_count = up_queue.qsize()

    # Exatamente 1 DOWN (vazio -> {cross}); 0 UP
    assert down_count == 1
    assert up_count == 0
    assert store.counter("button.down.emitted") == 1
    assert store.counter("button.up.emitted") == 0
