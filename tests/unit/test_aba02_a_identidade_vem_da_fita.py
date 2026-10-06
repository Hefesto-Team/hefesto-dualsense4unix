#!/usr/bin/env python3
"""A ABA 02 MOSTRA O CONTROLE DA MESA, NUNCA O DO MOCKUP — 03/09/2026."""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

BANCADA = RAIZ / "mockup/02-controles.html"

def _do_desenho() -> tuple[int, int]:
    import monta

    return len(monta.MESA), len(monta.CONECTADOS)


LUGARES, CHIPS = _do_desenho()


def _palavra_do_transporte(chave: str) -> str:
    """A palavra da TELA, LIDA do dono — nunca digitada aqui."""
    from hefesto_dualsense4unix.app.actions.home_actions import (
        palavra_do_transporte,
    )

    return palavra_do_transporte(chave)


UNIQ_CABO = "aa:bb:cc:00:00:01"
UNIQ_RADIO = "aa:bb:cc:00:00:02"

DO_MOCKUP = ("Cosmic Red", "Starlight Blue")

#: A BANCADA EM 03/09/2026, na forma que `mesa_viva.mesa_do_estado` devolve.
MESA = [
    {"pref": "p1", "uniq": UNIQ_CABO, "jogador": 1, "cor": "white",
     "nome": "White", "via": "USB", "transporte": "usb", "alvo": True,
     "mascara": "DualSense"},
    {"pref": "p2", "uniq": UNIQ_RADIO, "jogador": 2, "cor": "",
     "nome": "Não sei", "via": "BT", "transporte": "bt", "alvo": False,
     "mascara": "DualSense"},
]

CONECTADOS = [
    {"uniq": UNIQ_CABO, "transport": "usb", "battery_pct": 95, "player_slot": 1,
     "inputs": {"buttons": []}, "vpad_backend": "uhid"},
    {"uniq": UNIQ_RADIO, "transport": "bt", "battery_pct": 15, "player_slot": 2,
     "vpad_backend": "uhid"},
]


@pytest.fixture(scope="module")
def a02():
    from pacotes import a02_controles

    return a02_controles


@pytest.fixture()
def ctx(a02):
    """O `Contexto` da mesa acima, com a página da BANCADA como endereço válido."""
    from pacotes import Contexto

    a02._ENDERECOS = frozenset(
        re.findall(r'data-campo="([^"]+)"', BANCADA.read_text(encoding="utf-8")))
    yield Contexto(state={}, mesa=MESA, conectados=CONECTADOS, estados={})
    a02._ENDERECOS = None


def test_a_bancada_tem_os_quatro_enderecos_da_identidade():
    """Sem eles o pacote não tem onde pousar, e a pintura escreve zero, calada.

    A CONTA DO CARD PASSOU DE 2 PARA 4 — 07/09/2026,
    CONTROLES-O-LUGAR-VAZIO-TEM-ENDERECO-01, e ela não afrouxou: ficou maior.

    Até 07/09 o lugar vazio era um cartão à parte, sem UM `data-campo` por
    dentro — e `== 2` era o número que o DEFEITO produzia. Com os quatro
    DualSense do usuário na mesa, o daemon publicava quatro e a tela mostrava dois:
    o `peca` e o `via` do p3 e do p4 não existiam para o piloto pousar. Uma
    régua que confere com a metade errada da mesa dá verde sobre ela.

    O CHIP CONTINUA EM DOIS, e é a outra metade da correção: `monta.fita()` só
    desenha chip de quem ESTÁ na mesa. Cobrar quatro ali faria a régua reprovar
    no dia em que ela desligar um controle — o defeito irmão deste.
    """
    doc = BANCADA.read_text(encoding="utf-8")
    for campo in ("peca", "via"):
        assert doc.count(f'data-campo="{campo}"') == LUGARES, (
            f"`{campo}` não está nos {LUGARES} LUGARES da bancada — um lugar "
            f"vazio sem endereço é dado dela chegando e não tendo onde pousar")
    for campo in ("fita-peca", "fita-via"):
        assert doc.count(f'data-campo="{campo}"') == CHIPS, (
            f"`{campo}` não está nos {CHIPS} chips da fita do desenho")


def test_a_bancada_nao_traz_cor_de_plastico_no_estilo_de_linha():
    """`style="--plastico:#hex"` é a única forma que o produto NÃO consegue vencer.

    Estilo de linha ganha de qualquer folha de estilo, e o `escrever` do piloto
    não tem alvo que escreva propriedade personalizada de CSS (os sete são
    texto · largura · fundo · valor · html · classe · cor). Enquanto a cor
    morar ali, a borda do card é do mockup e ponto final.
    """
    corpo = BANCADA.read_text(encoding="utf-8").split("</head>", 1)[-1]
    assert "--plastico:#" not in corpo


def test_a_bancada_tem_a_folha_enderecada_do_plastico():
    """E o produto a TROCA INTEIRA — por isso ela nasce com o desenho dentro."""
    doc = BANCADA.read_text(encoding="utf-8")
    assert '<style data-campo="plastico-css" data-hef-alvo="html">' in doc
    assert "plastico-do-desenho" not in doc


def test_o_pacote_escreve_o_nome_do_aparelho_no_cabecalho(a02, ctx):
    """`White`, que é o que a fita diz — nunca `Cosmic Red`, que é o desenho."""
    p = a02.pacote(ctx)
    assert p["cards"][UNIQ_CABO]["peca"] == "White"
    assert p["cards"][UNIQ_CABO]["via"] == _palavra_do_transporte("usb")


def test_o_controle_sem_cor_lida_nao_ganha_nome_inventado(a02, ctx):
    """Regra de produto: campo sem informação não mostra nada.

    `identidade_de` cai no TRANSPORTE quando não sobrou nome, e o desenho já
    mostra o transporte ao lado — o cabeçalho leria a palavra duas vezes.
    Vazio é o que o piloto transforma em travessão.
    """
    p = a02.pacote(ctx)
    assert p["cards"][UNIQ_RADIO]["peca"] == ""
    assert p["cards"][UNIQ_RADIO]["via"] == _palavra_do_transporte("bt")


def test_o_pacote_escreve_a_cor_do_plastico_como_folha(a02, ctx):
    """A borda do card do `White` é branca, e a do que não se leu é o neutro."""
    folha = a02.pacote(ctx)["mesa"]["plastico-css"]
    assert '.ctl[data-controle="p1"]' in folha
    assert a02.cor_da_borda("white") in folha
    assert f'{{--plastico:{a02.BORDA_SEM_COR}}}' in folha


def test_o_pacote_escreve_os_chips_da_fita(a02, ctx):
    """A fita se troca inteira — MENOS quando ela não pode se trocar."""
    mesa = a02.pacote(ctx)["mesa"]
    assert mesa["fita-peca"] == ["White", ""]
    assert mesa["fita-via"] == ["USB", "BT"]


def test_nada_do_mockup_sai_deste_pacote(a02, ctx):
    """A varredura final: nenhum nome do desenho em nenhum valor emitido."""
    p = a02.pacote(ctx)
    texto = repr(p)
    for nome in DO_MOCKUP:
        assert nome not in texto, f"o pacote emitiu `{nome}`, que é do mockup"


#: que é o que `mesa_viva.mesa_do_estado` põe no campo `cor` do item da mesa.
@pytest.mark.parametrize("slug", ["white", "galactic-purple", "midnight-black"])
def test_a_cor_da_borda_sai_do_mapa(a02, slug):
    """Um hexa de verdade, e nunca o token neutro, para plástico conhecido."""
    cor = a02.cor_da_borda(slug)
    assert re.fullmatch(r"#[0-9a-fA-F]{6}", cor), f"`{slug}` não devolveu hexa"


def test_o_midnight_black_nao_vira_ausencia_de_borda(a02):
    """`#1C1C1E` cru sobre `#282a36` não é borda preta — é borda nenhuma."""
    assert a02.cor_da_borda("midnight-black").lower() != "#1c1c1e"


@pytest.mark.parametrize("slug", ["", "nao-sei", "verde-abacate", "White"])
def test_sem_leitura_a_borda_e_o_neutro(a02, slug):
    """E o neutro é o token que o lugar VAZIO desta aba já usa — não uma cor nova."""
    assert a02.cor_da_borda(slug) == a02.BORDA_SEM_COR
