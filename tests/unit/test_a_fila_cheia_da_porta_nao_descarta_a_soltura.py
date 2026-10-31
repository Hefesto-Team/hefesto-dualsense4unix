"""A fila cheia do tópico ``botoes`` nunca perde a última borda de um botão.

A extensão que lê devagar deixa a fila de 256 encher. Descartar a borda mais antiga podia
jogar fora um ``button.up``: o botão ficava apertado para a extensão, e o efeito dele preso.
A fila cheia junta duas bordas seguidas do mesmo botão (o aperto e a soltura, ou a soltura e
o reaperto), que se anulam: o estado final de cada botão, de cada controle, chega certo, e a
ordem das bordas de um botão é a do tique.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import DEFAULT_QUEUE_MAXSIZE, EventBus, EventTopic
from hefesto_dualsense4unix.daemon.subsystems.poll import evdev_buttons_once
from hefesto_dualsense4unix.mods.porta import Porta, botoes_de_todo_controle_no_servico
from tests.unit.test_as_capacidades_genericas_da_porta import (  # noqa: F401
    UNIQS,
    _drenar,
    _entrar,
    _porta,
    config_isolado,
    curto,
    kernel,
    montar_atalhos,
)
from tests.unit.test_o_jogo_espera_a_carta_do_lugar_guardado import TRANSPORTES

Chave = tuple[str | None, str]

MATRIZ = pytest.mark.parametrize(
    ("quantos", "transporte"),
    [(n, t) for n in (1, 2, 3, 4) for t in TRANSPORTES],
    ids=[f"{n}-controles-{t}" for n in (1, 2, 3, 4) for t in TRANSPORTES],
)


def _bordas(eventos: list[dict[str, Any]]) -> list[tuple[Chave, bool]]:
    saida: list[tuple[Chave, bool]] = []
    for evento in eventos:
        assert evento["topico"] == "botoes", evento
        apertado = evento["dados"]["pressed"]
        assert evento["nome"] == (EventTopic.BUTTON_DOWN if apertado else EventTopic.BUTTON_UP)
        assert evento["uniq"] == evento["dados"]["uniq"]
        saida.append(((evento["dados"]["uniq"], evento["dados"]["botao"]), apertado))
    return saida


def _estado_visto(bordas: list[tuple[Chave, bool]]) -> dict[Chave, bool]:
    """O que a extensão sabe de cada botão; cada borda tem de virar o estado dele."""
    estado: dict[Chave, bool] = {}
    for chave, apertado in bordas:
        assert estado.get(chave, False) != apertado, f"{chave} recebeu {apertado} duas vezes"
        estado[chave] = apertado
    return estado


def _rajada(porta: Porta, quadros: list[dict[str | None, frozenset[str]]]) -> None:
    """Os tiques de uma vez, sem devolver o laço: a extensão não lê nada no meio."""
    for apertados in quadros:
        porta.botoes_do_tique(apertados, lambda uniq: None)


def _ao_vivo(curto, quadros: list[dict[str | None, frozenset[str]]]) -> list[dict[str, Any]]:  # noqa: F811
    async def corrida() -> list[dict[str, Any]]:
        porta = await _porta(curto, EventBus(), ["ler:botoes"])
        ext = await _entrar(curto, ["botoes"])
        try:
            _rajada(porta, [{}, *quadros])
            return await asyncio.to_thread(_drenar, ext)
        finally:
            ext.fechar()
            await porta.parar()

    return asyncio.run(corrida())


Quadro = dict[str | None, frozenset[str]]


def _alternado(uniqs: tuple[str, ...], botao: str, vezes: int) -> list[Quadro]:
    return [{u: frozenset({botao}) if n % 2 == 0 else frozenset() for u in uniqs}
            for n in range(vezes)]


@pytest.mark.parametrize("quantos", [1, 2, 3, 4], ids=lambda n: f"{n}-controles")
def test_o_botao_que_alterna_ate_encher_termina_no_estado_do_tique(curto, quantos: int) -> None:  # noqa: F811
    """Um botão aperta e solta até a fila encher, e termina solto: a extensão o vê solto."""
    uniqs = UNIQS[:quantos]
    vezes = 2 * DEFAULT_QUEUE_MAXSIZE + 2
    bordas = _bordas(_ao_vivo(curto, [*_alternado(uniqs, "r1", vezes), {}]))
    assert len(bordas) <= DEFAULT_QUEUE_MAXSIZE
    assert _estado_visto(bordas) == {(u, "r1"): False for u in uniqs}


@pytest.mark.parametrize("quantos", [1, 2, 3, 4], ids=lambda n: f"{n}-controles")
def test_a_soltura_mais_antiga_nao_se_perde_quando_outro_botao_enche_a_fila(
    curto, quantos: int,  # noqa: F811
) -> None:
    """O ✕ aperta e solta; depois o R1 alterna até encher, e fica apertado no fim.

    A soltura do ✕ é a borda mais antiga da fila: descartá-la deixava o ✕ preso.
    """
    uniqs = UNIQS[:quantos]
    toque = [{u: frozenset({"cross"}) for u in uniqs}, {}]
    vezes = 2 * DEFAULT_QUEUE_MAXSIZE + 1
    bordas = _bordas(_ao_vivo(curto, [*toque, *_alternado(uniqs, "r1", vezes)]))
    visto = _estado_visto(bordas)
    for uniq in uniqs:
        assert visto.get((uniq, "cross"), False) is False, f"{uniq}: o ✕ ficou preso"
        assert visto[(uniq, "r1")] is True, f"{uniq}: o R1 apertado não chegou"


def test_o_aperto_que_ficou_chega_antes_da_soltura_dele(curto) -> None:  # noqa: F811
    """Muitos botões descem, um deles sobe, e a fila enche: a ordem de cada botão é a do tique."""
    uniq = UNIQS[0]
    botoes = [f"b{n}" for n in range(DEFAULT_QUEUE_MAXSIZE + 8)]
    quadros: list[dict[str | None, frozenset[str]]] = [
        {uniq: frozenset(botoes[: n + 1])} for n in range(len(botoes))
    ]
    quadros.append({uniq: frozenset(botoes[1:])})
    bordas = _bordas(_ao_vivo(curto, quadros))
    visto = _estado_visto(bordas)
    assert visto.get((uniq, "b0"), False) is False
    assert all(visto[(uniq, b)] for b in botoes[1:])


def test_sem_a_fila_cheia_toda_borda_chega_na_ordem(curto) -> None:  # noqa: F811
    """Abaixo do teto nada se junta: cada aperto e cada soltura chegam, na ordem do tique."""
    uniqs = UNIQS[:4]
    vezes = 20
    bordas = _bordas(_ao_vivo(curto, _alternado(uniqs, "cross", vezes)))
    esperado = [((u, "cross"), n % 2 == 0) for n in range(vezes) for u in uniqs]
    assert sorted(bordas, key=lambda b: b[0]) == sorted(esperado, key=lambda b: b[0])
    for uniq in uniqs:
        deste = [a for (u, _), a in bordas if u == uniq]
        assert deste == [n % 2 == 0 for n in range(vezes)]


@pytest.mark.usefixtures("config_isolado")
@MATRIZ
def test_cada_controle_cabo_e_radio_solta_o_que_apertou_com_a_fila_cheia(
    curto, monkeypatch, kernel, quantos: int, transporte: str,  # noqa: F811
) -> None:
    """O caminho do serviço inteiro, do P1 ao P4, cabo, rádio e mesa mista: o ✕ de cada um
    aperta e solta, o R1 de todos alterna até encher a fila e fica apertado no fim."""
    ensaio = montar_atalhos(monkeypatch, kernel, quantos, transporte)
    uniqs = UNIQS[:quantos]

    def tique() -> None:
        ensaio.tique(0.0)
        botoes = evdev_buttons_once(ensaio.daemon)
        botoes_de_todo_controle_no_servico(ensaio.daemon, botoes, botoes)

    async def corrida() -> list[dict[str, Any]]:
        porta = await _porta(curto, EventBus(), ["ler:botoes"])
        ensaio.daemon._mods_supervisor = SimpleNamespace(porta=porta)
        ext = await _entrar(curto, ["botoes"])
        try:
            tique()
            for uniq in uniqs:
                ensaio.mesa.apertados[uniq] = frozenset({"cross"})
            tique()
            for uniq in uniqs:
                del ensaio.mesa.apertados[uniq]
            tique()
            for n in range(2 * DEFAULT_QUEUE_MAXSIZE // quantos + 1):
                for uniq in uniqs:
                    if n % 2 == 0:
                        ensaio.mesa.apertados[uniq] = frozenset({"r1"})
                    else:
                        del ensaio.mesa.apertados[uniq]
                tique()
            return await asyncio.to_thread(_drenar, ext)
        finally:
            ext.fechar()
            await porta.parar()

    visto = _estado_visto(_bordas(asyncio.run(corrida())))
    for uniq in uniqs:
        assert visto.get((uniq, "cross"), False) is False, f"{transporte} {uniq}: o ✕ ficou preso"
        assert visto[(uniq, "r1")] is True, f"{transporte} {uniq}: o R1 apertado não chegou"
