"""Trocar duas entradas move o BURACO, e o nome fica — O-MAPA-QUE-ELA-CORRIGE-01, passo 4."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee
from hefesto_dualsense4unix.integrations.lugar_declarado import declarar_a_maquina
from hefesto_dualsense4unix.utils.maquina import (
    carregar_maquina,
    entrada_do_lugar,
    lugar_de,
)
from tests.unit.test_o_nome_da_entrada_e_da_posicao import (
    PCI_A,
    _a_maquina_dela,
    gravar_o_arquivo_de_antes,
)

_L7 = lugar_de(PCI_A, "5")
_L8 = lugar_de(PCI_A, "6")


def _com_o_que_ela_disse() -> dict[str, Any]:
    """A máquina dela, com nome, velocidade, hub e extensor nas entradas da troca.

    O extensor é a chave da porta (``extensor: true``, desde 04/10/2026) e a ponta ``8a`` é a
    entrada-filha que o Mapear grava; as duas vão com o buraco. O documento no jeito de ANTES
    (``liga: extensor``) é de ``test_o_extensor_e_a_chave_da_porta``.
    """
    documento = _a_maquina_dela()
    portas = documento["mapa"]["portas"]
    portas["7"].update({"usb": 2, "nome": "Sete"})
    portas["8"].update({"usb": 3, "extensor": True, "nome": "Oito"})
    portas["8a"] = {"filha_de": "8", "nome": "Ponta do cabo", "usb": 3}
    documento["lugares"][_L8]["fora"] = True
    return documento


@pytest.fixture()
def disco(tmp_path: Path) -> Path:
    alvo = gravar_o_arquivo_de_antes(tmp_path, _com_o_que_ela_disse())
    carregar_maquina()
    return alvo


def _lido(disco: Path) -> dict[str, Any]:
    return json.loads(disco.read_text(encoding="utf-8"))


def test_trocar_7_com_8_leva_o_buraco_e_deixa_o_nome(disco: Path) -> None:
    antes = carregar_maquina()
    assert ee.trocar_as_entradas("7", "8").gravou
    depois = carregar_maquina()
    sete, oito = depois.mapa.portas["7"], depois.mapa.portas["8"]
    a7, a8 = antes.mapa.portas["7"], antes.mapa.portas["8"]
    assert (sete.lugar, oito.lugar) == (_L8, _L7), "o lugar não foi"
    assert (sete.nos, oito.nos) == (a8.nos, a7.nos), "os nós não foram com o lugar"
    assert (sete.caminho, oito.caminho) == (a8.caminho, a7.caminho)
    assert (sete.usb, oito.usb) == (3, 2), "a velocidade não foi com o buraco"
    assert (sete.extensor, oito.extensor) == (True, None), "o extensor não foi com o buraco"
    assert (sete.liga, oito.liga) == (None, None)
    assert (sete.nome, oito.nome) == ("Sete", "Oito"), "o nome saiu da posição"
    assert "8a" not in depois.mapa.portas and depois.mapa.portas["7a"].filha_de == "7"
    assert depois.mapa.portas["7a"].nome == "Ponta do cabo", "a ponta não foi inteira"
    assert depois.mapa.faces == antes.mapa.faces, "as faces mudaram"

    assert depois.mapa.fora == [_L8], "o «Não alcanço» é do lugar e ficou"
    assert (entrada_do_lugar(depois, _L7), entrada_do_lugar(depois, _L8)) == ("8", "7")
    for lugar in (lugar_de(PCI_A, "4"), lugar_de(PCI_A, "3")):
        assert entrada_do_lugar(depois, lugar) == entrada_do_lugar(antes, lugar)


def test_trocar_de_novo_desfaz(disco: Path) -> None:
    """A troca é uma involução: duas trocas devolvem o documento igual."""
    assert ee.declarar_a_velocidade("9", 3).gravou
    antes = _lido(disco)
    assert ee.trocar_as_entradas("7", "8").gravou
    assert _lido(disco) != antes
    assert ee.trocar_as_entradas("8", "7").gravou
    assert _lido(disco) == antes


def test_o_hub_declarado_vai_com_o_buraco(disco: Path) -> None:
    """Hub declarado na 3, e a face «Hub na Entrada 3» no disco: trocada com a 5,"""
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


def test_o_nome_que_morava_no_lugar_nao_anda_com_o_buraco(tmp_path: Path) -> None:
    """No arquivo de antes, o «Meio» da 1 mora no lugar: a primeira leitura o"""
    gravar_o_arquivo_de_antes(tmp_path, _a_maquina_dela())
    assert ee.trocar_as_entradas("1", "2").gravou
    depois = carregar_maquina()
    assert ee.rotulo_do_numero("1", maquina=depois) == "Meio"
    assert ee.rotulo_do_numero("2", maquina=depois) == "Entrada 2"
    assert depois.mapa.portas["1"].caminho == "1-3"


def test_a_troca_sobrevive_ao_examinar_e_a_um_mapear_de_novo(disco: Path) -> None:
    """A conferência da O-MAPA-QUE-ELA-CORRIGE-01: a troca 7↔8 continua de pé"""
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
    assert entrada_do_lugar(depois, _L7) == "8"
    assert entrada_do_lugar(depois, _L8) == "7"
