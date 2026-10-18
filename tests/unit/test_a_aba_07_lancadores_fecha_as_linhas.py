#!/usr/bin/env python3
"""AS QUATRO DECISÕES DA ABA LANÇADORES, cobradas uma a uma.

Elas são do PO, 04/09/2026
(o registro «O-PO-DECIDE-as-54-e-os-sete-conflitos» de 04/09/2026 §2,
`07-lancadores`), e a sprint que as executa é a `ONDA2-07-LANCADORES-01`:

    [01] o reparo manual sem caminho   a linha à mostra, SÓ no estado em que
                                       o cartão já diz «linha intocável» (o
                                       botão «Copiar a linha» saiu em 21/09)
    [02] a frase que manda a um botão  ela para de nomear lugar. **O texto tem
         inexistente                   UM dono para as duas telas, e ele NÃO é
                                       desta posse** — o que esta régua cobra é
                                       que a aba não escreva uma SEGUNDA frase
    [03] de onde o aviso some          as DUAS recusas calam: a lista antiga
                                       do «Não perguntar» e o «Tirar daqui»
    [04] 63 e 22 na mesma tela         CADUCOU em 21/09: a frase do atalho
                                       saiu do corpo, e o corpo de todo cartão
                                       é o mesmo contador de pontes

Em 18/10/2026 a [02] e a [03] saíram da aba com a 07 antiga: a Experimental não mostra o aviso
do jogo aberto (ele segue na coluna Atenção da Jogar, por `home_actions`), e as réguas
dele saíram daqui.

O QUE ELAS CURAM, e cada uma é um defeito medido:

* a tela prometia um **reparo manual** e não oferecia caminho nenhum para
  fazê-lo — **não existia UM botão de copiar em toda a interface nova**;
* a frase do aviso manda copiar as opções *"na aba Sistema"*, e a aba Sistema
  da interface nova tem doze botões e **nenhum copia coisa alguma**;
* o *"Não usar neste jogo"* — a lista que o produto INTEIRO respeita no
  reparo — **não calava tela nenhuma**: ela tirava o jogo de propósito e o
  aviso voltava toda vez que ele abrisse;
* o cartão dizia `22 jogos instalados` e, uma linha abaixo, *"o atalho está no
  lugar em 63 jogos da sua biblioteca"* — as duas verdadeiras, e nada na tela
  dizendo que contam conjuntos diferentes.

A MORDIDA DE CADA UMA está colada no relatório desta frente
(`ONDA2-07`), e o resumo é este:

    apague o `if lida.intocaveis and lida.linha:` de `cartao_da_steam`
        → 1 reprova (o bloco some do corpo)
    torne o mesmo `if` incondicional
        → 1 reprova (o bloco nasce no dia bom)
    apague `linha=slo.WRAPPER_LAUNCH` de `_ler_do_disco`
        → 1 reprova (a linha nunca chega ao desenho)
"""

from __future__ import annotations

import pathlib
import sys
import types

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

PAGINA = "07-lancadores.html"


@pytest.fixture(scope="module")
def desenho():
    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as dl

    return dl


@pytest.fixture(scope="module")
def a07():
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores

    return a07_lancadores


@pytest.fixture(autouse=True)
def _a_maquina_nao_entra_na_regua(monkeypatch):
    """Nenhum teste daqui depende de haver jogo da Steam aberto na máquina."""
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    for dono in (slo, sw):
        monkeypatch.setattr(dono, "steam_game_running", lambda: False)
        monkeypatch.setattr(dono, "steam_running", lambda: False)


@pytest.fixture(scope="module")
def linha_do_motor() -> str:
    """A linha de inicialização, PERGUNTADA ao dono — nunca digitada aqui."""
    from hefesto_dualsense4unix.integrations.steam_launch_options import (
        WRAPPER_LAUNCH,
    )

    return WRAPPER_LAUNCH


@pytest.fixture
def ctx():
    import pacotes

    return pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})


def _fileira(desenho, lida) -> str:
    """A fileira de botões DO CARTÃO DA STEAM, como a pintura a emite."""
    return desenho.Quadro(lancadores=desenho.cartoes(lida)).valores()["steam-acoes"]


def _corpo(desenho, lida) -> str:
    """O corpo do cartão da Steam, como a pintura o emite."""
    return desenho.Quadro(lancadores=desenho.cartoes(lida)).valores()["steam-diz"]


def _com_intocavel(desenho, linha: str, **extra):
    """Uma leitura em que HÁ jogo com a linha intocável."""
    return desenho.Leitura(
        com_wrapper=("620", "440"),
        intocaveis=(("70", "Jogo de linha editada",
                     "linha editada à mão — não vou tocar"),),
        instalados=2, linha=linha, **extra)


def _em_ordem(desenho, linha: str, **extra):
    """Uma leitura em que a biblioteca está inteira em ordem — o dia bom."""
    return desenho.Leitura(com_wrapper=("620", "440"), instalados=2,
                           linha=linha, **extra)


COPIAR_QUE_SAIU = 'data-gesto="copiar-a-linha"'


def test_o_estado_intocavel_traz_a_linha_a_mostra(desenho, linha_do_motor):
    """Com jogo intocável, o cartão mostra a linha — e o «Copiar» não volta."""
    lida = _com_intocavel(desenho, linha_do_motor)
    corpo = _corpo(desenho, lida)

    assert COPIAR_QUE_SAIU not in _fileira(desenho, lida), (
        "o «Copiar a linha» voltou ao cartão da Steam — um botão que os outros "
        "sete cartões não têm")
    assert 'class="linha-do-wrapper"' in corpo, (
        "a linha à mostra não entrou no corpo do cartão — o carimbo diz «só "
        "reparo manual» e a tela ficaria sem o que copiar")
    assert desenho._e(linha_do_motor) in corpo, (
        "o bloco à mostra não traz a linha do motor. Uma linha diferente da "
        "que o produto grava faria ela colar à mão uma opção que o Hefesto "
        "não reconhece depois.")


def test_no_dia_bom_nada_disso_ocupa_a_tela(desenho, linha_do_motor):
    """Sem jogo intocável, o bloco da linha não nasce — a outra metade da decisão."""
    assert "linha-do-wrapper" not in _corpo(desenho, _em_ordem(desenho, linha_do_motor)), (
        "o bloco da linha apareceu numa biblioteca em ordem")


def test_sem_a_linha_o_cartao_cala_em_vez_de_inventar(desenho):
    """Leitura com intocáveis e SEM linha: nenhum bloco."""
    assert "linha-do-wrapper" not in _corpo(desenho, _com_intocavel(desenho, ""))


def test_o_produto_enche_a_linha_com_a_constante_do_motor(
        a07, desenho, linha_do_motor, monkeypatch):
    """`_ler_do_disco` põe `WRAPPER_LAUNCH` na `Leitura` — LIDO, não digitado."""
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw

    censo = types.SimpleNamespace(
        com_wrapper=["620"], reparaveis=[], intocaveis=[], recusados=[],
        erros=[], jogo_aberto=False, steam_aberta=False)
    monkeypatch.setattr(sw, "censo_do_wrapper", lambda **_: censo)
    monkeypatch.setattr(sw, "frase_do_aviso", lambda _c: "")
    lida = a07._ler_do_disco()
    assert lida.linha == linha_do_motor, (
        f"`_ler_do_disco` devolveu linha={lida.linha!r}. Ela tem de ser a "
        f"constante do motor: é a MESMA que o reparo grava no vdf e a MESMA "
        f"que o botão da janela velha copia.")


def test_o_jogo_nao_funciona_saiu(a07, desenho):
    """21/09/2026, o desenho aprovado pelo usuário (OS-LANCADORES-IGUAIS-E-A-LISTA-"""
    lida = desenho.Leitura(com_wrapper=("620",), instalados=1)
    fileira = desenho.acoes_html(desenho.cartoes(lida)[0])
    assert 'data-gesto="este-jogo-nao-funciona"' not in fileira
    assert not hasattr(a07, "este_jogo_nao_funciona"), (
        "o gesto velho continua registrado sem botão na tela — um clique que "
        "nenhuma página oferece")
