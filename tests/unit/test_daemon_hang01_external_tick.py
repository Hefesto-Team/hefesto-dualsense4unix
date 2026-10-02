"""HANG-01 (Sprint 2026-07-19) — o poll loop nunca mais morre por um tick"""
from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon import lifecycle as lifecycle_mod
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.testing import FakeController


async def _aguardar_condicao(
    predicate: Callable[[], bool], *, timeout: float = 5.0, passo: float = 0.02
) -> bool:
    """Poll leve até `predicate()` ficar True ou `timeout` esgotar."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(passo)
    return predicate()


def _daemon_hermetico() -> Daemon:
    """Daemon mínimo com os 2 executores reais (p/ `_run_blocking` e"""
    daemon = Daemon(
        controller=FakeController(transport="usb"),
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
    )
    daemon._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="test-hid")
    daemon._external_executor = ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="test-ext"
    )
    return daemon


class _FakeSyncTravado:
    """`tick()` bloqueia no `threading.Event` até alguém liberar — simula a"""

    def __init__(self, gate: threading.Event) -> None:
        self._gate = gate
        self.chamadas = 0

    def tick(self) -> None:
        self.chamadas += 1
        self._gate.wait(timeout=5.0)


async def test_schedule_nunca_aguarda_tick_travado_e_pula_com_guard_de_reentrancia() -> None:
    """FALHA-SEM: o `await self._sync_external_leds()` inline do HEAD 27b51d5"""
    gate = threading.Event()
    daemon = _daemon_hermetico()
    fake_sync = _FakeSyncTravado(gate)
    daemon._external_led_sync = fake_sync

    try:
        for _ in range(3):
            daemon._schedule_external_tick()
            await asyncio.sleep(0)

        assert fake_sync.chamadas == 1, (
            "só o 1º ciclo deveria ter disparado o tick de verdade"
        )
        assert daemon._external_tick_skipped == 2, (
            "os 2 ciclos seguintes deveriam ter pulado (task anterior pendente)"
        )
        task = daemon._external_tick_task
        assert task is not None and not task.done()
    finally:
        gate.set()
        task = daemon._external_tick_task
        if task is not None:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(task, timeout=2.0)
        daemon._executor.shutdown(wait=True)  # type: ignore[union-attr]
        daemon._external_executor.shutdown(wait=True)  # type: ignore[union-attr]


async def test_dois_timeouts_consecutivos_degradam_e_travam_o_agendamento(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2 timeouts seguidos (`EXTERNAL_TICK_TIMEOUT_SEC` encurtado p/ o teste)"""
    monkeypatch.setattr(lifecycle_mod, "EXTERNAL_TICK_TIMEOUT_SEC", 0.05)
    spy = MagicMock()
    monkeypatch.setattr(lifecycle_mod, "logger", spy)

    gate = threading.Event()
    daemon = _daemon_hermetico()
    daemon._external_led_sync = _FakeSyncTravado(gate)

    try:
        daemon._schedule_external_tick()
        await asyncio.sleep(0.2)
        assert daemon._external_tick_timeouts == 1
        assert daemon._external_tick_degraded is False
        warn_events = [c.args[0] for c in spy.warning.call_args_list]
        assert "external_tick_pendurado" in warn_events

        daemon._schedule_external_tick()
        await asyncio.sleep(0.2)
        assert daemon._external_tick_timeouts == 2
        assert daemon._external_tick_degraded is True
        error_events = [c.args[0] for c in spy.error.call_args_list]
        assert "external_tick_pendurado" in error_events
        info_events = [c.args[0] for c in spy.info.call_args_list]
        assert "external_tick_degradado" in info_events

        task_antes = daemon._external_tick_task
        daemon._schedule_external_tick()
        await asyncio.sleep(0.05)
        assert daemon._external_tick_task is task_antes, (
            "degradado não pode agendar discover de novo sozinho"
        )
        assert daemon._external_tick_watch is not None

        monkeypatch.setattr(daemon._external_tick_watch, "poll", lambda: True)
        daemon._schedule_external_tick()
        assert daemon._external_tick_degraded is False
        assert daemon._external_tick_timeouts == 0
        recovered_events = [c.args[0] for c in spy.info.call_args_list]
        assert "external_tick_recuperado" in recovered_events
    finally:
        gate.set()
        daemon._executor.shutdown(wait=True)  # type: ignore[union-attr]
        daemon._external_executor.shutdown(wait=True)  # type: ignore[union-attr]


async def test_tick_que_termina_a_tempo_zera_o_contador_de_timeouts() -> None:
    """Um tick saudável (não trava) zera `_external_tick_timeouts` — o"""
    daemon = _daemon_hermetico()
    daemon._external_tick_timeouts = 1

    calls: list[int] = []

    class _FakeSyncOk:
        def tick(self) -> None:
            calls.append(1)

    daemon._external_led_sync = _FakeSyncOk()
    try:
        daemon._schedule_external_tick()
        task = daemon._external_tick_task
        assert task is not None
        await asyncio.wait_for(task, timeout=2.0)
        assert calls == [1]
        assert daemon._external_tick_timeouts == 0
    finally:
        daemon._executor.shutdown(wait=True)  # type: ignore[union-attr]
        daemon._external_executor.shutdown(wait=True)  # type: ignore[union-attr]


async def test_poll_loop_de_verdade_sobrevive_ao_tick_de_externos_pendurado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integração fim-a-fim com `Daemon.run()`: o tick de externos trava para"""
    from hefesto_dualsense4unix.core.controller import ControllerState

    monkeypatch.setattr(lifecycle_mod, "EXTERNAL_TICK_TIMEOUT_SEC", 0.3)
    gate = threading.Event()

    class _FakeSyncTravadoParaSempre:
        def tick(self) -> None:
            gate.wait()

    states = [
        ControllerState(
            battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
        for _ in range(2000)
    ]
    daemon = Daemon(
        controller=FakeController(transport="usb", states=states),
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
    try:
        await asyncio.sleep(0.05)
        daemon._external_led_sync = _FakeSyncTravadoParaSempre()

        ticks_antes = daemon.store.counter("poll.tick")
        estourou = await _aguardar_condicao(
            lambda: daemon._external_tick_timeouts >= 1, timeout=6.0
        )
        assert estourou, (
            "o tick preso deveria ter estourado o timeout ao menos 1x em 6s"
        )
        ticks_depois = daemon.store.counter("poll.tick")

        assert ticks_depois - ticks_antes > 50, (
            "poll loop parou de ticar — o tick de externos travado voltou a "
            "pendurar a corrotina inteira (regressão do HANG-01)"
        )
    finally:
        gate.set()
        daemon.stop()
        await run_task


async def test_pool_do_tick_de_externos_e_isolado_do_pool_do_poll_loop() -> None:
    """Regressão do achado pós-auditoria (20/07): a 1ª versão do HANG-01"""
    daemon = Daemon(
        controller=FakeController(transport="usb"),
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
    )
    run_task = asyncio.create_task(daemon.run())
    try:
        await asyncio.sleep(0.05)
        assert daemon._executor is not None
        assert daemon._external_executor is not None
        assert daemon._executor is not daemon._external_executor, (
            "o tick de externos NÃO PODE reusar o pool de que read_state "
            "depende — reintroduziria o esgotamento do achado pós-auditoria"
        )
    finally:
        daemon.stop()
        await run_task


async def test_dois_timeouts_consecutivos_do_tick_nao_penduram_read_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integração fim-a-fim: PIOR CASO do achado pós-auditoria — os 2"""
    from hefesto_dualsense4unix.core.controller import ControllerState

    monkeypatch.setattr(lifecycle_mod, "EXTERNAL_TICK_TIMEOUT_SEC", 0.1)
    gate = threading.Event()

    class _FakeSyncTravadoParaSempre:
        def tick(self) -> None:
            gate.wait()

    states = [
        ControllerState(
            battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
        for _ in range(4000)
    ]
    daemon = Daemon(
        controller=FakeController(transport="usb", states=states),
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
    try:
        await asyncio.sleep(0.05)
        daemon._external_led_sync = _FakeSyncTravadoParaSempre()

        ticks_antes = daemon.store.counter("poll.tick")
        degradou = await _aguardar_condicao(
            lambda: daemon._external_tick_degraded, timeout=10.0
        )
        assert degradou, (
            "não atravessou os 2 timeouts CONSECUTIVOS + degradação em 10s "
            "— é essa sequência que esgotava o pool compartilhado no achado"
        )
        assert daemon._external_tick_timeouts >= 2
        ticks_depois = daemon.store.counter("poll.tick")

        assert ticks_depois - ticks_antes > 200, (
            "poll loop pendurou mesmo com os 2 pools isolados — regressão "
            "do achado pós-auditoria (esgotamento do pool compartilhado com "
            "read_state)"
        )
    finally:
        gate.set()
        daemon.stop()
        await run_task


def test_schedule_e_noop_sem_fiacao_dos_externos() -> None:
    """Sem `_external_led_sync` (backend fake/hermético), agendar é no-op —"""
    daemon = Daemon(
        controller=FakeController(transport="usb"),
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
    )
    assert daemon._external_led_sync is None
    daemon._schedule_external_tick()
    assert daemon._external_tick_task is None
