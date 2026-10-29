"""A extensão liga a própria chave pelo ``chave.ligar`` (28/10/2026).

Ela: «todo jogo adulto no estilo de jogo liga a extensão, caso note que funcione». Quem nota que o
jogo funciona é a extensão (a ponte do jogo conversou, ou o kit do jogo alcança a ponte); a chave
mora no ``opcoes.json`` que só o Hefesto grava. O ``chave.ligar`` a grava ligada como o clique da
janela, só a da extensão que pede, e só com a ``chave`` no manifesto instalado.
"""
from __future__ import annotations

import asyncio
import os
import pathlib
from types import SimpleNamespace
from typing import Any

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.mods import opcoes
from hefesto_dualsense4unix.mods.instalador import manifesto_instalado
from hefesto_dualsense4unix.mods.porta import CODE_SEM_PERMISSAO, Porta
from hefesto_dualsense4unix.mods.supervisor import Supervisor
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import lar  # noqa: F401
from tests.unit.test_a_chave_da_extensao_liga_e_desliga import _instalada_com_a_chave
from tests.unit.test_a_coluna_agora_e_o_parar_tudo_vem_do_servico import (  # noqa: F401
    GESTO,
    P1,
    _Extensao,
    curto,
)


async def _porta(curto: pathlib.Path, ligar: Any) -> Porta:  # noqa: F811
    async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
        return {"status": "ok"}

    porta = Porta(curto / "mods.sock", EventBus(), escritor=escritor,
                  o_jogo_escreve=lambda uniq, canal: False, uniq_do_posto=lambda: P1,
                  ligar_a_chave=ligar)
    await porta.iniciar()
    porta.registrar("ficha-a", "acessorios", os.getpid(), [GESTO])
    porta.registrar("ficha-b", "outra", os.getpid(), [GESTO])
    return porta


def test_a_extensao_liga_so_a_propria_chave(curto: pathlib.Path) -> None:  # noqa: F811
    """Prova da D-2810-O-JOGO-ADULTO-QUE-CONVERSA-LIGA-A-EXTENSAO."""
    pedidas: list[str] = []

    async def ligar(mod_id: str) -> bool:
        pedidas.append(mod_id)
        return mod_id == "acessorios"

    async def corrida() -> tuple[dict[str, Any], dict[str, Any]]:
        porta = await _porta(curto, ligar)
        a, b = _Extensao(curto / "mods.sock"), _Extensao(curto / "mods.sock")
        try:
            await asyncio.to_thread(a.pedir, "mod.ola", {"ficha": "ficha-a"})
            await asyncio.to_thread(b.pedir, "mod.ola", {"ficha": "ficha-b"})
            return (await asyncio.to_thread(a.pedir, "chave.ligar", {}),
                    await asyncio.to_thread(b.pedir, "chave.ligar", {}))
        finally:
            a.fechar()
            b.fechar()
            await porta.parar()

    dona, sem_chave = asyncio.run(corrida())
    assert dona.get("result") == {"ligada": True}, dona
    assert sem_chave["error"]["code"] == CODE_SEM_PERMISSAO, sem_chave
    assert pedidas == ["acessorios", "outra"], "cada uma pede só a própria chave"


def test_sem_quem_grave_a_chave_a_porta_recusa(curto: pathlib.Path) -> None:  # noqa: F811
    async def corrida() -> dict[str, Any]:
        porta = await _porta(curto, None)
        a = _Extensao(curto / "mods.sock")
        try:
            await asyncio.to_thread(a.pedir, "mod.ola", {"ficha": "ficha-a"})
            return await asyncio.to_thread(a.pedir, "chave.ligar", {})
        finally:
            a.fechar()
            await porta.parar()

    assert asyncio.run(corrida())["error"]["code"] == CODE_SEM_PERMISSAO


def test_o_supervisor_grava_a_chave_ligada_como_o_clique(lar: Any) -> None:  # noqa: F811
    _instalada_com_a_chave(lar)
    manifesto = manifesto_instalado("acessorios", lugares=lar)
    opcoes.guardar(manifesto, "ligada", False, lar)
    sup: Any = SimpleNamespace(lugares=lar)
    assert asyncio.run(Supervisor._ligar_a_chave(sup, "acessorios")) is True
    assert opcoes.ler(manifesto, lar)["ligada"] is True
    assert asyncio.run(Supervisor._ligar_a_chave(sup, "ninguem")) is False
