"""O estilo do perfil só vale com o jogo dele aberto (16/11/2026).

O-ESTILO-NATIVO-SO-CALA-COM-O-JOGO-ABERTO-01. O perfil de um jogo com estilo Nativo ficava em
vigor depois que o jogo fechava, e o `modo_do_controle` seguia devolvendo o Nativo: o Modo imersão e
as outras extensões calavam sem jogo nenhum. O `jogo.estilo` publicado às extensões dizia o estilo
do perfil que ficou («Estilo: Terror» sem jogo). A cura: o estilo vale só com um jogo em cena
(a autoridade do jogo, `display_authority`, para o modo; o `jogo` do `perfil.trocou` de cada
controle, para o `jogo.estilo`); sem jogo, o modo é o do pad e o `jogo.estilo` sai sem estilo.

MORDIDAS: tirar a condição do jogo em `modo_do_controle` (o `ha_jogo_em_cena`) devolve o Nativo
sem jogo; tirar a condição do jogo em `carga_do_estilo` devolve o estilo do perfil sem jogo.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.lifecycle import (
    MODO_DUALSENSE,
    MODO_NATIVO,
    MODO_NAVEGACAO,
    MODO_XBOX,
    Daemon,
    DaemonConfig,
    modo_do_controle,
    o_hefesto_fala_no_modo,
)
from hefesto_dualsense4unix.mods.porta import Porta, carga_do_estilo
from hefesto_dualsense4unix.testing.fake_controller import FakeController
from tests.unit.test_a_porta_ouve_o_jogo_e_o_microfone import P1, _Cliente

APPID_FORJADO = 9942231


class _Vpad:
    def __init__(self, backend: str) -> None:
        self.backend = backend


def _daemon(transporte: str, *, jogo: int | None) -> Daemon:
    d = Daemon(controller=FakeController(transport=transporte), config=DaemonConfig())  # type: ignore[arg-type]
    d._game_signal = SimpleNamespace(authority="game" if jogo is not None else "daemon")
    d._appid_da_evidencia = jogo
    return d


PADS = (("uhid", MODO_DUALSENSE), ("uinput", MODO_XBOX), (None, MODO_NAVEGACAO))


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize(("backend", "modo_do_pad"), PADS)
def test_sem_jogo_o_estilo_nativo_nao_cala_o_controle(
    transporte: str, backend: str | None, modo_do_pad: str
) -> None:
    d = _daemon(transporte, jogo=None)
    vpad = _Vpad(backend) if backend is not None else None

    modo = modo_do_controle(d, vpad, estilo="nativo")

    assert modo == modo_do_pad
    assert o_hefesto_fala_no_modo(modo)


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize(("backend", "_modo_do_pad"), PADS)
def test_com_o_jogo_em_cena_o_estilo_nativo_e_o_modo(
    transporte: str, backend: str | None, _modo_do_pad: str
) -> None:
    d = _daemon(transporte, jogo=APPID_FORJADO)
    vpad = _Vpad(backend) if backend is not None else None

    assert modo_do_controle(d, vpad, estilo="nativo") == MODO_NATIVO
    assert not o_hefesto_fala_no_modo(MODO_NATIVO)


def test_o_jogo_fora_da_steam_tambem_e_jogo_em_cena() -> None:
    """A regra de perfil que casa a janela (GOG, Heroic) dá a autoridade do jogo sem appid."""
    d = _daemon("bt", jogo=None)
    d._game_signal = SimpleNamespace(authority="game")
    assert modo_do_controle(d, _Vpad("uinput"), estilo="nativo") == MODO_NATIVO


def _perfil(estilo: str | None, jogos: list[str | None]) -> dict[str, Any]:
    controles = [{"jogador": n, "perfil": "Sackboy", "jogo": jogo, "estilo": estilo}
                 for n, jogo in enumerate(jogos, start=1)]
    return {"perfil": "Sackboy", "estilo": estilo, "jogo": jogos[0], "controles": controles,
            "memoria": False, "t": 1.0}


@pytest.mark.parametrize("estilo", ["nativo", "terror", "fps"])
def test_o_jogo_estilo_sai_vazio_sem_jogo(estilo: str) -> None:
    carga = carga_do_estilo(_perfil(estilo, [None] * 4))
    assert carga == {"estilo": None, "jogo": None,
                     "controles": [{"jogador": n, "estilo": None} for n in (1, 2, 3, 4)]}


@pytest.mark.parametrize("estilo", ["nativo", "terror", "fps"])
def test_o_jogo_estilo_diz_o_estilo_de_quem_esta_no_jogo(estilo: str) -> None:
    jogo = f"steam_app_{APPID_FORJADO}"
    carga = carga_do_estilo(_perfil(estilo, [jogo, None, jogo, None]))
    assert carga is not None
    assert (carga["estilo"], carga["jogo"]) == (estilo, jogo)
    assert [c["estilo"] for c in carga["controles"]] == [estilo, None, estilo, None]


def test_fechar_o_jogo_publica_o_jogo_estilo_sem_estilo() -> None:
    async def corrida() -> list[dict[str, Any]]:
        with tempfile.TemporaryDirectory(prefix="ej") as pasta:
            caminho = Path(pasta) / "m.sock"
            bus = EventBus()
            bus.bind_loop(asyncio.get_running_loop())

            async def escritor(_m: str, _p: dict[str, Any]) -> Any:
                return {"status": "ok"}

            porta = Porta(caminho, bus, escritor=escritor, o_jogo_escreve=lambda _u, _c: False,
                          uniq_do_posto=lambda: P1)
            await porta.iniciar()
            porta.registrar("f-e", "imersao", os.getpid(), ["ler:jogo.estilo"])
            cliente = _Cliente(caminho)
            cliente.sock.settimeout(5.0)
            try:
                await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "f-e"})
                jogo = f"steam_app_{APPID_FORJADO}"
                bus.publish(EventTopic.PERFIL_TROCOU, _perfil("terror", [jogo] * 4))
                await asyncio.to_thread(
                    cliente.pedir, "eventos.assinar", {"topicos": ["jogo.estilo"]})
                vistos = [await asyncio.to_thread(cliente.evento)]
                bus.publish(EventTopic.PERFIL_TROCOU, _perfil("terror", [None] * 4))
                vistos.append(await asyncio.to_thread(cliente.evento))
            finally:
                cliente.fechar()
                await porta.parar()
            return [v["params"]["dados"] for v in vistos]

    dados = asyncio.run(corrida())
    assert [(d["estilo"], d["jogo"]) for d in dados] == [
        ("terror", f"steam_app_{APPID_FORJADO}"), (None, None)]
    assert [c["estilo"] for c in dados[1]["controles"]] == [None] * 4
