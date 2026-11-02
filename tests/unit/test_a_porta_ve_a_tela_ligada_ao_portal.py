"""A porta vê a tela do jogo pelo portal, ligada ao serviço (02/11/2026, ensaio).

A fonte de mentira entrega quadros sintéticos à ``Captura`` que a porta liga: a extensão que assina
``jogo.tela`` recebe os cinco números, e as regiões que declara. Sem assinante a fonte nem abre; o
último que larga o tópico a fecha. No modo de mentira, a fonte do sistema é a ausente.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.integrations import tela_do_jogo as tj
from hefesto_dualsense4unix.mods.porta import CODE_INVALID_PARAMS, Porta
from tests.unit.test_a_porta_ouve_o_jogo_e_o_microfone import P1, _Cliente

L, A = 64, 36


def _quadro(r: int, g: int, b: int) -> tj.Quadro:
    return tj.Quadro(L, A, L * 4, "BGRx", bytes((b, g, r, 0)) * (L * A))


class _Fonte:
    def __init__(self) -> None:
        self.abertas = 0
        self.fechadas = 0

    def abrir(self) -> bool:
        self.abertas += 1
        return True

    def quadro(self) -> tj.Quadro | None:
        return _quadro(200, 30, 30)

    def fechar(self) -> None:
        self.fechadas += 1


async def _esperar(condicao: Any, segundos: float = 5.0) -> bool:
    for _ in range(int(segundos / 0.02)):
        if condicao():
            return True
        await asyncio.sleep(0.02)
    return bool(condicao())


def _porta(caminho: Path, bus: EventBus, fontes: list[_Fonte]) -> Porta:
    async def escritor(_m: str, _p: dict[str, Any]) -> Any:
        return {"status": "ok"}

    def fabrica() -> _Fonte:
        fontes.append(_Fonte())
        return fontes[-1]

    return Porta(caminho, bus, escritor=escritor, o_jogo_escreve=lambda _u, _c: False,
                 uniq_do_posto=lambda: P1, fonte_da_tela=fabrica)


def test_a_extensao_assinante_recebe_os_cinco_numeros_da_fonte_ligada() -> None:
    fontes: list[_Fonte] = []

    async def corrida() -> tuple[bool, dict[str, Any], dict[str, Any]]:
        with tempfile.TemporaryDirectory(prefix="pt") as pasta:
            caminho = Path(pasta) / "mods.sock"
            bus = EventBus()
            bus.bind_loop(asyncio.get_running_loop())
            porta = _porta(caminho, bus, fontes)
            await porta.iniciar()
            porta.registrar("ficha-t", "imersao", os.getpid(), ["ler:jogo.tela"])
            cliente = _Cliente(caminho)
            try:
                await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha-t"})
                await asyncio.sleep(0.3)
                antes = bool(fontes)
                aceito = await asyncio.to_thread(cliente.pedir, "eventos.assinar", {
                    "topicos": ["jogo.tela"],
                    "tela": {"regioes": [{"nome": "vida", "x": 0.1, "y": 0.9, "largura": 0.3,
                                          "altura": 0.05, "cor": [200, 30, 30]}]}})
                evento = await asyncio.wait_for(asyncio.to_thread(cliente.evento), 5)
            finally:
                cliente.fechar()
                await porta.parar()
            return antes, aceito, evento

    antes, aceito, evento = asyncio.run(corrida())
    assert not antes
    assert aceito["result"] == {"assinados": ["jogo.tela"]}
    dados = evento["params"]["dados"]
    assert evento["params"]["nome"] == "jogo.tela"
    assert set(dados) == {"t", "regioes", *tj.SINAIS}
    assert all(isinstance(dados[s], float) for s in tj.SINAIS)
    assert dados["regioes"] == {"vida": 1.0}
    assert len(fontes) == 1 and fontes[0].abertas == 1


def test_sem_assinante_a_fonte_nao_abre_e_o_ultimo_que_larga_a_fecha() -> None:
    fontes: list[_Fonte] = []

    async def corrida() -> tuple[int, bool]:
        with tempfile.TemporaryDirectory(prefix="pt") as pasta:
            caminho = Path(pasta) / "mods.sock"
            bus = EventBus()
            bus.bind_loop(asyncio.get_running_loop())
            porta = _porta(caminho, bus, fontes)
            await porta.iniciar()
            porta.registrar("ficha-t", "imersao", os.getpid(), ["ler:jogo.tela", "ler:jogo.som"])
            cliente = _Cliente(caminho)
            try:
                await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha-t"})
                await asyncio.to_thread(cliente.pedir, "eventos.assinar",
                                        {"topicos": ["jogo.som"]})
                await asyncio.sleep(0.4)
                sem_assinante = len(fontes)
                await asyncio.to_thread(cliente.pedir, "eventos.assinar",
                                        {"topicos": ["jogo.tela"]})
                await _esperar(lambda: bool(fontes) and fontes[0].abertas == 1)
                await asyncio.to_thread(cliente.pedir, "eventos.desassinar",
                                        {"topicos": ["jogo.tela"]})
                fechou = await _esperar(lambda: fontes[0].fechadas == 1)
            finally:
                cliente.fechar()
                await porta.parar()
            return sem_assinante, fechou

    sem_assinante, fechou = asyncio.run(corrida())
    assert sem_assinante == 0
    assert fechou


def test_a_regiao_fora_da_forma_recusa_a_assinatura() -> None:
    fontes: list[_Fonte] = []

    async def corrida() -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="pt") as pasta:
            caminho = Path(pasta) / "mods.sock"
            porta = _porta(caminho, EventBus(), fontes)
            await porta.iniciar()
            porta.registrar("ficha-t", "imersao", os.getpid(), ["ler:jogo.tela"])
            cliente = _Cliente(caminho)
            try:
                await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha-t"})
                return await asyncio.to_thread(cliente.pedir, "eventos.assinar", {
                    "topicos": ["jogo.tela"],
                    "tela": {"regioes": [{"nome": "vida", "x": 0.9, "y": 0.9, "largura": 0.5,
                                          "altura": 0.05, "cor": [200, 30, 30]}]}})
            finally:
                cliente.fechar()
                await porta.parar()

    resposta = asyncio.run(corrida())
    assert resposta["error"]["code"] == CODE_INVALID_PARAMS
    assert not fontes


def test_no_modo_de_mentira_a_fonte_do_sistema_e_a_ausente() -> None:
    assert isinstance(tj.fonte_do_sistema(), tj.FonteAusente)
    assert tj.FonteAusente().abrir() is False
