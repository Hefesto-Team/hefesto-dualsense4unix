"""A JANELA ABERTA NÃO GASTA O PROCESSADOR, na página 02.

A-JANELA-ABERTA-NAO-GASTA-O-PROCESSADOR-01.

Os três cenários da 02 (1, 2 e 4 controles) do `esconde_e_volta`, cada um com as seis
réguas de sempre; o ajudante e o resto das réguas estão em `janela_aberta_comum.py` e nos
quatro arquivos irmãos (A-JANELA-ABERTA-CABE-NA-PARTE-01).
"""
from __future__ import annotations

import pathlib
from types import SimpleNamespace
from typing import Any

import pytest

from tests.unit.janela_aberta_comum import (
    _a_aba_quieta_nao_e_muda,
    _a_escondida_nao_trabalha,
    _a_volta_leva_a_carga_inteira,
    _o_coracao_bate_escondido,
    _parada_pinta_so_as_cargas_inteiras,
    _trocar_de_aba_nao_e_esconder,
    cenarios_da,
    esconde_e_volta_de,
    ids_dos_cenarios,
    publicar_as_de_hoje,
)


@pytest.fixture(scope="module")
def publicado_de_hoje(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    return publicar_as_de_hoje(tmp_path_factory)


CENARIOS_DA_PAGINA = cenarios_da("02-controles.html")


@pytest.fixture(scope="module", params=CENARIOS_DA_PAGINA,
                ids=ids_dos_cenarios(CENARIOS_DA_PAGINA))
def esconde_e_volta(request: pytest.FixtureRequest,
                    publicado_de_hoje: pathlib.Path) -> SimpleNamespace:
    return esconde_e_volta_de(publicado_de_hoje, request.param)


def test_r1_a_janela_escondida_nao_pinta_nem_pergunta(esconde_e_volta: Any) -> None:
    """Escondida, zero pintura, zero `pactl` e uma leitura do estado por segundo."""
    _a_escondida_nao_trabalha(esconde_e_volta)


def test_r1_o_coracao_segue_batendo_escondido(esconde_e_volta: Any) -> None:
    """Esconder não é largar: o teste de motor em curso segue batendo."""
    _o_coracao_bate_escondido(esconde_e_volta)


def test_r1_na_volta_a_carga_vai_inteira_e_com_estado_novo(esconde_e_volta: Any) -> None:
    """Na volta, a primeira pintura é inteira, e sai em até 3 tiques, depois"""
    _a_volta_leva_a_carga_inteira(esconde_e_volta)


def test_r1_trocar_de_aba_nao_e_esconder(esconde_e_volta: Any) -> None:
    """A janela só se esconde quando a janela se esconde: a troca de aba não conta."""
    _trocar_de_aba_nao_e_esconder(esconde_e_volta)


def test_r2_parada_a_aba_pinta_so_as_cargas_inteiras(esconde_e_volta: Any) -> None:
    """Com o estado imóvel, os 40 tiques à vista dão no máximo 5 pinturas."""
    _parada_pinta_so_as_cargas_inteiras(esconde_e_volta)


def test_r2_a_aba_quieta_nao_e_aba_muda(esconde_e_volta: Any) -> None:
    """O detector de aba muda do `_relatar` não acusa a aba parada."""
    _a_aba_quieta_nao_e_muda(esconde_e_volta)
