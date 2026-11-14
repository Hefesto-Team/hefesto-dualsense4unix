"""A porta publica o estilo do jogo (14/11/2026).

``jogo.estilo`` (``ler:jogo.estilo``) sai do ``perfil.trocou`` com a chave do catálogo dos estilos:
abrir um jogo de tiro diz ``fps``, trocar para um de terror diz ``terror``. Só sai quando o estilo,
o jogo ou o estilo de um controle muda, e quem assina depois recebe o de agora.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.mods.porta import CODE_SEM_PERMISSAO, Porta, carga_do_estilo
from tests.unit.test_a_porta_ouve_o_jogo_e_o_microfone import P1, _Cliente


def _perfil(perfil: str, estilo: str | None, jogo: str | None) -> dict[str, Any]:
    controles = [{"jogador": n, "perfil": perfil, "jogo": jogo, "estilo": estilo}
                 for n in (1, 2, 3, 4)]
    return {"perfil": perfil, "estilo": estilo, "jogo": jogo, "controles": controles,
            "memoria": False, "t": 1.0}


def test_a_carga_traz_a_chave_do_catalogo_e_nunca_o_que_nao_esta_nele() -> None:
    assert carga_do_estilo(_perfil("A", "arco", "steam_app_1"))["estilo"] == "acao"  # (noqa-acento)
    assert carga_do_estilo(_perfil("A", "inventado", None))["estilo"] is None
    assert carga_do_estilo("lixo") is None
    carga = carga_do_estilo(_perfil("A", "terror", "steam_app_1"))
    assert carga == {"estilo": "terror", "jogo": "steam_app_1", "controles": [
        {"jogador": n, "estilo": "terror"} for n in (1, 2, 3, 4)]}


def test_abrir_um_jogo_de_tiro_publica_fps_e_trocar_para_terror_publica_terror() -> None:
    async def corrida() -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
        with tempfile.TemporaryDirectory(prefix="pe") as pasta:
            caminho = Path(pasta) / "m.sock"
            bus = EventBus()
            bus.bind_loop(asyncio.get_running_loop())

            async def escritor(_m: str, _p: dict[str, Any]) -> Any:
                return {"status": "ok"}

            porta = Porta(caminho, bus, escritor=escritor, o_jogo_escreve=lambda _u, _c: False,
                          uniq_do_posto=lambda: P1)
            await porta.iniciar()
            porta.registrar("f-c", "imersao", os.getpid(), ["ler:jogo.estilo"])
            porta.registrar("f-s", "sem", os.getpid(), ["ler:perfil.jogo"])
            com, sem = _Cliente(caminho), _Cliente(caminho)
            com.sock.settimeout(5.0)
            try:
                await asyncio.to_thread(com.pedir, "mod.ola", {"ficha": "f-c"})
                await asyncio.to_thread(sem.pedir, "mod.ola", {"ficha": "f-s"})
                recusa = await asyncio.to_thread(
                    sem.pedir, "eventos.assinar", {"topicos": ["jogo.estilo"]})
                bus.publish(EventTopic.PERFIL_TROCOU, _perfil("Navegar", None, None))
                await asyncio.to_thread(com.pedir, "eventos.assinar", {"topicos": ["jogo.estilo"]})
                vistos = [await asyncio.to_thread(com.evento)]
                bus.publish(EventTopic.PERFIL_TROCOU, _perfil("Doom", "fps", "steam_app_10"))
                vistos.append(await asyncio.to_thread(com.evento))
                bus.publish(EventTopic.PERFIL_TROCOU, {**_perfil("Doom", "fps", "steam_app_10"),
                                                       "memoria": True, "t": 2.0})
                bus.publish(EventTopic.PERFIL_TROCOU, _perfil("Amnesia", "terror", "steam_app_20"))
                vistos.append(await asyncio.to_thread(com.evento))
                tardio = _Cliente(caminho)
                tardio.sock.settimeout(5.0)
                porta.registrar("f-t", "tardio", os.getpid(), ["ler:jogo.estilo"])
                await asyncio.to_thread(tardio.pedir, "mod.ola", {"ficha": "f-t"})
                await asyncio.to_thread(
                    tardio.pedir, "eventos.assinar", {"topicos": ["jogo.estilo"]})
                de_agora = await asyncio.to_thread(tardio.evento)
                tardio.fechar()
            finally:
                com.fechar()
                sem.fechar()
                await porta.parar()
            return recusa, vistos, de_agora

    recusa, vistos, de_agora = asyncio.run(corrida())
    assert recusa["error"]["code"] == CODE_SEM_PERMISSAO
    assert [v["params"]["nome"] for v in vistos] == ["jogo.estilo"] * 3
    assert [v["params"]["topico"] for v in vistos] == ["jogo.estilo"] * 3
    dados = [v["params"]["dados"] for v in vistos]
    assert [(d["estilo"], d["jogo"]) for d in dados] == [
        (None, None), ("fps", "steam_app_10"), ("terror", "steam_app_20")]
    assert [c["estilo"] for c in dados[2]["controles"]] == ["terror"] * 4
    assert de_agora["params"]["dados"]["estilo"] == "terror"
