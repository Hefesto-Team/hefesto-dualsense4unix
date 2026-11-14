"""A porta só abre o que a extensão não escreve (14/11/2026).

O ``lancador.abrir`` roda fora da caixa, então o ``argv[0]`` tem de ser um nome nu, achado pelo
``PATH`` da sessão num arquivo de verdade que não é shell nem interpretador (pelo nome e pelo alvo
do link) e que não mora nas pastas de código ou de dados das extensões; os termos seguintes não
levam «/». A ``vibracao.escala`` tem a guarda de modo da mira e sai quando o controle deixa o modo
da extensão. O giro desligado e o peso da mira saem quando o jogo troca para um com anticheat e a
chave dele está desligada.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import struct
import tempfile
from collections.abc import Iterator, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import roteador_de_movimento as roteador
from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon import ipc_rumble_policy as politica
from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo
from hefesto_dualsense4unix.integrations import prontuario_dos_jogos
from hefesto_dualsense4unix.integrations.leitor_do_estado import (
    ChavesDaMemoria,
    arquivo_das_chaves,
)
from hefesto_dualsense4unix.mods import porta as porta_mod
from hefesto_dualsense4unix.mods.porta import CODE_NAO_ESCREVEU, CODE_SEM_PERMISSAO, Porta
from hefesto_dualsense4unix.utils import xdg_paths
from tests.unit.test_a_porta_ouve_o_jogo_e_o_microfone import _Cliente

MESA = ("aa:bb:cc:00:00:81", "aa:bb:cc:00:00:82", "02:fe:00:00:00:83", "02:fe:00:00:00:84")
P1, P2, P3, P4 = MESA
JANELA = struct.pack("<3h", 1000, -2000, 3000) + bytes(range(22))
SEM_ANTICHEAT = "steam_app_1111"
COM_ANTICHEAT = "steam_app_4242"


def _modos(no_modo: Sequence[str]) -> dict[str, dict[str, Any]]:
    return {u: {"uniq": u, "jogador": i, "secoes": {
        "controles": "extensao:hook" if u in no_modo else "personalizado"}}  # (noqa-acento)
        for i, u in enumerate(MESA, 1)}


@pytest.fixture(autouse=True)
def _limpo(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(tato_vivo, "_MODO_DA_ABA_DITO", _modos(MESA))
    roteador.PESO_DA_MIRA.soltar()
    roteador.PESO_DA_MIRA.religar_de("hook")
    politica.ESCALA_DA_VIBRACAO.soltar()
    yield
    roteador.PESO_DA_MIRA.soltar()
    roteador.PESO_DA_MIRA.religar_de("hook")
    politica.ESCALA_DA_VIBRACAO.soltar()


def _executavel(caminho: Path) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("#!/bin/sh\nexit 0\n")
    caminho.chmod(0o755)
    return caminho


@pytest.fixture
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    programas, dados, bin_ = tmp_path / "programas", tmp_path / "dados", tmp_path / "bin"
    monkeypatch.setattr(xdg_paths, "mods_codigo_dir", lambda: programas)
    monkeypatch.setattr(xdg_paths, "mods_dados_dir", lambda: dados)
    lancador = _executavel(bin_ / "hefesto-hookshot")
    sh = shutil.which("sh")
    assert sh is not None
    (bin_ / "abre-o-jogo").symlink_to(sh)
    _executavel(dados / "hook" / "joguinho")
    (bin_ / "atalho-dos-programas").symlink_to(_executavel(programas / "hook" / "abre"))
    (bin_ / "atalho-dos-dados").symlink_to(dados / "hook" / "joguinho")
    (bin_ / "sem-execucao").write_text("#!/bin/sh\n")
    caminho = [str(bin_), str(dados / "hook"), "/usr/bin", "/bin"]
    monkeypatch.setenv("PATH", os.pathsep.join(caminho))
    return SimpleNamespace(lancador=lancador, bin=bin_)


class _Abridor:
    def __init__(self) -> None:
        self.abertos: list[tuple[str, list[str]]] = []

    def __call__(self, mod_id: str, argv: Sequence[str]) -> str:
        self.abertos.append((mod_id, list(argv)))
        return "unidade"


async def _porta(caminho: Path, abridor: _Abridor, bus: EventBus | None = None) -> Porta:
    async def escritor(_m: str, _p: dict[str, Any]) -> Any:
        return {"status": "ok"}

    porta = Porta(caminho, bus or EventBus(), escritor=escritor,
                  o_jogo_escreve=lambda _u, _c: False,
                  uniq_do_posto=lambda: P1, abrir_o_jogo=abridor)
    await porta.iniciar()
    return porta


async def _entrar(porta: Porta, caminho: Path, permissoes: list[str],
                  comandos: Sequence[str] = ("hefesto-hookshot",)) -> _Cliente:
    porta.registrar("f-c", "hook", os.getpid(), permissoes, comandos=tuple(comandos))
    cliente = _Cliente(caminho)
    await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "f-c"})
    return cliente


RECUSADOS = (
    ["bash", "-c", "x"], ["bash"], ["/usr/bin/python3"], ["python3"], ["python3.12"], ["env"],
    ["sh"], ["dash"], ["perl"], ["node"], ["busybox"], ["xargs"], ["nohup"], ["setsid"],
    ["flatpak-spawn"], ["abre-o-jogo"], ["joguinho"], ["atalho-dos-programas"],
    ["atalho-dos-dados"],
    ["sem-execucao"], ["nao-existe"], ["./hefesto-hookshot"], ["hefesto-hookshot", "a/b"],
    ["hefesto-hookshot", "-x"], ["hefesto-hookshot", ".."],
)


@pytest.mark.parametrize("argv", RECUSADOS, ids="+".join)
def test_o_comando_que_sai_da_caixa_recusa_e_o_do_lancador_abre(
        lar: SimpleNamespace, argv: list[str]) -> None:
    async def corrida() -> tuple[dict[str, Any], dict[str, Any], list[tuple[str, list[str]]]]:
        with tempfile.TemporaryDirectory(prefix="pa") as pasta:
            caminho = Path(pasta) / "m.sock"
            abridor = _Abridor()
            porta = await _porta(caminho, abridor)
            com = await _entrar(porta, caminho, ["lancador", "pedir:lancador.abrir"],
                                ("hefesto-hookshot", argv[0]))
            try:
                await asyncio.to_thread(com.pedir, "lancador.jogos", {"jogos": [
                    {"chave": "ruim", "nome": "Ruim", "abrir": argv},
                    {"chave": "bom", "nome": "Bom", "abrir": ["hefesto-hookshot", "ocarina_1.0"]},
                ]})
                ruim = await asyncio.to_thread(com.pedir, "lancador.abrir", {"chave": "ruim"})
                bom = await asyncio.to_thread(com.pedir, "lancador.abrir", {"chave": "bom"})
            finally:
                com.fechar()
                await porta.parar()
            return ruim, bom, abridor.abertos

    ruim, bom, abertos = asyncio.run(corrida())
    assert ruim["error"]["code"] in (CODE_NAO_ESCREVEU, CODE_SEM_PERMISSAO)
    if ruim["error"]["code"] == CODE_NAO_ESCREVEU:
        assert ruim["error"]["message"] == "o jogo não abriu"
    assert bom["result"] == {"aberto": True, "chave": "bom"}
    assert abertos == [("hook", [os.path.realpath(lar.lancador), "ocarina_1.0"])]


def test_o_comando_e_conferido_na_hora_de_abrir_e_nao_so_na_lista(lar: SimpleNamespace) -> None:
    async def corrida() -> tuple[dict[str, Any], list[tuple[str, list[str]]]]:
        with tempfile.TemporaryDirectory(prefix="pa") as pasta:
            caminho = Path(pasta) / "m.sock"
            abridor = _Abridor()
            porta = await _porta(caminho, abridor)
            com = await _entrar(porta, caminho, ["lancador", "pedir:lancador.abrir"])
            try:
                await asyncio.to_thread(com.pedir, "lancador.jogos", {"jogos": [
                    {"chave": "bom", "nome": "Bom", "abrir": ["hefesto-hookshot"]}]})
                lar.lancador.unlink()
                lar.lancador.symlink_to(xdg_paths.mods_dados_dir() / "hook" / "joguinho")
                trocado = await asyncio.to_thread(com.pedir, "lancador.abrir", {"chave": "bom"})
            finally:
                com.fechar()
                await porta.parar()
            return trocado, abridor.abertos

    trocado, abertos = asyncio.run(corrida())
    assert trocado["error"] == {"code": CODE_NAO_ESCREVEU, "message": "o jogo não abriu"}
    assert abertos == []


def _forca(uniq: str) -> int:
    daemon = SimpleNamespace(config=DaemonConfig(), controller=SimpleNamespace())
    return politica.apply_rumble_policy(daemon, 200, 200, uniq=uniq)[0]


@pytest.mark.parametrize("fora", MESA)
def test_vibracao_escala_fora_do_modo_recusa_e_quem_sai_do_modo_volta_a_forca_inteira(
        monkeypatch: pytest.MonkeyPatch, fora: str) -> None:
    no_modo = [u for u in MESA if u != fora]
    monkeypatch.setattr(tato_vivo, "_MODO_DA_ABA_DITO", _modos(no_modo))
    sai, fica = no_modo[0], no_modo[1:]

    async def corrida() -> tuple[dict[str, Any], dict[str, int], dict[str, int]]:
        with tempfile.TemporaryDirectory(prefix="pa") as pasta:
            bus = EventBus()
            bus.bind_loop(asyncio.get_running_loop())
            caminho = Path(pasta) / "m.sock"
            porta = await _porta(caminho, _Abridor(), bus)
            com = await _entrar(porta, caminho, ["escrever:vibracao"])
            try:
                recusa = await asyncio.to_thread(
                    com.pedir, "vibracao.escala", {"uniq": fora, "escala": 0.5})
                for uniq in no_modo:
                    await asyncio.to_thread(
                        com.pedir, "vibracao.escala", {"uniq": uniq, "escala": 0.5})
                durante = {u: _forca(u) for u in MESA}
                bus.publish(EventTopic.MODO_ABA, {"uniq": sai, "secoes": {
                    "controles": "personalizado"}})
                for _ in range(100):
                    if politica.ESCALA_DA_VIBRACAO.de(sai) == 1.0:
                        break
                    await asyncio.sleep(0.02)
                depois = {u: _forca(u) for u in MESA}
            finally:
                com.fechar()
                await porta.parar()
            return recusa, durante, depois

    inteira = _forca(P1)
    recusa, durante, depois = asyncio.run(corrida())
    assert recusa["error"]["code"] == CODE_NAO_ESCREVEU
    metade = round(inteira / 2)
    assert durante == {u: (inteira if u == fora else metade) for u in MESA}
    assert depois == {u: (metade if u in fica else inteira) for u in MESA}


@pytest.mark.parametrize("alvo", MESA)
def test_o_jogo_que_troca_para_um_com_anticheat_religa_o_giro_e_solta_o_peso(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path, alvo: str) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    raiz_com = tmp_path / "com"
    (raiz_com / "EasyAntiCheat").mkdir(parents=True)
    raiz_sem = tmp_path / "sem"
    raiz_sem.mkdir()
    monkeypatch.setattr(prontuario_dos_jogos, "jogos_instalados", lambda: [
        ("1111", "Sem", raiz_sem), ("4242", "Com", raiz_com)])

    async def corrida() -> tuple[bytes, bytes, bool]:
        with tempfile.TemporaryDirectory(prefix="pa") as pasta:
            bus = EventBus()
            bus.bind_loop(asyncio.get_running_loop())
            bus.publish(EventTopic.JOGO_IDENTIDADE, {"chave": SEM_ANTICHEAT})
            caminho = Path(pasta) / "m.sock"
            porta = await _porta(caminho, _Abridor(), bus)
            com = await _entrar(porta, caminho, ["escrever:mira"])
            try:
                desligado = await asyncio.to_thread(
                    com.pedir, "mira.ligada", {"uniq": alvo, "ligada": False})
                pesado = await asyncio.to_thread(
                    com.pedir, "mira.peso", {"uniq": alvo, "ganho": 0.5, "ate_ms": 10_000})
                assert desligado["result"]["ligada"] is False
                assert pesado["result"] == {"status": "ok"}
                no_jogo_sem = roteador.janela_que_sai(alvo, JANELA)
                bus.publish(EventTopic.JOGO_IDENTIDADE, {"chave": COM_ANTICHEAT})
                for _ in range(150):
                    if roteador.janela_que_sai(alvo, JANELA) == JANELA:
                        break
                    await asyncio.sleep(0.02)
                no_jogo_com = roteador.janela_que_sai(alvo, JANELA)
                peso_ficou = bool(roteador.PESO_DA_MIRA.donos())
            finally:
                com.fechar()
                await porta.parar()
            return no_jogo_sem, no_jogo_com, peso_ficou

    no_jogo_sem, no_jogo_com, peso_ficou = asyncio.run(corrida())
    assert struct.unpack_from("<3h", no_jogo_sem) == (0, 0, 0)
    assert no_jogo_com == JANELA
    assert peso_ficou is False


def test_com_a_chave_do_jogo_ligada_o_giro_fica_desligado_na_troca(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    raiz_com = tmp_path / "com"
    (raiz_com / "EasyAntiCheat").mkdir(parents=True)
    monkeypatch.setattr(prontuario_dos_jogos, "jogos_instalados", lambda: [
        ("1111", "Sem", tmp_path), ("4242", "Com", raiz_com)])
    ChavesDaMemoria(arquivo_das_chaves().with_name(porta_mod.ARQUIVO_DO_PESO_DA_MIRA)).gravar(
        COM_ANTICHEAT, True, anticheat="Easy Anti-Cheat", aviso_visto=True)

    async def corrida() -> bytes:
        with tempfile.TemporaryDirectory(prefix="pa") as pasta:
            bus = EventBus()
            bus.bind_loop(asyncio.get_running_loop())
            caminho = Path(pasta) / "m.sock"
            porta = await _porta(caminho, _Abridor(), bus)
            com = await _entrar(porta, caminho, ["escrever:mira"])
            try:
                await asyncio.to_thread(com.pedir, "mira.ligada", {"uniq": P2, "ligada": False})
                bus.publish(EventTopic.JOGO_IDENTIDADE, {"chave": COM_ANTICHEAT})
                await asyncio.sleep(0.3)
                return roteador.janela_que_sai(P2, JANELA)
            finally:
                com.fechar()
                await porta.parar()

    assert struct.unpack_from("<3h", asyncio.run(corrida())) == (0, 0, 0)
