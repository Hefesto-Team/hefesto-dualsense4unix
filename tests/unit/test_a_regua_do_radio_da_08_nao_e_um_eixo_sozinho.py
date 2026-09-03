#!/usr/bin/env python3
"""A régua de Desempenho da aba 08 nunca sai como eixo e legenda sobre o vazio.

**03/09/2026.** Fotografado no WebKit do produto, na mesa dela, com **um
DualSense White no cabo e nada no rádio** — que é o estado mais comum de uma
mesa de uma pessoa só:

    document.querySelectorAll('.pista') .length → 0
    document.querySelectorAll('.bloco') .length → 0
    innerHTML de [data-campo="regua-do-radio"] → só <div class="eixo"> e
                                                 <div class="leg">

A seção diz **"Desempenho · O rádio de cada adaptador, em turnos"** e mostrava
a escala `0 400 800 1.200 1.600` com a legenda anunciando `+16,3` e `+276,7`
— dois números com cara de medição, sem uma barra a que pertencer. É a forma de
mentira que esta casa já nomeou: *a tela AFIRMA algo que não é verdade*.

A CAUSA: `_regua_do_radio` monta as pistas a partir de `grupos`, que nasce dos
controles que estão NO RÁDIO. Zero controles no rádio, zero pistas. O dono da
frase (`gui.aba_conexoes.html_das_pistas`) percorre os **adaptadores**, e um
adaptador sem ninguém vira `Nenhum controle neste rádio · 0 de 1.600` — a mesma
pista vazia que a `08-conexoes` publicada já traz DESENHADA.

A MORDIDA: apague o ramo `if not pistas:` de
`interface/pacotes/a08_conexoes._regua_do_radio` e rode este arquivo — os dois
primeiros testes reprovam, e o terceiro (a mesa COM alguém no rádio) continua
verde, que é a prova de que a cura não trocou o caso que já funcionava.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: A faixa sintética da casa — há dois portões de anonimato nesta árvore.
P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"


def _pacote() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


def _ctx(*, com_radio: bool) -> Any:
    """A mesa dela de hoje: um White no cabo. Com `com_radio`, mais um no rádio."""
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    mesa: list[dict[str, Any]] = [
        {"pref": "p1", "uniq": P1, "jogador": 1, "cor": "white",
         "nome": "White", "via": "USB", "transporte": "usb", "mascara": "DualSense"},
    ]
    conectados: list[dict[str, Any]] = [
        {"uniq": P1, "transport": "usb", "connected": True, "battery_pct": 100},
    ]
    if com_radio:
        mesa.append(
            {"pref": "p2", "uniq": P2, "jogador": 2, "cor": "galactic-purple",
             "nome": "Galactic Purple", "via": "BT", "transporte": "bt",
             "mascara": "DualSense"})
        conectados.append(
            {"uniq": P2, "transport": "bt", "connected": True, "battery_pct": 64})
    return Contexto(state={"controllers": conectados}, mesa=mesa,
                    conectados=conectados, estados={})


def _regua(*, com_radio: bool) -> str:
    return str(_pacote().pacote(_ctx(com_radio=com_radio)).get("regua-do-radio") or "")


def test_sem_ninguem_no_radio_a_regua_ainda_tem_pista() -> None:
    """Com a mesa só no cabo, o bloco não pode sair como eixo e legenda."""
    html = _regua(com_radio=False)
    assert 'class="pista"' in html, (
        "a régua de Desempenho saiu SEM PISTA NENHUMA com a mesa só no cabo — "
        "é o eixo `0 … 1.600` e a legenda `+16,3 / +276,7` sobre zero barra, "
        f"que foi o que a foto de 03/09 pegou. HTML:\n{html}")


def test_sem_ninguem_no_radio_a_pista_diz_que_esta_vazia() -> None:
    """E a pista tem de DIZER que está vazia, com a palavra do dono.

    A frase é de `gui.aba_conexoes.html_das_pistas` e já está desenhada na
    `08-conexoes` publicada. Nenhuma palavra nova nasce nesta cura.
    """
    html = _regua(com_radio=False)
    assert "Nenhum controle neste rádio" in html, (
        f"a pista vazia não disse que está vazia:\n{html}")
    assert 'class="bloco' not in html, (
        "a régua desenhou uma barra sem ninguém no rádio — isso é inventar "
        f"ocupação:\n{html}")
    # E NÃO SE INVENTA UM ADAPTADOR: sem `uniq` no rádio ninguém perguntou ao
    # sysfs qual adaptador é, e ela tem TRÊS. `Sem nome` afirmaria que existe um
    # e que ele não tem apelido.
    assert "Sem nome" not in html, (
        "a régua nomeou um adaptador que ninguém mediu — a coluna fica vazia "
        f"quando não se sabe qual é:\n{html}")


def test_com_alguem_no_radio_a_regua_continua_como_era() -> None:
    """A cura não pode trocar o caso que já funcionava.

    Este é o caso que a régua de identidade já cobre: com o Galactic Purple no
    rádio, a pista nasce com a fatia dele e a legenda o nomeia.
    """
    html = _regua(com_radio=True)
    assert 'class="pista"' in html and 'class="leg"' in html
    assert "Galactic Purple" in html, (
        f"a régua deixou de nomear o controle que está NO rádio:\n{html}")
    assert 'class="bloco usa"' in html, (
        f"a régua deixou de desenhar a fatia de quem está no rádio:\n{html}")
    assert "Nenhum controle neste rádio" not in html, (
        f"a pista de quem TEM controle disse que está vazia:\n{html}")
