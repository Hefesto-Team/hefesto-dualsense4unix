"""RESPOSTA-QUE-CHEGA-TARDE-01 — o `ok` não espera a consequência."""
from __future__ import annotations

import asyncio
import threading
import time

import pytest

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

PRAZO_DO_CLIENTE_S = 0.25
REPINTURA_LENTA_S = 0.6


class _Handlers(IpcHandlersMixin):
    """Só o que este teste toca."""

    def __init__(self) -> None:
        self.repintou = 0
        self.terminou_em: float | None = None

    def _repintar_apos_renumeracao(self, laco_do_daemon: object = None) -> None:
        time.sleep(REPINTURA_LENTA_S)
        self.repintou += 1
        self.terminou_em = time.monotonic()


@pytest.mark.asyncio
async def test_a_resposta_nao_espera_a_repintura() -> None:
    """Despacha e responde: o `ok` cabe no prazo do cliente."""
    h = _Handlers()
    inicio = time.monotonic()
    h._despachar_repintura("teste")
    gasto = time.monotonic() - inicio

    assert gasto < PRAZO_DO_CLIENTE_S, (
        f"despachar custou {gasto:.3f}s e o cliente espera "
        f"{PRAZO_DO_CLIENTE_S}s — a tela negaria uma troca que aconteceu")
    assert h.repintou == 0, "a repintura rodou EM LINHA; ela é consequência"

    await asyncio.sleep(REPINTURA_LENTA_S + 0.3)
    assert h.repintou == 1, "a repintura foi despachada e nunca rodou"


@pytest.mark.asyncio
async def test_a_repintura_que_falha_nao_desmente_o_ok() -> None:
    """O número trocou; uma repintura que explode não pode dizer o contrário."""

    class _Explode(_Handlers):
        def _repintar_apos_renumeracao(self, laco_do_daemon: object = None) -> None:
            self.repintou += 1
            raise RuntimeError("o rádio caiu no meio")

    h = _Explode()
    h._despachar_repintura("teste")
    await asyncio.sleep(0.2)
    assert h.repintou == 1


def test_sem_laco_de_eventos_roda_em_linha() -> None:
    """Chamada síncrona (dublês da suíte): comportamento anterior à cura."""
    h = _Handlers()
    h._despachar_repintura("teste")
    assert h.repintou == 1


class _DaemonComTiqueReal:
    """O `_schedule_external_tick` do `daemon/lifecycle.py`, no essencial."""

    def __init__(self) -> None:
        self.tiques = 0
        self.thread_do_tique: int | None = None
        self.coroutine_rodou = False
        self._external_tick_task: asyncio.Task[None] | None = None

    async def _sync_external_leds(self) -> None:
        self.coroutine_rodou = True

    def _schedule_external_tick(self) -> None:
        self.tiques += 1
        self.thread_do_tique = threading.get_ident()
        self._external_tick_task = asyncio.create_task(
            self._sync_external_leds(), name="external_led_tick"
        )


class _HandlersDeVerdade(IpcHandlersMixin):
    """Usa o `_repintar_apos_renumeracao` REAL — é ele que está sob teste."""

    def __init__(self, daemon: _DaemonComTiqueReal) -> None:
        self.daemon = daemon
        self.controller = None


@pytest.mark.asyncio
async def test_o_tique_dos_externos_e_agendado_na_thread_do_laco() -> None:
    """FALHA-SEM / PASSA-COM — a mordida é o `laco_do_daemon`."""
    d = _DaemonComTiqueReal()
    h = _HandlersDeVerdade(d)
    thread_do_laco = threading.get_ident()

    h._despachar_repintura("identity.renumber")
    await asyncio.sleep(0.25)

    assert d.tiques == 1, (
        "o PASSO 3 não aconteceu — é o `no running event loop` do journal "
        "dela: os LEDs dos externos não são repintados depois de renumerar")
    assert d.thread_do_tique == thread_do_laco, (
        "o tique rodou na thread do worker; `asyncio.create_task` só vale na "
        "thread do laço")
    assert d.coroutine_rodou, (
        "a coroutine `_sync_external_leds` ficou órfã — é o "
        "`RuntimeWarning: was never awaited` do journal dela")


def test_sem_laco_o_passo_tres_ainda_roda_em_linha() -> None:
    """O caminho síncrono não pode ter regredido: sem laço, o passo 3 roda."""

    class _TiqueSimples:
        def __init__(self) -> None:
            self.tiques = 0

        def _schedule_external_tick(self) -> None:
            self.tiques += 1

    d = _TiqueSimples()
    h = _HandlersDeVerdade(d)   # type: ignore[arg-type]
    h._despachar_repintura("teste")
    assert d.tiques == 1
