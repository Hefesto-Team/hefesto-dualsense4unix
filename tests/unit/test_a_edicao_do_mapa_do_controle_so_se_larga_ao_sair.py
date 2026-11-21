"""A-EDICAO-DO-MAPA-DO-CONTROLE-SO-SE-LARGA-AO-SAIR-01: a edição só se larga ao sair.

O mapa largava a edição pelo relógio (o tique parado por mais de 5 s), e os gestos e o tique
renovavam o relógio por conta própria: uma hora sem tique e o tique seguinte mantinha a edição;
seis segundos com a janela escondida e um «Guardar» que chegava antes do tique perdia as trocas.
Agora a edição se larga em dois pontos, a abertura da página e o «Cancelar», e o «← Voltar» e o
«Cancelar» voltam pelo histórico.

A mordida: devolver o relógio ao `_estado` reprova os de tempo; tirar o `@ao_abrir` reprova o de
reabrir; voltar o `href` fixo ou tirar o gesto do «← Voltar» reprova os de página.
"""
from __future__ import annotations

import pathlib
import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a06_navegacao as a06
from hefesto_dualsense4unix.interface.pacotes import a13_mapa_do_controle as a13

RAIZ = pathlib.Path(__file__).resolve().parents[2]
NOME = "Regua"


def _ctx() -> Any:
    return Contexto(state={"active_profile": NOME}, mesa=[], conectados=[], escolhido="")


@pytest.fixture
def mapa() -> Any:
    a13._largar()
    yield a13
    a13._largar()


@pytest.fixture
def perfil_no_disco() -> None:
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile

    loader.save_profile(Profile(name=NOME, match=MatchManual(), remapeamento={"triangle": "cross"}))


def _troca_a_quadrado_pelo_circulo(mapa: Any, ctx: Any) -> None:
    mapa.mapa_botao(ctx, {"b": "square"}, None)
    mapa.mapa_escolher(ctx, {"v": "troca:circle"}, None)


def _adiante(monkeypatch: pytest.MonkeyPatch, segundos: float) -> None:
    agora = time.monotonic()
    monkeypatch.setattr(time, "monotonic", lambda: agora + segundos)


def test_uma_hora_sem_tique_a_edicao_continua_e_o_guardar_grava(
        mapa: Any, perfil_no_disco: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2011-A-EDICAO-DO-MAPA-SO-SE-LARGA-AO-SAIR: o relógio não larga a edição."""
    from hefesto_dualsense4unix.profiles import loader

    ctx = _ctx()
    mapa.pacote(ctx)
    _troca_a_quadrado_pelo_circulo(mapa, ctx)
    _adiante(monkeypatch, 3600)

    mapa.mapa_guardar(ctx, {}, MagicMock())

    assert loader.load_profile(NOME).remapeamento == {"triangle": "cross", "square": "circle"}


def test_seis_segundos_de_janela_escondida_e_o_guardar_antes_do_tique_grava(
        mapa: Any, perfil_no_disco: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.profiles import loader

    ctx = _ctx()
    mapa.pacote(ctx)
    _troca_a_quadrado_pelo_circulo(mapa, ctx)
    _adiante(monkeypatch, 6)

    mapa.mapa_guardar(ctx, {}, MagicMock())

    assert loader.load_profile(NOME).remapeamento == {"triangle": "cross", "square": "circle"}


def test_o_tique_depois_de_uma_hora_mantem_a_edicao(
        mapa: Any, perfil_no_disco: None, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx()
    mapa.pacote(ctx)
    _troca_a_quadrado_pelo_circulo(mapa, ctx)
    _adiante(monkeypatch, 3600)

    carga = mapa.pacote(ctx)["mesa"]

    assert carga["atual-square"] == "troca:circle"


def test_reabrir_a_pagina_larga_a_edicao_que_ficou(mapa: Any, perfil_no_disco: None) -> None:
    ctx = _ctx()
    mapa.pacote(ctx)
    _troca_a_quadrado_pelo_circulo(mapa, ctx)

    pacotes.a_aba_abriu(mapa.PAGINA)

    assert mapa._estado()["edicoes"] == {}
    assert not str(mapa.pacote(ctx)["mesa"]["atual-square"]).startswith("troca:")


def test_o_cancelar_larga_a_edicao(mapa: Any, perfil_no_disco: None) -> None:
    ctx = _ctx()
    mapa.pacote(ctx)
    _troca_a_quadrado_pelo_circulo(mapa, ctx)

    mapa.mapa_cancelar(ctx, {}, None)

    assert mapa._estado()["edicoes"] == {}


def test_nenhuma_constante_de_pausa_sobrou() -> None:
    assert not hasattr(a13, "PAUSA_DE_OUTRA_ABA")
    assert not hasattr(a06, "PAUSA_DE_OUTRA_ABA")
    assert not hasattr(a13, "_VISTO")


def _desenho() -> str:
    return (RAIZ / "mockup" / "mapa-do-controle.html").read_text(encoding="utf-8")


def _tag(texto: str, rotulo: str) -> str:
    fim = texto.index(rotulo)
    return texto[texto.rindex("<a ", 0, fim):fim]


def test_o_cancelar_e_o_voltar_mandam_mapa_cancelar_e_voltam_pelo_historico() -> None:
    texto = _desenho()
    for rotulo in (">Cancelar</a>", ">← Voltar</a>"):
        tag = _tag(texto, rotulo)
        assert 'data-gesto="mapa-cancelar"' in tag, rotulo
        assert "history.back()" in tag, rotulo
    assert "Volta para onde você estava" in _tag(texto, ">← Voltar</a>")
