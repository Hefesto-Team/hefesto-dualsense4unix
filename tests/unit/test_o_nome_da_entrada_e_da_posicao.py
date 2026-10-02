"""O nome da entrada é da POSIÇÃO — O-MAPA-QUE-ELA-CORRIGE-01, passo 2 (D1)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee
from hefesto_dualsense4unix.integrations.lugar_declarado import declarar_a_maquina
from hefesto_dualsense4unix.utils.maquina import (
    MaquinaConfig,
    caminho_da_maquina,
    carregar_maquina,
    lugar_de,
    migrar_o_documento,
)
from hefesto_dualsense4unix.utils.rotulo_da_entrada import (
    FRASE_DO_NOME_COMPRIDO,
    nome_que_vale,
)

PCI_A = "0000:0a:00.0"
PCI_B = "0000:0b:00.0"

_ENTRADAS: dict[str, tuple[str, str, str, list[str]]] = {
    "1": (PCI_A, "4", "1-4", ["usb1-port4"]),
    "2": (PCI_A, "3", "1-3", ["usb1-port3"]),
    "3": (PCI_B, "1", "3-1", ["usb3-port1", "usb4-port1"]),
    "4": (PCI_B, "2", "3-2", ["usb3-port2", "usb4-port2"]),
    "5": (PCI_B, "3", "3-3", ["usb3-port3", "usb4-port3"]),
    "6": (PCI_B, "4", "3-4", ["usb3-port4", "usb4-port4"]),
    "7": (PCI_A, "5", "1-5", ["usb1-port5"]),
    "8": (PCI_A, "6", "1-6", ["usb1-port6"]),
    "9": (PCI_B, "1.1.4", "3-1.1.4", ["3-1.1-port4", "4-1.1-port4"]),
    "10": (PCI_B, "1.1.3", "3-1.1.3", ["3-1.1-port3", "4-1.1-port3"]),
    "11": (PCI_B, "1.1.2", "3-1.1.2", ["3-1.1-port2", "4-1.1-port2"]),
    "12": (PCI_B, "1.1.1", "3-1.1.1", ["3-1.1-port1", "4-1.1-port1"]),
    "13": (PCI_B, "1.4", "3-1.4", ["3-1-port4", "4-1-port4"]),
    "14": (PCI_B, "1.3", "3-1.3", ["3-1-port3", "4-1-port3"]),
    "15": (PCI_B, "1.2", "3-1.2", ["3-1-port2", "4-1-port2"]),
}

_ORFAOS = {
    lugar_de(PCI_B, "4.1.1"): "Centro",
    lugar_de(PCI_B, "4.1.2"): "Esquerda",
    lugar_de(PCI_B, "4.1.3"): "Direita",
}


def _a_maquina_dela() -> dict[str, Any]:
    """O ``maquina.json`` sintético, como o Mapear de antes o deixava."""
    lugares: dict[str, Any] = {
        lugar_de(pci, devpath): {
            "entrada": numero,
            "caminho": caminho,
            "nome": "Meio" if numero == "1" else numero,
        }
        for numero, (pci, devpath, caminho, _nos) in _ENTRADAS.items()
    }
    lugares.update({lugar: {"nome": nome} for lugar, nome in _ORFAOS.items()})
    return {
        "mapa": {
            "faces": [
                {"nome": ee.FACE_FRENTE, "portas": ["1", "2"], "perto": True},
                {"nome": ee.FACE_ATRAS, "portas": ["3", "4", "5", "6", "7", "8"]},
                {"nome": ee.FACE_HUB, "portas": [str(n) for n in range(9, 16)], "alto": True},
            ],
            "portas": {
                numero: {"caminho": caminho, "nos": nos}
                for numero, (_pci, _devpath, caminho, nos) in _ENTRADAS.items()
            },
        },
        "lugares": lugares,
        "adaptadores": {"aabbcc00001a": {"nome": "Rádio da mesa"}},
    }


def gravar_o_arquivo_de_antes(tmp_path: Path, documento: dict[str, Any]) -> Path:
    """O ``maquina.json`` como o produto de antes o deixava — escrito CRU, sem"""
    alvo = caminho_da_maquina()
    assert alvo.is_relative_to(tmp_path), f"o maquina.json da régua não está desviado: {alvo}"
    corpo = {"version": 1, **documento}
    alvo.write_text(
        json.dumps(corpo, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    return alvo


@pytest.fixture()
def disco(tmp_path: Path) -> Path:
    """A máquina sintética no ``maquina.json`` do ``tmp_path``, na forma de antes."""
    return gravar_o_arquivo_de_antes(tmp_path, _a_maquina_dela())


def _migrada() -> MaquinaConfig:
    return MaquinaConfig.model_validate(migrar_o_documento(_a_maquina_dela()))


def test_o_rotulo_pergunta_ao_dono_e_o_nome_mora_na_posicao() -> None:
    """A 1 é «Meio» e a 2 é «Entrada 2»: o «Meio» veio para a posição, e o"""
    documento = _migrada()
    assert documento.mapa.portas["1"].nome == "Meio"
    assert ee.rotulo_do_numero("1", maquina=documento) == "Meio"
    assert ee.rotulo_do_numero("2", maquina=documento) == "Entrada 2"
    assert ee.rotulo_do_numero("15", maquina=documento) == "Entrada 15"
    assert ee.nome_da_entrada("2", maquina=documento) is None
    assert ee.rotulo_do_numero("2") == "Entrada 2", "sem o maquina é a palavra do dono"
    rotulos = ee.rotulos_das_entradas(documento)
    assert rotulos["1"] == {"rotulo": "Meio", "naFrase": "entrada Meio"}
    assert rotulos["2"] == {"rotulo": "Entrada 2", "naFrase": "Entrada 2"}
    assert list(rotulos) == [str(n) for n in range(1, 16)], "a ordem é a do desenho"
    assert not any(r["rotulo"].isdigit() for r in rotulos.values()), rotulos

    com_o_numero = documento.model_copy(deep=True)
    com_o_numero.mapa.portas["2"].nome = "2"
    assert ee.nome_da_entrada("2", maquina=com_o_numero) is None
    assert ee.rotulo_do_numero("2", maquina=com_o_numero) == "Entrada 2"


def test_a_primeira_leitura_muda_o_nome_de_casa(disco: Path) -> None:
    """A primeira leitura leva o «Meio» para a posição, cada lugar para a"""
    depois = carregar_maquina()
    assert "lugares" not in json.loads(disco.read_text(encoding="utf-8"))
    assert depois.mapa.portas["1"].nome == "Meio"
    for numero, (pci, devpath, _caminho, _nos) in _ENTRADAS.items():
        assert depois.mapa.portas[numero].lugar == lugar_de(pci, devpath), numero
        if numero != "1":
            assert depois.mapa.portas[numero].nome is None, (
                f"o «{numero}» virou nome da entrada {numero}")
    texto = disco.read_text(encoding="utf-8")
    assert not any(f'"{nome}"' in texto for nome in _ORFAOS.values()), texto
    assert depois.adaptadores["aabbcc00001a"].nome == "Rádio da mesa"

    bytes_depois = disco.read_bytes()
    assert ee.declarar_a_velocidade("4", 3).gravou
    assert carregar_maquina().mapa.portas["4"].usb == 3
    agora = json.loads(disco.read_bytes())
    agora["mapa"]["portas"]["4"].pop("usb")
    assert MaquinaConfig.model_validate(agora) == MaquinaConfig.model_validate(
        json.loads(bytes_depois))


def test_o_nome_de_mais_de_24_nao_se_perde_e_o_nome_dela_destrava(tmp_path: Path) -> None:
    """O nome comprido demais não cabe na posição: aquele lugar fica no arquivo"""
    comprido = "A de trás, perto do cabo de rede"
    assert len(comprido) > 24
    lugar_5 = lugar_de(PCI_B, "3")
    documento = _a_maquina_dela()
    documento["lugares"][lugar_5]["nome"] = comprido
    disco = gravar_o_arquivo_de_antes(tmp_path, documento)

    depois = carregar_maquina()
    assert json.loads(disco.read_text(encoding="utf-8"))["lugares"][lugar_5]["nome"] == comprido
    assert depois.mapa.portas["5"].nome is None and depois.mapa.portas["5"].lugar is None
    assert ee.rotulo_do_numero("5", maquina=depois) == "Entrada 5"

    assert ee.dar_nome_a_entrada("5", "Trás").gravou
    destravada = carregar_maquina()
    assert "lugares" not in json.loads(disco.read_text(encoding="utf-8"))
    assert destravada.mapa.portas["5"].lugar == lugar_5
    assert ee.rotulo_do_numero("5", maquina=destravada) == "Trás"


def test_o_nome_grava_apaga_e_recusa_o_comprido(disco: Path) -> None:
    """``dar_nome_a_entrada``: grava na posição, vazio (ou «Entrada N») apaga,"""
    assert ee.dar_nome_a_entrada("3", "  Hub da mesa  ").gravou
    documento = carregar_maquina()
    assert documento.mapa.portas["3"].nome == "Hub da mesa"
    assert ee.rotulo_do_numero("3", maquina=documento) == "Hub da mesa"
    assert documento.mapa.portas["3"].lugar == lugar_de(PCI_B, "1"), "o nome mexeu no lugar"

    assert ee.dar_nome_a_entrada("3", "Entrada 3").gravou
    assert ee.rotulo_do_numero("3", maquina=carregar_maquina()) == "Entrada 3"
    assert ee.dar_nome_a_entrada("3", "Canto").gravou
    assert ee.dar_nome_a_entrada("3", "").gravou
    documento = carregar_maquina()
    assert documento.mapa.portas["3"].nome is None
    assert ee.rotulo_do_numero("3", maquina=documento) == "Entrada 3"

    guardado = disco.read_bytes()
    with pytest.raises(ValueError, match=re.escape(FRASE_DO_NOME_COMPRIDO)):
        ee.dar_nome_a_entrada("3", "x" * 25)
    with pytest.raises(ValueError, match="não está no mapa"):
        ee.dar_nome_a_entrada("99", "Nenhuma")
    assert disco.read_bytes() == guardado, "a recusa escreveu no disco"
    assert ee.dar_nome_a_entrada("3", "y" * 24).gravou, "24 cabem"


def test_o_mapear_grava_o_nome_na_posicao_e_o_no_mora_numa_entrada_so(disco: Path) -> None:
    """O Mapear com número grava ``portas[N].nome``; e quando o buraco sai de"""
    documento = carregar_maquina()
    vista = ee.PortaVista(lugar=lugar_de(PCI_A, "4"), caminho="1-4")
    feita = ee._gravar_as_portas(
        [(vista, ("usb1-port4",))],
        ee.FACE_FRENTE,
        maquina=documento,
        controladores={1: PCI_A, 3: PCI_B},
        nome="Frente de baixo",
    )
    assert feita.gravou and feita.entrada == "1"
    depois = carregar_maquina()
    assert depois.mapa.portas["1"].nome == "Frente de baixo"
    assert depois.mapa.portas["1"].lugar == lugar_de(PCI_A, "4")

    assert declarar_a_maquina({"mapa": {"portas": {
        "2": {"lugar": lugar_de(PCI_A, "5"), "nos": []},
        "7": {"lugar": None},
    }}}).gravou
    depois = carregar_maquina()
    assert depois.mapa.portas["7"].nos == ["usb1-port5"] and depois.mapa.portas["7"].lugar is None
    vista = ee.PortaVista(lugar=lugar_de(PCI_A, "5"), caminho="1-5")
    assert ee._gravar_as_portas(
        [(vista, ("usb1-port5",))],
        ee.FACE_FRENTE,
        maquina=depois,
        controladores={1: PCI_A, 3: PCI_B},
    ).gravou
    depois = carregar_maquina()
    assert depois.mapa.portas["2"].nos == ["usb1-port5"]
    sete = depois.mapa.portas.get("7")
    assert sete is None or (sete.caminho is None and not sete.nos), (
        f"o nó da 2 ficou também na 7: {sete}")


def test_o_gesto_do_nome_arma_no_clique_e_grava_no_change(
    disco: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O gesto ``entrada-nome`` do ``a12``: o clique que só põe o cursor arma;"""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")
    from hefesto_dualsense4unix.interface import arranjo_desta_maquina
    from hefesto_dualsense4unix.interface.pacotes import a12_mapa_das_portas as a12

    monkeypatch.setattr(arranjo_desta_maquina, "depois_de_gravar", lambda: {"ok": True})
    assert a12.entrada_nome(None, {"evento": "click", "entrada": "2"}, None) == {"armou": True}
    assert carregar_maquina().mapa.portas["2"].nome is None, "o clique gravou"
    volta = a12.entrada_nome(None, {"evento": "change", "entrada": "2", "valor": "Canto"}, None)
    assert volta == {arranjo_desta_maquina.CHAVE_DEPOIS_DE_GRAVAR: {"ok": True}}
    assert carregar_maquina().mapa.portas["2"].nome == "Canto"
    with pytest.raises(ValueError, match=re.escape(FRASE_DO_NOME_COMPRIDO)):
        a12.entrada_nome(None, {"evento": "change", "entrada": "2", "valor": "z" * 25}, None)


def _com_o_mapa_trocado_por_fora() -> dict[str, Any]:
    """A forma do disco dela depois de 26/09/2026 às 15h43 (MEDIDO): o ``mapa``"""
    documento = _a_maquina_dela()
    portas = documento["mapa"]["portas"]
    for um, outro in (("3", "4"), ("7", "8")):
        portas[um], portas[outro] = portas[outro], portas[um]
    return documento


def test_o_numero_de_outra_entrada_tambem_nao_e_nome() -> None:
    """O «3» que o Mapear gravou no lugar da 3 não vira o nome da 4."""
    documento = MaquinaConfig.model_validate(migrar_o_documento(_com_o_mapa_trocado_por_fora()))
    controladores = {1: PCI_A, 3: PCI_B, 4: PCI_B}
    hub, mouse = lugar_de(PCI_B, "1"), lugar_de(PCI_A, "5")
    assert ee.nome_da_porta("3-1", maquina=documento, controladores=controladores) == (
        "Entrada 4")
    assert ee.nome_da_porta("1-5", maquina=documento, controladores=controladores) == (
        "Entrada 8")
    assert ee.rotulo_da_entrada(hub, maquina=documento, controladores=controladores) == (
        "Entrada 4")
    assert ee.nome_do_lugar(mouse, maquina=documento, controladores=controladores) == (
        "Entrada 8")
    assert ee.nome_da_entrada("4", maquina=documento) is None
    assert ee.nome_da_entrada("7", maquina=documento) is None
    assert ee.rotulo_do_numero("1", maquina=documento) == "Meio"
    for nome in ("Meio", "USB 3", "3ª de cima", "Hub 2"):
        assert nome_que_vale("4", nome) == nome
    for numero_como_nome in ("3", "8", "15a", "Entrada 3", "entrada  12"):
        assert nome_que_vale("4", numero_como_nome) is None, numero_como_nome
