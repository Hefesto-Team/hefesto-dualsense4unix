"""Testes do reconnect_loop não-bloqueante (BUG-DAEMON-NO-DEVICE-FATAL-01).

Cobre:
- IPC sobe ANTES do daemon conectar (o controle pode aparecer depois).
- reconnect_loop publica CONTROLLER_CONNECTED na transição offline→online.
- _stop_event durante o backoff faz a task retornar rapidamente.
"""
from __future__ import annotations

import asyncio

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.testing.fake_controller import FakeController


def _mk_state() -> ControllerState:
    return ControllerState(
        battery_pct=75,
        l2_raw=0,
        r2_raw=0,
        connected=True,
        transport="usb",
    )


class _OfflineThenOnlineController(FakeController):
    """FakeController cujo connect() falha com "No device detected" nas
    primeiras `fail_until` chamadas e depois conecta."""

    def __init__(self, fail_until: int) -> None:
        super().__init__(transport="usb", states=[_mk_state()])
        self._fail_until = fail_until
        self._calls = 0

    def connect(self) -> None:
        self._calls += 1
        if self._calls <= self._fail_until:
            # Mimetiza pydualsense quando hardware está ausente. Backend real
            # trataria isso como offline-OK; aqui o FakeController não tem
            # essa lógica, então testamos via asserções direto na task.
            self._connected = False
            return
        super().connect()


@pytest.mark.asyncio
async def test_run_inicia_ipc_antes_de_conectar(monkeypatch) -> None:
    """Subsystems sobem mesmo quando o controle não conecta — `_start_ipc` é
    chamado antes do daemon esperar por hardware.

    O teste evita levantar um IpcServer real (poderia colidir com socket de
    produção, A-01) e monkeypatcha `_start_ipc` para registrar timestamps,
    confirmando que ele foi invocado antes do reconnect_loop entrar em sleep.
    """
    fc = _OfflineThenOnlineController(fail_until=999)  # nunca conecta
    bus = EventBus()

    ipc_started: list[bool] = []

    async def _fake_start_ipc(self):  # type: ignore[no-untyped-def]
        ipc_started.append(True)
        # Sentinela truthy — confirma que o atributo foi populado.
        self._ipc_server = object()

    monkeypatch.setattr(Daemon, "_start_ipc", _fake_start_ipc, raising=True)

    daemon = Daemon(
        controller=fc,
        bus=bus,
        config=DaemonConfig(
            poll_hz=120,
            auto_reconnect=False,
            ipc_enabled=True,
            udp_enabled=False,
            autoswitch_enabled=False,
            keyboard_emulation_enabled=False,
            mic_button_toggles_system=False,
        ),
    )

    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.15)
    try:
        assert ipc_started, "_start_ipc não foi chamado em ≤150ms"
        assert daemon._ipc_server is not None
        assert fc.is_connected() is False
    finally:
        daemon.stop()
        await asyncio.wait_for(run_task, timeout=2.0)


@pytest.mark.asyncio
async def test_reconnect_loop_publica_controller_connected_em_transicao(
    tmp_path, monkeypatch
) -> None:
    """reconnect_loop emite CONTROLLER_CONNECTED quando hardware aparece
    depois do boot offline."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))

    # O reconnect_loop só publica connected na transição. Como temos uma
    # primeira chamada de connect no run(), forçamos `fail_until=1` para
    # que a primeira tentativa NÃO conecte; depois o probe loop reconecta.
    fc = _OfflineThenOnlineController(fail_until=1)
    bus = EventBus()

    # Encurta intervalo do probe para não atrasar o teste.
    import hefesto_dualsense4unix.daemon.connection as conn_mod

    monkeypatch.setattr(conn_mod, "RECONNECT_PROBE_INTERVAL_SEC", 0.05)

    queue = bus.subscribe(EventTopic.CONTROLLER_CONNECTED)
    daemon = Daemon(
        controller=fc,
        bus=bus,
        config=DaemonConfig(
            poll_hz=120,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            keyboard_emulation_enabled=False,
            mic_button_toggles_system=False,
        ),
    )

    run_task = asyncio.create_task(daemon.run())
    payload = await asyncio.wait_for(queue.get(), timeout=2.0)
    assert payload == {"transport": "usb"}
    daemon.stop()
    await asyncio.wait_for(run_task, timeout=2.0)


@pytest.mark.asyncio
async def test_reconnect_loop_respeita_stop_event(tmp_path, monkeypatch) -> None:
    """_stop_event sinalizado durante o sleep do probe finaliza a task em ≤500ms."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))

    # Probe interval longo: sem cooperar com stop_event, a task ficaria horas dormindo.
    import hefesto_dualsense4unix.daemon.connection as conn_mod

    monkeypatch.setattr(conn_mod, "RECONNECT_PROBE_INTERVAL_SEC", 30.0)
    monkeypatch.setattr(conn_mod, "RECONNECT_ONLINE_CHECK_INTERVAL_SEC", 30.0)

    fc = _OfflineThenOnlineController(fail_until=999)
    bus = EventBus()
    daemon = Daemon(
        controller=fc,
        bus=bus,
        config=DaemonConfig(
            poll_hz=120,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            keyboard_emulation_enabled=False,
            mic_button_toggles_system=False,
        ),
    )

    run_task = asyncio.create_task(daemon.run())
    # Da tempo do reconnect_loop entrar no primeiro sleep de 30s.
    await asyncio.sleep(0.2)

    daemon.stop()
    # Apesar do timeout de 30s no probe, _stop_event deve cortar em <0.5s.
    await asyncio.wait_for(run_task, timeout=0.7)
