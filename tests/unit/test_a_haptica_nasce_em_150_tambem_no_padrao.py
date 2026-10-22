"""A-HAPTICA-NASCE-EM-150-TAMBEM-NO-PADRAO-01 (22/10/2026): no Padrão a háptica chega a 150%.

A escolha do usuário nas perguntas do chat: «150% também no Padrão». O ganho que vale em Padrão é o
de fábrica (`HAPTICA_PCT_PADRAO`), e não mais o 100% de antes; o que ela guardou na barra espera,
como as barras dos motores, e volta com a Economia ou o Máximo.

MORDIDA: devolver `return 100` ao `pct` em Padrão (o antigo `PCT_DO_JOGO`).
"""

from __future__ import annotations

import functools
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.ganho_da_haptica import GanhoDaHaptica
from hefesto_dualsense4unix.profiles.schema import (
    HAPTICA_PCT_MAX,
    HAPTICA_PCT_PADRAO,
    ControllerOverrides,
    ControllerRumbleOverride,
)
from tests.unit.test_cada_motor_tem_o_seu_multiplicador import BRANCO, PRETO
from tests.unit.test_o_ganho_da_haptica_tem_dono import _bloco, _CaboDeMentira

# Os quatro jogadores: faixa forjada, nunca endereço da bancada.
_QUATRO = tuple(f"aa:bb:cc:00:00:0{n}" for n in (1, 2, 3, 4))


def _daemon_em(politica: str, orcamento: str | None = None) -> Any:
    return SimpleNamespace(
        config=SimpleNamespace(rumble_policy=politica, orcamento_da_mesa=lambda: orcamento)
    )


def _dono(guardado: int | None, *uniqs: str, politica_da_peca: str | None = None) -> GanhoDaHaptica:
    """Um dono lido de um perfil em que cada controle guardou ``guardado`` na barra."""
    dono = GanhoDaHaptica()
    dono.ler_do_perfil({
        u: ControllerOverrides(rumble=ControllerRumbleOverride(
            haptica_pct=guardado, policy=politica_da_peca))
        for u in uniqs
    })
    return dono


def test_o_padrao_de_fabrica_e_150() -> None:
    """Prova da D-2210-A-HAPTICA-NASCE-EM-150-TAMBEM-NO-PADRAO."""
    assert HAPTICA_PCT_PADRAO == 150 and HAPTICA_PCT_MAX == 200


@pytest.mark.parametrize("uniq", _QUATRO)
def test_em_padrao_o_ganho_que_vale_e_150_nos_quatro_controles(uniq: str) -> None:
    """Sem perfil (a fábrica) e com o 50% guardado: o Padrão aplica os 150%."""
    sem_perfil = GanhoDaHaptica()
    sem_perfil.ler_o_teto(_daemon_em("balanceado"))
    com_50 = _dono(50, *_QUATRO)
    com_50.ler_o_teto(_daemon_em("balanceado"))
    for dono in (sem_perfil, com_50):
        assert dono.pct(uniq) == 150
        assert dono.fator(uniq) == pytest.approx(1.5)
        assert dono.pct_que_vale(uniq) == 150
    assert com_50.pct_guardado(uniq) == 50, "o guardado espera, não se perde"


def test_o_degrau_da_propria_peca_tambem_vale_150_no_padrao() -> None:
    dono = _dono(50, *_QUATRO[:2], politica_da_peca="balanceado")
    dono.ler_o_teto(_daemon_em("max"))
    assert dono.pct(_QUATRO[0]) == 150
    assert dono.fator(_QUATRO[1]) == pytest.approx(1.5)


def test_fora_do_padrao_o_guardado_volta_e_a_economia_segue_cortando() -> None:
    dono = _dono(50, *_QUATRO)
    dono.ler_o_teto(_daemon_em("max"))
    assert dono.pct(_QUATRO[0]) == 50
    dono.ler_o_teto(_daemon_em("balanceado", "economia"))
    assert dono.fator(_QUATRO[0]) == pytest.approx(0.3), "o teto da Economia vence o Padrão"


def test_no_radio_o_padrao_manda_o_bloco_de_150() -> None:
    """A ponte do rádio pergunta ao dono: 150% é o nível 95, e não o 64 dos 100%."""
    dono = _dono(50, BRANCO, PRETO)
    dono.ler_o_teto(_daemon_em("balanceado"))
    for uniq in (BRANCO, PRETO):
        assert set(_bloco(functools.partial(dono.fator, uniq))) == {95}
    assert set(_bloco(1.0)) == {64}


def test_no_cabo_o_padrao_leva_1_5_ao_laco_de_cada_controle() -> None:
    dono = _dono(50, BRANCO, PRETO)
    dono.ler_o_teto(_daemon_em("balanceado"))
    mesa = _CaboDeMentira()
    mesa.volta(dono, [BRANCO, PRETO])
    assert mesa.motores(BRANCO) == [1.5, 1.5]
    assert mesa.motores(PRETO) == [1.5, 1.5]
