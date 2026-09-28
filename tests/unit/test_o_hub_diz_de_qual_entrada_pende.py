"""O hub diz de qual entrada pende — O-MAPA-QUE-ELA-CORRIGE-01, passo 5.

Pedido dela: *«identificar onde fica o hub»*. A face «Num hub ou extensão» não
sabia que pendia da entrada 3: o plugue 3 dizia «Hub · 3-1», a face dizia «4 de
7», e nada ligava um ao outro. Declarar «Hub» na 3 PIORAVA: nascia uma segunda
face com quatro buracos inventados, e o painel passava a «15 de 19» — a
deduplicação comparava só o nome da face (D-2609-O-HUB-PENDE-DA-ENTRADA).
<!-- noqa-acento: citação literal dela -->

A ligação é do dono (``entrada_a_entrada.de_quem_pende``), sobre o que o
Mapear gravou no disco — por isso vale com o hub desplugado. A tela a recebe
pelo arranjo: ``daEntrada``, o ``titulo`` («Hub na Entrada 3»), a
``diverge`` (a frase da divergência) e o ``hubLido``.

A MORDIDA: devolva a deduplicação pelo nome no
``arranjo_desta_maquina._o_que_ela_declarou_nas_entradas`` (``nome in nomes``
no lugar de ``numero in ligadas``) — o «Hub» na 3 volta a criar a face de
quatro buracos, e «15 de 19» reprova
(``test_hub_declarado_na_3_nao_cria_face``).

Máquina sintética (a forma da dela, de ``test_o_nome_da_entrada_e_da_posicao``)
e o censo sintético do hub de dois chips, nos barramentos ``3``/``4`` dela.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee
from hefesto_dualsense4unix.integrations import mapa_das_portas
from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    Aparelho,
    Barramento,
    Censo,
)
from hefesto_dualsense4unix.interface import arranjo_desta_maquina
from hefesto_dualsense4unix.utils.maquina import MaquinaConfig, migrar_o_documento
from tests.unit.test_o_nome_da_entrada_e_da_posicao import _a_maquina_dela


def _aparelho(caminho: str, mbps: float, classe: str, *, hub: bool = False) -> Aparelho:
    return Aparelho(
        no=f"/sys/{caminho}", nome_do_kernel=caminho, produto=f"Aparelho {caminho}",
        classe=classe, velocidade_mbps=mbps, e_hub=hub,
    )


#: O hub de dois chips na entrada 3 (``3-1``/``3-1.1`` e o gêmeo ``4-1``/``4-1.1``)
#: e dois aparelhos nele: o teclado na 11 e o adaptador na 13.
_CENSO = Censo(
    aparelhos=(
        _aparelho("3-1", 480.0, "09", hub=True),
        _aparelho("3-1.1", 480.0, "09", hub=True),
        _aparelho("4-1", 5000.0, "09", hub=True),
        _aparelho("4-1.1", 5000.0, "09", hub=True),
        _aparelho("3-1.1.2", 12.0, "03"),
        _aparelho("3-1.4", 12.0, "e0"),
    ),
    barramentos=(
        Barramento(no="/sys/usb3", nome_do_kernel="usb3", velocidade_mbps=480.0),
        Barramento(no="/sys/usb4", nome_do_kernel="usb4", velocidade_mbps=5000.0),
    ),
)

_HUB = ee.FACE_HUB


def _documento(**mudar: Any) -> MaquinaConfig:
    """A máquina sintética; ``mudar`` põe campos em ``portas[N]``."""
    dado = _a_maquina_dela()
    for numero, campos in mudar.items():
        dado["mapa"]["portas"].setdefault(numero.lstrip("_"), {}).update(campos)
    return MaquinaConfig.model_validate(migrar_o_documento(dado))


def _arranjo(documento: MaquinaConfig, censo: Censo = _CENSO) -> dict[str, Any]:
    dado = arranjo_desta_maquina.arranjo(
        carregar=lambda: documento, ler_o_barramento=lambda: censo,
        ler_o_serial=lambda _no: "")
    assert dado is not None
    return dado


def _entradas(dado: dict[str, Any]) -> int:
    return sum(len(f["portas"]) + sum(1 for p in f["portas"] if "filho" in p)
               for f in dado["faces"])


def _a_face(dado: dict[str, Any], nome: str) -> dict[str, Any]:
    return next(f for f in dado["faces"] if f["nome"] == nome)


def test_a_face_do_hub_pende_da_3() -> None:
    """Sem declarar nada: o barramento lê a face 9…15 na 3, e a tela diz
    «Hub na Entrada 3» e marca a 3."""
    documento = _documento()
    pende = ee.de_quem_pende(documento.mapa)
    assert pende == {_HUB: ee.Pendencia("3", None, False, "3")}
    dado = _arranjo(documento)
    face = _a_face(dado, _HUB)
    assert (face["daEntrada"], face["titulo"]) == ("3", "Hub na Entrada 3")
    assert "diverge" not in face
    assert dado["hubLido"] == {"3": True}
    assert _entradas(dado) == 15


def test_hub_declarado_na_3_nao_cria_face() -> None:
    """«Hub» declarado na 3 liga à face que já existe: continuam 15 entradas."""
    dado = _arranjo(_documento(**{"3": {"liga": "hub"}}))
    assert _entradas(dado) == 15, "o hub declarado criou a face de quatro buracos"
    assert not any(f.get("fantasma") for f in dado["faces"])
    assert _a_face(dado, _HUB)["titulo"] == "Hub na Entrada 3"


def test_so_hub_na_5_vale_a_dela_e_diz_onde_o_computador_le() -> None:
    """Só «Hub» na 5, e nada na 3: vale a dela, com a linha a mais — e sem a
    face fantasma."""
    dado = _arranjo(_documento(**{"5": {"liga": "hub"}}))
    face = _a_face(dado, _HUB)
    assert face["daEntrada"] == "5"
    assert face["titulo"] == "Hub na Entrada 5"
    assert face["diverge"] == "O computador lê este hub na Entrada 3."
    assert dado["hubLido"] == {"3": True}
    assert _entradas(dado) == 15


def test_hub_declarado_com_nada_lido_desenha_os_quatro_buracos() -> None:
    """Uma máquina sem o hub no disco: o hub declarado na 5 é a face de quatro
    buracos, como antes."""
    dado = _a_maquina_dela()
    dado["mapa"]["faces"] = dado["mapa"]["faces"][:2]
    for numero in range(9, 16):
        del dado["mapa"]["portas"][str(numero)]
    dado["mapa"]["portas"]["5"]["liga"] = "hub"
    documento = MaquinaConfig.model_validate(migrar_o_documento(dado))
    assert ee.de_quem_pende(documento.mapa) == {}
    arranjo = _arranjo(documento, Censo(barramentos=_CENSO.barramentos))
    fantasma = _a_face(arranjo, ee.FACE_DO_HUB_DECLARADO.format(numero="5"))
    assert fantasma["fantasma"] and fantasma["daEntrada"] == "5"
    assert [p["n"] for p in fantasma["portas"]] == ["5.1", "5.2", "5.3", "5.4"]
    assert fantasma["titulo"] == "Hub na Entrada 5"


def test_dois_hubs_lidos_cada_um_com_a_sua_face() -> None:
    """Um segundo hub na 6 (``3-4``), com a face dele: cada face na sua entrada."""
    dado = _a_maquina_dela()
    dado["mapa"]["faces"].append({"nome": "Outro hub", "portas": ["16", "17"]})
    dado["mapa"]["portas"]["16"] = {"caminho": "3-4.1", "nos": ["3-4-port1", "4-4-port1"]}
    dado["mapa"]["portas"]["17"] = {"caminho": "3-4.2", "nos": ["3-4-port2", "4-4-port2"]}
    pende = ee.de_quem_pende(MaquinaConfig.model_validate(migrar_o_documento(dado)).mapa)
    assert {nome: p.entrada for nome, p in pende.items()} == {_HUB: "3", "Outro hub": "6"}


def test_a_face_mista_nao_pende_de_ninguem() -> None:
    dado = _a_maquina_dela()
    dado["mapa"]["faces"][2]["portas"].append("7")
    assert _HUB not in ee.de_quem_pende(MaquinaConfig.model_validate(migrar_o_documento(dado)).mapa)


def test_o_hub_desplugado_continua_ligado() -> None:
    """O barramento de agora sem o hub: a ligação é pelo que o Mapear gravou."""
    documento = _documento()
    sem_hub = Censo(barramentos=_CENSO.barramentos)
    dado = _arranjo(documento, sem_hub)
    face = _a_face(dado, _HUB)
    assert (face["daEntrada"], face["titulo"]) == ("3", "Hub na Entrada 3")


def test_o_titulo_diz_o_nome_que_ela_deu() -> None:
    documento = _documento(**{"3": {"nome": "Traseira de cima"}})
    face = _a_face(_arranjo(documento), _HUB)
    assert face["titulo"] == "Hub na entrada Traseira de cima"


@pytest.mark.parametrize("numero", ["3", "5"])
def test_a_face_da_tela_bate_com_o_motor(numero: str) -> None:
    """O motor do mapa lê as mesmas entradas que o arranjo manda para a tela."""
    documento = _documento(**{numero: {"liga": "hub"}})
    mesa = mapa_das_portas.mesa_do_motor(documento.mapa, _CENSO).mesa
    dado = _arranjo(documento)
    assert {f.nome for f in mesa.faces} <= {f["nome"] for f in dado["faces"]}
