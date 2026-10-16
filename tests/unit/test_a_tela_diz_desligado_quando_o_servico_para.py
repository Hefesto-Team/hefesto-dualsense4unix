#!/usr/bin/env python3
"""Com o serviço parado, a aba Jogar e o topo dizem que o Hefesto está desligado.

A queixa de 15/10/2026: «Sair» pela bandeja, a interface aberta com o serviço fora mostrou o Status
em Ligado, o topo com «Nenhum controle» ao lado do ponto verde e a mesa vazia sem dizer por quê,
com o Galactic Purple e o Cosmic Red ligados pelo rádio. O piloto entrega o estado vazio (`{}`)
depois da folga; o pacote é quem lia esse vazio como Ligado.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import pacotes
from pacotes import Contexto
from pacotes import a01_jogar as aba

UNIQ_ROXO = "aa:bb:cc:00:00:01"
UNIQ_VERMELHO = "aa:bb:cc:00:00:02"

NO_RADIO: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
    "paused": False,
    "controllers": [
        {"uniq": UNIQ_ROXO, "connected": True, "player_slot": 1, "transport": "bt"},
        {"uniq": UNIQ_VERMELHO, "connected": True, "player_slot": 2, "transport": "bt"},
    ],
}


def _parado() -> Contexto:
    """O que o piloto entrega depois da folga: estado vazio, mesa vazia."""
    return Contexto(state={}, mesa=[], conectados=[], estados={})


def _no_radio() -> Contexto:
    mesa = [{"uniq": c["uniq"], "pref": f"p{i}", "transporte": "bt", "jogador": i}
            for i, c in enumerate(NO_RADIO["controllers"], 1)]
    return Contexto(state=NO_RADIO, mesa=mesa,
                    conectados=list(NO_RADIO["controllers"]), estados={})


def _de_pe_sem_controle() -> Contexto:
    return Contexto(state={**NO_RADIO, "controllers": []}, mesa=[], conectados=[], estados={})


def test_o_status_marca_desligado_com_o_servico_parado() -> None:
    """Posição vazia caía no rádio que o gerador marcou (Ligado): o interruptor mentia."""
    fora = aba.pacote(_parado())
    assert fora["hef-posicao"] == aba.POSICAO_COM_O_SERVICO_PARADO == "desligado", (
        f"o Status saiu {fora['hef-posicao']!r} com o serviço parado")
    assert fora["modo-aceso"] == "", "um chip acendeu sobre estado que ninguém leu"
    assert fora["steam-input-aceso"] == ""


def test_a_mesa_diz_por_que_esta_vazia() -> None:
    """A frase do serviço desligado, e nunca a da mesa vazia (haveria controle ligado)."""
    frase = aba.pacote(_parado())["mesa-frase"]
    assert frase == aba.SERVICO_CALADO, f"a mesa disse {frase!r}"
    assert frase != aba.MESA_VAZIA
    assert frase.startswith(aba.SERVICO_DESLIGADO)


def test_o_topo_diz_desligado_e_nao_nenhum_controle() -> None:
    """«Nenhum controle» ao lado do ponto verde lia-se como tela vazia com controle ligado."""
    topo = pacotes.topo(_parado())
    assert topo["conta-b"] == aba.SERVICO_DESLIGADO.rstrip(".")
    assert topo["conta-b"] != pacotes.SEM_CONTROLE_NA_MESA
    # é este campo que apaga o ponto verde no desenho
    assert topo["servico"] == "parado"  # (noqa-acento) chave da página


def test_com_dois_controles_no_radio_volta_ao_ligado_e_aos_cartoes() -> None:
    """A volta: o primeiro estado que responder desfaz o Desligado, a frase e o topo."""
    ctx = _no_radio()
    fora = aba.pacote(ctx)
    assert fora["hef-posicao"] == "ligado"
    assert fora["mesa-frase"] == ""
    assert set(fora["cartoes"]) == {UNIQ_ROXO, UNIQ_VERMELHO}
    topo = pacotes.topo(ctx)
    assert topo["conta-b"] == "2 BT"
    assert topo["servico"] == "de-pe"  # (noqa-acento) chave da página


def test_servico_de_pe_sem_controle_continua_dizendo_que_nao_ha_controle() -> None:
    """O serviço respondeu e a mesa está vazia: aí «Nenhum controle» é verdade."""
    ctx = _de_pe_sem_controle()
    assert aba.pacote(ctx)["mesa-frase"] == aba.MESA_VAZIA
    assert pacotes.topo(ctx)["conta-b"] == pacotes.SEM_CONTROLE_NA_MESA


def test_clicar_em_ligado_com_o_servico_parado_liga_o_servico(monkeypatch: Any) -> None:
    """O mesmo ato da aba Sistema; e o «Desligado» nunca liga o serviço."""
    from pacotes import a09_sistema

    chamadas: list[str] = []
    monkeypatch.setattr(a09_sistema, "ativar_o_servico",
                        lambda: chamadas.append("ligou") or True)
    monkeypatch.setattr(aba, "_hefesto_o_modo", lambda ctx, o, p: None)
    aba.hefesto(_parado(), {"modo": "gamepad"}, None)
    assert chamadas == ["ligou"], "o Ligado não ligou o serviço"
    aba.hefesto(_parado(), {"modo": "native"}, None)
    assert chamadas == ["ligou"], "o Desligado ligou o serviço"


REGRAS_DO_TOPO = (
    '.fita-linha:has(i[data-servico="parado"]) .conectado .bolinha{display:none}',
    '.fita-linha:has(i[data-servico="parado"]) .conectado{color:var(--orange)}',
)


def test_o_desenho_apaga_o_ponto_verde_com_o_servico_parado() -> None:
    """A regra mora no gerador e no desenho (mockup), as duas metades do mesmo endereço."""
    gerador = (INTERFACE / "aba01.py").read_text(encoding="utf-8")
    desenho = (RAIZ / "mockup" / "01-jogar.html").read_text(encoding="utf-8")
    for nome, texto in (("aba01.py", gerador), ("mockup/01-jogar.html", desenho)):
        for regra in REGRAS_DO_TOPO:
            assert regra in texto, f"{nome}: o topo com o serviço parado perdeu {regra!r}"
