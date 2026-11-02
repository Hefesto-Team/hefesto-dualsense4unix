"""A porta pede o peso da mira no giroscópio (02/11/2026, ensaio).

``mira.peso`` com a permissão ``escrever:mira`` multiplica o giro: a deflexão da máscara Xbox e os
três eixos da janela da máscara DualSense saem pelo ganho, e sem pedido a janela sai byte a byte.
O ganho volta a 1 no prazo, quando a extensão cai, quando o jogo fecha e quando a seção Controles
deixa de estar no modo da extensão. Num jogo com anticheat, só com a chave do jogo ligada.
"""
from __future__ import annotations

import asyncio
import os
import struct
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core import roteador_de_movimento as roteador
from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo
from hefesto_dualsense4unix.integrations.leitor_do_estado import (
    ChavesDaMemoria,
    arquivo_das_chaves,
)
from hefesto_dualsense4unix.mods import porta as porta_mod
from hefesto_dualsense4unix.mods.porta import CODE_NAO_ESCREVEU, CODE_SEM_PERMISSAO, Porta
from tests.unit.test_a_porta_ouve_o_jogo_e_o_microfone import P1, _Cliente

JANELA = struct.pack("<3h", 1000, -2000, 3000) + bytes(range(22))


@pytest.fixture(autouse=True)
def _sem_peso(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(tato_vivo, "_MODO_DA_ABA_DITO", {P1: {
        "uniq": P1, "jogador": 1, "secoes": {"controles": "extensao:mira"}}})  # (noqa-acento)
    roteador.PESO_DA_MIRA.soltar()
    yield
    roteador.PESO_DA_MIRA.soltar()


def test_sem_pedido_a_janela_sai_byte_a_byte_e_com_meio_ganho_o_giro_sai_pela_metade() -> None:
    assert roteador.janela_que_sai(P1, JANELA) == JANELA
    roteador.PESO_DA_MIRA.pedir("m", P1, 0.5, 5000)
    pesada = roteador.janela_que_sai(P1, JANELA)
    assert struct.unpack_from("<3h", pesada) == (500, -1000, 1500)
    assert pesada[6:] == JANELA[6:]
    assert roteador.pesar_a_janela(JANELA, 1.0) is JANELA


def test_com_meio_ganho_a_deflexao_da_mascara_xbox_sai_pela_metade() -> None:
    arranjo = roteador.ArranjoDeMovimento(destino=roteador.DESTINO_ANALOGICO_DIREITO)
    inteira = roteador.deflexao((200.0, 120.0, 0.0), arranjo)
    assert inteira != (0, 0)
    metade = roteador.deflexao((200.0, 120.0, 0.0), arranjo, 0.5)
    assert all(abs(m - i / 2) <= 1 for m, i in zip(metade, inteira, strict=True))
    assert roteador.pixels((2.0, 1.0, 0.0), arranjo, 0.5) == pytest.approx(
        tuple(v / 2 for v in roteador.pixels((2.0, 1.0, 0.0), arranjo)))


def test_o_prazo_devolve_o_ganho_1_e_vale_o_menor_e_o_todos() -> None:
    agora = [0.0]
    peso = roteador.PesoDaMira(relogio=lambda: agora[0])
    peso.pedir("a", P1, 0.8, 1000)
    peso.pedir("b", roteador.TODOS_OS_CONTROLES, 0.6, 500)
    assert peso.ganho(P1) == 0.6
    assert peso.ganho("outro") == 0.6
    agora[0] = 0.6
    assert peso.ganho(P1) == 0.8 and peso.ganho("outro") == 1.0
    agora[0] = 1.1
    assert peso.ganho(P1) == 1.0
    with pytest.raises(ValueError):
        peso.pedir("a", P1, 0.2, 100)


async def _sessao(caminho: Path, bus: EventBus, permissoes: list[str]
                  ) -> tuple[Porta, _Cliente]:
    async def escritor(_m: str, _p: dict[str, Any]) -> Any:
        return {"status": "ok"}

    porta = Porta(caminho, bus, escritor=escritor, o_jogo_escreve=lambda _u, _c: False,
                  uniq_do_posto=lambda: P1)
    await porta.iniciar()
    porta.registrar("ficha-m", "mira", os.getpid(), permissoes)
    cliente = _Cliente(caminho)
    await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha-m"})
    return porta, cliente


def _pedido(ganho: float = 0.5) -> dict[str, Any]:
    return {"uniq": P1, "ganho": ganho, "ate_ms": 5000}


def test_sem_a_permissao_recusa_e_a_extensao_que_cai_devolve_o_ganho_1() -> None:
    async def corrida() -> tuple[dict[str, Any], dict[str, Any], float, float]:
        with tempfile.TemporaryDirectory(prefix="pm") as pasta:
            bus = EventBus()
            porta, sem = await _sessao(Path(pasta) / "a.sock", bus, ["ler:botoes"])
            recusa = await asyncio.to_thread(sem.pedir, "mira.peso", _pedido())
            sem.fechar()
            await porta.parar()
            porta, com = await _sessao(Path(pasta) / "b.sock", bus, ["escrever:mira"])
            try:
                aceito = await asyncio.to_thread(com.pedir, "mira.peso", _pedido())
                durante = roteador.PESO_DA_MIRA.ganho(P1)
                com.fechar()
                for _ in range(100):
                    if roteador.PESO_DA_MIRA.ganho(P1) == 1.0:
                        break
                    await asyncio.sleep(0.02)
                depois = roteador.PESO_DA_MIRA.ganho(P1)
            finally:
                await porta.parar()
            return recusa, aceito, durante, depois

    recusa, aceito, durante, depois = asyncio.run(corrida())
    assert recusa["error"]["code"] == CODE_SEM_PERMISSAO
    assert aceito["result"] == {"status": "ok"}
    assert durante == 0.5
    assert depois == 1.0


def test_o_jogo_que_fecha_e_o_modo_que_sai_devolvem_o_ganho_1() -> None:
    async def corrida() -> tuple[float, float, float]:
        with tempfile.TemporaryDirectory(prefix="pm") as pasta:
            bus = EventBus()
            bus.bind_loop(asyncio.get_running_loop())
            porta, com = await _sessao(Path(pasta) / "m.sock", bus, ["escrever:mira"])
            try:
                await asyncio.to_thread(com.pedir, "mira.peso", _pedido())
                bus.publish(EventTopic.MODO_ABA, {"uniq": P1, "secoes": {
                    "controles": "extensao:mira"}})  # (noqa-acento)
                await asyncio.sleep(0.2)
                no_modo = roteador.PESO_DA_MIRA.ganho(P1)
                bus.publish(EventTopic.MODO_ABA, {"uniq": P1, "secoes": {
                    "controles": "personalizado"}})
                await asyncio.sleep(0.2)
                fora_do_modo = roteador.PESO_DA_MIRA.ganho(P1)
                await asyncio.to_thread(com.pedir, "mira.peso", _pedido())
                bus.publish(EventTopic.JOGO_FECHOU, {"appid": "1"})
                await asyncio.sleep(0.2)
                fechou = roteador.PESO_DA_MIRA.ganho(P1)
            finally:
                com.fechar()
                await porta.parar()
            return no_modo, fora_do_modo, fechou

    no_modo, fora_do_modo, fechou = asyncio.run(corrida())
    assert no_modo == 0.5
    assert fora_do_modo == 1.0
    assert fechou == 1.0


def test_jogo_com_anticheat_recusa_sem_a_chave_e_aceita_com_a_chave_ligada(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(porta_mod, "anticheat_do_jogo", lambda _p, appid: "EasyAntiCheat")
    chaves = ChavesDaMemoria(arquivo_das_chaves().with_name(porta_mod.ARQUIVO_DO_PESO_DA_MIRA))

    async def corrida() -> tuple[dict[str, Any], dict[str, Any]]:
        with tempfile.TemporaryDirectory(prefix="pm") as pasta:
            bus = EventBus()
            bus.publish(EventTopic.JOGO_IDENTIDADE, {"chave": "steam_app_4242"})
            porta, com = await _sessao(Path(pasta) / "c.sock", bus, ["escrever:mira"])
            try:
                sem_chave = await asyncio.to_thread(com.pedir, "mira.peso", _pedido())
                chaves.gravar("steam_app_4242", True, anticheat="EasyAntiCheat",
                              aviso_visto=True)
                com_chave = await asyncio.to_thread(com.pedir, "mira.peso", _pedido())
            finally:
                com.fechar()
                await porta.parar()
            return sem_chave, com_chave

    sem_chave, com_chave = asyncio.run(corrida())
    assert sem_chave["error"]["code"] == CODE_NAO_ESCREVEU
    assert com_chave["result"] == {"status": "ok"}


def test_com_a_secao_controles_fora_do_modo_da_extensao_o_pedido_recusa(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tato_vivo, "_MODO_DA_ABA_DITO", {P1: {
        "uniq": P1, "jogador": 1, "secoes": {"controles": "personalizado"}}})

    async def corrida() -> tuple[dict[str, Any], dict[str, Any], float]:
        with tempfile.TemporaryDirectory(prefix="pm") as pasta:
            bus = EventBus()
            porta, com = await _sessao(Path(pasta) / "f.sock", bus, ["escrever:mira"])
            try:
                um = await asyncio.to_thread(com.pedir, "mira.peso", _pedido())
                todos = await asyncio.to_thread(com.pedir, "mira.peso", {
                    "uniq": roteador.TODOS_OS_CONTROLES, "ganho": 0.5, "ate_ms": 5000})
                ganho = roteador.PESO_DA_MIRA.ganho(P1)
            finally:
                com.fechar()
                await porta.parar()
            return um, todos, ganho

    um, todos, ganho = asyncio.run(corrida())
    assert um["error"]["code"] == CODE_NAO_ESCREVEU
    assert todos["error"]["code"] == CODE_NAO_ESCREVEU
    assert ganho == 1.0
