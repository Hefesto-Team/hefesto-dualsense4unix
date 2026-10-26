"""O duplo clique de «Permitir correções automáticas» se conta pelo carimbo do clique.

O-DUPLO-CLIQUE-DAS-CORRECOES-SE-MEDE-PELO-EVENTO-DO-CLIQUE-01 (20/10/2026). Medido no piloto, em
lar de mentira, com 160 laços de CPU em 16 núcleos: dois cliques a 0,215 s um do outro (relógio
da página) chegaram ao gesto a 0,619 s, e o duplo virou dois cliques simples. O gesto roda numa
fila e numa thread; a hora em que ele roda carrega o atraso do laço. A página carimba cada
clique (`carimbo`, o `ev.timeStamp` somado à origem do documento, em ms) e o gesto compara os
carimbos.

Mordidas:

* devolva a conta pelo relógio do gesto (``agora = time.monotonic()`` no lugar de
  ``_hora_do_clique(o)``): o primeiro caso vira dois simples e o segundo vira duplo;
* tire o ``carimbo`` da `carga_do_alvo` do `hefesto_vivo`: o duplo clique no WebKit
  (`test_cada_botao_da_aba_sistema_faz_o_que_diz.py::test_na_tela_o_duplo_clique_das_correcoes_
  reaplica_e_deixa_o_recibo`) nunca reaplica, e o piloto em lar de mentira dá 0 de 20.
"""

from __future__ import annotations

import pathlib
import time
from typing import Any

import pytest


from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

ATRASO_DO_LACO_S = 0.8


@pytest.fixture
def interruptor(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> list[str]:
    """Um HOME de mentira, nada fala com o systemd; devolve a lista do que se reaplicou."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setattr(a09._vigia, "_recarregar_o_systemd", lambda: True)
    monkeypatch.setattr(a09._vigia, "garantir", lambda: "escrito")
    a09._ULTIMO_CLIQUE_DAS_CORRECOES.clear()
    reaplicou: list[str] = []
    monkeypatch.setattr(a09, "_reaplicar_as_correcoes",
                        lambda: reaplicou.append("sim") or "Reaplicado.")
    return reaplicou


def _ctx() -> Contexto:
    return Contexto(state={"controllers": []}, mesa=[], conectados=[], estados={})


def _clicar(carimbo_ms: Any) -> None:
    a09.correcoes_automaticas(_ctx(), {"carimbo": carimbo_ms}, None)


def test_dois_carimbos_a_0_3_s_com_o_laco_atrasado_sao_o_duplo(interruptor: list[str]) -> None:
    _clicar(1_000_000.0)
    time.sleep(ATRASO_DO_LACO_S)
    _clicar(1_000_300.0)
    assert interruptor == ["sim"], (
        "dois cliques carimbados a 0,3 s viraram dois simples porque o segundo gesto rodou "
        f"{ATRASO_DO_LACO_S} s depois do primeiro")
    assert a09._vigia.interruptor_ligado() is True, "o duplo clique termina ligado"


def test_dois_carimbos_a_0_7_s_entregues_juntos_sao_dois_simples(
        interruptor: list[str]) -> None:
    _clicar(1_000_000.0)
    _clicar(1_000_700.0)
    assert interruptor == [], "cliques a 0,7 s um do outro não são o duplo, chegue quando chegar"
    assert a09._vigia.interruptor_ligado() is True, "dois simples: desliga e liga de novo"


def test_o_terceiro_clique_seguido_volta_a_alternar(interruptor: list[str]) -> None:
    for carimbo in (1_000_000.0, 1_000_200.0, 1_000_400.0):
        _clicar(carimbo)
    assert interruptor == ["sim"]
    assert a09._vigia.interruptor_ligado() is False


@pytest.mark.parametrize("carimbo", [None, "", "nao-e-hora", float("nan")])
def test_o_pedido_sem_carimbo_nunca_forma_par(interruptor: list[str], carimbo: Any) -> None:
    _clicar(1_000_000.0)
    _clicar(carimbo)
    _clicar(1_000_100.0)
    assert interruptor == [], "um clique sem a hora dele formou par com o vizinho"


def test_o_carimbo_que_volta_no_tempo_nao_forma_par(interruptor: list[str]) -> None:
    """Um carimbo anterior ao do clique de antes nunca é o segundo clique dele."""
    _clicar(1_000_300.0)
    _clicar(1_000_000.0)
    assert interruptor == []
