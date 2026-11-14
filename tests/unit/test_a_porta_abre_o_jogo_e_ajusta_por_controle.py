"""A porta abre o jogo e ajusta por controle (14/11/2026).

``lancador.abrir {chave}`` com ``pedir:lancador.abrir`` abre só o jogo que a própria extensão
entregou no ``lancador.jogos``, pelo abridor do serviço (fora da caixa, pelo ``hefesto-launch``).
``mira.ligada`` (``escrever:mira``) desliga o giroscópio de um controle, na máscara DualSense e na
Xbox, e ``vibracao.escala`` (``escrever:vibracao``) multiplica a força do motor daquele controle no
funil único; os dois valem enquanto a extensão vale, por controle, de um a quatro.
"""
from __future__ import annotations

import asyncio
import os
import struct
import tempfile
from collections.abc import Iterator, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import roteador_de_movimento as roteador
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon import ipc_rumble_policy as politica
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.mods import porta as porta_mod
from hefesto_dualsense4unix.mods.manifesto import permissao_valida
from hefesto_dualsense4unix.mods.porta import (
    CODE_INVALID_PARAMS,
    CODE_NAO_ESCREVEU,
    CODE_SEM_PERMISSAO,
    Porta,
)
from tests.unit.test_a_porta_ouve_o_jogo_e_o_microfone import _Cliente

MESA = ("aa:bb:cc:00:00:71", "aa:bb:cc:00:00:72", "02:fe:00:00:00:73", "02:fe:00:00:00:74")
P1, P2, P3, P4 = MESA
JANELA = struct.pack("<3h", 1000, -2000, 3000) + bytes(range(22))
JOGO = {"chave": "zelda", "nome": "Ocarina", "abrir": ["hefesto-hookshot"], "janela": "hookshot"}


@pytest.fixture(autouse=True)
def _limpo() -> Iterator[None]:
    roteador.PESO_DA_MIRA.soltar()
    for dono in ("hook", "outra"):
        roteador.PESO_DA_MIRA.religar_de(dono)
    politica.ESCALA_DA_VIBRACAO.soltar()
    yield
    roteador.PESO_DA_MIRA.soltar()
    for dono in ("hook", "outra"):
        roteador.PESO_DA_MIRA.religar_de(dono)
    politica.ESCALA_DA_VIBRACAO.soltar()


class _Abridor:
    def __init__(self, falha: Exception | None = None) -> None:
        self.abertos: list[tuple[str, list[str]]] = []
        self.falha = falha

    def __call__(self, mod_id: str, argv: Sequence[str]) -> str:
        if self.falha is not None:
            raise self.falha
        self.abertos.append((mod_id, list(argv)))
        return "unidade"


async def _porta(caminho: Path, abridor: _Abridor) -> Porta:
    async def escritor(_m: str, _p: dict[str, Any]) -> Any:
        return {"status": "ok"}

    porta = Porta(caminho, EventBus(), escritor=escritor, o_jogo_escreve=lambda _u, _c: False,
                  uniq_do_posto=lambda: P1, abrir_o_jogo=abridor)
    await porta.iniciar()
    return porta


async def _entrar(porta: Porta, caminho: Path, ficha: str, mod_id: str,
                  permissoes: list[str]) -> _Cliente:
    porta.registrar(ficha, mod_id, os.getpid(), permissoes, comandos=("hefesto-hookshot",))
    cliente = _Cliente(caminho)
    await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": ficha})
    return cliente


def test_as_permissoes_e_o_topico_novos_estao_no_manifesto() -> None:
    assert permissao_valida("pedir:lancador.abrir")
    assert permissao_valida("ler:jogo.estilo")


def test_lancador_abrir_sem_permissao_recusa_e_com_o_id_de_outra_extensao_recusa() -> None:
    async def corrida() -> tuple[dict[str, Any], ...]:
        with tempfile.TemporaryDirectory(prefix="pa") as pasta:
            caminho = Path(pasta) / "m.sock"
            abridor = _Abridor()
            porta = await _porta(caminho, abridor)
            outra = await _entrar(porta, caminho, "f-o", "outra",
                                  ["lancador", "pedir:lancador.abrir"])
            sem = await _entrar(porta, caminho, "f-s", "sem", ["lancador"])
            com = await _entrar(porta, caminho, "f-c", "hook",
                                ["lancador", "pedir:lancador.abrir"])
            try:
                await asyncio.to_thread(outra.pedir, "lancador.jogos", {"jogos": [
                    {**JOGO, "chave": "da-outra"}]})
                await asyncio.to_thread(com.pedir, "lancador.jogos", {"jogos": [JOGO]})
                sem_permissao = await asyncio.to_thread(
                    sem.pedir, "lancador.abrir", {"chave": "zelda"})
                de_outra = await asyncio.to_thread(
                    com.pedir, "lancador.abrir", {"chave": "da-outra"})
                desconhecido = await asyncio.to_thread(
                    com.pedir, "lancador.abrir", {"chave": "nenhum"})
                aberto = await asyncio.to_thread(com.pedir, "lancador.abrir", {"chave": "zelda"})
                assert abridor.abertos == [("hook", ["hefesto-hookshot"])]
            finally:
                for cliente in (outra, sem, com):
                    cliente.fechar()
                await porta.parar()
            return sem_permissao, de_outra, desconhecido, aberto

    sem_permissao, de_outra, desconhecido, aberto = asyncio.run(corrida())
    assert sem_permissao["error"]["code"] == CODE_SEM_PERMISSAO
    assert "pedir:lancador.abrir" in sem_permissao["error"]["message"]
    assert de_outra["error"]["code"] == CODE_SEM_PERMISSAO
    assert "outra extensão" in de_outra["error"]["message"]
    assert desconhecido["error"]["code"] == CODE_INVALID_PARAMS
    assert aberto["result"] == {"aberto": True, "chave": "zelda"}


def test_o_jogo_que_nao_abre_volta_com_o_motivo() -> None:
    async def corrida() -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="pa") as pasta:
            caminho = Path(pasta) / "m.sock"
            porta = await _porta(caminho, _Abridor(OSError("sem systemd")))
            com = await _entrar(porta, caminho, "f-c", "hook",
                                ["lancador", "pedir:lancador.abrir"])
            try:
                await asyncio.to_thread(com.pedir, "lancador.jogos", {"jogos": [JOGO]})
                return await asyncio.to_thread(com.pedir, "lancador.abrir", {"chave": "zelda"})
            finally:
                com.fechar()
                await porta.parar()

    falhou = asyncio.run(corrida())
    assert falhou["error"]["code"] == CODE_NAO_ESCREVEU
    assert "sem systemd" in falhou["error"]["message"]


def test_o_abridor_do_servico_recusa_sob_a_suite() -> None:
    with pytest.raises(OSError):
        porta_mod.abrir_pelo_lancador("hook", ["hefesto-hookshot"])


def _forca(uniq: str) -> int:
    daemon = SimpleNamespace(config=DaemonConfig(), controller=SimpleNamespace())
    return politica.apply_rumble_policy(daemon, 200, 200, uniq=uniq)[0]


@pytest.mark.parametrize("alvo", MESA)
def test_vibracao_escala_pela_metade_corta_so_aquele_controle(alvo: str) -> None:
    async def corrida() -> tuple[dict[str, Any], dict[str, Any], dict[str, int], dict[str, int]]:
        with tempfile.TemporaryDirectory(prefix="pa") as pasta:
            caminho = Path(pasta) / "m.sock"
            porta = await _porta(caminho, _Abridor())
            sem = await _entrar(porta, caminho, "f-s", "outra", ["escrever:luz"])
            com = await _entrar(porta, caminho, "f-c", "hook", ["escrever:vibracao"])
            try:
                recusa = await asyncio.to_thread(
                    sem.pedir, "vibracao.escala", {"uniq": alvo, "escala": 0.5})
                aceito = await asyncio.to_thread(
                    com.pedir, "vibracao.escala", {"uniq": alvo, "escala": 0.5})
                durante = {u: _forca(u) for u in MESA}
                com.fechar()
                for _ in range(100):
                    if politica.ESCALA_DA_VIBRACAO.de(alvo) == 1.0:
                        break
                    await asyncio.sleep(0.02)
                depois = {u: _forca(u) for u in MESA}
            finally:
                sem.fechar()
                await porta.parar()
            return recusa, aceito, durante, depois

    inteira = _forca(P1)
    recusa, aceito, durante, depois = asyncio.run(corrida())
    assert recusa["error"]["code"] == CODE_SEM_PERMISSAO
    assert aceito["result"] == {"status": "ok", "escala": 0.5}
    assert inteira > 0
    assert durante == {u: (round(inteira / 2) if u == alvo else inteira) for u in MESA}
    assert depois == dict.fromkeys(MESA, inteira)


def test_vibracao_escala_fora_da_faixa_ou_sem_uniq_recusa() -> None:
    async def corrida() -> list[dict[str, Any]]:
        with tempfile.TemporaryDirectory(prefix="pa") as pasta:
            caminho = Path(pasta) / "m.sock"
            porta = await _porta(caminho, _Abridor())
            com = await _entrar(porta, caminho, "f-c", "hook", ["escrever:vibracao"])
            try:
                return [await asyncio.to_thread(com.pedir, "vibracao.escala", p) for p in (
                    {"uniq": P2, "escala": 1.5}, {"escala": 0.5}, {"uniq": P2, "escala": True})]
            finally:
                com.fechar()
                await porta.parar()

    for resposta in asyncio.run(corrida()):
        assert resposta["error"]["code"] == CODE_INVALID_PARAMS


@pytest.mark.parametrize("alvo", MESA)
def test_mira_ligada_false_desliga_o_giro_so_daquele_controle_nas_duas_mascaras(alvo: str) -> None:
    arranjo = roteador.ArranjoDeMovimento(destino=roteador.DESTINO_ANALOGICO_DIREITO)
    giro = (40.0, 60.0, 0.0)

    def deflexao(uniq: str) -> tuple[int, int]:
        roteador.zerar_o_resto(SimpleNamespace(), uniq)
        return roteador.deflexao_do_tique(SimpleNamespace(), uniq, giro, arranjo,
                                          roteador.PESO_DA_MIRA.ganho(uniq))

    async def corrida() -> tuple[dict[str, Any], ...]:
        with tempfile.TemporaryDirectory(prefix="pa") as pasta:
            caminho = Path(pasta) / "m.sock"
            porta = await _porta(caminho, _Abridor())
            sem = await _entrar(porta, caminho, "f-s", "outra", ["escrever:vibracao"])
            com = await _entrar(porta, caminho, "f-c", "hook", ["escrever:mira"])
            try:
                recusa = await asyncio.to_thread(
                    sem.pedir, "mira.ligada", {"uniq": alvo, "ligada": False})
                desligada = await asyncio.to_thread(
                    com.pedir, "mira.ligada", {"uniq": alvo, "ligada": False})
                for uniq in MESA:
                    janela = roteador.janela_que_sai(uniq, JANELA)
                    if uniq == alvo:
                        assert struct.unpack_from("<3h", janela) == (0, 0, 0)
                        assert janela[6:] == JANELA[6:]
                        assert deflexao(uniq) == (0, 0)
                    else:
                        assert janela == JANELA
                        assert deflexao(uniq) != (0, 0)
                ligada = await asyncio.to_thread(
                    com.pedir, "mira.ligada", {"uniq": alvo, "ligada": True})
                assert roteador.janela_que_sai(alvo, JANELA) == JANELA
                await asyncio.to_thread(com.pedir, "mira.ligada", {"uniq": alvo, "ligada": False})
                com.fechar()
                for _ in range(100):
                    if roteador.janela_que_sai(alvo, JANELA) == JANELA:
                        break
                    await asyncio.sleep(0.02)
                assert roteador.janela_que_sai(alvo, JANELA) == JANELA
            finally:
                sem.fechar()
                await porta.parar()
            return recusa, desligada, ligada

    recusa, desligada, ligada = asyncio.run(corrida())
    assert recusa["error"]["code"] == CODE_SEM_PERMISSAO
    assert desligada["result"] == {"status": "ok", "ligada": False}
    assert ligada["result"] == {"status": "ok", "ligada": True}


def test_o_giro_desligado_sobrevive_ao_jogo_que_fecha_e_sai_no_parar_tudo() -> None:
    async def corrida() -> tuple[bytes, bytes]:
        with tempfile.TemporaryDirectory(prefix="pa") as pasta:
            caminho = Path(pasta) / "m.sock"
            porta = await _porta(caminho, _Abridor())
            com = await _entrar(porta, caminho, "f-c", "hook", ["escrever:mira"])
            try:
                await asyncio.to_thread(com.pedir, "mira.ligada", {"uniq": P3, "ligada": False})
                roteador.PESO_DA_MIRA.soltar()
                depois_do_jogo = roteador.janela_que_sai(P3, JANELA)
                porta.parar_tudo("hook")
                depois_do_parar = roteador.janela_que_sai(P3, JANELA)
            finally:
                com.fechar()
                await porta.parar()
            return depois_do_jogo, depois_do_parar

    depois_do_jogo, depois_do_parar = asyncio.run(corrida())
    assert struct.unpack_from("<3h", depois_do_jogo) == (0, 0, 0)
    assert depois_do_parar == JANELA
