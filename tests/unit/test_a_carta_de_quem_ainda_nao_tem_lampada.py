"""OS-QUATRO-EM-HARMONIA-01, item 2: quem entra sem lâmpada não mexe na carta de quem tem.

Medido em 14/10/2026 (10h42m08,997 a 10h42m11,680): três controles entraram com
o jogo aberto, e o primário trocou três vezes. A carta da mesa caía INTEIRA para
a fila gravada, de outra sessão, enquanto um recém-chegado não acendia número.
O P1 sentado na lâmpada 1 passava a ser o 3º da fila, e voltava a ser o 1 no
tique seguinte, quando a lâmpada do novo acendia.

A régua vale para 1 a 4 controles, cabo e rádio misturados, em qualquer ordem
de entrada: a carta é a lâmpada, e a fila só decide entre quem não tem lâmpada.
"""

from __future__ import annotations

import itertools
from typing import Any

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

# Faixa forjada da casa (``aa:bb:cc``), na forma da key do handle; nunca um endereço real.
UM, DOIS, TRES, QUATRO = (f"aabbcc0000{n:02x}" for n in range(1, 5))


class _Mesa:
    """O provider da camada automática: lâmpadas acesas e a fila gravada."""

    def __init__(self, lampadas: dict[str, int], fila: dict[str, int]) -> None:
        self.lampadas = lampadas
        self.fila = fila

    def __call__(self, _uniq: str) -> Any:
        return None

    def numero_do_slot(self, uniq: str) -> int | None:
        return self.lampadas.get(uniq)

    def posto_na_fila(self, uniq: str) -> int | None:
        return self.fila.get(uniq)


def _backend(chaves: list[str], mesa: _Mesa) -> PyDualSenseController:
    ctl = PyDualSenseController()
    ctl._auto_output_provider = mesa
    for chave in chaves:
        ctl._handles[chave] = object()
    return ctl


def _chave(uniq: str) -> str:
    return uniq


@pytest.mark.parametrize("ordem", list(itertools.permutations([UM, DOIS, TRES, QUATRO])))
def test_o_recem_chegado_sem_lampada_nao_derruba_o_p1(ordem: tuple[str, ...]) -> None:
    """A lâmpada 1 fica no posto, chegue quem chegar, na ordem que for.

    A fila de outra sessão diz o contrário da lâmpada (o 1 aceso é o 4º da fila).
    MORDIDA: devolva o «tudo ou nada» em ``_cartas_locked`` (lâmpada só quando
    todos têm) e o P1 sentado passa para o 1º da fila velha.
    """
    fila_velha = {UM: 4, DOIS: 3, TRES: 2, QUATRO: 1}
    acesas: dict[str, int] = {}
    mesa = _Mesa(acesas, fila_velha)
    chaves: list[str] = []
    ctl = _backend(chaves, mesa)
    sentado: str | None = None
    for n, uniq in enumerate(ordem, start=1):
        chave = _chave(uniq)
        ctl._handles[chave] = object()
        if sentado is None:
            sentado = chave
            acesas[uniq] = 1
            continue
        with ctl._io_lock:
            assert ctl._a_carta_menor_locked(sentado) == sentado, (
                f"o {n}º a entrar, ainda sem lâmpada, derrubou o P1"
            )
        acesas[uniq] = n
        with ctl._io_lock:
            assert ctl._a_carta_menor_locked(sentado) == sentado


def test_quem_nao_tem_lampada_vem_depois_na_ordem_da_fila() -> None:
    mesa = _Mesa({UM: 1, DOIS: 2}, {TRES: 7, QUATRO: 5, UM: 9})
    chaves = [_chave(u) for u in (UM, DOIS, TRES, QUATRO)]
    ctl = _backend(chaves, mesa)
    with ctl._io_lock:
        cartas = ctl._cartas_locked(chaves)
    assert cartas == {chaves[0]: 1, chaves[1]: 2, chaves[3]: 3, chaves[2]: 4}


def test_sem_lampada_nenhuma_a_fila_decide() -> None:
    """O boot: ninguém acendeu ainda, e a fila gravada é a única carta."""
    mesa = _Mesa({}, {UM: 2, DOIS: 1})
    chaves = [_chave(UM), _chave(DOIS), _chave(TRES)]
    ctl = _backend(chaves, mesa)
    with ctl._io_lock:
        assert ctl._cartas_locked(chaves) == {chaves[0]: 2, chaves[1]: 1, chaves[2]: 3}


def test_a_lampada_menor_que_chega_leva_o_posto() -> None:
    """A troca que ela pede na tela continua valendo: a lâmpada 1 nova senta."""
    mesa = _Mesa({UM: 2, DOIS: 1}, {})
    chaves = [_chave(UM), _chave(DOIS)]
    ctl = _backend(chaves, mesa)
    with ctl._io_lock:
        assert ctl._a_carta_menor_locked(chaves[0]) == chaves[1]
