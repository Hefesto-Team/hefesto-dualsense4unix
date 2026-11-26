"""A extensão recebe um apelido do controle (A-EXTENSAO-RECEBE-UM-APELIDO-DO-CONTROLE-01).

Medido em 26/11/2026 por este teste com a tradução arrancada: o ``controles.lista`` e o envelope
de evento entregavam o ``uniq``, que no DualSense é o endereço do aparelho, no cabo e no rádio. A
porta do serviço passa a entregar, no mesmo campo, um apelido por extensão (HMAC-SHA256 do ``uniq``
com a chave da casa e o id da extensão, guardada ao lado do registro) e traduz de volta todo
``uniq`` que a extensão manda.

MORDIDAS (26/11/2026, executadas sobre a cura e devolvidas):

- sem a troca no ``_enviar``: ``test_nada_que_vai_a_extensao_tem_forma_de_endereco``;
- sem a troca no ``_despachar``: ``test_a_luz_com_o_apelido_chega_ao_controle_certo``;
- o supervisor sem ``apelidos``: ``test_a_porta_do_servico_da_apelidos``.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.mods import supervisor as sup
from hefesto_dualsense4unix.mods.instalador import Lugares
from hefesto_dualsense4unix.mods.porta import (
    PREFIXO_DO_APELIDO,
    Apelidos,
    Porta,
    chave_dos_apelidos,
)
from tests.unit import test_as_modificacoes_rodam_fora_do_daemon as _base

_Cliente, curto = _base._Cliente, _base.curto
UM, DOIS = "aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"
FORMA_DE_ENDERECO = re.compile(r"[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}")
PERMISSOES = ["ler:conexao", "escrever:luz"]  # (noqa-acento)


def _controles() -> list[dict[str, Any]]:
    return [{"uniq": UM, "jogador": 1}, {"uniq": DOIS, "jogador": 2}]


async def _porta(curto: Path, chave: Path, escritas: list[Any]) -> Porta:
    async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
        escritas.append((metodo, pedido))
        return {"status": "ok"}

    porta = Porta(curto / "mods.sock", EventBus(), escritor=escritor,
                  o_jogo_escreve=lambda _u, _c: False, uniq_do_posto=lambda: UM,
                  controles=_controles,
                  apelidos=Apelidos(lambda: chave_dos_apelidos(chave),
                                    lambda: [UM, DOIS]))
    await porta.iniciar()
    porta.registrar("ficha-a", "ext-a", os.getpid(), PERMISSOES)
    porta.registrar("ficha-b", "ext-b", os.getpid(), PERMISSOES)
    return porta


def _lista(curto: Path, chave: Path, ficha: str) -> list[str]:
    async def corrida() -> list[str]:
        porta = await _porta(curto, chave, [])
        cliente = _Cliente(curto / "mods.sock")
        try:
            await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": ficha})
            lida = await asyncio.to_thread(cliente.pedir, "controles.lista", {})
            return [c["uniq"] for c in lida["result"]["controles"]]
        finally:
            cliente.fechar()
            await porta.parar()

    return asyncio.run(corrida())


def test_cada_extensao_tem_o_seu_apelido_e_ele_sobrevive_ao_reinicio(curto: Path) -> None:
    chave = curto / "config" / "mods-apelidos.chave"
    da_a, da_b = _lista(curto, chave, "ficha-a"), _lista(curto, chave, "ficha-b")
    assert len(da_a) == 2 and len(set(da_a)) == 2
    assert all(a.startswith(PREFIXO_DO_APELIDO) for a in [*da_a, *da_b])
    assert set(da_a).isdisjoint(da_b)
    assert _lista(curto, chave, "ficha-a") == da_a, "o apelido mudou ao reabrir a porta"
    assert chave.stat().st_mode & 0o777 == 0o600


def test_nada_que_vai_a_extensao_tem_forma_de_endereco(curto: Path) -> None:
    async def corrida() -> list[str]:
        porta = await _porta(curto, curto / "chave", [])
        cliente = _Cliente(curto / "mods.sock")
        try:
            await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha-a"})
            lida = await asyncio.to_thread(cliente.pedir, "controles.lista", {})
            assert porta._avisar_a("ext-a", "teste", {"uniq": DOIS, "lista": [{"uniq": UM}]})
            evento = await asyncio.to_thread(cliente.arquivo.readline)
            return [json.dumps(lida), evento.decode()]
        finally:
            cliente.fechar()
            await porta.parar()

    linhas = asyncio.run(corrida())
    for linha in linhas:
        assert not FORMA_DE_ENDERECO.search(linha), linha
    assert PREFIXO_DO_APELIDO in linhas[1]


def test_a_luz_com_o_apelido_chega_ao_controle_certo(curto: Path) -> None:
    escritas: list[Any] = []

    async def corrida() -> None:
        porta = await _porta(curto, curto / "chave", escritas)
        cliente = _Cliente(curto / "mods.sock")
        try:
            await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha-a"})
            lida = await asyncio.to_thread(cliente.pedir, "controles.lista", {})
            segundo = lida["result"]["controles"][1]["uniq"]
            feita = await asyncio.to_thread(
                cliente.pedir, "luz.set", {"uniq": segundo, "rgb": [1, 2, 3]})
            assert feita["result"] == {"status": "ok"}, feita
        finally:
            cliente.fechar()
            await porta.parar()

    asyncio.run(corrida())
    assert [p["uniq"] for m, p in escritas if m == "led.set"] == [DOIS], escritas


def test_o_apelido_guardado_antes_do_reinicio_ainda_acha_o_controle(tmp_path: Path) -> None:
    chave = tmp_path / "chave"
    guardado = Apelidos(lambda: chave_dos_apelidos(chave)).de("ext-a", DOIS)
    depois = Apelidos(lambda: chave_dos_apelidos(chave), lambda: [UM, DOIS])
    assert depois.uniq_de("ext-a", guardado) == DOIS
    assert depois.uniq_de("ext-b", guardado) == guardado, "o apelido de outra extensão não vale"
    assert depois.de("ext-a", "todos") == "todos" and depois.de("ext-a", "") == ""


def test_a_porta_do_servico_da_apelidos(tmp_path: Path) -> None:
    lg = Lugares(codigo=tmp_path / "codigo", dados=tmp_path / "dados",  # (noqa-acento)
                 registro=tmp_path / "config" / "mods.json", estado=tmp_path / "estado.json")

    async def escritor(_metodo: str, _pedido: dict[str, Any]) -> Any:
        return {}

    supervisor = sup.Supervisor(
        EventBus(), lugares=lg, porta=tmp_path / "mods.sock", escritor=escritor,
        o_jogo_escreve=lambda _u, _c: False, uniq_do_posto=lambda: UM)
    apelidos = supervisor.porta.apelidos
    assert apelidos is not None
    assert apelidos.de("ext-a", UM).startswith(PREFIXO_DO_APELIDO)
    assert (tmp_path / "config" / sup.CHAVE_DOS_APELIDOS).is_file()
