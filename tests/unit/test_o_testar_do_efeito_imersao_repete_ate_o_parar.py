"""O «Testar» com o Efeito imersão escolhido repete o padrão até o «Parar», com as barras ao vivo.

Pedido de 19/10/2026: o teste da vibração e o da háptica ficam até o «Parar», para ajustar em tempo
real. A háptica tem a régua dela em
`test_o_testar_toca_a_forma_escolhida_e_o_fim_do_padrao_poupa_o_par`.

MORDIDAS:
  * troque `_repetir_o_padrao` por `_padrao_neste_controle` no `testar`: o padrão toca uma volta só;
  * tire o ramo `_REPIQUE_DO_PADRAO` do `_refrescar_o_teste`: o arraste não muda a volta seguinte;
  * tire o `_cortar_o_repique` do começo do `parar`: um par sai depois do stop;
  * tire o `join` do `_cortar_o_repique`: o stop sai com um pedido ainda em curso.
"""
from __future__ import annotations

import time

import pytest


from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import a05_vibracao as a05
from tests.unit.test_a_aba_vibracao_tem_o_sensor_haptico_e_dois_testes import (
    PAGINA,
    UNIQ,
    _ctx,
    _Ponte,
    _sem_teste_ligado,  # noqa: F401
)

VOLTA_S = 0.12


@pytest.fixture
def coice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(a05, "_padrao_escolhido", lambda _ctx, _u: "coice")
    monkeypatch.setattr(a05, "_pontos_das_barras", lambda _ctx, _u: (100, 100))


def _clicar(papel: str, ponte: _Ponte) -> None:
    gesto = pacotes.gesto_da_pagina(PAGINA, papel)
    assert gesto is not None, papel
    gesto(_ctx({"rumble_policy": "balanceado"}), {"uniq": UNIQ}, ponte)


def _pares(ponte: _Ponte) -> list[tuple[int, int]]:
    return [(c[1], c[2]) for c in list(ponte.chamadas) if c[0] == "rumble_set_checked"]


def test_o_padrao_volta_do_comeco_ate_o_parar(coice: None) -> None:
    """D-1910-O-TESTE-DA-VIBRACAO-E-CONTINUO: várias voltas, e nenhuma depois do «Parar»."""
    ponte = _Ponte()
    _clicar("testar", ponte)
    time.sleep(VOLTA_S * 4)
    assert _pares(ponte).count((120, 200)) >= 3, f"o padrão não repetiu: {_pares(ponte)}"
    assert UNIQ in a05.em_teste()
    _clicar("parar", ponte)
    depois = len(_pares(ponte))
    time.sleep(VOLTA_S * 3)
    assert len(_pares(ponte)) == depois, "o padrão seguiu depois do «Parar»"
    assert ("rumble_passthrough", True, UNIQ) in ponte.chamadas, "a mão não voltou ao jogo"
    assert UNIQ not in a05.em_teste()


class _PonteDeStopLento(_Ponte):
    """O stop que demora mais que um passo do padrão: a corrida com o fio do padrão aparece."""

    def rumble_stop_checked(self, uniq: str | None = None) -> tuple[bool, None]:
        resposta = super().rumble_stop_checked(uniq)
        time.sleep(VOLTA_S)
        return resposta


def test_nenhum_par_sai_depois_do_stop(coice: None) -> None:
    """O padrão para ANTES do stop: um par depois dele prenderia o motor até o teto do daemon."""
    ponte = _PonteDeStopLento()
    _clicar("testar", ponte)
    time.sleep(VOLTA_S * 2)
    _clicar("parar", ponte)
    nomes = ponte.nomes()
    ultimo_par = max(i for i, n in enumerate(nomes) if n == "rumble_set_checked")
    assert ultimo_par < nomes.index("rumble_stop_checked"), "um par saiu depois do stop"


class _PonteDeSetLento(_Ponte):
    """O pedido que demora: o «Parar» chega com ele em curso, e ele se anota ao VOLTAR."""

    def rumble_set_checked(self, weak: int, strong: int,
                           uniq: str | None = None) -> tuple[bool, None]:
        time.sleep(VOLTA_S)
        return super().rumble_set_checked(weak, strong, uniq=uniq)


def test_o_parar_espera_o_pedido_em_curso(coice: None) -> None:
    """O stop sai depois do último pedido do padrão voltar, nunca no meio dele."""
    ponte = _PonteDeSetLento()
    _clicar("testar", ponte)
    time.sleep(VOLTA_S / 2)
    _clicar("parar", ponte)
    nomes = ponte.nomes()
    ultimo_par = max(i for i, n in enumerate(nomes) if n == "rumble_set_checked")
    assert ultimo_par < nomes.index("rumble_stop_checked"), (
        "o stop saiu com um pedido do padrão ainda em curso")

def test_o_arraste_da_barra_vale_na_volta_seguinte(coice: None) -> None:
    ponte = _Ponte()
    _clicar("testar", ponte)
    time.sleep(VOLTA_S * 2)
    a05._refrescar_o_teste(_ctx({}), ponte, UNIQ, acabou_de_gravar=("e", 50))
    ponte.chamadas.clear()
    time.sleep(VOLTA_S * 3)
    _clicar("parar", ponte)
    fortes = {forte for _fraco, forte in _pares(ponte) if forte}
    assert fortes == {100}, f"o motor esquerdo a 50% devia bater 100, bateu {fortes}"
    assert (120, 200) not in _pares(ponte)


def test_o_testar_de_novo_nao_deixa_dois_padroes_no_ar(coice: None) -> None:
    ponte = _Ponte()
    _clicar("testar", ponte)
    _clicar("testar", ponte)
    assert len(a05._REPIQUE_DO_PADRAO) == 1
    _clicar("parar", ponte)
    assert a05._REPIQUE_DO_PADRAO == {}


def test_a_janela_que_fecha_corta_o_padrao(coice: None) -> None:
    ponte = _Ponte()
    _clicar("testar", ponte)
    a05.parar_o_teste()
    depois = len(_pares(ponte))
    time.sleep(VOLTA_S * 2)
    assert len(_pares(ponte)) == depois and a05._REPIQUE_DO_PADRAO == {}
