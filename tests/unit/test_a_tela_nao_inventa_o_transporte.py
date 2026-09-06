"""A tela não diz "BT" sobre um transporte que o daemon não publicou.

Medido em 05/09/2026: `interface/mesa_viva.mesa_do_estado` montava a palavra
curta do transporte com

    "via": "USB" if transporte == "usb" else "BT"

— e o `else` pegava a AUSÊNCIA. Um controle cujo `transport` o daemon não
publicasse aparecia na aba 01 como **"BT"**: a tela afirmando rádio sobre um
campo que ninguém leu.

Havia QUATRO respostas vivas no produto para o mesmo campo, e a do produto
estável é a que traz a razão escrita (`app/actions/home_actions.py:1333`):

    "'?' não é resposta — é a tela encolhendo os ombros"

A agravante era de documentação: o comentário de `pacotes.VIA_DO_TRANSPORTE`
AFIRMAVA ser "a MESMA tradução do `mesa_viva.mesa_do_estado`". Não era — as
duas divergiam exatamente na ausência. Hoje o `mesa_viva` lê aquele dicionário,
e a afirmação virou verdade.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.interface import mesa_viva
from hefesto_dualsense4unix.interface.pacotes import VIA_DO_TRANSPORTE


@pytest.mark.parametrize("ausente", [None, "", "   "])
def test_transporte_ausente_nao_vira_radio(ausente):
    saida = mesa_viva._via_do_transporte(ausente)
    assert saida != "BT", (
        f"com transport={ausente!r} a tela escreveu 'BT'. Afirmar rádio sobre "
        "um campo vazio é a tela inventando o que não leu."
    )
    assert saida == "", "ausência tem de virar travessão na tela"


def test_os_dois_transportes_conhecidos_continuam_certos():
    assert mesa_viva._via_do_transporte("usb") == "USB"
    assert mesa_viva._via_do_transporte("bt") == "BT"
    assert mesa_viva._via_do_transporte("BT") == "BT", "o daemon pode mandar maiúscula"


def test_ha_um_dono_so_e_o_mesa_viva_o_le():
    """A cópia não pode voltar: as duas telas leem o MESMO dicionário."""
    for chave, palavra in VIA_DO_TRANSPORTE.items():
        assert mesa_viva._via_do_transporte(chave) == palavra, (
            "o `mesa_viva` deixou de ler `pacotes.VIA_DO_TRANSPORTE` e voltou a "
            "traduzir por conta própria"
        )


def test_a_mesa_montada_nao_afirma_via_sem_leitura():
    """A ponta que ela vê: o dicionário que vai para a aba 01."""
    estado = {"controllers": [{"uniq": "aabbcc000011", "connected": True}]}
    mesa = mesa_viva.mesa_do_estado(estado, {})
    assert mesa, "a mesa veio vazia — esta régua perdeu o objeto"
    assert mesa[0]["via"] == "", (
        f"a mesa afirma via={mesa[0]['via']!r} para um controle cujo transporte "
        "o daemon não publicou"
    )
