"""Trocar duas entradas move o BURACO, e o nome fica — O-MAPA-QUE-ELA-CORRIGE-01, passo 4.

Pedido dela: *«trocar elas de lugar no meapemento»*. O Mapear pôs o cabo de
uma entrada no número de outra (na máquina em que isto nasceu, 3↔4, 5↔6 e
7↔8 estavam trocadas), e ela corrige sem mapear de novo
(D-2609-TROCAR-MOVE-O-BURACO). <!-- noqa-acento: citação literal dela -->

O QUE VAI COM O BURACO: o caminho e os nós (juntos), a ``liga`` e a ``usb``, a
ponta do extensor inteira, a amarra de cada lugar e a face do hub declarado.
O QUE FICA NA POSIÇÃO: o número, o nome, a face e a ordem da fileira.

AS MORDIDAS:

* mova só o ``caminho`` (o defeito do ``colocar``) — a régua dos nós reprova
  (``test_trocar_7_com_8_leva_o_buraco_e_deixa_o_nome``);
* mova o ``nome`` — «o nome fica» reprova (a mesma);
* não troque os ``lugares`` — a coerência do ``entrada_do_lugar`` reprova (a
  mesma).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee
from hefesto_dualsense4unix.integrations.lugar_declarado import declarar_a_maquina
from hefesto_dualsense4unix.utils.maquina import (
    caminho_da_maquina,
    carregar_maquina,
    entrada_do_lugar,
    lugar_de,
)
from tests.unit.test_o_nome_da_entrada_e_da_posicao import PCI_A, _a_maquina_dela

_L7 = lugar_de(PCI_A, "5")
_L8 = lugar_de(PCI_A, "6")


def _com_o_que_ela_disse() -> dict[str, Any]:
    """A máquina dela, com nome, velocidade, hub e extensor nas entradas da troca."""
    documento = _a_maquina_dela()
    portas = documento["mapa"]["portas"]
    portas["7"].update({"usb": 2, "nome": "Sete"})
    portas["8"].update({"usb": 3, "liga": "extensor", "nome": "Oito"})
    portas["8a"] = {"filha_de": "8", "nome": "Ponta do cabo", "usb": 3}
    documento["lugares"][_L8]["fora"] = True
    return documento


@pytest.fixture()
def disco(tmp_path: Path) -> Path:
    alvo = caminho_da_maquina()
    assert alvo.is_relative_to(tmp_path), f"o maquina.json da régua não está desviado: {alvo}"
    assert declarar_a_maquina(_com_o_que_ela_disse()).gravou
    # A mudança do nome de casa (a primeira gravação) já feita: a troca parte
    # de um documento que ela não muda mais.
    assert ee.dar_nome_a_entrada("1", "Meio").gravou
    return alvo


def _lido(disco: Path) -> dict[str, Any]:
    return json.loads(disco.read_text(encoding="utf-8"))


def test_trocar_7_com_8_leva_o_buraco_e_deixa_o_nome(disco: Path) -> None:
    antes = carregar_maquina()
    assert ee.trocar_as_entradas("7", "8").gravou
    depois = carregar_maquina()
    sete, oito = depois.mapa.portas["7"], depois.mapa.portas["8"]
    a7, a8 = antes.mapa.portas["7"], antes.mapa.portas["8"]
    assert (sete.caminho, oito.caminho) == (a8.caminho, a7.caminho), "o caminho não foi"
    assert (sete.nos, oito.nos) == (a8.nos, a7.nos), "os nós não foram com o caminho"
    assert (sete.usb, oito.usb) == (3, 2), "a velocidade não foi com o buraco"
    assert (sete.liga, oito.liga) == ("extensor", None), "o extensor não foi com o buraco"
    assert (sete.nome, oito.nome) == ("Sete", "Oito"), "o nome saiu da posição"
    assert "8a" not in depois.mapa.portas and depois.mapa.portas["7a"].filha_de == "7"
    assert depois.mapa.portas["7a"].nome == "Ponta do cabo", "a ponta não foi inteira"
    assert depois.mapa.faces == antes.mapa.faces, "as faces mudaram"

    assert (depois.lugares[_L7].entrada, depois.lugares[_L8].entrada) == ("8", "7")
    assert depois.lugares[_L7].caminho == antes.lugares[_L7].caminho, "a testemunha andou"
    assert depois.lugares[_L8].fora is True, "o «Não alcanço» é do lugar e ficou"
    assert (entrada_do_lugar(depois, _L7), entrada_do_lugar(depois, _L8)) == ("8", "7")
    for lugar in (lugar_de(PCI_A, "4"), lugar_de(PCI_A, "3")):
        assert entrada_do_lugar(depois, lugar) == entrada_do_lugar(antes, lugar)


def test_trocar_de_novo_desfaz(disco: Path) -> None:
    """A troca é uma involução: duas trocas devolvem o documento igual."""
    antes = _lido(disco)
    assert ee.trocar_as_entradas("7", "8").gravou
    assert _lido(disco) != antes
    assert ee.trocar_as_entradas("8", "7").gravou
    assert _lido(disco) == antes


def test_o_hub_declarado_vai_com_o_buraco(disco: Path) -> None:
    """Hub declarado na 3, e a face «Hub na Entrada 3» no disco: trocada com a 5,
    a face passa a «Hub na Entrada 5», e a fileira dela fica onde estava."""
    documento = _lido(disco)
    faces = documento["mapa"]["faces"]
    faces[2]["nome"] = ee.FACE_DO_HUB_DECLARADO.format(numero="3")
    documento["mapa"]["portas"]["3"]["liga"] = "hub"
    assert declarar_a_maquina(documento).gravou

    assert ee.trocar_as_entradas("3", "5").gravou
    depois = carregar_maquina()
    nomes = [f.nome for f in depois.mapa.faces]
    assert ee.FACE_DO_HUB_DECLARADO.format(numero="5") in nomes
    assert ee.FACE_DO_HUB_DECLARADO.format(numero="3") not in nomes
    assert depois.mapa.faces[2].portas == [str(n) for n in range(9, 16)]
    assert (depois.mapa.portas["5"].liga, depois.mapa.portas["3"].liga) == ("hub", None)


@pytest.mark.parametrize(("um", "outro", "frase"), [
    ("7", "7", ee.RECUSA_A_MESMA_ENTRADA),
    ("7", "99", ee.RECUSA_FORA_DO_MAPA),
    ("7", "8a", ee.RECUSA_FORA_DO_MAPA),
    ("7", "5.1", ee.RECUSA_FORA_DO_MAPA),
])
def test_as_recusas_dizem_a_frase_do_dono(disco: Path, um: str, outro: str, frase: str) -> None:
    guardado = disco.read_bytes()
    with pytest.raises(ValueError) as erro:
        ee.trocar_as_entradas(um, outro)
    assert str(erro.value) == frase
    assert disco.read_bytes() == guardado, "a recusa escreveu no disco"


def test_nenhuma_das_duas_mapeada_recusa(disco: Path) -> None:
    documento = _lido(disco)
    documento["mapa"]["faces"][0]["portas"] += ["16", "17"]
    assert declarar_a_maquina(documento).gravou
    guardado = disco.read_bytes()
    with pytest.raises(ValueError) as erro:
        ee.trocar_as_entradas("16", "17")
    assert str(erro.value) == ee.RECUSA_NENHUMA_MAPEADA
    assert disco.read_bytes() == guardado


def test_o_nome_que_ainda_mora_no_lugar_nao_anda_com_o_buraco(tmp_path: Path) -> None:
    """Antes da primeira gravação, o «Meio» da 1 mora no lugar: a troca 1↔2 o
    muda de casa ANTES, e ele fica com a 1."""
    alvo = caminho_da_maquina()
    assert alvo.is_relative_to(tmp_path)
    assert declarar_a_maquina(_a_maquina_dela()).gravou
    assert ee.trocar_as_entradas("1", "2").gravou
    depois = carregar_maquina()
    assert ee.rotulo_do_numero("1", maquina=depois) == "Meio"
    assert ee.rotulo_do_numero("2", maquina=depois) == "Entrada 2"
    assert depois.mapa.portas["1"].caminho == "1-3"


def test_a_troca_sobrevive_ao_examinar_e_a_um_mapear_de_novo(disco: Path) -> None:
    """A conferência da O-MAPA-QUE-ELA-CORRIGE-01: a troca 7↔8 continua de pé
    depois do «Examinar» (o arranjo relido do disco) e de um «Mapear Entradas»
    que passa de novo pelo buraco que foi para a 8.

    O Mapear pergunta o número ao LUGAR (``_numero_conhecido``: a amarra, e
    depois o caminho). MEDIDO com a amarra arrancada da troca: ele ainda acha
    a 8 pelo caminho, mas o lugar da outra ponta perde a amarra
    (``entrada_do_lugar`` = ``None``) — e esta régua reprova. O nome de cada
    posição fica.
    """
    from hefesto_dualsense4unix.integrations.censo_do_barramento import Censo
    from hefesto_dualsense4unix.interface import arranjo_desta_maquina
    from tests.unit.test_o_nome_da_entrada_e_da_posicao import PCI_B

    assert ee.trocar_as_entradas("7", "8").gravou
    trocado = carregar_maquina()
    assert trocado.mapa.portas["8"].caminho == "1-5"

    relido = arranjo_desta_maquina.reexaminar(ler_o_barramento=lambda: Censo())
    assert relido is not None
    assert relido["rotulos"]["7"]["rotulo"] == "Sete"
    assert relido["rotulos"]["8"]["rotulo"] == "Oito"
    assert (relido["declarado"]["7"].get("usb"), relido["declarado"]["8"].get("usb")) == (3, 2)

    controladores = {1: PCI_A, 3: PCI_B}
    feita = ee._gravar_as_portas(
        [(ee.PortaVista(lugar=_L7, caminho="1-5"), ("usb1-port5",))],
        ee.FACE_ATRAS,
        maquina=trocado,
        controladores=controladores,
    )
    assert feita.gravou and feita.entrada == "8", "o Mapear devolveu o cabo à 7"
    depois = carregar_maquina()
    assert (depois.mapa.portas["7"].caminho, depois.mapa.portas["8"].caminho) == ("1-6", "1-5")
    assert (depois.mapa.portas["7"].nome, depois.mapa.portas["8"].nome) == ("Sete", "Oito")
    assert entrada_do_lugar(depois, _L7, controladores) == "8"
    assert entrada_do_lugar(depois, _L8, controladores) == "7"
