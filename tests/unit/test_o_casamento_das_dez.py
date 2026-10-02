#!/usr/bin/env python3
"""A RÉGUA DO CASAMENTO: o que o pacote emite tem onde cair na página."""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PISO = {
    "01-jogar.html": 9,
    "02-controles.html": 9,
    "03-gatilhos.html": 19,
    "04-iluminacao.html": 8,
    "05-vibracao.html": 9,
    "06-navegacao.html": 4,
    "08-conexoes.html": 5,
    "09-sistema.html": 9,
    "10-perfis.html": 10,
}


PERFIL = {
    "name": "Régua", "version": 1, "priority": 50, "match": {"type": "criteria"},
    "triggers": {"left": {"mode": "Rigid", "params": [0, 180]},
                 "right": {"mode": "Vibration", "params": [3, 8, 20]}},
    "leds": {"lightbar": [255, 80, 0], "player_leds": [True] * 5,
             "lightbar_brightness": 0.7},
    "rumble": {"passthrough": True},
    "mouse": {"enabled": True, "speed": 6, "scroll_speed": 1},
}


@pytest.fixture(scope="module")
def casamento(tmp_path_factory):
    """O instrumento com um perfil de mentira sob ele — **e o desvio se desfaz**."""
    import casamento as mod
    from pacotes import perfil

    pasta = tmp_path_factory.mktemp("perfis")
    (pasta / "regua.json").write_text(json.dumps(PERFIL), encoding="utf-8")
    guardado = perfil.pasta
    perfil.pasta = lambda: pasta  # type: ignore[assignment]
    mod.ESTADO_DA_REGUA = {"active_profile": "regua", "rumble_policy": "balanceado"}
    try:
        yield mod
    finally:
        perfil.pasta = guardado  # type: ignore[assignment]


def test_o_instrumento_acha_os_tres_vocabularios(casamento):
    """`data-campo`, `data-papel` e `data-hef` — as dez páginas usam os três."""
    campos, _ = casamento.do_html("10-perfis.html")
    assert len(campos) >= 14, (
        f"a Perfis tem {len(campos)} endereços e ela endereça por `data-hef` — "
        f"se caiu para 3, a régua voltou a contar só `data-campo`.")
    campos5, _ = casamento.do_html("05-vibracao.html")
    assert len(campos5) >= 10, "a Vibração endereça por `data-papel`"


@pytest.mark.parametrize("pagina", sorted(PISO))  # (noqa-acento)  (nome do parâmetro)
def test_a_aba_casa_pelo_menos_o_piso(casamento, pagina):
    """Zero é ERRO, e uma queda também."""
    m = casamento.medir(pagina)
    assert m["emite"], f"{pagina}: o pacote não emitiu nada — ver a régua do despachante"
    assert len(m["casam"]) >= PISO[pagina], (
        f"{pagina} casa {len(m['casam'])} endereços e o piso medido é "
        f"{PISO[pagina]}.\n"
        f"  casam : {sorted(m['casam'])}\n"
        f"  órfãos (o pacote manda e a tela não tem onde): {sorted(m['orfaos'])}\n"
        f"  vazios (a tela tem onde e ninguém manda): {sorted(m['vazios'])}\n"
        f"Uma queda aqui não aparece na tela: o valor simplesmente não é escrito.")


def test_nenhuma_aba_com_pacote_casa_zero(casamento):
    """O resumo, e é o que o `casamento.py` devolve como rc=1."""
    zeradas = [p for p in PISO if casamento.medir(p)["emite"]
               and not casamento.medir(p)["casam"]]
    assert zeradas == [], (
        f"estas abas emitem valores e não têm onde pô-los: {zeradas}. "
        f"É a forma exata do defeito que esta régua existe para pegar — a "
        f"pintura escreve zero e nada acusa.")
