"""Testes do reconnect_loop não-bloqueante (BUG-DAEMON-NO-DEVICE-FATAL-01)."""
from __future__ import annotations

import asyncio
import threading

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
    """FakeController cujo connect() falha com "No device detected" nas"""

    def __init__(self, fail_until: int) -> None:
        super().__init__(transport="usb", states=[_mk_state()])
        self._fail_until = fail_until
        self._calls = 0

    def connect(self) -> None:
        self._calls += 1
        if self._calls <= self._fail_until:
            self._connected = False
            return
        super().connect()


@pytest.mark.asyncio
async def test_run_inicia_ipc_antes_de_conectar(monkeypatch) -> None:
    """Subsystems sobem mesmo quando o controle não conecta — `_start_ipc` é"""
    fc = _OfflineThenOnlineController(fail_until=999)
    bus = EventBus()

    ipc_started: list[bool] = []

    async def _fake_start_ipc(self):  # type: ignore[no-untyped-def]
        ipc_started.append(True)
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
    """reconnect_loop emite CONTROLLER_CONNECTED quando hardware aparece"""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))

    fc = _OfflineThenOnlineController(fail_until=1)
    bus = EventBus()

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


class _DepthLock:
    """RLock instrumentado: expõe a profundidade de aquisição vigente."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.depth = 0

    def __enter__(self) -> _DepthLock:
        self._lock.acquire()
        self.depth += 1
        return self

    def __exit__(self, *exc: object) -> None:
        self.depth -= 1
        self._lock.release()


def _config() -> DaemonConfig:
    """Config hermética padrão destes testes (sem IPC/UDP/autoswitch)."""
    return DaemonConfig(
        poll_hz=120,
        auto_reconnect=False,
        ipc_enabled=False,
        udp_enabled=False,
        autoswitch_enabled=False,
        keyboard_emulation_enabled=False,
        mic_button_toggles_system=False,
    )


def _intercepta_upgrade(
    monkeypatch: pytest.MonkeyPatch, lock: _DepthLock
) -> list[dict[str, object]]:
    """Troca `upgrade_primary_vpad_to_uhid` por um espião que registra a"""
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    chamadas: list[dict[str, object]] = []

    def _fake_upgrade(_daemon: object) -> bool:
        chamadas.append(
            {
                "thread": threading.current_thread().name,
                "lock_depth": lock.depth,
            }
        )
        return True

    monkeypatch.setattr(gp, "upgrade_primary_vpad_to_uhid", _fake_upgrade)
    return chamadas


@pytest.mark.asyncio
async def test_hotplug_tardio_promove_o_vpad_exatamente_uma_vez(
    tmp_path, monkeypatch
) -> None:
    """VPAD-01: a transição offline→online do probe chama a promoção 1x — e só"""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    import hefesto_dualsense4unix.daemon.connection as conn_mod

    monkeypatch.setattr(conn_mod, "RECONNECT_PROBE_INTERVAL_SEC", 0.05)

    lock = _DepthLock()
    chamadas = _intercepta_upgrade(monkeypatch, lock)

    fc = _OfflineThenOnlineController(fail_until=1)
    bus = EventBus()
    queue = bus.subscribe(EventTopic.CONTROLLER_CONNECTED)
    daemon = Daemon(controller=fc, bus=bus, config=_config())
    daemon._emu_lock = lock

    run_task = asyncio.create_task(daemon.run())
    try:
        await asyncio.wait_for(queue.get(), timeout=2.0)
        for _ in range(40):
            if chamadas:
                break
            await asyncio.sleep(0.05)
        assert len(chamadas) == 1, "offline→online tem que promover exatamente 1x"
        assert str(chamadas[0]["thread"]).startswith("hefesto-hid"), (
            "a promoção deve rodar via _run_blocking (executor) — síncrona no "
            "event loop ela congelaria o input por até UHID_BIND_TIMEOUT_S"
        )
        assert chamadas[0]["lock_depth"] == 1, (
            "a promoção deve segurar o _emu_lock (serializada com os toggles "
            "de emulação do IPC/GUI)"
        )
        await asyncio.sleep(0.2)
        assert len(chamadas) == 1
    finally:
        daemon.stop()
        await asyncio.wait_for(run_task, timeout=2.0)


@pytest.mark.asyncio
async def test_conectado_no_boot_so_o_gancho_do_boot_promove(
    tmp_path, monkeypatch
) -> None:
    """Já conectado no boot: quem promove é o gancho do lifecycle (síncrono,"""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    import hefesto_dualsense4unix.daemon.connection as conn_mod

    monkeypatch.setattr(conn_mod, "RECONNECT_PROBE_INTERVAL_SEC", 0.05)

    lock = _DepthLock()
    chamadas = _intercepta_upgrade(monkeypatch, lock)

    fc = _OfflineThenOnlineController(fail_until=0)
    bus = EventBus()
    queue = bus.subscribe(EventTopic.CONTROLLER_CONNECTED)
    daemon = Daemon(controller=fc, bus=bus, config=_config())
    daemon._emu_lock = lock

    run_task = asyncio.create_task(daemon.run())
    try:
        await asyncio.wait_for(queue.get(), timeout=2.0)
        await asyncio.sleep(0.3)
        assert len(chamadas) == 1, "conectado no boot = só o gancho do boot"
        assert not str(chamadas[0]["thread"]).startswith("hefesto-hid"), (
            "a chamada única deve ser a do boot (lifecycle, thread do event "
            "loop) — o reconnect_loop não viu transição nenhuma"
        )
    finally:
        daemon.stop()
        await asyncio.wait_for(run_task, timeout=2.0)


@pytest.mark.asyncio
async def test_offline_continuo_nao_promove(tmp_path, monkeypatch) -> None:
    """Sem transição não há promoção: controle nunca aparece, vpad em paz."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    import hefesto_dualsense4unix.daemon.connection as conn_mod

    monkeypatch.setattr(conn_mod, "RECONNECT_PROBE_INTERVAL_SEC", 0.05)

    lock = _DepthLock()
    chamadas = _intercepta_upgrade(monkeypatch, lock)

    fc = _OfflineThenOnlineController(fail_until=999)
    bus = EventBus()
    daemon = Daemon(controller=fc, bus=bus, config=_config())
    daemon._emu_lock = lock

    run_task = asyncio.create_task(daemon.run())
    try:
        await asyncio.sleep(0.3)
        assert chamadas == []
    finally:
        daemon.stop()
        await asyncio.wait_for(run_task, timeout=2.0)


@pytest.mark.asyncio
async def test_reconnect_loop_respeita_stop_event(tmp_path, monkeypatch) -> None:
    """_stop_event sinalizado durante o sleep do probe finaliza a task em ≤500ms."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))

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
    await asyncio.sleep(0.2)

    daemon.stop()
    await asyncio.wait_for(run_task, timeout=0.7)
