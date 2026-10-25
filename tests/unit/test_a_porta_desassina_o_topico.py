"""A porta desassina o tópico que a extensão larga (25/10/2026).

A sprint A-PORTA-DESASSINA-O-TOPICO-QUE-A-EXTENSAO-LARGA-01. A porta só tinha
``eventos.assinar``: quem assinava ``movimento`` segurava o leitor de movimento de cada controle
até a conexão fechar, e a extensão que tira «Sacudir» não tinha como largá-lo. Aqui:

1. ``eventos.desassinar`` do ``movimento`` faz os tiques seguintes pararem de pedir o leitor, e
   a reconciliação o fecha nos quatro controles, em toda mesa;
2. com duas extensões, a que desassina larga só o dela: a outra segue recebendo, e o leitor vive;
3. ``botoes``, ``entradas`` (com e sem ``dedos``) e um tópico do barramento desassinam igual;
4. tópico não assinado ou desconhecido é recusa sem efeito.

Os dublês são os do aparelho (o leitor de movimento do hub e o backend sem E/S); a porta, o
socket, o ``SensorHub`` e o barramento são os de verdade.
"""

from __future__ import annotations

import asyncio
import os
import pathlib
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventTopic
from hefesto_dualsense4unix.daemon.protocolo_do_ipc import CODE_INVALID_PARAMS
from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub
from hefesto_dualsense4unix.mods.porta import Porta
from tests.unit.test_a_coluna_agora_e_o_parar_tudo_vem_do_servico import curto  # noqa: F401
from tests.unit.test_a_porta_entrega_as_entradas_de_cada_controle import (
    _drenar,
    _Extensao,
    _Relogio,
)
from tests.unit.test_o_movimento_chega_as_extensoes import (
    MESAS,
    P2,
    UNIQS,
    _hub_que_descobre,
    _Mesa,
    _porta,
)

PERMISSOES = ["ler:movimento", "ler:entradas", "ler:botoes", "ler:bateria"]


async def _entrar(pasta: pathlib.Path, ficha: str, topicos: list[str],
                  **extra: Any) -> _Extensao:
    ext = _Extensao(pasta / "mods.sock")
    await asyncio.to_thread(ext.pedir, "mod.ola", {"ficha": ficha})
    assinou = await asyncio.to_thread(
        ext.pedir, "eventos.assinar", {"topicos": topicos, **extra})
    assert "result" in assinou, assinou
    return ext


async def _porta_de_duas(pasta: pathlib.Path, relogio: _Relogio) -> Porta:
    porta = await _porta(pasta, relogio)
    porta.registrar("ficha", "exemplo", os.getpid(), PERMISSOES)
    porta.registrar("outra-ficha", "outra", os.getpid(), PERMISSOES)
    return porta


async def _esperar(condicao: Any, segundos: float = 3.0) -> None:
    prazo = asyncio.get_running_loop().time() + segundos
    while not condicao() and asyncio.get_running_loop().time() < prazo:
        await asyncio.sleep(0.02)


def _conexao_de(porta: Porta, mod_id: str) -> Any:
    (con,) = [c for c in porta._conexoes if c.sessao and c.sessao.mod_id == mod_id]
    return con


def _vivas(tarefas: list[asyncio.Task[None]]) -> list[asyncio.Task[None]]:
    return [t for t in tarefas if not t.done()]


# -- 1: desassinado o movimento, o leitor de cada controle fecha ------------------------------


@pytest.mark.parametrize("mesa", list(MESAS))
def test_desassinar_o_movimento_fecha_o_leitor_de_cada_controle(
    curto: pathlib.Path, mesa: str,  # noqa: F811
) -> None:
    relogio = _Relogio()

    async def corrida() -> dict[str, Any]:
        porta = await _porta_de_duas(curto, relogio)
        bancada = _Mesa(porta, MESAS[mesa])
        bancada.hub = _hub_que_descobre(bancada.uniqs, relogio)
        bancada.daemon._garantir_sensor_hub = lambda: bancada.hub
        ext = await _entrar(curto, "ficha", ["movimento"])
        try:
            bancada.tique(relogio)
            bancada.hub.reconciliar()
            abertos, leitores = set(bancada.hub._motion), dict(bancada.hub._motion)
            con = _conexao_de(porta, "exemplo")
            tarefas = list(con.tarefas)
            resposta = await asyncio.to_thread(
                ext.pedir, "eventos.desassinar", {"topicos": ["movimento"]})
            await _esperar(lambda: not _vivas(tarefas))
            for _ in range(3):  # os tiques seguem, e ninguém mais pede
                bancada.tique(relogio, SensorHub._DEMANDA_TTL_S)
            bancada.hub.reconciliar()
            # A conexão segue aberta e assina de novo: desassinar não a derruba.
            de_novo = await asyncio.to_thread(
                ext.pedir, "eventos.assinar", {"topicos": ["bateria"]})
            return {
                "abertos": abertos, "leitores": leitores, "resposta": resposta,
                "le": porta.le_o_movimento(), "filas": list(con.filas_do_movimento),
                "quedas": porta.bus.subscriber_count(EventTopic.CONTROLLER_DISCONNECTED),
                "depois": set(bancada.hub._motion), "de_novo": de_novo,
                "tarefas": _vivas(tarefas),
            }
        finally:
            ext.fechar()
            await porta.parar()

    r = asyncio.run(corrida())
    assert r["abertos"] == set(UNIQS[: len(MESAS[mesa])]), "o pedido não abriu o leitor"
    assert r["resposta"].get("result") == {"desassinados": ["movimento"]}, r["resposta"]
    assert not r["le"] and r["filas"] == [], "a fila do movimento ficou na conexão"
    assert r["quedas"] == 0, "a assinatura das quedas do movimento ficou no barramento"
    assert r["tarefas"] == [], "o encaminhamento ou as quedas do movimento seguiram vivos"
    assert r["depois"] == set(), f"o leitor seguiu vivo desassinado: {sorted(r['depois'])}"
    assert all(leitor.parado for leitor in r["leitores"].values()), "o leitor saiu sem parar"
    assert "result" in r["de_novo"], r["de_novo"]


# -- 2: duas extensões, uma desassina --------------------------------------------------------


def test_a_que_desassina_larga_so_o_dela(curto: pathlib.Path) -> None:  # noqa: F811
    relogio = _Relogio()

    async def corrida() -> dict[str, Any]:
        porta = await _porta_de_duas(curto, relogio)
        bancada = _Mesa(porta, MESAS["mista"])
        bancada.hub = _hub_que_descobre(bancada.uniqs, relogio)
        bancada.daemon._garantir_sensor_hub = lambda: bancada.hub
        uma = await _entrar(curto, "ficha", ["movimento"])
        outra = await _entrar(curto, "outra-ficha", ["movimento"])
        try:
            bancada.tique(relogio)
            bancada.hub.reconciliar()
            await asyncio.to_thread(_drenar, uma, 0.2)
            await asyncio.to_thread(_drenar, outra, 0.2)
            resposta = await asyncio.to_thread(
                uma.pedir, "eventos.desassinar", {"topicos": ["movimento"]})
            for leitor in bancada.hub._motion.values():
                leitor.giro = (300.0, 0.0, 0.0)
            for _ in range(3):
                bancada.tique(relogio, SensorHub._DEMANDA_TTL_S)
            bancada.hub.reconciliar()
            return {
                "resposta": resposta,
                "da_uma": await asyncio.to_thread(_drenar, uma, 0.3),
                "da_outra": await asyncio.to_thread(_drenar, outra, 0.3),
                "vivos": set(bancada.hub._motion),
            }
        finally:
            uma.fechar()
            outra.fechar()
            await porta.parar()

    r = asyncio.run(corrida())
    assert "result" in r["resposta"], r["resposta"]
    assert r["da_uma"] == [], "quem desassinou seguiu recebendo o movimento"
    assert {e["dados"]["uniq"] for e in r["da_outra"]} == set(UNIQS), "a outra parou de receber"
    assert r["vivos"] == set(UNIQS), "o leitor fechou com a outra extensão assinada"


# -- 3: os outros tópicos desassinam igual ---------------------------------------------------


@pytest.mark.parametrize("dedos", [False, True])
def test_as_entradas_desassinam_e_largam_os_dedos(
    curto: pathlib.Path, dedos: bool,  # noqa: F811
) -> None:
    relogio = _Relogio()

    async def corrida() -> dict[str, Any]:
        porta = await _porta_de_duas(curto, relogio)
        ext = await _entrar(curto, "ficha", ["entradas"], dedos=dedos)
        try:
            antes = (porta.le_as_entradas(), porta.pede_os_dedos())
            con = _conexao_de(porta, "exemplo")
            tarefas = list(con.tarefas)
            resposta = await asyncio.to_thread(
                ext.pedir, "eventos.desassinar", {"topicos": ["entradas"]})
            await _esperar(lambda: not _vivas(tarefas))
            return {
                "antes": antes, "resposta": resposta,
                "depois": (porta.le_as_entradas(), porta.pede_os_dedos()),
                "tarefas": _vivas(tarefas) + con.tarefas, "quer": con.quer_os_dedos,
                "quedas": porta.bus.subscriber_count(EventTopic.CONTROLLER_DISCONNECTED),
            }
        finally:
            ext.fechar()
            await porta.parar()

    r = asyncio.run(corrida())
    assert r["antes"] == (True, dedos)
    assert r["resposta"].get("result") == {"desassinados": ["entradas"]}, r["resposta"]
    assert r["depois"] == (False, False), "as entradas ou os dedos seguiram pedidos"
    assert not r["quer"], "a conexão seguiu querendo os dedos"
    assert r["tarefas"] == [] and r["quedas"] == 0, "o encaminhamento ou as quedas ficaram"


def test_os_botoes_desassinam(curto: pathlib.Path) -> None:  # noqa: F811
    relogio = _Relogio()

    async def corrida() -> dict[str, Any]:
        porta = await _porta_de_duas(curto, relogio)
        ext = await _entrar(curto, "ficha", ["botoes"])
        try:
            porta.botoes_do_tique({P2: frozenset()}, lambda uniq: 2)
            con = _conexao_de(porta, "exemplo")
            tarefas = list(con.tarefas)
            resposta = await asyncio.to_thread(
                ext.pedir, "eventos.desassinar", {"topicos": ["botoes"]})
            porta.botoes_do_tique({P2: frozenset({"cross"})}, lambda uniq: 2)
            await _esperar(lambda: not _vivas(tarefas))
            return {"resposta": resposta, "le": porta.le_os_botoes(),
                    "eventos": await asyncio.to_thread(_drenar, ext, 0.3),
                    "tarefas": _vivas(tarefas) + con.tarefas}
        finally:
            ext.fechar()
            await porta.parar()

    r = asyncio.run(corrida())
    assert r["resposta"].get("result") == {"desassinados": ["botoes"]}, r["resposta"]
    assert not r["le"] and r["eventos"] == [], "os botões seguiram chegando"
    assert r["tarefas"] == [], "o encaminhamento dos botões ficou"


def test_um_topico_do_barramento_desassina(curto: pathlib.Path) -> None:  # noqa: F811
    relogio = _Relogio()

    async def corrida() -> dict[str, Any]:
        porta = await _porta_de_duas(curto, relogio)
        ext = await _entrar(curto, "ficha", ["bateria", "movimento"])
        try:
            resposta = await asyncio.to_thread(
                ext.pedir, "eventos.desassinar", {"topicos": ["bateria"]})
            porta.bus.publish(EventTopic.BATTERY_CHANGE, {"uniq": P2, "pct": 40})
            return {"resposta": resposta,
                    "inscritos": porta.bus.subscriber_count(EventTopic.BATTERY_CHANGE),
                    "eventos": await asyncio.to_thread(_drenar, ext, 0.3),
                    "movimento": porta.le_o_movimento()}
        finally:
            ext.fechar()
            await porta.parar()

    r = asyncio.run(corrida())
    assert r["resposta"].get("result") == {"desassinados": ["bateria"]}, r["resposta"]
    assert r["inscritos"] == 0 and r["eventos"] == [], "a bateria seguiu no barramento"
    assert r["movimento"], "desassinar a bateria levou o movimento junto"


# -- 4: a recusa não tem efeito --------------------------------------------------------------


@pytest.mark.parametrize("topicos", [["movimento", "botoes"], ["movimento", "inventado"], [], None])
def test_topico_nao_assinado_ou_desconhecido_e_recusa_sem_efeito(
    curto: pathlib.Path, topicos: Any,  # noqa: F811
) -> None:
    relogio = _Relogio()

    async def corrida() -> tuple[dict[str, Any], bool]:
        porta = await _porta_de_duas(curto, relogio)
        ext = await _entrar(curto, "ficha", ["movimento"])
        try:
            resposta = await asyncio.to_thread(
                ext.pedir, "eventos.desassinar", {"topicos": topicos})
            return resposta, porta.le_o_movimento()
        finally:
            ext.fechar()
            await porta.parar()

    resposta, segue = asyncio.run(corrida())
    assert resposta["error"]["code"] == CODE_INVALID_PARAMS, resposta
    assert segue, "a recusa desassinou o movimento"
