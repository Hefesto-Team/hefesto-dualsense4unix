"""A-TROCA-DE-CABO-PARA-RADIO-NAO-E-CHEGADA-01: o mesmo controle em outro fio não ganha a Chegada.

A Chegada é da conexão e da subida do daemon (A-CHEGADA-TOCA-TODOS-QUANDO-O-HEFESTO-REINICIA-01,
`test_a_chegada_e_a_assinatura_de_cada_controle.py`). O cabo que assume do
rádio, ou o controle que volta pelo outro fio, não conectou: a barra não sobe de novo, a háptica
não toca e o gatilho não clica no meio do jogo. A queda de verdade continua tocando ao voltar.

As mordidas (arrancar a cura, ver reprovar, devolver):
- o `anunciar_a_chegada` comparando só as chaves (sem o `_quem_entrou`) faz a régua 2 reprovar;
- o `anunciar_bordas_por_alvo` chamando a Chegada com `troca_de_transporte=True` faz a 1 reprovar.
"""
from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon import connection as conn
from hefesto_dualsense4unix.daemon.subsystems import chegada as ch

AZUL, BRANCO, VERMELHO, ROXO = (f"aa:bb:cc:00:00:{n:02x}" for n in (0x21, 0x22, 0x23, 0x24))
QUATRO = (AZUL, BRANCO, VERMELHO, ROXO)
SENTIDOS = (("bt", "usb"), ("usb", "bt"))


class _Backend:
    """O backend enxuto: o fio de cada controle e quem está trocando de fio."""

    def __init__(self, transportes: dict[str, str]) -> None:
        self.transportes = dict(transportes)
        self.trocando: set[str] = set()

    def transportes_dos_alvos(self) -> dict[str, str]:
        return dict(self.transportes)

    def em_troca_de_transporte(self, uniq: str | None) -> bool:
        return uniq in self.trocando

    def trocas_de_transporte_pendentes(self) -> frozenset[str]:
        return frozenset(u for u in self.trocando if u not in self.transportes)


def _daemon(transportes: dict[str, str]) -> tuple[Any, list[str]]:
    """Um daemon mínimo com a Chegada montada em pontas de lista; devolve quem tocou."""
    tocou: list[str] = []
    na_mesa = frozenset(QUATRO)
    pontas = ch.PontasDaChegada(
        pode=lambda: True,
        conectados=lambda: na_mesa,
        jogo_escreve=lambda _u, _c: False,
        nota=lambda _u: 160,
        cor=lambda _u: (10, 20, 30),
        pintar=lambda *_a: True,
        devolver_a_luz=lambda: None,
        tocar=lambda uniq, *_a: tocou.append(uniq) or True,
        clicar=lambda *_a: True,
        soltar_o_clique=lambda *_a: True,
        dormir=lambda _s: None,
    )
    daemon = SimpleNamespace(
        bus=EventBus(), controller=_Backend(transportes), _chegada=ch.Chegada(pontas),
        _registro_de_gatilhos=None)
    return daemon, tocou


def _disparar(daemon: Any) -> None:
    for gatilho, _ in conn.registro_de_gatilhos_de(daemon).devidos(time.monotonic() + 3600):
        gatilho.tarefa()


@pytest.fixture(autouse=True)
def _sem_som(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _nada(*_a: Any, **_k: Any) -> None:
        return None

    monkeypatch.setattr(conn, "reapply_speaker_after_connect", _nada)
    monkeypatch.setattr(conn, "reapply_mic_after_connect", _nada)
    monkeypatch.setattr(conn, "nascer_o_microfone_ao_conectar", lambda *_a, **_k: None)


@pytest.mark.parametrize(("de", "para"), SENTIDOS)
@pytest.mark.parametrize("quem", QUATRO)
def test_o_controle_que_troca_de_fio_entre_dois_tiques_nao_ganha_chegada(
    quem: str, de: str, para: str) -> None:
    mesa = {u: u for u in QUATRO}
    antes = {u: "usb" for u in QUATRO} | {quem: de}
    daemon, tocou = _daemon(antes | {quem: para})
    trocaram = asyncio.run(
        conn.reaplicar_som_de_quem_trocou_de_transporte(daemon, mesa, mesa, antes,
                                                        daemon.controller.transportes))
    assert trocaram == 1
    _disparar(daemon)
    assert tocou == [], (
        f"o controle que trocou de {de} para {para} ganhou a Chegada: a barra sobe, a háptica "
        "toca e o gatilho clica no meio do jogo, sem conexão nova")


@pytest.mark.parametrize("quem", QUATRO)
def test_o_controle_que_volta_pelo_outro_fio_nao_ganha_chegada(quem: str) -> None:
    outros = {u: u for u in QUATRO if u != quem}
    daemon, tocou = _daemon({u: "usb" for u in QUATRO})
    assert conn.anunciar_a_chegada(daemon, outros | {"/dev/hidraw9": quem},
                                   outros | {quem: quem}) == 0
    daemon.controller.trocando.add(quem)
    assert conn.anunciar_a_chegada(daemon, outros, outros | {quem: quem}) == 0
    asyncio.run(conn.anunciar_bordas_por_alvo(daemon, outros, outros | {quem: quem}))
    _disparar(daemon)
    assert tocou == [], "a volta de uma troca de fio tocou a Chegada como se fosse conexão nova"


@pytest.mark.parametrize("fio", ["usb", "bt"])
def test_o_controle_que_caiu_de_verdade_ganha_a_chegada_ao_voltar(fio: str) -> None:
    daemon, tocou = _daemon({u: fio for u in QUATRO})
    assert conn.anunciar_a_chegada(daemon, {}, {u: u for u in QUATRO}) == 4
    _disparar(daemon)
    assert sorted(tocou) == sorted(QUATRO)
    tocou.clear()
    outros = {u: u for u in QUATRO if u != ROXO}
    asyncio.run(conn.anunciar_bordas_por_alvo(daemon, outros, outros | {ROXO: ROXO}))
    _disparar(daemon)
    assert tocou == [ROXO]
