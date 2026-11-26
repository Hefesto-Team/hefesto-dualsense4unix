"""O jogo e o valor de fábrica das seções densas (mouse, luz, vibração).

(O-JOGO-PODE-APAGAR-E-IGUALAR-A-FABRICA-O-QUE-O-COMPUTADOR-DIZ-01 e
O-JOGO-QUE-ESCOLHE-O-VALOR-DE-FABRICA-VENCE-O-COMPUTADOR-01.)

O QUE FOI MEDIDO (08/10/2026): o arquivo do jogo guarda as seções ``leds``,
``rumble`` e ``mouse`` POR EXTENSO (o ``save_profile`` escreve o ``model_dump``
inteiro), então o ``model_fields_set`` de quem relê é sempre «todos os campos».
Pelo formato do arquivo não se separa «o usuário escolheu 6» de «a cópia do 6».
A CURA (D-2611-O-JOGO-MARCA-O-QUE-ESCOLHEU-IGUAL-A-FABRICA): o gesto que grava no
jogo um valor igual ao de fábrica marca o campo em ``Profile.escolhas_de_fabrica``;
o arquivo de antes, sem a marca, segue com o filtro de fábrica (a cópia não vence).

A MORDIDA: tire ``or campo in marcados`` de ``escolhas_globais_do_jogo`` e as réguas
da marca (mouse, luz e vibração) reprovam; tire o filtro de fábrica e as duas do
arquivo antigo reprovam.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc
from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    Profile,
    ProfileMouseConfig,
    RumbleConfig,
)
from hefesto_dualsense4unix.utils import maquina as m

JOGO = "Jogo X"
DO_COMPUTADOR = 9
_FABRICA = {c: ProfileMouseConfig.model_fields[c].default for c in ("speed", "scroll_speed")}


def _perfil(**mouse: Any) -> Profile:
    return Profile.model_validate({
        "name": JOGO, "match": {"type": "criteria", "window_class": ["jogo x"]},
        "mouse": {"enabled": True, **mouse}})


def _vale() -> Profile:
    return opc.perfil_que_vale(load_profile(JOGO), opc.o_computador())


@pytest.fixture(autouse=True)
def _computador_em_nove() -> None:
    assert m.gravar_o_computador({"global": {"mouse": {"speed": DO_COMPUTADOR}}})


def test_a_copia_de_fabrica_do_arquivo_antigo_nao_vence_o_computador() -> None:
    """Arquivo de antes: o 6 por extenso é a cópia, e o computador em 9 vale."""
    save_profile(_perfil(**_FABRICA))
    assert not opc.escolhas_globais_do_jogo(load_profile(JOGO), "mouse")
    assert _vale().mouse is not None and _vale().mouse.speed == DO_COMPUTADOR


def test_o_valor_diferente_da_fabrica_e_escolha_do_jogo() -> None:
    save_profile(_perfil(speed=7, scroll_speed=_FABRICA["scroll_speed"]))
    assert opc.escolhas_globais_do_jogo(load_profile(JOGO), "mouse") == {"speed": 7}
    assert _vale().mouse is not None and _vale().mouse.speed == 7


def test_a_seccao_do_jogo_vai_ao_disco_por_extenso() -> None:
    """A premissa medida: mover UM campo no jogo grava a seção inteira."""
    save_profile(_perfil(speed=5))

    def _muda(vista: Profile) -> Profile:
        assert vista.mouse is not None
        return vista.model_copy(update={"mouse": vista.mouse.model_copy(
            update={"speed": 7})})

    opc.gravar_pelo_gesto("mouse", JOGO, _muda, origem="regua")
    bruto = json.loads(loader._profile_path(load_profile(JOGO)).read_text(encoding="utf-8"))
    assert set(bruto["mouse"]) == {"enabled", "speed", "scroll_speed"}, bruto["mouse"]


def _gesto_do_mouse_para_a_fabrica() -> None:
    def _para_a_fabrica(vista: Profile) -> Profile:
        assert vista.mouse is not None
        return vista.model_copy(update={"mouse": vista.mouse.model_copy(
            update={"speed": _FABRICA["speed"]})})

    opc.gravar_pelo_gesto("mouse", JOGO, _para_a_fabrica, origem="regua")


def test_o_jogo_que_escolhe_a_fabrica_contra_o_computador_vale() -> None:
    """D-2611-O-JOGO-MARCA-O-QUE-ESCOLHEU-IGUAL-A-FABRICA: o 6 vale com o computador em 9."""
    save_profile(_perfil(speed=7))
    _gesto_do_mouse_para_a_fabrica()
    assert _vale().mouse is not None and _vale().mouse.speed == _FABRICA["speed"]
    assert load_profile(JOGO).escolhas_de_fabrica == {"mouse": ["speed"]}


def test_a_luz_que_o_jogo_escolhe_igual_a_fabrica_vale_contra_o_computador() -> None:
    """D-2611-O-JOGO-MARCA-O-QUE-ESCOLHEU-IGUAL-A-FABRICA: o brilho de fábrica do jogo vale."""
    fabrica = LedsConfig.model_fields["lightbar_brightness"].default
    assert m.gravar_o_computador({"global": {"leds": {"lightbar_brightness": 0.5}}})
    save_profile(Profile.model_validate({
        "name": JOGO, "match": {"type": "criteria", "window_class": ["jogo x"]},
        "leds": {"lightbar_brightness": 0.3}}))

    def _para_a_fabrica(vista: Profile) -> Profile:
        return vista.model_copy(update={"leds": vista.leds.model_copy(
            update={"lightbar_brightness": fabrica})})

    opc.gravar_pelo_gesto("luz", JOGO, _para_a_fabrica, origem="regua")
    assert _vale().leds.lightbar_brightness == fabrica
    assert load_profile(JOGO).escolhas_de_fabrica == {"leds": ["lightbar_brightness"]}


def test_a_vibracao_que_o_jogo_escolhe_igual_a_fabrica_vale_contra_o_computador() -> None:
    """D-2611-O-JOGO-MARCA-O-QUE-ESCOLHEU-IGUAL-A-FABRICA: o passthrough de fábrica do jogo vale."""
    fabrica = RumbleConfig.model_fields["passthrough"].default
    assert m.gravar_o_computador({"global": {"rumble": {"passthrough": not fabrica}}})
    save_profile(Profile.model_validate({
        "name": JOGO, "match": {"type": "criteria", "window_class": ["jogo x"]},
        "rumble": {"policy": "max", "passthrough": not fabrica}}))

    def _para_a_fabrica(vista: Profile) -> Profile:
        return vista.model_copy(update={"rumble": vista.rumble.model_copy(
            update={"passthrough": fabrica})})

    opc.gravar_pelo_gesto("vibracao", JOGO, _para_a_fabrica, origem="regua")
    assert _vale().rumble.passthrough is fabrica
    assert load_profile(JOGO).escolhas_de_fabrica == {"rumble": ["passthrough"]}


def test_voltar_ao_do_computador_tira_a_marca_e_o_computador_vale() -> None:
    """D-2611-O-JOGO-MARCA-O-QUE-ESCOLHEU-IGUAL-A-FABRICA: «sem escolha» é o que o voltar grava."""
    save_profile(_perfil(speed=7))
    _gesto_do_mouse_para_a_fabrica()
    opc.voltar_ao_do_computador("mouse", None, JOGO)
    assert load_profile(JOGO).escolhas_de_fabrica is None
    assert _vale().mouse is not None and _vale().mouse.speed == DO_COMPUTADOR


def test_o_gesto_que_tira_o_campo_da_fabrica_desmarca() -> None:
    """D-2611-O-JOGO-MARCA-O-QUE-ESCOLHEU-IGUAL-A-FABRICA: a marca vale com o valor de fábrica."""
    save_profile(_perfil(speed=7))
    _gesto_do_mouse_para_a_fabrica()

    def _para_o_oito(vista: Profile) -> Profile:
        assert vista.mouse is not None
        return vista.model_copy(update={"mouse": vista.mouse.model_copy(update={"speed": 8})})

    opc.gravar_pelo_gesto("mouse", JOGO, _para_o_oito, origem="regua")
    assert load_profile(JOGO).escolhas_de_fabrica is None
    assert _vale().mouse is not None and _vale().mouse.speed == 8


def test_a_marca_de_campo_desconhecido_cai_e_o_perfil_carrega() -> None:
    """D-2611-O-JOGO-MARCA-O-QUE-ESCOLHEU-IGUAL-A-FABRICA: a marca lida é tolerante."""
    perfil = Profile.model_validate({
        "name": JOGO, "match": {"type": "any"},
        "escolhas_de_fabrica": {"mouse": ["speed", "nao_existe"], "outra": ["x"]}})
    assert perfil.escolhas_de_fabrica == {"mouse": ["speed"]}
    assert "escolhas_de_fabrica" not in Profile.model_validate(
        {"name": JOGO, "match": {"type": "any"}}).model_dump(mode="json")
