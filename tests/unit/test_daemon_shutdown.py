"""Testes isolados para `daemon.connection.shutdown` (DAEMON-SHUTDOWN-TEST-01)."""
from __future__ import annotations

import asyncio

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.connection import shutdown
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.testing.fake_controller import FakeController


def _mk_state() -> ControllerState:
    return ControllerState(
        battery_pct=80,
        l2_raw=0,
        r2_raw=0,
        connected=True,
        transport="usb",
    )


def _mk_daemon(*, ipc_enabled: bool = True) -> Daemon:
    fc = FakeController(transport="usb", states=[_mk_state()])
    return Daemon(
        controller=fc,
        bus=EventBus(),
        config=DaemonConfig(
            poll_hz=120,
            auto_reconnect=False,
            ipc_enabled=ipc_enabled,
            udp_enabled=False,
            autoswitch_enabled=False,
            mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
            mic_button_toggles_system=False,
            plugins_enabled=False,
        ),
    )


async def _let_subsystems_boot(daemon: Daemon, *, timeout: float = 1.0) -> None:
    """Espera o `run()` popular pelo menos as tasks de poll e (se habilitado) o IPC."""
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if daemon._tasks and (
            not daemon.config.ipc_enabled or daemon._ipc_server is not None
        ):
            return
        await asyncio.sleep(0.02)


@pytest.mark.asyncio
async def test_shutdown_zera_subsystems_e_tasks(tmp_path_factory, monkeypatch) -> None:
    """`shutdown` deve liberar IPC, executor e cancelar tasks pendentes."""
    short_runtime = tmp_path_factory.mktemp("hsd", numbered=True)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(short_runtime))
    daemon = _mk_daemon(ipc_enabled=True)

    run_task = asyncio.create_task(daemon.run())
    try:
        await _let_subsystems_boot(daemon)
        assert daemon._ipc_server is not None, "IPC não subiu em tempo hábil"
        assert daemon._executor is not None
        assert daemon._tasks, "_tasks vazio antes do shutdown"

        await shutdown(daemon)

        assert daemon._ipc_server is None
        assert daemon._udp_server is None
        assert daemon._autoswitch is None
        assert daemon._mouse_device is None
        assert daemon._keyboard_device is None
        assert daemon._executor is None
        assert daemon._tasks == []
        assert daemon._reconnect_task is None
        assert daemon._last_state is None
    finally:
        daemon.stop()
        import contextlib as _ctx

        with _ctx.suppress(asyncio.CancelledError, asyncio.TimeoutError):
            await asyncio.wait_for(run_task, timeout=2.0)


@pytest.mark.asyncio
async def test_shutdown_tolera_subsystem_que_falha_no_stop(
    tmp_path, monkeypatch
) -> None:
    """Erro em `.stop()` de um subsystem não impede a limpeza dos demais."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    daemon = _mk_daemon(ipc_enabled=False)

    class _ExplodingDevice:
        stopped = False

        def stop(self) -> None:
            type(self).stopped = True
            raise RuntimeError("simulado: falha no stop()")

    daemon._mouse_device = _ExplodingDevice()
    from concurrent.futures import ThreadPoolExecutor

    daemon._executor = ThreadPoolExecutor(max_workers=1)

    await shutdown(daemon)

    assert _ExplodingDevice.stopped is True, "stop() do device foi chamado"
    assert daemon._mouse_device is None, "ref do device foi zerada mesmo após erro"
    assert daemon._executor is None
    assert daemon._tasks == []


@pytest.mark.asyncio
async def test_shutdown_eh_idempotente(tmp_path, monkeypatch) -> None:
    """Chamar `shutdown` 2x não levanta — segunda chamada vê tudo zerado."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    daemon = _mk_daemon(ipc_enabled=False)

    await shutdown(daemon)
    await shutdown(daemon)

    assert daemon._executor is None
    assert daemon._tasks == []
    assert daemon._ipc_server is None


@pytest.mark.asyncio
async def test_shutdown_nao_fica_preso_na_tarefa_que_engole_o_cancelamento(
    tmp_path, monkeypatch
) -> None:
    """Uma tarefa que engole o primeiro cancelamento não prende o ``shutdown``."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    daemon = _mk_daemon(ipc_enabled=False)
    cancelamentos: list[int] = []

    async def _engole_o_primeiro() -> None:
        while True:
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                cancelamentos.append(1)
                if len(cancelamentos) >= 2:
                    raise

    tarefa = asyncio.create_task(_engole_o_primeiro())
    await asyncio.sleep(0)
    daemon._tasks.append(tarefa)

    await asyncio.wait_for(shutdown(daemon), timeout=5.0)

    assert tarefa.done()
    assert len(cancelamentos) >= 2, "o shutdown não cancelou de novo"
    assert daemon._tasks == []


@pytest.mark.asyncio
async def test_shutdown_segue_depois_do_teto_da_tarefa_que_nunca_cai(
    tmp_path, monkeypatch
) -> None:
    """A tarefa que engole todo cancelamento fica para trás, e o ``shutdown`` volta."""
    from hefesto_dualsense4unix.daemon import connection

    monkeypatch.setattr(connection, "_TETO_DA_TAREFA_S", 0.6)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    daemon = _mk_daemon(ipc_enabled=False)
    solta = asyncio.Event()

    async def _nunca_cai() -> None:
        while not solta.is_set():
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                continue

    tarefa = asyncio.create_task(_nunca_cai())
    await asyncio.sleep(0)
    daemon._tasks.append(tarefa)
    try:
        await asyncio.wait_for(shutdown(daemon), timeout=5.0)
        assert not tarefa.done()
        assert daemon._tasks == []
    finally:
        solta.set()
        tarefa.cancel()
        await asyncio.wait({tarefa}, timeout=1.0)
