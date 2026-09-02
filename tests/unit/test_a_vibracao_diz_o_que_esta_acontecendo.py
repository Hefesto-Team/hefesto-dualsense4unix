#!/usr/bin/env python3
"""A ABA VIBRAÇÃO DIZ O QUE ESTÁ ACONTECENDO — a linha do estado.

POR QUE ELA EXISTE, e o número foi medido em 02/09/2026 contra o daemon dela: a
janela estável mostra QUATRO avisos nesta aba e a interface nova mostrava
**zero**. A tela nova tinha os dois motores, os quatro degraus e o "Testar", e
nenhuma palavra sobre o que acontece com eles.

**E o pior estado era o de HOJE.** Com os dois controles na mesa, o daemon dela
respondia ``rumble_ff.vpads == 0`` — não há gamepad virtual —, o que quer dizer
que os quatro degraus de força **não agem sobre a vibração de jogo nenhum**. A
janela estável diz isso desde 11/08/2026
(``rumble_actions.texto_do_alcance_da_intensidade``); a interface nova ficava
calada e a pessoa continuava clicando em "Máximo".

AS QUATRO FRASES JÁ EXISTIAM E NINGUÉM AS CHAMAVA — ``rumble_actions.py``
:186, :291, :370, :459. Esta régua vigia as duas metades do reuso:

1. **o texto é o do produto**, byte a byte. Nenhuma comparação com string
   digitada aqui: o esperado sai das MESMAS funções. Uma frase reescrita neste
   módulo passaria por qualquer teste que a redigitasse — e é assim que um texto
   de tela ganha duas versões que divergem na primeira edição;
2. **o desenho e a tela viva saem do MESMO emissor** (``html_do_estado``), e o
   pacote emite o bloco.

AS MORDIDAS, e cada uma reprova um teste diferente:

* apague a chave ``blocos`` do ``a05_vibracao.pacote`` →
  ``test_o_pacote_emite_o_bloco_do_estado`` reprova;
* troque uma frase por texto digitado em ``textos_do_estado`` →
  ``test_as_frases_sao_as_do_produto`` reprova nomeando a frase;
* devolva ``dict`` fixo em vez de lista (a linha que não se aplica virando
  travessão) → ``test_o_que_nao_se_aplica_nao_e_montado`` reprova;
* troque o alvo padrão para ``CONTROLE`` → ``test_o_alvo_padrao_desta_aba_e_todos``
  reprova;
* tire o bloco do ``MIOLO`` do gerador → ``test_a_bancada_tem_o_bloco`` reprova
  (e o próprio ``_conferir`` do gerador recusa gerar).
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.app.actions import rumble_actions as _ra
from hefesto_dualsense4unix.app.alvo_de_edicao import (
    AlvoDeEdicao,
    EstadoDoAlvo,
)
from hefesto_dualsense4unix.app.telas import vibracao as _tela

PAGINA = "05-vibracao.html"

#: Um controle de mentira. MAC da faixa SINTÉTICA da casa — há dois portões de
#: anonimato nesta árvore, e um endereço mascarado ainda carrega o OUI dela.
UNIQ = "aa:bb:cc:00:00:01"

#: O estado em que os quatro degraus NÃO alcançam a vibração do jogo. É o estado
#: que a máquina dela estava em 02/09/2026, e é o que a aba ficava calada sobre.
SEM_VPAD = {"rumble_policy": "max", "rumble_mult_applied": 1.5,
            "rumble_ff": {"plays": 0, "nao_nulos": 0, "vpads": 0}}

#: A mesa quieta: há gamepad virtual, e nenhum jogo pediu nada ainda.
QUIETA = {"rumble_policy": "balanceado", "rumble_mult_applied": 1.0,
          "rumble_ff": {"plays": 0, "nao_nulos": 0, "vpads": 1}}

#: O daemon que não respondeu sobre vibração. Nada a dizer — e a linha some.
MUDA: dict = {"rumble_policy": "balanceado"}


# --------------------------------------------------------------------------
# 1. o texto é o do produto, e não uma segunda cópia
# --------------------------------------------------------------------------
@pytest.mark.parametrize("estado", [SEM_VPAD, QUIETA])
def test_as_frases_sao_as_do_produto(estado):
    """Cada frase da linha TEM de ser a que ``rumble_actions`` devolve.

    O esperado é COMPUTADO das mesmas funções, nunca digitado: uma régua que
    redigita a frase dá verde sobre a segunda cópia dela, que é exatamente o
    defeito que se quer impedir.
    """
    do_produto = [f for f in (_ra.texto_dos_pedidos_de_vibracao(estado),
                              _ra.texto_do_alcance_da_intensidade(estado)) if f]
    ditas = [frase for _tom, frase in _tela.textos_do_estado(estado)]
    faltam = [f for f in do_produto if f not in ditas]
    assert not faltam, (
        f"a aba deixou de dizer o que o produto já sabe: {faltam}. "
        f"O que ela diz hoje: {ditas}")


def test_o_alerta_de_alcance_e_alerta():
    """O aviso de que a intensidade não chega tem de sair com o TOM de alerta.

    Sem isso ele sai da mesma cor do resto e some no meio da linha — e a
    diferença entre "está acontecendo" e "o que você escolheu não chega" é a
    razão inteira de a linha existir.
    """
    tons = dict((frase, tom) for tom, frase in _tela.textos_do_estado(SEM_VPAD))
    alcance = _ra.texto_do_alcance_da_intensidade(SEM_VPAD)
    assert alcance, "o dublê deixou de acender o aviso: a régua mediria o vazio"
    assert tons.get(alcance) == _tela.ALERTA, (
        f"o aviso de alcance saiu como {tons.get(alcance)!r}, não como alerta")


# --------------------------------------------------------------------------
# 2. o que não se aplica NÃO É MONTADO — nunca vira travessão
# --------------------------------------------------------------------------
def test_o_que_nao_se_aplica_nao_e_montado():
    """Daemon calado sobre vibração → linha nenhuma, e HTML vazio.

    O pintor troca vazio por ``—`` (``hefesto_vivo.py``, o ``escrever()``), então
    um campo fixo mostraria um travessão numa linha de alerta — que afirmaria
    "não sei" onde a resposta certa é "não há nada a avisar". A cura é o bloco
    VAZIO, que o CSS esconde com ``.vib-estado:empty``.
    """
    assert _tela.textos_do_estado(MUDA) == []
    assert _tela.html_do_estado([]) == ""


def test_o_alvo_padrao_desta_aba_e_todos():
    """Sem alvo por controle, a confissão "grava aqui, manda ali" não aparece.

    Nesta aba a fita do topo é inerte e o degrau manda ``rumble.policy_set``, que
    não leva endereço: não há override de peça sendo escrito, logo não há a
    divergência que aquela frase confessa. Um aviso permanente seria ruído
    crônico — o próprio contrato da função.

    E a CHAMADA continua viva: com o alvo por controle, a frase sai. É isto que
    separa "não se aplica hoje" de "ninguém chama esta função".
    """
    frase = _ra.TEXTO_ONDE_GRAVA_E_ONDE_MANDA
    assert frase not in [f for _t, f in _tela.textos_do_estado(QUIETA)]
    com_alvo = _tela.textos_do_estado(
        QUIETA, alvo=AlvoDeEdicao(estado=EstadoDoAlvo.CONTROLE, uniq=UNIQ))
    assert frase in [f for _t, f in com_alvo], (
        "com alvo por controle a confissão tem de sair — se não sai, a chamada "
        "à `texto_de_onde_grava_e_onde_manda` virou linha morta")


def test_o_multiplicador_pedido_vem_da_tabela_do_produto():
    """``_pedido_da_politica`` lê ``RUMBLE_POLICY_MULT``; não guarda cópia.

    Um número digitado aqui divergiria no dia em que o produto mudar um degrau —
    e a linha "limitado a 30% pelo orçamento" passaria a mentir por dentro.
    """
    from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT

    for chave, mult in RUMBLE_POLICY_MULT.items():
        assert _tela._pedido_da_politica({"rumble_policy": chave}) == mult
    assert _tela._pedido_da_politica({"rumble_policy": "auto"}) is None
    assert _tela._pedido_da_politica(
        {"rumble_policy": "custom", "rumble_mult_applied": 0.7}) == 0.7


# --------------------------------------------------------------------------
# 3. o HTML: um emissor só, e ele escapa
# --------------------------------------------------------------------------
def test_o_html_escapa_o_que_vier():
    """Uma frase com ``<`` ou ``&`` não pode sumir da tela sem dizer nada.

    Nenhuma das quatro leva isso hoje — mas elas são texto de tela e mudam sem
    passar por aqui.
    """
    saiu = _tela.html_do_estado([(_tela.DIZ, 'a & b <script>x</script>')])
    assert "<script>" not in saiu
    assert "&amp;" in saiu and "&lt;script&gt;" in saiu


def test_o_pacote_emite_o_bloco_do_estado():
    """O pacote da aba manda o bloco, com o HTML do MESMO emissor.

    Se ele parar de emitir, a tela viva volta a mostrar a frase CRAVADA no
    desenho — que é o pior dos casos: a linha existe, parece dado, e é o mockup.
    """
    import pacotes

    falso = {"uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
             "battery_pct": 95, "is_primary": True, "inputs": {}}
    mesa = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
             "via": "USB", "cor": "starlight-blue", "plastico": "#123456",
             "conectado": True}]
    ctx = pacotes.Contexto(state=dict(SEM_VPAD, active_profile="regua"),
                           mesa=mesa, conectados=[falso], estados={})
    pacote = pacotes.pacote_da_pagina(PAGINA, ctx)
    blocos = pacote.get("blocos") or {}
    assert "#vib-estado" in blocos, (
        f"o pacote não emite o bloco do estado. Emitiu: {sorted(blocos)}")
    assert blocos["#vib-estado"] == _tela.html_do_estado(
        _tela.textos_do_estado(ctx.state)), (
        "o HTML do pacote divergiu do emissor único — há um segundo emissor")
    assert _ra.texto_do_alcance_da_intensidade(SEM_VPAD) in blocos["#vib-estado"]


# --------------------------------------------------------------------------
# 4. o desenho da BANCADA tem o bloco — e é lá que o gerador escreve
# --------------------------------------------------------------------------
def test_a_bancada_tem_o_bloco():
    """A página que ELA olha tem o endereço do bloco e a frase do produto.

    Mede na BANCADA (``mockup/``), nunca no publicado: o publicado é a página
    congelada, e apontar a régua para lá dá verde sobre o desenho velho — a
    armadilha que o ``onde.pagina()`` documenta.
    """
    import onde

    doc = onde.pagina(PAGINA).read_text(encoding="utf-8")
    assert 'id="vib-estado"' in doc, "o bloco do estado sumiu do desenho"
    assert ".vib-estado:empty{display:none}" in doc, (
        "sem o `:empty` a linha vazia deixa um vão no meio da aba")
    cena = _tela.textos_do_estado(
        {"rumble_policy": "economia",
         "rumble_ff": {"plays": 0, "nao_nulos": 0, "vpads": 1}})
    assert cena, "a cena do desenho ficou muda"
    assert _tela.html_do_estado(cena) in doc, (
        "o texto do desenho não é o que o produto monta — há prosa digitada no "
        "gerador")
