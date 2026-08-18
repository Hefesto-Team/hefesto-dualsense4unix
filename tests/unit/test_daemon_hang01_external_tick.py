"""HANG-01 (Sprint 2026-07-19) — o poll loop nunca mais morre por um tick
pendurado do LED dos externos.

Contexto: `ExternalLedSync.tick()` enumera TODO /dev/input; numa "debandada"
(mass-unplug) uma thread do pool `hefesto-hid` pode travar de vez (wedge de
GIL sob churn extremo, medido ao vivo 19/07 16:08 — 10 min de silêncio total
do daemon, PID 2835). Antes deste sprint o poll loop fazia
`await self._sync_external_leds()` INLINE — um tick preso suspendia a
corrotina do poll loop PARA SEMPRE (zero read_state, zero logs, zero
watchdog). Estes testes provam, sem depender de `Daemon.run()` inteiro nem de
sleeps de produção, que:

1. `_schedule_external_tick()` NUNCA aguarda o tick — chamá-lo repetidas
   vezes com o `tick()` travado (um `threading.Event` nunca setado) não
   trava o TESTE (o "poll loop" simulado completa ≥3 ciclos seguidos); o
   guard de reentrância pula o agendamento enquanto a task anterior está
   pendente, só contando (`_external_tick_skipped`).
2. 2 timeouts CONSECUTIVOS de `_sync_external_leds` degradam
   (`_external_tick_degraded=True`, log `external_tick_degradado`) e
   `_schedule_external_tick` para de agendar `discover` até um
   `InputDirWatch.poll()` simulado reportar mudança em /dev/input.
"""
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
    """Poll leve até `predicate()` ficar True ou `timeout` esgotar.

    Correção pós-auditoria (20/07): os testes de integração fim-a-fim deste
    arquivo usavam `sleep` de duração FIXA quase coincidente com a fronteira
    dos ~2s do reagendamento do tick lento (`external_led_next_at` em
    `_poll_loop`) — flakey por construção (a 1ª chamada real do fake só
    ocorre no reagendamento seguinte, não na atribuição do teste). Este
    helper espera a CONDIÇÃO de verdade em vez de uma janela de tempo
    adivinhada, tolerando o jitter do scheduler/ambiente sem alongar o pior
    caso (`timeout` é só um teto de segurança)."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(passo)
    return predicate()


def _daemon_hermetico() -> Daemon:
    """Daemon mínimo com os 2 executores reais (p/ `_run_blocking` e
    `_run_external_blocking`) e sem subsistemas.

    Correção pós-auditoria (20/07): o tick de externos passou a rodar no
    pool DEDICADO `_external_executor` — isolado de `_executor` — então o
    helper precisa dos dois para os testes exercitarem o código real (senão
    `_run_external_blocking` esbarraria no `assert ... não inicializado`).
    """
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
    """`tick()` bloqueia no `threading.Event` até alguém liberar — simula a
    debandada travando a thread do pool."""

    def __init__(self, gate: threading.Event) -> None:
        self._gate = gate
        self.chamadas = 0

    def tick(self) -> None:
        self.chamadas += 1
        self._gate.wait(timeout=5.0)


async def test_schedule_nunca_aguarda_tick_travado_e_pula_com_guard_de_reentrancia() -> None:
    """FALHA-SEM: o `await self._sync_external_leds()` inline do HEAD 27b51d5
    travaria este teste no 1º ciclo (o `tick()` só retorna quando `gate` é
    liberado). PASSA-COM: `_schedule_external_tick()` retorna na hora nos 3
    ciclos; só 1 task de verdade é criada — as outras 2 pulam (reentrância)."""
    gate = threading.Event()
    daemon = _daemon_hermetico()
    fake_sync = _FakeSyncTravado(gate)
    daemon._external_led_sync = fake_sync

    try:
        # Simula 3 ciclos SEGUIDOS do poll loop (~2s de produção cada) com o
        # tick anterior ainda pendurado — nenhuma chamada aqui bloqueia.
        for _ in range(3):
            daemon._schedule_external_tick()
            await asyncio.sleep(0)  # cede ao loop p/ a task começar a rodar

        assert fake_sync.chamadas == 1, (
            "só o 1º ciclo deveria ter disparado o tick de verdade"
        )
        assert daemon._external_tick_skipped == 2, (
            "os 2 ciclos seguintes deveriam ter pulado (task anterior pendente)"
        )
        task = daemon._external_tick_task
        assert task is not None and not task.done()
    finally:
        gate.set()  # libera a thread presa antes de encerrar o executor
        task = daemon._external_tick_task
        if task is not None:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(task, timeout=2.0)
        daemon._executor.shutdown(wait=True)  # type: ignore[union-attr]
        daemon._external_executor.shutdown(wait=True)  # type: ignore[union-attr]


async def test_dois_timeouts_consecutivos_degradam_e_travam_o_agendamento(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2 timeouts seguidos (`EXTERNAL_TICK_TIMEOUT_SEC` encurtado p/ o teste)
    disparam `external_tick_degradado` e `_schedule_external_tick` para de
    criar tasks novas — até um `InputDirWatch.poll()` (mockado) reportar
    mudança real em /dev/input, quando destrava e zera o contador."""
    monkeypatch.setattr(lifecycle_mod, "EXTERNAL_TICK_TIMEOUT_SEC", 0.05)
    spy = MagicMock()
    monkeypatch.setattr(lifecycle_mod, "logger", spy)

    gate = threading.Event()  # nunca liberado — todo tick estoura o timeout
    daemon = _daemon_hermetico()
    daemon._external_led_sync = _FakeSyncTravado(gate)

    try:
        # 1º ciclo: agenda, espera o timeout curto estourar -> WARNING.
        daemon._schedule_external_tick()
        await asyncio.sleep(0.2)
        assert daemon._external_tick_timeouts == 1
        assert daemon._external_tick_degraded is False
        warn_events = [c.args[0] for c in spy.warning.call_args_list]
        assert "external_tick_pendurado" in warn_events

        # 2º ciclo: 2º timeout CONSECUTIVO -> ERROR + degrada.
        daemon._schedule_external_tick()
        await asyncio.sleep(0.2)
        assert daemon._external_tick_timeouts == 2
        assert daemon._external_tick_degraded is True
        error_events = [c.args[0] for c in spy.error.call_args_list]
        assert "external_tick_pendurado" in error_events
        info_events = [c.args[0] for c in spy.info.call_args_list]
        assert "external_tick_degradado" in info_events

        # 3º ciclo: degradado -> NENHUMA task nova é criada.
        task_antes = daemon._external_tick_task
        daemon._schedule_external_tick()
        await asyncio.sleep(0.05)
        assert daemon._external_tick_task is task_antes, (
            "degradado não pode agendar discover de novo sozinho"
        )
        assert daemon._external_tick_watch is not None

        # Hotplug simulado: InputDirWatch observa mudança -> destrava.
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
    """Um tick saudável (não trava) zera `_external_tick_timeouts` — o
    contador é de timeouts CONSECUTIVOS, não cumulativo."""
    daemon = _daemon_hermetico()
    daemon._external_tick_timeouts = 1  # simula 1 timeout anterior

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
    """Integração fim-a-fim com `Daemon.run()`: o tick de externos trava para
    sempre (gate nunca liberado) e o poll loop, mesmo assim, segue lendo
    `read_state`/publicando `poll.tick` através da fronteira dos ~2s em que o
    HEAD 27b51d5 teria suspendido a corrotina inteira (mecanismo do incidente
    de 16:08). `EXTERNAL_TICK_TIMEOUT_SEC` encurtado só para o teste terminar
    rápido — a lógica exercitada é a mesma do valor de produção (10s).
    Espera por CONDIÇÃO (`_aguardar_condicao`), não por `sleep` de janela
    fixa (achado pós-auditoria: a janela fixa original ficava quase
    coincidente com a fronteira do reagendamento e podia falhar por 1
    ciclo de jitter do scheduler)."""
    from hefesto_dualsense4unix.core.controller import ControllerState

    monkeypatch.setattr(lifecycle_mod, "EXTERNAL_TICK_TIMEOUT_SEC", 0.3)
    gate = threading.Event()  # nunca liberado nesta vida

    class _FakeSyncTravadoParaSempre:
        def tick(self) -> None:
            gate.wait()  # bloqueia até o teste liberar, no finally

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
        await asyncio.sleep(0.05)  # deixa o run() subir e conectar
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
    """Regressão do achado pós-auditoria (20/07): a 1ª versão do HANG-01
    rodava `sync.tick` no MESMO `self._executor` ("hefesto-hid", 2 workers)
    de que `read_state`/`_gather_game_signal_inputs`/o watchdog evdev
    dependem — 2 timeouts CONSECUTIVOS do tick esgotavam os 2 workers do
    MESMO pool, reproduzindo o hang original de forma adiada. FALHA-SEM: no
    código anterior `_external_executor` nem existe (AttributeError) e o
    tick usaria `self._executor` — este teste falharia por identidade
    (mesmo objeto) ou por atributo ausente. PASSA-COM: `Daemon.run()` cria 2
    `ThreadPoolExecutor` DISTINTOS — um pro poll loop, outro EXCLUSIVO do
    tick de externos."""
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
    """Integração fim-a-fim: PIOR CASO do achado pós-auditoria — os 2
    timeouts CONSECUTIVOS do tick de externos (que degradam o inventário)
    acontecem com o `tick()` travado PARA SEMPRE (gate nunca liberado, cada
    timeout vaza 1 worker). Na versão com pool COMPARTILHADO isso esgotava
    os 2 workers do `self._executor` e suspendia `read_state` para sempre a
    partir daí (o hang original, só que adiado ~2x `EXTERNAL_TICK_TIMEOUT_
    SEC`). Com o pool DEDICADO, `poll.tick` segue avançando através da
    janela inteira — 1º timeout, reagendamento (~2s depois) e 2º timeout
    consecutivo com degradação."""
    from hefesto_dualsense4unix.core.controller import ControllerState

    monkeypatch.setattr(lifecycle_mod, "EXTERNAL_TICK_TIMEOUT_SEC", 0.1)
    gate = threading.Event()  # nunca liberado — os 2 ticks travam pra sempre

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
        await asyncio.sleep(0.05)  # deixa o run() subir e conectar
        daemon._external_led_sync = _FakeSyncTravadoParaSempre()

        ticks_antes = daemon.store.counter("poll.tick")
        # Atravessa os 2 reagendamentos (~2s fixos, ver `_poll_loop`) até a
        # degradação — o pior caso do achado, com os 2 timeouts CONSECUTIVOS
        # vazando 1 worker cada do pool `hefesto-ext`. Espera por CONDIÇÃO
        # (não por janela fixa) — teto de segurança generoso (10s) porque a
        # sequência real leva ~2x (2.0 + EXTERNAL_TICK_TIMEOUT_SEC).
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
    """Sem `_external_led_sync` (backend fake/hermético), agendar é no-op —
    nenhuma task, nenhum executor tocado (paridade com o HEAD)."""
    daemon = Daemon(
        controller=FakeController(transport="usb"),
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
    )
    assert daemon._external_led_sync is None
    daemon._schedule_external_tick()
    assert daemon._external_tick_task is None
