"""D-2611-A-COR-DO-JOGO-VENCE-O-MODO-E-O-EFEITO-DO-COMPUTADOR.

A cor da barra que o perfil do jogo escreveu já escolhe o Personalizado: o modo e o efeito
guardados no computador só preenchem o jogo que não escreveu cor (a regra do gatilho, na luz).
O lar é de mentira (o `conftest` desvia `HOME` e os `XDG_*`).
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc
from hefesto_dualsense4unix.profiles.schema import (
    MODO_AUTOMATICO,
    TODAS_AS_BASES_DA_LUZ,
    Profile,
    decidir_o_modo_da_luz,
    escrever_o_efeito_da_luz,
    perfil_no_modo,
)
from hefesto_dualsense4unix.utils import maquina as m

CHAVE = "aabbcc000001"
COR = [10, 200, 30]
EFEITO = escrever_o_efeito_da_luz(TODAS_AS_BASES_DA_LUZ[0], ["FF0000"], 3)


def _computador(**leds: Any) -> Any:
    assert m.gravar_o_computador({"global": {"leds": leds}})
    return opc.o_computador()


def _jogo(nome: str = "jogo", **cru: Any) -> Profile:
    return Profile.model_validate({"name": nome, "match": {"type": "any"}, **cru})


@pytest.mark.parametrize("do_computador", [
    {"modo": MODO_AUTOMATICO},
    {"efeito": EFEITO},
    {"modo": MODO_AUTOMATICO, "efeito": EFEITO},
], ids=["modo-automatico", "efeito", "os-dois"])
def test_a_cor_escrita_no_jogo_vale_sobre_o_modo_e_o_efeito_do_computador(
        do_computador: dict[str, Any]) -> None:
    """D-2611-A-COR-DO-JOGO-VENCE-O-MODO-E-O-EFEITO-DO-COMPUTADOR: a barra mostra a cor do jogo."""
    vale = opc.perfil_que_vale(_jogo(leds={"lightbar": COR}), _computador(**do_computador))
    assert vale.leds.modo is None and vale.leds.efeito is None
    assert decidir_o_modo_da_luz(vale.leds.modo, vale.leds.auto_player_colors, True) != (
        MODO_AUTOMATICO)
    assert tuple(perfil_no_modo(vale).leds.lightbar) == tuple(COR)


def test_o_jogo_sem_cor_escrita_recebe_o_modo_e_o_efeito_do_computador() -> None:
    """D-2611-A-COR-DO-JOGO-VENCE-O-MODO-E-O-EFEITO-DO-COMPUTADOR: sem cor, vale o computador."""
    computador = _computador(modo=MODO_AUTOMATICO, efeito=EFEITO)
    vale = opc.perfil_que_vale(_jogo(leds={"lightbar_brightness": 0.4}), computador)
    assert vale.leds.modo == MODO_AUTOMATICO and vale.leds.efeito == EFEITO
    vazio = opc.perfil_que_vale(_jogo(), computador)
    assert vazio.leds.modo == MODO_AUTOMATICO and vazio.leds.efeito == EFEITO


def test_a_cor_de_um_controle_do_jogo_tambem_vence_o_modo_do_computador() -> None:
    """D-2611-A-COR-DO-JOGO-VENCE-O-MODO-E-O-EFEITO-DO-COMPUTADOR: a cor por controle vale."""
    computador = _computador(modo=MODO_AUTOMATICO)
    jogo = _jogo(controllers={CHAVE: {"leds": {"lightbar": COR}}})
    vale = opc.perfil_que_vale(jogo, computador)
    assert vale.leds.modo is None
    assert tuple(perfil_no_modo(vale).controllers[CHAVE].leds.lightbar) == tuple(COR)


def test_o_modo_do_computador_por_controle_nao_cala_a_cor_do_jogo() -> None:
    """D-2611-A-COR-DO-JOGO-VENCE-O-MODO-E-O-EFEITO-DO-COMPUTADOR: vale também no controle."""
    assert m.gravar_o_computador({"controles": {CHAVE: {"leds": {
        "modo": MODO_AUTOMATICO, "efeito": EFEITO}}}})
    vale = opc.perfil_que_vale(_jogo(leds={"lightbar": COR}), opc.o_computador())
    leds = vale.controllers[CHAVE].leds if vale.controllers and CHAVE in vale.controllers else None
    assert leds is None or (leds.modo is None and leds.efeito is None)
    sem_cor = opc.perfil_que_vale(_jogo(), opc.o_computador())
    assert sem_cor.controllers[CHAVE].leds.modo == MODO_AUTOMATICO


def test_o_freestyle_nao_sobrepoe_o_modo_do_computador() -> None:
    """D-2611-A-COR-DO-JOGO-VENCE-O-MODO-E-O-EFEITO-DO-COMPUTADOR: o Freestyle segue à parte."""
    vale = opc.perfil_que_vale(
        _jogo("Freestyle", leds={"lightbar": COR}), _computador(modo=MODO_AUTOMATICO))
    assert vale.leds.modo == MODO_AUTOMATICO
