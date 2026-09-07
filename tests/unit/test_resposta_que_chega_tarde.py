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

    def _repintar_apos_renumeracao(self) -> None:
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
        def _repintar_apos_renumeracao(self) -> None:
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
