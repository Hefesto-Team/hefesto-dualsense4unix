"""A Conexões sem o «Onde fica?», sem o sino do adaptador e sem o título dos outros rádios.

Pedido de 29/10/2026, que já tinha sido feito antes: os três voltaram porque nunca saíram do
gerador. A sprint A-LINHA-DO-ADAPTADOR-NAO-CABE-NA-COLUNA-DO-ONDE-01 (24/10) deu lugar próprio ao
«Onde fica?» e ao sino em vez de tirá-los. Agora saem do pacote, do desenho do rádio de onde a 08
tira a sala, da camada e do registro de gestos, e a régua reprova se um deles voltar a qualquer um.
MORDIDA: o `<div class="ar-grupo outros">Outros dispositivos sem fio</div>` de volta em
`html_dos_canais` reprova o desenho, depois do `regerar.py`.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import GESTOS, a08_conexoes, camada

PROIBIDOS = ("Onde fica?", "Outros dispositivos sem fio", 'class="sino"', 'class="ensina"',
             "adaptador-historico", 'data-painel="sino"', "ar-no-titulo", "data-fora-no-titulo")


@pytest.mark.parametrize("publicado", [False, True], ids=["desenho", "publicado"])
def test_a_pagina_da_08_nao_tem_nenhum_dos_tres(publicado: bool) -> None:
    doc = onde.pagina("08-conexoes.html", publicado=publicado).read_text(encoding="utf-8")
    achados = [p for p in PROIBIDOS if p in doc]
    assert not achados, f"voltou à Conexões: {achados}"


@pytest.mark.parametrize("publicado", [False, True], ids=["desenho", "publicado"])
def test_o_desenho_do_radio_nao_cria_nenhum_dos_tres(publicado: bool) -> None:
    doc = onde.pagina("mapa-do-radio.html", publicado=publicado).read_text(encoding="utf-8")
    achados = [p for p in (*PROIBIDOS, "'sino'", "'ensina'", "abrirHistorico") if p in doc]
    assert not achados, f"voltou ao desenho de onde a 08 tira a sala: {achados}"


def test_o_sino_nao_e_gesto_nem_camada() -> None:
    assert a08_conexoes.html_dos_canais
    assert ("08-conexoes.html", "adaptador-historico") not in GESTOS
    assert ("08-conexoes.html", "adaptador-historico") not in camada.CAMADA
