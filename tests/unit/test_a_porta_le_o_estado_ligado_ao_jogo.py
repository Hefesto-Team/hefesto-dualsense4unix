"""A porta lê o estado que a receita declara, ligada ao jogo de verdade (02/11/2026, ensaio).

O ``hefesto-launch.sh`` põe o leitor como pai do jogo só com a chave «Memória» dele ligada; o
leitor atende a porta pelo soquete da pasta de execução, e a extensão que assina ``jogo.memoria``
com as linhas da receita recebe os valores. Com a chave desligada, o jogo abre sem o leitor.
"""
from __future__ import annotations

import asyncio
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.integrations import leitor_do_estado as leitor
from hefesto_dualsense4unix.mods.porta import Porta
from tests.unit.test_a_coluna_agora_e_o_parar_tudo_vem_do_servico import (  # noqa: F401
    _Extensao,
    curto,
)

RAIZ = pathlib.Path(__file__).resolve().parents[2]
LANCADOR = RAIZ / "assets" / "hefesto-launch.sh"
APPID = "4242"
VALOR = 0x5EED1234
JOGO = r"""
import ctypes, os, sys
v = ctypes.c_int32(VALOR)
print(ctypes.addressof(v), os.getppid(), flush=True)
for linha in sys.stdin:
    v.value = int(linha)
    print("ok", flush=True)
""".replace("VALOR", str(VALOR))


@pytest.fixture
def lar(curto: pathlib.Path, tmp_path: pathlib.Path) -> Iterator[dict[str, str]]:  # noqa: F811
    home = tmp_path / "home"
    bin_ = home / ".local" / "share" / "hefesto-dualsense4unix" / "bin"
    bin_.mkdir(parents=True)
    fonte = RAIZ / "src" / "hefesto_dualsense4unix" / "integrations"
    shutil.copy(fonte / "leitor_do_estado.py", bin_ / "hefesto-leitor-do-estado")
    shutil.copy(fonte / "anticheat_conhecido.json", bin_ / "anticheat_conhecido.json")
    mudos = tmp_path / "mudos"
    mudos.mkdir()
    for nome in ("system76-power", "busctl", "dbus-send", "sudo"):
        falso = mudos / nome
        falso.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        falso.chmod(0o755)
    runtime = curto / "run"
    runtime.mkdir(mode=0o700)
    yield {
        "HOME": str(home),
        "PATH": f"{mudos}:/usr/bin:/bin",
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_STATE_HOME": str(tmp_path / "state"),
        "XDG_RUNTIME_DIR": str(runtime),
        "SteamAppId": APPID,
    }


def _chave(env: dict[str, str], ligada: bool) -> None:
    leitor.ChavesDaMemoria(leitor.arquivo_das_chaves(env)).gravar(f"steam_app_{APPID}", ligada)


def _lancar(env: dict[str, str]) -> tuple[subprocess.Popen[str], int, int]:
    proc = subprocess.Popen(["/bin/sh", str(LANCADOR), sys.executable, "-I", "-c", JOGO],
                            env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    assert proc.stdout is not None
    endereco, pai = (int(x) for x in proc.stdout.readline().split())
    return proc, endereco, pai


def _fechar(proc: subprocess.Popen[str]) -> None:
    assert proc.stdin is not None
    proc.stdin.close()
    proc.wait(timeout=30)


def _soquete(env: dict[str, str], segundos: float = 15.0) -> pathlib.Path:
    caminho = leitor.caminho_do_soquete(env)
    fim = time.monotonic() + segundos
    while not caminho.is_socket() and time.monotonic() < fim:
        time.sleep(0.05)
    return caminho


def _perguntar(caminho: pathlib.Path, pedido: dict[str, Any]) -> dict[str, Any]:
    with socket.socket(socket.AF_UNIX) as s:
        s.settimeout(10)
        s.connect(str(caminho))
        s.sendall(json.dumps(pedido).encode() + b"\n")
        resposta: dict[str, Any] = json.loads(s.makefile("rb").readline())
    return resposta


def _entradas(endereco: int) -> list[dict[str, Any]]:
    return [{"nome": "vida", "cadeia_de_ponteiros": [endereco], "tipo": "i32",
             "hz": 30}]


def test_com_a_chave_ligada_o_leitor_e_pai_do_jogo_e_le_o_valor_declarado(lar) -> None:
    _chave(lar, True)
    proc, endereco, pai = _lancar(lar)
    try:
        caminho = _soquete(lar)
        assert caminho.is_socket()
        assert oct(caminho.stat().st_mode & 0o777) == oct(0o600)
        lido = _perguntar(caminho, {"verbo": "ler", "entradas": _entradas(endereco)})
        assert lido["valores"]["vida"] == VALOR, lido
        assert pai == proc.pid
    finally:
        _fechar(proc)
    assert proc.returncode == 0
    assert not leitor.caminho_do_soquete(lar).exists()


def test_com_a_chave_desligada_o_jogo_abre_sem_o_leitor(lar) -> None:
    _chave(lar, False)
    proc, _endereco, pai = _lancar(lar)
    try:
        assert pai != proc.pid
        time.sleep(0.5)
        assert not leitor.caminho_do_soquete(lar).exists()
    finally:
        _fechar(proc)


def test_sem_registro_do_jogo_o_lancador_nem_chama_o_leitor(lar) -> None:
    proc, _endereco, pai = _lancar(lar)
    try:
        assert pai != proc.pid
        assert not leitor.caminho_do_soquete(lar).exists()
    finally:
        _fechar(proc)


def test_a_chave_desligada_no_meio_para_a_leitura(lar) -> None:
    _chave(lar, True)
    proc, endereco, _pai = _lancar(lar)
    try:
        caminho = _soquete(lar)
        assert "valores" in _perguntar(caminho, {"verbo": "ler", "entradas": _entradas(endereco)})
        _chave(lar, False)
        resposta = _perguntar(caminho, {"verbo": "ler", "entradas": _entradas(endereco)})
        assert "recusa" in resposta and "valores" not in resposta
    finally:
        _fechar(proc)


def test_a_varredura_pela_porta_devolve_token_e_contagem(lar) -> None:
    _chave(lar, True)
    proc, _endereco, _pai = _lancar(lar)
    try:
        caminho = _soquete(lar)
        resposta = _perguntar(caminho, {"verbo": "varrer", "tipo": "i32", "valor": VALOR})
        assert set(resposta) == {"token", "contagem"} and resposta["contagem"] >= 1, resposta
    finally:
        _fechar(proc)


def test_a_extensao_assinante_recebe_o_valor_pela_porta(lar, curto, monkeypatch) -> None:  # noqa: F811
    _chave(lar, True)
    monkeypatch.setenv("XDG_RUNTIME_DIR", lar["XDG_RUNTIME_DIR"])
    proc, endereco, _pai = _lancar(lar)

    async def corrida() -> dict[str, Any] | None:
        async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
            return {"status": "ok"}

        porta = Porta(curto / "mods.sock", EventBus(), escritor=escritor,
                      o_jogo_escreve=lambda uniq, canal: False, uniq_do_posto=lambda: None)
        await porta.iniciar()
        porta.registrar("ficha-m", "imersao", os.getpid(), ["ler:jogo.memoria"])
        ext = _Extensao(curto / "mods.sock")
        try:
            await asyncio.to_thread(ext.pedir, "mod.ola", {"ficha": "ficha-m"})
            assinou = await asyncio.to_thread(ext.pedir, "eventos.assinar", {
                "topicos": ["jogo.memoria"], "memoria": {"entradas": _entradas(endereco)}})
            assert "result" in assinou, assinou
            return await asyncio.to_thread(ext.esperar_evento, 15.0)
        finally:
            ext.fechar()
            await porta.parar()

    try:
        _soquete(lar)
        evento = asyncio.run(corrida())
    finally:
        _fechar(proc)
    assert evento is not None
    assert evento["params"]["topico"] == "jogo.memoria"
    assert evento["params"]["dados"]["vida"] == VALOR


def test_a_assinatura_sem_as_linhas_da_receita_e_recusada(curto) -> None:  # noqa: F811
    async def corrida() -> list[dict[str, Any]]:
        async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
            return {"status": "ok"}

        porta = Porta(curto / "mods.sock", EventBus(), escritor=escritor,
                      o_jogo_escreve=lambda uniq, canal: False, uniq_do_posto=lambda: None)
        await porta.iniciar()
        porta.registrar("ficha-m", "imersao", os.getpid(), ["ler:jogo.memoria"])
        ext = _Extensao(curto / "mods.sock")
        try:
            await asyncio.to_thread(ext.pedir, "mod.ola", {"ficha": "ficha-m"})
            return [
                await asyncio.to_thread(ext.pedir, "eventos.assinar", params)
                for params in (
                    {"topicos": ["jogo.memoria"]},
                    {"topicos": ["jogo.memoria"], "memoria": {"entradas": [{"nome": "X"}]}},
                )
            ]
        finally:
            ext.fechar()
            await porta.parar()

    for resposta in asyncio.run(corrida()):
        assert "error" in resposta and "result" not in resposta, resposta


def test_a_varredura_sem_a_permissao_e_recusada(curto) -> None:  # noqa: F811
    async def corrida() -> dict[str, Any]:
        async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
            return {"status": "ok"}

        porta = Porta(curto / "mods.sock", EventBus(), escritor=escritor,
                      o_jogo_escreve=lambda uniq, canal: False, uniq_do_posto=lambda: None)
        await porta.iniciar()
        porta.registrar("ficha-s", "sem", os.getpid(), ["ler:botoes"])
        ext = _Extensao(curto / "mods.sock")
        try:
            await asyncio.to_thread(ext.pedir, "mod.ola", {"ficha": "ficha-s"})
            return await asyncio.to_thread(ext.pedir, "memoria.varrer",
                                           {"tipo": "i32", "valor": 1})
        finally:
            ext.fechar()
            await porta.parar()

    resposta = asyncio.run(corrida())
    assert "error" in resposta, resposta
