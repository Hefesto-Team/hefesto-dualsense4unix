"""A mesa vazia não para o laço do serviço — o achado de 02/10/2026.

**O DEFEITO, no diário dela:** em 30/09 às 01h13 e em 01/10 às 13h28 e às
19h05, logo depois do ``controller_disconnected reason=probe_offline`` do
último controle, o serviço parou de responder: a janela travou, o controle
que voltou não foi aceito (nenhum ``controller_connected`` até o reinício) e o
SIGTERM, que o laço atende, não foi atendido.

**A CAUSA, medida em 02/10 com o daemon do produto num lar de mentira** (a
mesa de rádio que se esvazia, o ``state_full`` lido a cada segundo pelo
instrumento da O-TRAVAMENTO-SE-SEPARA-UM-FATOR-POR-VEZ-01): o ``state_full``
emudeceu um segundo depois do ``probe_offline`` do último controle e não
voltou mais, nem com os dois controles de volta; o SIGTERM não foi atendido em
10 s; e a pilha do fio do laço estava no ``canal_do_microfone_loop``. A espera
do canal (``_esperar_o_som_mudar``) não passa da hora da próxima conferência,
a hora só anda na volta COM controle, e com a mesa vazia ela ficava no
passado: prazo zero, e o ``esperar_async`` de prazo zero volta sem ceder o
laço. A corrotina girava sem suspender, e o laço inteiro parava com ela.

**A RÉGUA** roda o laço do canal de produção num fio próprio, com uma batida
de 10 ms ao lado, e mede a batida enquanto a mesa está vazia. Laço parado é
batida parada. No fim a mesa volta, o que solta o laço que girava: a régua
reprova, e não fica pendurada.

**MORDIDA:** devolva o ``_CANAL_POR_UNIQ.clear()`` no lugar do
``_a_mesa_vazia_esquece_o_canal(daemon)`` no ``canal_do_microfone_loop``, e
a batida para (zero batidas em 0,6 s).

Nenhum teste deste arquivo toca o servidor de som nem o aparelho de quem o
roda: as leituras do canal e a conferência são dublês, e o retrato do som não
tem dono aqui.
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import retrato_do_som as rs

UNIQ = "aa:bb:cc:00:00:a1"

TTL_S = 0.1


def _ate(condicao: Any, motivo: str, prazo: float = 3.0) -> None:
    fim = time.monotonic() + prazo
    while not condicao():
        if time.monotonic() > fim:
            raise AssertionError(f"não chegou no prazo: {motivo}")
        time.sleep(0.01)


def test_a_mesa_vazia_nao_para_o_laco_do_servico(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import hotkey

    mesa = [UNIQ]
    conferencias: list[float] = []

    async def ler(_daemon: Any, _uniq: str) -> dict[str, Any]:
        await asyncio.sleep(0)
        return {"fonte": None}

    async def conferir(_daemon: Any, _uniqs: list[str]) -> list[str]:
        conferencias.append(time.monotonic())
        return []

    monkeypatch.setattr(hotkey, "_uniqs_conectados", lambda _d: list(mesa))
    monkeypatch.setattr(hotkey, "_ler_o_canal_deste", ler)
    monkeypatch.setattr(hotkey, "_conferir_quem_saiu_do_ar", conferir)
    monkeypatch.setattr(hotkey, "_CANAL_POR_UNIQ", {})
    monkeypatch.setattr(hotkey, "CANAL_TTL_S", TTL_S)
    monkeypatch.setattr(hotkey, "_MARCA_DO_CANAL", [None])

    parar = threading.Event()
    batidas = [0]

    class _Daemon:
        def _is_stopping(self) -> bool:
            return parar.is_set()

    daemon = _Daemon()

    async def bater() -> None:
        while not parar.is_set():
            batidas[0] += 1
            await asyncio.sleep(0.01)

    async def cenario() -> None:
        canal = asyncio.create_task(hotkey.canal_do_microfone_loop(daemon))  # type: ignore[arg-type]
        batida = asyncio.create_task(bater())
        while not parar.is_set():
            await asyncio.sleep(0.01)
        rs.RETRATO._avisar({"sources"})
        await asyncio.wait_for(canal, 2.0)
        await batida

    erros: list[BaseException] = []

    def correr() -> None:
        try:
            asyncio.run(cenario())
        except BaseException as erro:
            erros.append(erro)

    fio = threading.Thread(target=correr, name="laco-da-regua", daemon=True)
    fio.start()
    conferidas_na_volta = 0
    try:
        _ate(lambda: bool(conferencias), "a primeira conferência, com o controle na mesa")
        mesa.clear()
        time.sleep(2 * TTL_S)
        antes = batidas[0]
        time.sleep(6 * TTL_S)
        depois = batidas[0]
        ja = len(conferencias)
        mesa.append(UNIQ)
        _ate(lambda: len(conferencias) > ja, "a conferência de quem voltou", prazo=2.0)
        conferidas_na_volta = len(conferencias) - ja
    finally:
        if UNIQ not in mesa:
            mesa.append(UNIQ)
        parar.set()
        fio.join(5.0)
    assert not fio.is_alive(), "o laço da régua não terminou"
    assert not erros, f"o laço da régua levantou: {erros!r}"
    assert depois - antes >= 20, (
        f"com a mesa vazia o laço deu {depois - antes} batidas de 10 ms em "
        f"{6 * TTL_S:.1f} s: o canal do microfone girou sem ceder e parou o laço "
        "do serviço"
    )
    assert conferidas_na_volta >= 1
