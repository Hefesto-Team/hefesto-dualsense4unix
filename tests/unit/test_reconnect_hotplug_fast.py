"""Reconciliação rápida de hotplug no reconnect_loop (FEAT-BACKEND-HOTPLUG-FAST-01).

Cobre, com um fake do `InputDirWatch` (hermético — nada de /dev/input real):

- mudança em /dev/input antecipa o `controller.connect()` de reconciliação
  (em fatias de `RECONNECT_HOTPLUG_POLL_INTERVAL_SEC`) em vez de esperar o
  fallback de 30s;
- SEM mudança, nenhum connect() extra acontece dentro da janela online —
  mas o watch É consultado (custo ~µs por fatia);
- a primeira leitura do watch é baseline (o `poll()` inicial devolve True por
  construção e NÃO deve disparar reconciliação);
- o fallback periódico (`RECONNECT_ONLINE_CHECK_INTERVAL_SEC`) segue vivo.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

import hefesto_dualsense4unix.daemon.connection as conn_mod
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.connection import reconnect_loop


class _CountingController:
    """Controller sempre online que conta as chamadas de connect()."""

    def __init__(self) -> None:
        self.connect_calls = 0

    def connect(self) -> None:
        self.connect_calls += 1

    def is_connected(self) -> bool:
        return True

    def get_transport(self) -> str:
        return "usb"


class _FakeWatch:
    """Dublê do InputDirWatch: `trip()` simula uma mudança em /dev/input.

    Como no real, `poll()` consome a mudança (duas leituras seguidas não
    devolvem True para o mesmo evento).
    """

    def __init__(self) -> None:
        self._changed = False
        self.polls = 0

    def trip(self) -> None:
        self._changed = True

    def poll(self) -> bool:
        self.polls += 1
        changed = self._changed
        self._changed = False
        return changed


class _StubDaemon:
    """Superfície mínima do DaemonProtocol que o reconnect_loop toca."""

    def __init__(self, controller: _CountingController) -> None:
        self.controller = controller
        self.bus = EventBus()
        self.config = SimpleNamespace(reconnect_backoff_sec=0.01, auto_reconnect=True)
        self._stop_event = asyncio.Event()

    def _is_stopping(self) -> bool:
        return self._stop_event.is_set()

    async def _run_blocking(self, fn: Callable[..., Any], *args: Any) -> Any:
        return fn(*args)

    def _arm_input_grace(self) -> None:
        pass

    def stop(self) -> None:
        self._stop_event.set()


async def _until(cond: Callable[[], bool], timeout: float = 2.0) -> None:
    """Espera `cond()` virar True (poll de 5ms) ou falha após `timeout`."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not cond():
        if loop.time() > deadline:
            raise AssertionError("condição não alcançada dentro do prazo")
        await asyncio.sleep(0.005)


def _fast_slices(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fatia de hotplug curta + fallback online longe (isola o gatilho)."""
    monkeypatch.setattr(conn_mod, "RECONNECT_HOTPLUG_POLL_INTERVAL_SEC", 0.01)
    monkeypatch.setattr(conn_mod, "RECONNECT_ONLINE_CHECK_INTERVAL_SEC", 30.0)


@pytest.mark.asyncio
async def test_mudanca_no_dir_antecipa_reconciliacao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Watch acusou mudança → connect() (reconciliação) roda em ~1 fatia,
    sem esperar o fallback de 30s."""
    _fast_slices(monkeypatch)
    ctrl = _CountingController()
    daemon = _StubDaemon(ctrl)
    watch = _FakeWatch()

    task = asyncio.create_task(reconnect_loop(daemon, input_watch=watch))
    try:
        await _until(lambda: ctrl.connect_calls >= 1)
        base = ctrl.connect_calls
        watch.trip()
        await _until(lambda: ctrl.connect_calls > base)
        # UMA reconciliação por mudança — o evento foi consumido pelo poll().
        assert ctrl.connect_calls == base + 1
    finally:
        daemon.stop()
        await asyncio.wait_for(task, timeout=1.0)


@pytest.mark.asyncio
async def test_sem_mudanca_nao_reconcilia(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem mudança em /dev/input, nenhum connect() extra dentro da janela
    online — mas o watch é consultado a cada fatia (sinal barato ativo)."""
    _fast_slices(monkeypatch)
    ctrl = _CountingController()
    daemon = _StubDaemon(ctrl)
    watch = _FakeWatch()

    task = asyncio.create_task(reconnect_loop(daemon, input_watch=watch))
    try:
        await asyncio.sleep(0.15)
        assert ctrl.connect_calls == 1  # só o probe inicial da iteração 1
        assert watch.polls >= 2  # baseline + fatias — o watch FOI sondado
    finally:
        daemon.stop()
        await asyncio.wait_for(task, timeout=1.0)


@pytest.mark.asyncio
async def test_primeira_leitura_do_watch_e_baseline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O InputDirWatch real devolve True no 1º poll() (sem snapshot anterior).

    O reconnect_loop consome essa leitura como baseline — ela NÃO pode contar
    como hotplug (o connect() do boot já cobriu o estado inicial).
    """
    _fast_slices(monkeypatch)
    ctrl = _CountingController()
    daemon = _StubDaemon(ctrl)
    watch = _FakeWatch()
    watch.trip()  # 1ª leitura devolverá True, como no watch real recém-criado

    task = asyncio.create_task(reconnect_loop(daemon, input_watch=watch))
    try:
        await asyncio.sleep(0.15)
        assert ctrl.connect_calls == 1  # nenhuma reconciliação antecipada
    finally:
        daemon.stop()
        await asyncio.wait_for(task, timeout=1.0)


@pytest.mark.asyncio
async def test_fallback_periodico_segue_vivo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mesmo sem NENHUMA mudança no watch, o check periódico online continua
    reconciliando (fallback de RECONNECT_ONLINE_CHECK_INTERVAL_SEC)."""
    monkeypatch.setattr(conn_mod, "RECONNECT_HOTPLUG_POLL_INTERVAL_SEC", 0.01)
    monkeypatch.setattr(conn_mod, "RECONNECT_ONLINE_CHECK_INTERVAL_SEC", 0.03)
    ctrl = _CountingController()
    daemon = _StubDaemon(ctrl)
    watch = _FakeWatch()

    task = asyncio.create_task(reconnect_loop(daemon, input_watch=watch))
    try:
        await _until(lambda: ctrl.connect_calls >= 3)
    finally:
        daemon.stop()
        await asyncio.wait_for(task, timeout=1.0)
