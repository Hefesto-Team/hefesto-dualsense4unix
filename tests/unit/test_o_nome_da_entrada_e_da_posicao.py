"""O nome da entrada é da POSIÇÃO — O-MAPA-QUE-ELA-CORRIGE-01, passo 2 (D1).

O pedido dela, com o mapa aberto: *«me referi as portas renomear»*. O nome
morava em ``lugares[<lugar>].nome`` e o Mapear gravava o número como nome
(«2», «15»); a tela dizia «2» onde devia dizer «Entrada 2». Desde
26/09/2026 (D-2609-O-NOME-E-DA-POSICAO) ele mora em ``mapa.portas[N].nome``,
até 24 caracteres, e o dono da leitura é ``entrada_a_entrada.nome_da_entrada``.
<!-- noqa-acento: citação literal dela -->

A MÁQUINA DAQUI É SINTÉTICA, NA FORMA DA DELA: 15 entradas, Frente [1, 2],
Atrás [3…8] e uma face de hub [9…15] sob ``3-1``/``3-1.1``; os nomes «1»…
«15» nos lugares, a 1 como «Meio», e três lugares órfãos (nome sem número).
Controladores e endereços são da faixa sintética da casa (``0000:0a:00.0``,
``0000:0b:00.0``, ``aa:bb:cc``).

AS MORDIDAS:

* tire a reserva do ``nome_da_entrada`` (a leitura de
  ``lugares[lugar_da_entrada(N)].nome``): «Meio» some antes da primeira
  gravação (``test_o_rotulo_pergunta_ao_dono_e_a_reserva_le_o_lugar``);
* tire o ``nome_que_vale`` do ``nome_da_entrada``: volta «2»
  (``test_o_rotulo_pergunta_ao_dono_e_a_reserva_le_o_lugar``).
"""

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
)
from hefesto_dualsense4unix.utils.rotulo_da_entrada import FRASE_DO_NOME_COMPRIDO

PCI_A = "0000:0a:00.0"
PCI_B = "0000:0b:00.0"

#: ``número -> (controlador, devpath, caminho, nós)`` — a forma do gabinete dela.
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

#: Os três lugares que ela nomeou e que não são entrada de número nenhum.
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


@pytest.fixture()
def disco(tmp_path: Path) -> Path:
    """A máquina sintética no ``maquina.json`` do ``tmp_path`` — conferido antes."""
    alvo = caminho_da_maquina()
    assert alvo.is_relative_to(tmp_path), f"o maquina.json da régua não está desviado: {alvo}"
    assert declarar_a_maquina(_a_maquina_dela()).gravou
    return alvo


def test_o_rotulo_pergunta_ao_dono_e_a_reserva_le_o_lugar() -> None:
    """Antes de qualquer gravação: a 1 é «Meio» (pela reserva) e a 2 é «Entrada 2».

    O «2» gravado como nome não é nome; o «Meio» ainda mora no lugar, e a
    reserva do dono o lê até a primeira gravação o mudar de casa.
    """
    documento = MaquinaConfig.model_validate(_a_maquina_dela())
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


def test_a_primeira_gravacao_muda_o_nome_de_casa(disco: Path) -> None:
    """Uma gravação que já acontece (a velocidade da 4) leva o «Meio» para a
    posição, apaga o «2»… «15» dos lugares, e deixa os órfãos e o adaptador.

    Os rótulos antes e depois são IGUAIS: a mudança não se vê na tela.
    """
    antes = carregar_maquina()
    rotulos_antes = ee.rotulos_das_entradas(antes)
    assert ee.declarar_a_velocidade("4", 3).gravou

    depois = carregar_maquina()
    assert depois.mapa.portas["1"].nome == "Meio"
    assert depois.mapa.portas["4"].usb == 3, "a declaração explícita também foi"
    for numero, (pci, devpath, _caminho, _nos) in _ENTRADAS.items():
        dele = depois.lugares[lugar_de(pci, devpath)]
        assert dele.nome is None, f"o nome da entrada {numero} ficou no lugar: {dele.nome!r}"
        assert dele.entrada == numero, "mudar o nome de casa mexeu na amarra"
        if numero != "1":
            assert depois.mapa.portas[numero].nome is None, (
                f"o «{numero}» virou nome da entrada {numero}")
    for lugar, nome in _ORFAOS.items():
        assert depois.lugares[lugar].nome == nome, "o lugar sem número foi tocado"
    assert depois.adaptadores["aabbcc00001a"].nome == "Rádio da mesa"
    assert ee.rotulos_das_entradas(depois) == rotulos_antes

    assert ee._o_nome_que_sai_do_lugar(depois, {}) == {}, "a mudança não é idempotente"
    bytes_depois = disco.read_bytes()
    assert ee.declarar_a_velocidade("4", 3).gravou
    assert json.loads(disco.read_bytes()) == json.loads(bytes_depois)


def test_o_nome_de_mais_de_24_fica_no_lugar_e_a_reserva_o_le(disco: Path) -> None:
    """O nome comprido demais não cabe na posição: não muda de casa, e a tela
    continua o dizendo pela reserva."""
    comprido = "A de trás, perto do cabo de rede"
    assert len(comprido) > 24
    lugar_5 = lugar_de(PCI_B, "3")
    assert declarar_a_maquina({"lugares": {lugar_5: {"nome": comprido}}}).gravou
    assert ee.declarar_a_velocidade("4", 2).gravou
    depois = carregar_maquina()
    assert depois.lugares[lugar_5].nome == comprido
    assert depois.mapa.portas["5"].nome is None
    assert ee.rotulo_do_numero("5", maquina=depois) == comprido


def test_o_nome_grava_apaga_e_recusa_o_comprido(disco: Path) -> None:
    """``dar_nome_a_entrada``: grava na posição, vazio (ou «Entrada N») apaga,
    25 caracteres recusa com a frase do dono e não toca o disco."""
    assert ee.dar_nome_a_entrada("3", "  Hub da mesa  ").gravou
    documento = carregar_maquina()
    assert documento.mapa.portas["3"].nome == "Hub da mesa"
    assert ee.rotulo_do_numero("3", maquina=documento) == "Hub da mesa"
    assert documento.lugares[lugar_de(PCI_B, "1")].nome is None

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
    """O Mapear com número grava ``portas[N].nome``; e quando o caminho sai de
    outra entrada, os nós dela saem junto (o nó velho punha o mesmo aparelho em
    duas entradas)."""
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
    assert depois.lugares[lugar_de(PCI_A, "4")].nome is None

    # a 2 passa a ser o buraco que era da 7: a 7 perde o caminho E os nós
    vista = ee.PortaVista(lugar=lugar_de(PCI_A, "3"), caminho="1-5")
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
    """O gesto ``entrada-nome`` do ``a12``: o clique que só põe o cursor arma;
    o ``change`` grava; o comprido recusa (a página pisca o campo)."""
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
