#!/usr/bin/env python3
"""A ABA CONTROLES PERGUNTA O ESTADO DO CARD AO DONO — 16/10/2026.

`mesa_viva.estado_do_card` foi escrita para o piloto antigo e ficou como
verdade DIVIDIDA: o pacote da tela (`pacotes/a02_controles`) refazia, por conta
própria, a bateria, o volume do microfone, o do alto-falante, os glifos, os
gatilhos, os analógicos e os dois sensores. Medido com 559 entradas válidas, as
duas contas discordavam em giro (largura fixa contra duas casas), alto-falante
(`Padrão`), glifo (`l2` por nome contra por curso) e bateria (`True` valia 1).

O dono é UM: o pacote o pergunta e põe os fatos nos endereços da página. Esta
régua prende as duas pontas:

- o pacote MOSTRA o que o dono diz (um dono trocado por um dublê com números
  inconfundíveis aparece na página); um pacote que voltasse a calcular por conta
  própria mostraria os números reais e reprovaria;
- o dono lê com os leitores do cartão (`cartao_do_controle`), em cabo e em rádio,
  com e sem `inputs`.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

UNIQ_CABO = "aa:bb:cc:00:00:01"
UNIQ_RADIO = "aa:bb:cc:00:00:02"

CABO = {
    "uniq": UNIQ_CABO, "transport": "usb", "battery_pct": 95, "player_slot": 1,
    "vpad_backend": "uhid",
    "inputs": {
        "buttons": ["cross", "r1", "create"], "l2_raw": 200, "r2_raw": 12,
        "lx": 125, "ly": 121, "rx": 128, "ry": 125,
        "gyro": {"x": -0.24, "y": -412.0, "z": 22.8},
        "accel": {"x": 0.116, "y": 0.948, "z": 0.204},
    },
    "speaker": {"volume": 30, "muted": False},
    "audio": {"mic_mudo": False, "volume_captura": 55},
}
RADIO = {
    "uniq": UNIQ_RADIO, "transport": "bt", "battery_pct": 40, "player_slot": 2,
    "vpad_backend": "uhid",
    "speaker": {"volume": 30, "muted": True},
}


def _pacote(entradas: list[dict], monkeypatch: pytest.MonkeyPatch) -> dict:
    from pacotes import Contexto, a02_controles

    desenho = (RAIZ / "mockup/02-controles.html").read_text(encoding="utf-8")
    monkeypatch.setattr(
        a02_controles, "_ENDERECOS", frozenset(re.findall(r'data-campo="([^"]+)"', desenho))
    )
    mesa = [
        {"pref": f"p{i}", "uniq": e["uniq"], "jogador": i, "cor": "white", "nome": "White",
         "via": "USB", "transporte": e["transport"], "alvo": True, "mascara": "DualSense"}
        for i, e in enumerate(entradas, 1)
    ]
    ctx = Contexto(state={}, mesa=mesa, conectados=entradas, estados={})
    return a02_controles.pacote(ctx)["cards"]


def test_o_pacote_mostra_o_que_o_dono_diz(monkeypatch: pytest.MonkeyPatch) -> None:
    """Um dono com números inconfundíveis aparece, um por um, na página.

    Prova da D-1610-O-ESTADO-DO-CARD-TEM-UM-DONO-SO.
    """
    import mesa_viva

    real = mesa_viva.estado_do_card
    perguntas: list[str] = []

    def dono(entrada, **kw):
        perguntas.append(entrada["uniq"])
        estado = dict(real(entrada, **kw))
        estado.update(
            bat=77, mic_vol=33, alto_pct=44, l2=111, r2=222,
            glifos_on={"triangle", "l3"}, sticks=(10, 20, 30, 40),
            giro_lido=(1.5, -2.5, 3.5), accel_lido=(0.25, -0.5, 0.75), alto_mudo=True,
        )
        return estado

    monkeypatch.setattr(mesa_viva, "estado_do_card", dono)
    cards = _pacote([dict(CABO), dict(RADIO)], monkeypatch)
    from pacotes.a02_controles import CLICADO, ROTULO_DO_CLIQUE

    assert perguntas.count(UNIQ_CABO) >= 1 and perguntas.count(UNIQ_RADIO) >= 1
    for uniq in (UNIQ_CABO, UNIQ_RADIO):
        card = cards[uniq]
        assert card["bateria-barra"] == 77
        assert card["mic-barra"] == 33
        assert card["alto-num"] == 44 and card["alto-barra"] == 44
        assert card["l2-num"] == "111 / 255" and card["r2-num"] == "222 / 255"
        assert card["l2-barra"] == 111 * 100 // 255
        assert card["glifo-triangle"] == "sim"
        assert card["glifo-cross"] == "" and card["glifo-r1"] == ""
        assert card["xy-l"] != "" and "10" in card["xy-l"] and "20" in card["xy-l"]
        assert "30" in card["xy-r"] and "40" in card["xy-r"]
        assert "1.5" in card["giro-x"] and "2.5" in card["giro-y"] and "3.5" in card["giro-z"]
        assert "0.25" in card["accel-x"] and "0.75" in card["accel-z"]
        assert card["alto-mudo"] == mesa_viva.selo_do_mic(True, True)
    assert cards[UNIQ_CABO]["l3"] == CLICADO % ROTULO_DO_CLIQUE["l"]
    assert cards[UNIQ_CABO]["r3"] == ROTULO_DO_CLIQUE["r"]


def test_o_dono_sem_leitor_devolve_repouso_nos_dois_transportes() -> None:
    """Rádio sem `inputs`: repouso, nunca o último valor nem o desenho."""
    import mesa_viva

    for entrada in (RADIO, {**CABO, "inputs": None}, {**CABO, "inputs": "x"}):
        est = mesa_viva.estado_do_card(entrada)
        assert est["glifos_on"] == set() and est["l2"] == 0 and est["r2"] == 0
        assert est["sticks"] == (128, 128, 128, 128)
        assert est["giro_lido"] is None and est["accel_lido"] is None
        assert [linha[1] for linha in est["giro"]] == [mesa_viva.SEM_LEITOR] * 3


def test_o_dono_le_com_os_leitores_do_cartao() -> None:
    """Giro com a grafia do produto, gatilho por curso, alto-falante nas duas posições."""
    import mesa_viva
    from hefesto_dualsense4unix.interface.cartao_do_controle import (
        L2_R2_THRESHOLD,
        speaker_do_entry,
    )
    from hefesto_dualsense4unix.interface.sensores import texto_eixo

    est = mesa_viva.estado_do_card(CABO)
    assert [linha[1] for linha in est["giro"]] == [
        texto_eixo(-0.24), texto_eixo(-412.0), texto_eixo(22.8)
    ]
    assert est["giro_lido"] == (-0.24, -412.0, 22.8)
    por_nome = {**CABO, "inputs": {**CABO["inputs"], "buttons": ["l2", "r2"], "l2_raw": 0}}
    assert not {"l2", "r2"} & mesa_viva.estado_do_card(por_nome)["glifos_on"]
    por_curso = {**CABO, "inputs": {**CABO["inputs"], "buttons": [], "l2_raw": L2_R2_THRESHOLD + 1}}
    assert "l2" in mesa_viva.estado_do_card(por_curso)["glifos_on"]
    assert "share" in est["glifos_on"] and "create" not in est["glifos_on"]
    dentro = {"uniq": UNIQ_CABO, "transport": "usb", "inputs": {"speaker": {"volume": 102}}}
    fora = {"uniq": UNIQ_CABO, "transport": "usb", "speaker": {"volume": 102}}
    for entrada in (dentro, fora):
        alto = speaker_do_entry(entrada)
        assert alto is not None
        assert mesa_viva.estado_do_card(entrada)["alto_pct"] == mesa_viva.percentual_do_volume(
            alto[0]
        )
    assert mesa_viva.estado_do_card({"uniq": UNIQ_CABO, "transport": "usb"})["alto_pct"] is None


def test_bateria_booleana_nao_vale_porcentagem() -> None:
    """`True` é `int` em Python; sem a trava a barra de bateria enchia 1%."""
    import mesa_viva

    assert mesa_viva.estado_do_card({**CABO, "battery_pct": True})["bat"] == 0
    assert mesa_viva.estado_do_card({**CABO, "battery_pct": 95})["bat"] == 95
    assert mesa_viva.estado_do_card({**CABO, "battery_pct": "95"})["bat"] == 0
