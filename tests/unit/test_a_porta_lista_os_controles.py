"""O ``controles.lista`` da porta: a extensão sabe quais controles estão ligados, de P1 a P4.

Os tópicos de estado e de entrada e saída são do controle do posto; quem faz cada controle vibrar (o
servidor Buttplug da extensão ``intiface``) precisa da lista inteira, com o número que cada um
acende. O método pede a permissão de ler a entrada e a saída, repete cada controle uma vez só e,
sem a lista do serviço, devolve o controle do posto.

MORDIDAS (executadas): sem a conferência da permissão, a recusa some; sem o filtro do repetido, o
mesmo controle aparece duas vezes; sem o ``connected``, o controle que caiu entra na lista.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.mods.porta import CODE_SEM_PERMISSAO, Porta, controles_no_servico
from tests.unit import test_as_modificacoes_rodam_fora_do_daemon as _base

_Cliente, curto = _base._Cliente, _base.curto
UM, DOIS = "aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"
LER_CONEXAO = "ler:conexao"  # (noqa-acento)


async def _nada(_metodo: str, _pedido: dict[str, Any]) -> Any:
    return {"status": "ok"}


def _pedir_a_lista(curto: Path, permissoes: list[str], controles: Any = None) -> dict[str, Any]:
    async def corrida() -> dict[str, Any]:
        porta = Porta(curto / "mods.sock", EventBus(), escritor=_nada,
                      o_jogo_escreve=lambda uniq, canal: False, uniq_do_posto=lambda: UM,
                      controles=controles)
        await porta.iniciar()
        porta.registrar("ficha", "intiface", os.getpid(), permissoes)
        cliente = _Cliente(curto / "mods.sock")
        try:
            await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha"})
            return await asyncio.to_thread(cliente.pedir, "controles.lista", {})
        finally:
            cliente.fechar()
            await porta.parar()

    return asyncio.run(corrida())


def test_sem_ler_conexao_a_lista_e_recusada_nomeando_a_permissao(curto: Path) -> None:
    resposta = _pedir_a_lista(curto, ["escrever:vibracao"])
    assert resposta["error"]["code"] == CODE_SEM_PERMISSAO
    assert LER_CONEXAO in resposta["error"]["message"]


def test_sem_a_lista_do_servico_vale_o_controle_do_posto(curto: Path) -> None:
    resposta = _pedir_a_lista(curto, [LER_CONEXAO])
    assert resposta["result"] == {"controles": [{"uniq": UM, "jogador": None}]}


def test_a_lista_traz_cada_controle_uma_vez_com_o_numero_que_acende(curto: Path) -> None:
    def controles() -> list[dict[str, Any]]:
        return [{"uniq": UM, "jogador": 1}, {"uniq": DOIS, "jogador": 2},
                {"uniq": UM, "jogador": 1}, {"uniq": "", "jogador": 3},
                {"uniq": "aa:bb:cc:00:00:03", "jogador": True}]

    resposta = _pedir_a_lista(curto, [LER_CONEXAO], controles)
    assert resposta["result"]["controles"] == [
        {"uniq": UM, "jogador": 1}, {"uniq": DOIS, "jogador": 2},
        {"uniq": "aa:bb:cc:00:00:03", "jogador": None}]


def test_a_lista_que_falha_e_vazia_e_a_porta_segue(curto: Path) -> None:
    def quebra() -> list[dict[str, Any]]:
        raise RuntimeError("o backend caiu")

    assert _pedir_a_lista(curto, [LER_CONEXAO], quebra)["result"] == {"controles": []}


def test_o_servico_lista_so_os_ligados_com_o_jogador_de_cada_um() -> None:
    descricao = [
        {"index": 0, "connected": True, "uniq": UM},
        {"index": 1, "connected": False, "uniq": DOIS},
        {"index": 2, "connected": True, "uniq": None},
    ]
    daemon = SimpleNamespace(controller=SimpleNamespace(describe_controllers=lambda: descricao))
    lista = controles_no_servico(daemon)()
    assert [c["uniq"] for c in lista] == [UM]
    assert set(lista[0]) == {"uniq", "jogador"}
