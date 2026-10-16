"""A JANELA ABERTA NÃO GASTA O PROCESSADOR, com a máquina ocupada.

A-JANELA-ABERTA-NAO-GASTA-O-PROCESSADOR-01.

O cenário que reprovou em 28/09 (a 08 com um controle), com o laço do GTK parado ou lento, e
com o teto de fase de 1 s. O ajudante está em `janela_aberta_comum.py`
(A-JANELA-ABERTA-CABE-NA-PARTE-01).
"""
from __future__ import annotations

import pathlib
from types import SimpleNamespace
from typing import Any

import pytest

from tests.unit.janela_aberta_comum import (
    CARGAS,
    TIQUES_POR_FASE,
    _a_escondida_nao_trabalha,
    _com_carga,
    _correr,
    _entre,
    _janela_escondida,
    _nominal_s,
    _o_coracao_bate_escondido,
    _roteiro_esconde_e_volta,
    publicar_as_de_hoje,
)


#: A carga que roda no tempo de verdade, a de 28/09; as outras andam na cadência acelerada.
NO_TEMPO_REAL = "buraco"


@pytest.fixture(scope="module")
def publicado_de_hoje(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    return publicar_as_de_hoje(tmp_path_factory)


@pytest.fixture(scope="module", params=sorted(CARGAS))
def sob_carga(request: pytest.FixtureRequest,
              publicado_de_hoje: pathlib.Path) -> SimpleNamespace:
    """A 08 com um controle — o cenário que reprovou em 28/09 —, com a carga pedida."""
    fora = _correr(publicado_de_hoje, "08-conexoes.html", 1,
                   _com_carga(_roteiro_esconde_e_volta, **CARGAS[request.param]),
                   tempo_real=request.param == NO_TEMPO_REAL)
    fora.pagina, fora.n, fora.carga = "08-conexoes.html", 1, request.param
    return fora


def test_r1_sob_carga_a_janela_escondida_mede_o_mesmo(sob_carga: Any) -> None:
    """Com o laço do GTK parado ou lento, a R1 e o coração continuam verdes."""
    fora = sob_carga
    _a_escondida_nao_trabalha(fora)
    _o_coracao_bate_escondido(fora)
    de, _ate = _janela_escondida(fora)
    relogio = _entre(fora, de, fora.marcos["esconde"] + _nominal_s(TIQUES_POR_FASE, fora))
    assert len(relogio) < 25, (
        f"a carga {fora.carga!r} não atrasou o laço: o relógio de 28/09 teria "
        f"juntado {len(relogio)} tiques, e esta régua não provaria nada")


@pytest.fixture(scope="module")
def sob_carga_com_teto_curto(publicado_de_hoje: pathlib.Path) -> SimpleNamespace:
    """O buraco de 28/09 com um teto de fase de 1 s (0,1 s na cadência acelerada): passa fome."""
    fora = _correr(publicado_de_hoje, "08-conexoes.html", 1,
                   _com_carga(_roteiro_esconde_e_volta, **CARGAS["buraco"]),
                   teto_da_fase_s=0.1)
    fora.pagina, fora.n = "08-conexoes.html", 1
    return fora


def test_r1_o_teto_batido_diz_que_foi_a_maquina(sob_carga_com_teto_curto: Any) -> None:
    """A fase que bate o teto anota a fome, e a R1 reprova dizendo a causa."""
    fora = sob_carga_com_teto_curto
    tiques, segundos, _buraco = fora.famintas["escondida"]
    assert tiques < TIQUES_POR_FASE and segundos >= fora.teto_da_fase_s, fora.famintas
    with pytest.raises(AssertionError, match=(
            r"a fase escondida juntou \d+ de 40 tiques em \d+,\d s \(maior buraco: "
            r"\d+,\d s\): o laço do GTK andou devagar demais para medir")):
        _a_escondida_nao_trabalha(fora)
