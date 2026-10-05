"""O extensor é a chave da porta, não o que está ligado nela.

O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 (04/10/2026). Ela disse: *«marcar Extensor impede
dizer que há um dispositivo BT ali»*. Antes, «Extensor» era uma das respostas de «O que tem
na entrada», ao lado de «Direto» e «Hub», e criava uma entrada-filha (a ponta). Agora é uma
chave ``extensor`` da própria entrada, que convive com o que ela declara estar ligado nela, e
que o motor lê como entrada esticada.

TUDO AQUI É DE MENTIRA: barramentos ``usb9``/``usb10`` e o ``maquina.json`` no ``tmp_path``
que o ``conftest`` desvia.

AS MORDIDAS (feitas na sprint, arrancando a cura e vendo reprovar):
* ``esticada=`` do ``mesa_do_motor`` — a régua do peso reprova;
* o passo ``_o_extensor_vira_a_chave`` da migração — a régua do disco antigo reprova;
* o ``extensor`` do ``_o_buraco`` — a troca deixa o extensor para trás e a régua reprova.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import arranjo_da_mesa as motor
from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee
from hefesto_dualsense4unix.integrations import mapa_das_portas
from hefesto_dualsense4unix.integrations.censo_do_barramento import Barramento, Censo
from hefesto_dualsense4unix.utils.maquina import (
    FaceDeclarada,
    MapaDaMesa,
    PortaDeclarada,
    caminho_da_maquina,
    carregar_maquina,
    gravar_maquina,
)

_LENTO, _RAPIDO = "usb9", "usb10"
_NOS = {
    "1": [f"{_LENTO}-port4"],
    "5": [f"{_LENTO}-port5", f"{_RAPIDO}-port1"],
    "7": [f"{_LENTO}-port6", f"{_RAPIDO}-port2"],
}


def _censo() -> Censo:
    return Censo(
        aparelhos=(),
        barramentos=(
            Barramento(no=f"/sys/{_LENTO}", nome_do_kernel=_LENTO, velocidade_mbps=480.0),
            Barramento(no=f"/sys/{_RAPIDO}", nome_do_kernel=_RAPIDO, velocidade_mbps=5000.0),
        ),
    )


def _mapa(extensor_na: str = "") -> MapaDaMesa:
    return MapaDaMesa(
        faces=[FaceDeclarada(nome="Frente", portas=["1"], perto=True),
               FaceDeclarada(nome="Traseira", portas=["5", "7"])],
        portas={
            n: PortaDeclarada(nos=nos, extensor=True if n == extensor_na else None)
            for n, nos in _NOS.items()
        },
    )


@pytest.fixture()
def disco(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from hefesto_dualsense4unix.integrations import censo_do_barramento

    alvo = caminho_da_maquina()
    assert alvo.is_relative_to(tmp_path), f"o maquina.json da régua não está desviado: {alvo}"
    assert gravar_maquina({"mapa": _mapa().model_dump(mode="json")})
    monkeypatch.setattr(censo_do_barramento, "ler_o_barramento", _censo)
    monkeypatch.setattr(mapa_das_portas, "serial_do_no", lambda _no: "")
    return alvo


def test_o_extensor_pesa_no_motor_so_nas_entradas_que_ela_marcou() -> None:
    """O motor lê ``esticada`` da chave da porta, e o BT ganha ponto na ponta do extensor."""
    bancada = mapa_das_portas.mesa_do_motor(_mapa(extensor_na="7"), _censo())
    esticadas = {e.n: e.esticada for f in bancada.mesa.faces for e in f.entradas}
    assert esticadas == {"1": False, "5": False, "7": True}, esticadas

    entradas = {e.n: e for f in bancada.mesa.faces for e in f.entradas}
    dongle = motor.Aparelho(id="9-9", tipo="Bluetooth", nome="Dongle", classe="bt")
    razoes = {
        n: {r.texto for r in motor.nota_de(
            bancada.mesa, dongle, entradas[n], {}, (), {}).razoes}
        for n in ("5", "7")
    }
    ponta = "na ponta do extensor: a antena que fica mais longe das outras"
    assert ponta in razoes["7"], "o BT na entrada esticada não ganhou a razão do extensor"
    assert ponta not in razoes["5"], "o extensor vazou para uma entrada que ela não marcou"


def test_o_disco_antigo_com_liga_extensor_e_a_ponta_vira_a_chave(disco: Path) -> None:
    """``liga: extensor`` + ``1a`` (filha) viram ``extensor: true`` na ``1``, sem a ponta."""
    bruto = json.loads(disco.read_text(encoding="utf-8"))
    bruto["mapa"]["portas"]["1"]["liga"] = "extensor"
    bruto["mapa"]["portas"]["1a"] = {"filha_de": "1", "nos": [f"{_LENTO}-port9"], "usb": 3}
    disco.write_text(json.dumps(bruto), encoding="utf-8")

    portas = carregar_maquina().mapa.portas
    assert portas["1"].extensor is True and portas["1"].liga is None
    assert "1a" not in portas, "a ponta do desenho antigo ficou no disco"
    assert portas["1"].nos == _NOS["1"], "a migração trocou os nós que o Mapear tinha gravado"
    assert portas["1"].usb == 3, "a velocidade que só a ponta tinha se perdeu"
    # idempotente: ler de novo não muda nada
    assert carregar_maquina().mapa.portas["1"].extensor is True


def test_o_hub_e_o_nome_da_ponta_antiga_passam_para_a_entrada(disco: Path) -> None:
    """A ponta que tinha um hub e um nome não os perde na migração.

    A cópia de antes (``.com-os-lugares``) só se escreve uma vez, e quem migrou os lugares em
    26/09 já a tem: o que a ponta sabia e a ``N`` não, ou passa para a ``N``, ou some. MORDE:
    tirar ``liga`` e ``nome`` dos campos que a migração leva reprova.
    """
    bruto = json.loads(disco.read_text(encoding="utf-8"))
    bruto["mapa"]["portas"]["1"]["liga"] = "extensor"
    bruto["mapa"]["portas"]["1a"] = {"filha_de": "1", "liga": "hub", "nome": "Mesa"}
    disco.write_text(json.dumps(bruto), encoding="utf-8")

    porta = carregar_maquina().mapa.portas["1"]
    assert porta.extensor is True
    assert porta.liga == "hub", "o hub que estava na ponta do extensor se perdeu"
    assert porta.nome == "Mesa", "o nome que ela deu à ponta se perdeu"


def test_o_extensor_convive_com_o_hub_e_cada_um_se_desliga_sozinho(disco: Path) -> None:
    """Marcar Extensor não tira o Hub (e vice-versa): são duas respostas."""
    assert ee.declarar_a_ligacao("5", "hub").gravou
    assert ee.declarar_o_extensor("5", True).gravou
    porta = carregar_maquina().mapa.portas["5"]
    assert (porta.liga, porta.extensor) == ("hub", True)

    assert ee.declarar_o_extensor("5", False).gravou
    porta = carregar_maquina().mapa.portas["5"]
    assert (porta.liga, porta.extensor) == ("hub", None)
    assert porta.nos == _NOS["5"]

    assert ee.declarar_o_extensor("5", True).gravou
    assert ee.declarar_a_ligacao("5", None).gravou
    porta = carregar_maquina().mapa.portas["5"]
    assert (porta.liga, porta.extensor) == (None, True)


def test_o_extensor_vai_junto_com_o_buraco_na_troca(disco: Path) -> None:
    """Trocar a 1 com a 7 leva o extensor com o buraco (o cabo é do buraco)."""
    assert ee.declarar_o_extensor("1", True).gravou
    assert ee.trocar_as_entradas("1", "7").gravou
    portas = carregar_maquina().mapa.portas
    assert portas["7"].extensor is True and portas["7"].nos == _NOS["1"]
    assert not portas["1"].extensor and portas["1"].nos == _NOS["7"]


def test_voltar_ao_automatico_tira_o_extensor_e_deixa_o_hub(disco: Path) -> None:
    assert ee.declarar_a_ligacao("5", "hub").gravou
    assert ee.declarar_o_extensor("5", True).gravou
    assert ee.voltar_ao_automatico(numero="5").gravou
    porta = carregar_maquina().mapa.portas["5"]
    assert (porta.liga, porta.extensor) == ("hub", None)
    with pytest.raises(ValueError):
        ee.voltar_ao_automatico(numero="99")
    with pytest.raises(ValueError):
        ee.voltar_ao_automatico()
