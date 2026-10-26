"""O Hefesto servidor Buttplug do DualSense: o servidor mora na extensão, o Hefesto dá a porta.

O servidor (o protocolo Buttplug, o WebSocket, a força e o teto de cada controle) é a extensão
``intiface``, em repositório próprio (``Hefesto-Team/hefesto-mod-intiface``), com a régua do cliente
Buttplug de mentira e a mordida da escrita direta no hidraw. No Hefesto ficam a porta e a janela
genérica que o manifesto da extensão desenha. Esta régua prova o lado do Hefesto: nenhum código do
protocolo no produto (nem no ``plugin_api``), e a porta entrega o que o servidor usa, a lista dos
controles e a vibração de cada um pelo par do serviço.

MORDIDAS (executadas): uma mensagem Buttplug tratada no ``plugin_api`` reprova a primeira; o
``vibracao.set`` que perde o ``uniq`` do controle pedido reprova a segunda.
"""
from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.mods.porta import Porta
from tests.unit import test_as_modificacoes_rodam_fora_do_daemon as _base

_Cliente, curto = _base._Cliente, _base.curto
RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"
MENSAGENS = re.compile(r"RequestServerInfo|ScalarCmd|VibrateCmd|StopAllDevices|RequestDeviceList")
UM, DOIS = "aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"


def _o_protocolo_no_produto(raiz: Path = SRC) -> list[str]:
    return sorted(str(p.relative_to(raiz)) for p in raiz.rglob("*.py")
                  if MENSAGENS.search(p.read_text(encoding="utf-8")))


def test_nenhum_codigo_do_protocolo_buttplug_mora_no_produto() -> None:
    """D-1910-O-SERVIDOR-BUTTPLUG-MORA-NA-EXTENSAO: o protocolo é da extensão ``intiface``."""
    assert _o_protocolo_no_produto() == []


def test_a_regua_morde_o_protocolo_que_volta_ao_plugin_api(tmp_path: Path) -> None:
    falso = tmp_path / "plugin_api"
    falso.mkdir()
    (falso / "__init__.py").write_text('if tipo == "ScalarCmd":\n    pass\n', encoding="utf-8")
    assert _o_protocolo_no_produto(tmp_path) == ["plugin_api/__init__.py"]


def test_a_porta_da_ao_servidor_a_lista_e_a_vibracao_do_controle_pedido(curto: Path) -> None:
    escritas: list[tuple[str, dict[str, Any]]] = []

    async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
        escritas.append((metodo, pedido))
        return {"status": "ok"}

    async def corrida() -> tuple[dict[str, Any], dict[str, Any]]:
        porta = Porta(curto / "mods.sock", EventBus(), escritor=escritor,
                      o_jogo_escreve=lambda uniq, canal: False, uniq_do_posto=lambda: UM,
                      controles=lambda: [{"uniq": UM, "jogador": 1}, {"uniq": DOIS, "jogador": 2}])
        await porta.iniciar()
        porta.registrar("ficha", "intiface", os.getpid(),
                        ["ler:conexao", "escrever:vibracao", "rede:local"])  # (noqa-acento)
        cliente = _Cliente(curto / "mods.sock")
        try:
            await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha"})
            lista = await asyncio.to_thread(cliente.pedir, "controles.lista", {})
            vibrou = await asyncio.to_thread(
                cliente.pedir, "vibracao.set", {"uniq": DOIS, "fraco": 64, "forte": 102})
            return lista, vibrou
        finally:
            cliente.fechar()
            await porta.parar()

    lista, vibrou = asyncio.run(corrida())
    assert [c["jogador"] for c in lista["result"]["controles"]] == [1, 2]
    assert "result" in vibrou, vibrou
    rumble = [p for m, p in escritas if m == "rumble.set"]
    assert rumble and rumble[0]["uniq"] == DOIS
    assert (rumble[0]["weak"], rumble[0]["strong"]) == (64, 102)
