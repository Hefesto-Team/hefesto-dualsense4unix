"""RESPOSTA-QUE-CHEGA-TARDE-01 — o `ok` não espera a consequência.

Ela clicou em "Player 1" no Cosmic Red, a tela disse *"não consegui trocar o
número"* — e o controle trocou. Palavra dela, 07/09/2026: *"não conseguiu
trocar de numero mas trocou na vida real, esse aviso é mentiroso"*.

A CONTA QUE EXPLICA: o cliente espera 250 ms (`app/ipc_bridge.py:88`) e o
handler repintava ANTES de responder — `coop.sync(force=True)`, o reassert dos
quatro controles e o tique dos externos, três deles por Bluetooth. Não cabe. O
daemon fazia o trabalho inteiro, certo, e a resposta chegava depois de a tela
parar de ouvir: `_safe_call` devolvia `(False, None)` e a frase genérica saía
por cima de um SUCESSO.

A REGRA: *a resposta é sobre o que foi PEDIDO, não sobre as consequências
dele.* O número já trocou quando a repintura começa — foi `_set_number_locked`,
sob lock, que o afirmou. Segurar a resposta transformava um efeito colateral
lento em veredito.

Herméticos: nenhum aparelho, nenhum socket. A repintura é um dublê LENTO de
propósito — é a lentidão que reproduz o defeito.
"""
from __future__ import annotations

import asyncio
import threading
import time

import pytest

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

#: O prazo REAL do cliente, de `app/ipc_bridge.py`. Não é número escolhido aqui.
PRAZO_DO_CLIENTE_S = 0.25
#: Uma repintura que estoura o prazo — é o caso dela, com três por rádio.
REPINTURA_LENTA_S = 0.6


class _Handlers(IpcHandlersMixin):
    """Só o que este teste toca."""

    def __init__(self) -> None:
        self.repintou = 0
        self.terminou_em: float | None = None

    # A ASSINATURA É A DO PRODUTO, e isto não é detalhe: um dublê mais FROUXO
    # que a função real é a armadilha nº 1 desta casa. O `laco_do_daemon` é o
    # que `_despachar_repintura` passa de dentro da thread — ver
    # `test_o_tique_dos_externos_e_agendado_na_thread_do_laco`.
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

    # E ELA ACONTECE — despachar não pode virar engolir.
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
    h._despachar_repintura("teste")           # não levanta
    await asyncio.sleep(0.2)
    assert h.repintou == 1


def test_sem_laco_de_eventos_roda_em_linha() -> None:
    """Chamada síncrona (dublês da suíte): comportamento anterior à cura.

    Sem laço não há para onde despachar, e engolir a repintura seria trocar um
    defeito por outro — a lâmpada ficaria no número velho para sempre.
    """
    h = _Handlers()
    h._despachar_repintura("teste")
    assert h.repintou == 1


# ---------------------------------------------------------------------------
# O PASSO 3 QUE MORRIA NA THREAD — achado no journal da bancada dela,
# 07/09/2026, no mesmo segundo em que `identity.renumber` reescreveu o
# `controllers.json`:
#
#     repintura_apos_renumeracao_falhou de_onde=identity.renumber
#         err='no running event loop'
#     RuntimeWarning: coroutine 'Daemon._sync_external_leds' was never awaited
#
# A cura acima (despachar num `asyncio.to_thread` para não estourar os 250 ms)
# levou o corpo inteiro para um WORKER THREAD — e o passo 3,
# `_schedule_external_tick`, termina em `asyncio.create_task`, que EXIGE laço
# rodando na thread atual. Os passos 1 e 2 rodavam; o 3 levantava `RuntimeError`
# e a coroutine já construída ficava órfã. Os LEDs dos EXTERNOS (o Pro e o
# 8BitDo) não eram repintados depois de renumerar.
# ---------------------------------------------------------------------------


class _DaemonComTiqueReal:
    """O `_schedule_external_tick` do `daemon/lifecycle.py`, no essencial.

    O QUE ELE COPIA, e é a linha que importa: o tique termina em
    `asyncio.create_task(self._sync_external_leds(), ...)`. Um dublê que só
    contasse chamadas seria mais FROUXO que o daemon vivo e daria verde sobre
    o defeito — foi assim que ele passou por esta suíte inteira.
    """

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
        # A referência fica guardada como no `lifecycle.py` — lá é
        # `self._external_tick_task`, e um dublê que a soltasse seria mais
        # frouxo que o daemon vivo.
        self._external_tick_task = asyncio.create_task(
            self._sync_external_leds(), name="external_led_tick"
        )


class _HandlersDeVerdade(IpcHandlersMixin):
    """Usa o `_repintar_apos_renumeracao` REAL — é ele que está sob teste."""

    def __init__(self, daemon: _DaemonComTiqueReal) -> None:
        self.daemon = daemon
        self.controller = None      # sem `reassert_resolved_outputs`: passo 2 é no-op


@pytest.mark.asyncio
async def test_o_tique_dos_externos_e_agendado_na_thread_do_laco() -> None:
    """FALHA-SEM / PASSA-COM — a mordida é o `laco_do_daemon`.

    ARRANQUE A CURA (o `_repintar_apos_renumeracao` chamado sem o laço, ou o
    passo 3 chamado direto em vez de por `call_soon_threadsafe`) e este teste
    reprova: `create_task` levanta `RuntimeError: no running event loop` dentro
    da thread, o passo 3 não acontece e `tiques` fica em 0.
    """
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
    """O caminho síncrono não pode ter regredido: sem laço, o passo 3 roda.

    Aqui o tique é o de um daemon que NÃO agenda coroutine (dublê legado), que
    é a única forma de ele existir fora de um laço.
    """

    class _TiqueSimples:
        def __init__(self) -> None:
            self.tiques = 0

        def _schedule_external_tick(self) -> None:
            self.tiques += 1

    d = _TiqueSimples()
    h = _HandlersDeVerdade(d)   # type: ignore[arg-type]
    h._despachar_repintura("teste")
    assert d.tiques == 1
