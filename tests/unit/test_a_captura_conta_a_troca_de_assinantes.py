"""A captura conta as assinaturas que nasceram, não as que existem (11/11/2026).

Depois de uma escolha de tela cancelada, o pedido só volta com assinatura NOVA de ``jogo.tela``.
Quem sai e quem entra no mesmo passo deixa a conta de existentes igual, e o pedido novo não saía;
a porta agora entrega o contador de nascidas. Sem assinatura nova a recusa continua valendo.
A prova da porta tem quatro extensões assinando ao mesmo tempo: a troca de assinatura de uma
extensão reabre a fonte, e o evento chega às quatro.
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.integrations import tela_do_jogo as tj
from hefesto_dualsense4unix.mods import porta as modulo_porta
from hefesto_dualsense4unix.mods.porta import Porta
from tests.unit.test_a_porta_ouve_o_jogo_e_o_microfone import P1, _Cliente

L, A = 64, 36


def _quadro() -> tj.Quadro:
    return tj.Quadro(L, A, L * 4, "BGRx", bytes((30, 30, 200, 0)) * (L * A))


class _FonteQueRecusaUmaVez:
    """A primeira abertura é a escolha cancelada (depois de ``janela`` liberar, a janela do
    portal aberta enquanto os outros chegam); a segunda entrega quadro."""

    def __init__(self) -> None:
        self.aberturas = 0
        self.janela = threading.Event()
        self.janela.set()

    def abrir(self) -> bool:
        self.aberturas += 1
        if self.aberturas == 1:
            self.janela.wait(5.0)
            raise tj.EscolhaCanceladaError("a pessoa cancelou")
        return True

    def quadro(self) -> tj.Quadro | None:
        return _quadro()

    def fechar(self) -> None:
        return None

    def interromper(self) -> None:
        return None


class _Cena:
    """A captura com o relógio e as duas contas na mão do teste."""

    def __init__(self) -> None:
        self.agora = [100.0]
        self.existentes = [1]
        self.nascidas = [1]
        self.fonte = _FonteQueRecusaUmaVez()
        self.captura = tj.Captura(
            self.fonte, tj.TelaDoJogo(relogio=lambda: self.agora[0]),
            publicar=lambda _carga: None, assinantes=lambda: self.existentes[0],
            nascidas=lambda: self.nascidas[0], relogio=lambda: self.agora[0])

    def correr(self, passos: int, passo_s: float = 0.2) -> None:
        for _ in range(passos):
            self.captura.passo()
            self.agora[0] += passo_s


def test_a_troca_de_assinante_no_mesmo_passo_pede_a_escolha_de_novo() -> None:
    cena = _Cena()
    cena.correr(15)
    assert cena.fonte.aberturas == 1
    cena.nascidas[0] += 1
    cena.correr(15)
    assert cena.fonte.aberturas == 2
    assert cena.captura.aberta


def test_sem_assinatura_nova_a_recusa_continua_valendo() -> None:
    cena = _Cena()
    cena.correr(15)
    assert cena.fonte.aberturas == 1
    cena.correr(100)
    assert cena.fonte.aberturas == 1
    assert not cena.captura.aberta


def test_quem_chega_com_a_janela_aberta_ouve_o_mesmo_cancelamento() -> None:
    cena = _Cena()
    abrir = cena.fonte.abrir

    def abre_e_chega_outro() -> bool:
        cena.nascidas[0] += 1
        return abrir()

    cena.fonte.abrir = abre_e_chega_outro  # type: ignore[method-assign]
    cena.correr(100)
    assert cena.fonte.aberturas == 1


def test_todos_sairem_e_um_voltar_pede_de_novo_sem_nascida_nova() -> None:
    cena = _Cena()
    cena.correr(15)
    cena.existentes[0] = 0
    cena.correr(2)
    cena.existentes[0] = 1
    cena.correr(15)
    assert cena.fonte.aberturas == 2


async def _esperar(condicao: Any, segundos: float) -> bool:
    for _ in range(int(segundos / 0.02)):
        if condicao():
            return True
        await asyncio.sleep(0.02)
    return bool(condicao())


def _ler_ate(cliente: _Cliente, req_id: int) -> dict[str, Any]:
    while True:
        linha: dict[str, Any] = json.loads(cliente.arquivo.readline())
        if linha.get("id") == req_id:
            return linha


def _ler_um_quadro_medido(cliente: _Cliente) -> dict[str, Any]:
    while True:
        dados: dict[str, Any] = cliente.evento()["params"]["dados"]
        if dados.get("escuro") is not None:
            return dados


def test_a_porta_reabre_a_fonte_na_troca_e_o_evento_chega_as_quatro_extensoes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(modulo_porta, "HZ_DA_TELA", 1.0)
    fonte = _FonteQueRecusaUmaVez()
    fonte.janela.clear()

    async def corrida() -> tuple[int, list[dict[str, Any]]]:
        with tempfile.TemporaryDirectory(prefix="pt") as pasta:
            caminho = Path(pasta) / "mods.sock"
            bus = EventBus()
            bus.bind_loop(asyncio.get_running_loop())

            async def escritor(_m: str, _p: dict[str, Any]) -> Any:
                return {"status": "ok"}

            porta = Porta(caminho, bus, escritor=escritor, o_jogo_escreve=lambda _u, _c: False,
                          uniq_do_posto=lambda: P1, fonte_da_tela=lambda: fonte)
            await porta.iniciar()
            clientes = [_Cliente(caminho) for _ in range(4)]
            try:
                for i, cliente in enumerate(clientes):
                    porta.registrar(f"ficha-{i}", f"imersao{i}", os.getpid(), ["ler:jogo.tela"])
                    await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": f"ficha-{i}"})
                    await asyncio.to_thread(cliente.pedir, "eventos.assinar",
                                            {"topicos": ["jogo.tela"]})
                assert await _esperar(lambda: fonte.aberturas == 1, 3.0)
                fonte.janela.set()
                await asyncio.sleep(0.3)
                assert fonte.aberturas == 1
                troca = b"".join(json.dumps({"jsonrpc": "2.0", "id": 9000 + n, "method": m,
                                             "params": {"topicos": ["jogo.tela"]}}).encode()
                                 + b"\n" for n, m in enumerate(
                                     ("eventos.desassinar", "eventos.assinar")))
                clientes[0].sock.sendall(troca)
                await asyncio.to_thread(_ler_ate, clientes[0], 9001)
                reabriu = await _esperar(lambda: fonte.aberturas == 2, 6.0)
                assert reabriu, fonte.aberturas
                eventos = [await asyncio.wait_for(
                    asyncio.to_thread(_ler_um_quadro_medido, c), 5) for c in clientes]
            finally:
                for cliente in clientes:
                    cliente.fechar()
                await porta.parar()
            return fonte.aberturas, eventos

    aberturas, eventos = asyncio.run(corrida())
    assert aberturas == 2
    assert len(eventos) == 4
    assert all(set(e) >= set(tj.SINAIS) and e["escuro"] is not None for e in eventos)
