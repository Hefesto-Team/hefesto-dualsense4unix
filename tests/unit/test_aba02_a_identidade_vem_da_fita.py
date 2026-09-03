#!/usr/bin/env python3
"""A ABA 02 MOSTRA O CONTROLE DA MESA, NUNCA O DO MOCKUP — 03/09/2026.

A LEI É DELA, e ela a escreveu olhando as duas coisas na mesma tela, com três
centímetros entre uma e outra:

    *"se no topo tá mostrando controle white player 1, então cada aba vai usar
    os controles lá de cima. Não mistura com a info dos mockups. (…) Por isso
    temos o mapa pra servir como variável de identificação"*

E, sobre a cor: *"se identificou o controle como modelo White a cor do card em
volta tem que ser branco. Temos isso no mapa."*

O QUE ESTAVA NA TELA, fotografado nesta árvore em 03/09/2026 com os dois
controles dela ligados (um `White` no cabo, um por rádio):

    a fita do topo (lê do aparelho)   P1 · White · USB        P2 · — · BT
    o cabeçalho do card (do mockup)   Cosmic Red · USB        P2 · Starlight Blue · BT

POR QUE UM TESTE ALÉM DA RÉGUA DA SPRINT. `scripts/check_identidade_vem_de_cima.py`
mede o ARQUIVO: ela acha valor de identidade em elemento sem endereço. Isso é
metade do trabalho — e a metade que não pega o defeito pior. **Medido aqui, na
mordida de 03/09:** com os quatro endereços no HTML e o pacote NÃO os
escrevendo, a régua da sprint dá **ZERO** e a tela volta inteira para
`Cosmic Red` e `Starlight Blue`, com as bordas vermelha e azul do desenho.
Trocar um congelado por um vazio zera a régua e deixa a tela mentindo igual.

ENTÃO ESTE ARQUIVO MEDE O OUTRO LADO: que o PACOTE escreve, com o que leu, e que
o que ele escreve não é o desenho.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

BANCADA = RAIZ / "mockup/02-controles.html"

#: MACs da faixa sintética da casa — há dois portões de anonimato nesta árvore.
UNIQ_CABO = "aa:bb:cc:00:00:01"
UNIQ_RADIO = "aa:bb:cc:00:00:02"

#: OS DOIS NOMES DO DESENHO. Eles são o que a tela dela mostrava, e por isso
#: nenhum deles pode sair do pacote — o pacote só fala do aparelho.
DO_MOCKUP = ("Cosmic Red", "Starlight Blue")

#: A MESA DELA EM 03/09/2026, na forma que `mesa_viva.mesa_do_estado` devolve.
#: O segundo vem SEM COR de propósito: pelo rádio a cor do plástico não é lida —
#: o mapa de canais diz `identidade.cor_do_aparelho`, `radio_aciona = não` — e é
#: exatamente esse controle que fazia a fita inteira ficar no desenho.
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
    """O `Contexto` da mesa acima, com a página da BANCADA como endereço válido.

    POR QUE A BANCADA E NÃO O PUBLICADO: `_so_se_a_pagina_tiver` pergunta à
    página PUBLICADA quais `data-campo` existem, e **publicar é ato dela** — a
    `02-controles` só ganha estes quatro endereços no minuto em que ela mandar.
    Um teste que perguntasse ao publicado hoje passaria por VACUIDADE: o pacote
    não emitiria nada e nada seria conferido. Aqui a pergunta é feita ao arquivo
    que o gerador acabou de escrever, que é o desenho de HOJE.
    """
    from pacotes import Contexto

    a02._ENDERECOS = frozenset(
        re.findall(r'data-campo="([^"]+)"', BANCADA.read_text(encoding="utf-8")))
    yield Contexto(state={}, mesa=MESA, conectados=CONECTADOS, estados={})
    a02._ENDERECOS = None


# ---------------------------------------------------------------------------
# 1. O DESENHO TEM ONDE O PRODUTO ESCREVER
# ---------------------------------------------------------------------------
def test_a_bancada_tem_os_quatro_enderecos_da_identidade():
    """Sem eles o pacote não tem onde pousar, e a pintura escreve zero, calada."""
    doc = BANCADA.read_text(encoding="utf-8")
    for campo in ("peca", "via", "fita-peca", "fita-via"):
        assert doc.count(f'data-campo="{campo}"') == 2, (
            f"`{campo}` não está nos DOIS controles conectados da bancada")


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
    """E o produto a TROCA INTEIRA — por isso ela nasce com o desenho dentro.

    FATO SUBSTITUÍDO, 03/09/2026. Esta linha exigia
    `<style data-campo="plastico-css"></style>` — a folha VAZIA, com a do
    desenho separada por cima. **Duas folhas só se sobrepõem no assento que a
    segunda NOMEIA**, e o buraco está medido no WebKitGTK: com um controle só na
    mesa (P1 White), o `p2` ficava `rgb(126, 184, 212)` — Starlight Blue, a cor
    do desenho, num assento onde não há controle nenhum.

    Agora é UMA folha, com `data-hef-alvo="html"`: ela nasce com o desenho (é o
    que a bancada tem de mostrar) e o produto substitui o `innerHTML` inteiro.
    O que a troca não escreve deixa de existir.
    `test_aba02_a_cor_do_plastico_vem_do_aparelho.py` é quem guarda a cascata.
    """
    doc = BANCADA.read_text(encoding="utf-8")
    assert '<style data-campo="plastico-css" data-hef-alvo="html">' in doc
    assert "plastico-do-desenho" not in doc


# ---------------------------------------------------------------------------
# 2. O PACOTE ESCREVE — e é aqui que a régua da sprint é cega
# ---------------------------------------------------------------------------
def test_o_pacote_escreve_o_nome_do_aparelho_no_cabecalho(a02, ctx):
    """`White`, que é o que a fita diz — nunca `Cosmic Red`, que é o desenho."""
    p = a02.pacote(ctx)
    assert p["cards"][UNIQ_CABO]["peca"] == "White"
    assert p["cards"][UNIQ_CABO]["via"] == "USB"


def test_o_controle_sem_cor_lida_nao_ganha_nome_inventado(a02, ctx):
    """Regra dela: campo sem informação não mostra nada.

    `identidade_de` cai no TRANSPORTE quando não sobrou nome, e o desenho já
    mostra o transporte ao lado — o cabeçalho leria `BT • BT`. Vazio é o que o
    piloto transforma em travessão: `P2 • — • BT`.
    """
    p = a02.pacote(ctx)
    assert p["cards"][UNIQ_RADIO]["peca"] == ""
    assert p["cards"][UNIQ_RADIO]["via"] == "BT"


def test_o_pacote_escreve_a_cor_do_plastico_como_folha(a02, ctx):
    """A borda do card do `White` é branca, e a do que não se leu é o neutro."""
    folha = a02.pacote(ctx)["mesa"]["plastico-css"]
    assert '.ctl[data-controle="p1"]' in folha
    assert a02.cor_da_borda("White") in folha
    assert f'{{--plastico:{a02.BORDA_SEM_COR}}}' in folha


def test_o_pacote_escreve_os_chips_da_fita(a02, ctx):
    """A fita se troca inteira — MENOS quando ela não pode se trocar.

    `hefesto_vivo._fita` devolve `""` se UM controle da mesa vier sem cor, e o
    da mesa dela vem: pelo rádio a cor não é lida. Nesse tique o bloco NÃO é
    substituído e os chips continuam sendo os do arquivo — foi assim que a fita
    ficou dizendo `Cosmic Red` e `Starlight Blue` com o topo já correto. Estes
    dois endereços são o que salva a verdade quando a troca não acontece.
    """
    mesa = a02.pacote(ctx)["mesa"]
    assert mesa["fita-peca"] == ["White", ""]
    assert mesa["fita-via"] == ["USB", "BT"]


def test_nada_do_mockup_sai_deste_pacote(a02, ctx):
    """A varredura final: nenhum nome do desenho em nenhum valor emitido."""
    p = a02.pacote(ctx)
    texto = repr(p)
    for nome in DO_MOCKUP:
        assert nome not in texto, f"o pacote emitiu `{nome}`, que é do mockup"


# ---------------------------------------------------------------------------
# 3. O HEXA VEM DO MAPA, e o "não sei" não vira cor
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("nome", ["White", "Galactic Purple", "Midnight Black"])
def test_a_cor_da_borda_sai_do_mapa(a02, nome):
    """Um hexa de verdade, e nunca o token neutro, para plástico conhecido."""
    cor = a02.cor_da_borda(nome)
    assert re.fullmatch(r"#[0-9a-fA-F]{6}", cor), f"`{nome}` não devolveu hexa"


def test_o_midnight_black_nao_vira_ausencia_de_borda(a02):
    """`#00040d` cru sobre `#282a36` não é borda preta — é borda nenhuma.

    Quem sabe disso é `cor_do_plastico.tom_para_a_borda`, com o piso de 2,2:1 e
    a mistura com branco. Esta aba NÃO reescreve a conta: ela a chama.
    """
    from hefesto_dualsense4unix.integrations.cor_do_plastico import TONS

    assert a02.cor_da_borda("Midnight Black").lower() != TONS["05"].lower()


@pytest.mark.parametrize("nome", ["", "Não sei", "Verde Abacate"])
def test_sem_leitura_a_borda_e_o_neutro(a02, nome):
    """E o neutro é o token que o lugar VAZIO desta aba já usa — não uma cor nova."""
    assert a02.cor_da_borda(nome) == a02.BORDA_SEM_COR
