"""Testes do Daemon (lifecycle + poll loop)."""
from __future__ import annotations

import asyncio
import dataclasses

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.lifecycle import (
    BATTERY_DEBOUNCE_SEC,
    Daemon,
    DaemonConfig,
)
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.testing import FakeController


async def _ate(condicao, prazo_s: float = 3.0) -> bool:  # type: ignore[no-untyped-def]
    """Espera a condição com prazo, em vez de um sono fixo que o tique pode perder."""
    laco = asyncio.get_running_loop()
    fim = laco.time() + prazo_s
    while not condicao():
        if laco.time() > fim:
            return False
        await asyncio.sleep(0.01)
    return True


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
    daemon.stop()
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


class _ControleQueCaiPeloProbe(FakeController):
    """A queda pela porta do `is_connected()` — e SÓ por ela. E quem cai não volta."""

    caiu = False

    def cair(self) -> None:
        """A queda: nenhum controle na mesa a partir daqui."""
        self.caiu = True
        self.disconnect()

    def connect(self) -> None:
        if not self.caiu:
            super().connect()

    def read_state(self) -> ControllerState:
        if not self._connected:
            return dataclasses.replace(self._states[-1], connected=False)
        return super().read_state()


class _ControleQueSomeNaLeitura(FakeController):
    """A queda pela porta da LEITURA — e SÓ por ela.

    Um DualSense que sai da mesa de vez aparece primeiro como leitura que
    levanta, com o handle ainda aberto (`poll_read_failed` antes do
    `probe_offline`, ver `DiarioDaBateria.registrar_queda`). Depois de
    `leituras` leituras boas, a próxima levanta como o hidraw que sumiu, e a
    reconexão não acha ninguém — como o backend real, cujo `connect()` devolve
    sem levantar e fica fora de linha.
    """

    def __init__(self, leituras: int) -> None:
        super().__init__(transport="bt", states=_mk_states(leituras, "bt"))
        self._restam = leituras
        self.sumiu = False

    def connect(self) -> None:
        if not self.sumiu:
            super().connect()

    def read_state(self) -> ControllerState:
        if self._restam <= 0:
            self.sumiu = True
            raise OSError(5, "Input/output error")
        self._restam -= 1
        return super().read_state()


@pytest.mark.asyncio
async def test_borda_de_queda_limpa_o_estado_publicado():
    """ONDA0-Z5/T1 — mordida.

    Sem controle na mesa, o daemon não pode seguir dizendo a última leitura
    boa (medido: `connected: true, transport: "bt", battery_pct: 75` com
    ZERO controles na bancada, ONDA0-Z5 §2.2). O FakeController conecta, lê
    alguns estados e então "cai" (`disconnect()`, um probe/unplug real) — a
    BORDA tem de escrever `None` no store e apagar `_last_state` uma única
    vez, para que `daemon.status` e `daemon.state_full` parem de repetir
    bt/75% para uma mesa vazia.
    """
    fc = _ControleQueCaiPeloProbe(transport="bt", states=_mk_states(30, "bt"))
    bus = EventBus()
    store = StateStore()
    daemon = Daemon(
        controller=fc, bus=bus, store=store,
        config=DaemonConfig(
            poll_hz=200, auto_reconnect=False,
            ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False,
        ),
    )

    run_task = asyncio.create_task(daemon.run())
    assert await _ate(
        lambda: store.snapshot().controller is not None and daemon._last_state is not None
    ), "o daemon não leu nada antes da queda"

    fc.cair()
    await _ate(lambda: store.snapshot().controller is None and daemon._last_state is None)

    daemon.stop()
    await run_task

    snap = store.snapshot()
    assert snap.controller is None, (
        "o store guardou a última leitura boa em vez de limpar na queda — "
        "é a mentira medida na ONDA0-Z5 (bt/75% sobrevivendo à desconexão)"
    )
    assert daemon._last_state is None, (
        "_last_state sobreviveu à queda — daemon.state_full priorizaria "
        "essa carga estagnada sobre o store já limpo (CLUSTER-IPC-STATE-"
        "PROFILE-01)"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("auto_reconnect", [False, True])
async def test_a_queda_pela_leitura_tambem_limpa_o_estado_publicado(
    auto_reconnect: bool,
) -> None:
    """A MESMA BORDA, PELA OUTRA PORTA (27/09/2026)."""
    fc = _ControleQueSomeNaLeitura(leituras=20)
    store = StateStore()
    daemon = Daemon(
        controller=fc, bus=EventBus(), store=store,
        config=DaemonConfig(
            poll_hz=200, auto_reconnect=auto_reconnect, reconnect_backoff_sec=0.01,
            ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False,
        ),
    )

    run_task = asyncio.create_task(daemon.run())
    try:
        assert await _ate(lambda: fc.sumiu), "a leitura nunca levantou"
        limpo = await _ate(
            lambda: store.snapshot().controller is None and daemon._last_state is None
        )
    finally:
        daemon.stop()
        await run_task

    assert store.counter("poll.tick") >= 1, "o daemon não leu nada antes da queda"
    assert limpo, (
        "a queda chegou pela leitura e o daemon seguiu publicando a última "
        "leitura boa — a mentira da ONDA0-Z5 pela outra porta"
    )


def test_battery_debounce_constants_coerentes_com_adr008():
    from hefesto_dualsense4unix.daemon.lifecycle import (
        BATTERY_DELTA_THRESHOLD_PCT,
        BATTERY_MIN_INTERVAL_SEC,
    )

    assert BATTERY_DELTA_THRESHOLD_PCT == 1
    assert BATTERY_DEBOUNCE_SEC == 5.0
    assert BATTERY_MIN_INTERVAL_SEC == 0.1


@pytest.mark.asyncio
async def test_poll_loop_emits_button_down_up_on_diff(monkeypatch):
    """Publica BUTTON_DOWN/UP ao diff entre ticks (INFRA-BUTTON-EVENTS-01)."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.0
    )
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
    await asyncio.sleep(0.15)
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

    assert "cross" in down_buttons
    assert "circle" in down_buttons
    assert "cross" in up_buttons
    assert "circle" in up_buttons

    assert store.counter("button.down.emitted") >= 2
    assert store.counter("button.up.emitted") >= 2

    for ev in down_events:
        assert ev["pressed"] is True
    for ev in up_events:
        assert ev["pressed"] is False


@pytest.mark.asyncio
async def test_poll_loop_emits_mic_btn_down_up(monkeypatch):
    """Mic button via ControllerState.buttons_pressed gera BUTTON_DOWN/UP (INFRA-MIC-HID-01)."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.0
    )
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

    mic_down = next((e for e in down_events if e["button"] == "mic_btn"), None)
    mic_up = next((e for e in up_events if e["button"] == "mic_btn"), None)
    assert mic_down is not None and mic_down["pressed"] is True
    assert mic_up is not None and mic_up["pressed"] is False


@pytest.mark.asyncio
async def test_poll_loop_no_event_when_buttons_unchanged(monkeypatch):
    """Nenhum evento publicado se buttons_pressed não muda (idempotência — critério 5)."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.0
    )
    state_base = ControllerState(
        battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb",
        buttons_pressed=frozenset({"cross"}),
    )
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

    assert down_count == 1
    assert up_count == 0
    assert store.counter("button.down.emitted") == 1
    assert store.counter("button.up.emitted") == 0


def _free_port() -> int:
    """Retorna uma porta TCP livre em 127.0.0.1."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.mark.asyncio
async def test_metrics_sobe_quando_metrics_enabled():
    """Com metrics_enabled=True, `run()` sobe o servidor HTTP de métricas."""
    import urllib.request

    port = _free_port()
    fc = FakeController(transport="usb", states=_mk_states(20))
    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=120, auto_reconnect=False,
            ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False,
            metrics_enabled=True, metrics_port=port,
        ),
    )

    run_task = asyncio.create_task(daemon.run())
    try:
        await asyncio.sleep(0.1)
        assert daemon._metrics_subsystem is not None
        url = f"http://127.0.0.1:{port}/metrics"
        payload = await asyncio.to_thread(
            lambda: urllib.request.urlopen(url, timeout=5).read().decode("utf-8")
        )
        assert "hefesto_poll_ticks_total" in payload
    finally:
        daemon.stop()
        await run_task
        await daemon._stop_metrics()


@pytest.mark.asyncio
async def test_metrics_nao_sobe_quando_disabled():
    """Com metrics_enabled=False (default), `_start_metrics` é no-op (gate)."""
    fc = FakeController(transport="usb", states=_mk_states(2))
    daemon = Daemon(controller=fc, config=DaemonConfig(metrics_enabled=False))
    await daemon._start_metrics()
    assert daemon._metrics_subsystem is None
