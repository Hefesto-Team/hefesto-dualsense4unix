#!/usr/bin/env python3
"""A ABA VIBRAÇÃO DIZ O QUE ESTÁ ACONTECENDO — a linha do estado.

POR QUE ELA EXISTE, e o número foi medido em 02/09/2026 contra o daemon do usuário: a
janela estável mostra QUATRO avisos nesta aba e a interface nova mostrava
**zero**. A tela nova tinha os dois motores, os quatro degraus e o "Testar", e
nenhuma palavra sobre o que acontece com eles.

**E o pior estado era o de HOJE.** Com os dois controles na mesa, o daemon do usuário
respondia ``rumble_ff.vpads == 0`` — não há gamepad virtual —, o que quer dizer
que os quatro degraus de força **não agem sobre a vibração de jogo nenhum**. A
janela estável diz isso desde 11/08/2026
(``rumble_actions.texto_do_alcance_da_intensidade``); a interface nova ficava
calada e a pessoa continuava clicando em "Máximo".

**ERAM QUATRO ATÉ 07/09/2026, E HOJE SÃO TRÊS.** A primeira — a contagem de
pedidos do jogo — saiu por ordem de produto: *"Vibração remove essa última frase
também."* Ver ``app/telas/vibracao.py`` (as três frases que ficam) e
``test_as_frases_sao_as_do_produto``, que segura a lista fora (uma frase a mais
reprova). **A função do produto NÃO morreu** — a janela estável continua a chamar;
o que esta aba deixou de fazer é perguntar.

AS FRASES JÁ EXISTIAM E NINGUÉM AS CHAMAVA — ``rumble_actions.py``
:291, :370, :459. Esta régua vigia as duas metades do reuso:

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
* **arranque a chamada ao teto do orçamento** → o mesmo caso reprova;
* **acrescente uma frase que motor nenhum assina** → o mesmo caso reprova;
* devolva ``dict`` fixo em vez de lista (a linha que não se aplica virando
  travessão) → ``test_o_que_nao_se_aplica_nao_e_montado`` reprova;
* troque o alvo padrão para ``CONTROLE`` → ``test_o_alvo_padrao_desta_aba_e_todos``
  reprova;
* **faça o ``auto`` responder ``None``** →
  ``test_o_teto_e_a_mesma_frase_que_a_janela_estavel_escreve`` reprova;
* **tire o ``quote=False`` da FRASE em ``html_do_estado``** →
  ``test_a_aspa_reta_nao_vira_entidade`` reprova;
* **ponha ``quote=False`` no TOM** → ``test_o_tom_e_escapado_como_atributo``
  reprova: ali o valor vai para dentro de ``class="…"``, e uma aspa reta fecha o
  atributo;
* tire o bloco do ``MIOLO`` do gerador → ``test_a_bancada_tem_o_bloco`` reprova
  (e o próprio ``_conferir`` do gerador recusa gerar).

AS TRÊS MORDIDAS EM NEGRITO SÃO DE 02/09/2026, e as três primeiras existem
porque a régua NÃO MORDIA. Reproduzido antes de curar: com o aviso do teto
arrancado, **17 testes passavam**; com uma frase inventada no fim da lista, os
mesmos **17 passavam** e a prosa chegava ao ``mockup/05-vibracao.html`` que ela
olha, com o ``_conferir`` do gerador dizendo OK.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `app.actions.rumble_actions`, que carrega o GTK")

from hefesto_dualsense4unix.app.actions import rumble_actions as _ra
from hefesto_dualsense4unix.app.alvo_de_edicao import (
    AlvoDeEdicao,
    EstadoDoAlvo,
)
from hefesto_dualsense4unix.app.telas import vibracao as _tela

PAGINA = "05-vibracao.html"

UNIQ = "aa:bb:cc:00:00:01"

#: O vpad que não subiu (emulação ligada, nenhum gamepad virtual): é o único
#: estado de falha que acende o aviso. A Navegação (`enabled=False`) cala, e a
#: régua dela é `test_a_navegacao_nao_e_defeito_na_vibracao.py`.
SEM_VPAD = {"rumble_policy": "max", "rumble_mult_applied": 1.5,
            "gamepad_emulation": {"enabled": True},
            "rumble_ff": {"plays": 0, "nao_nulos": 0, "vpads": 0}}

QUIETA = {"rumble_policy": "balanceado", "rumble_mult_applied": 1.0,
          "rumble_ff": {"plays": 0, "nao_nulos": 0, "vpads": 1}}

MUDA: dict = {"rumble_policy": "balanceado"}


ORCAMENTOS = ["economia", "balanceado", None]


@pytest.mark.parametrize("orcamento", ORCAMENTOS)
@pytest.mark.parametrize("estado", [SEM_VPAD, QUIETA])
def test_as_frases_sao_as_do_produto(estado, orcamento, monkeypatch):
    """A linha diz AS QUATRO do produto — nem menos, nem uma a mais."""
    monkeypatch.setattr(_tela, "_orcamento_da_maquina", lambda: orcamento)
    do_produto = [f for f in (
        _ra.texto_do_alcance_da_intensidade(estado),
        _ra.texto_do_teto_do_orcamento(_tela._pedido_da_politica(estado), orcamento),
        _ra.texto_de_onde_grava_e_onde_manda(
            AlvoDeEdicao(estado=EstadoDoAlvo.TODOS)),
    ) if f]
    ditas = [frase for _tom, frase in _tela.textos_do_estado(estado)]
    assert ditas == do_produto, (
        "a linha do estado divergiu do produto.\n"
        f"  o produto diz: {do_produto}\n"
        f"  a aba diz:     {ditas}\n"
        "Falta = frase do produto que ninguém chama; sobra = prosa que motor "
        "nenhum assina, e ela vai para o desenho que ELA olha.")


def test_o_alerta_de_alcance_e_alerta():
    """O aviso de que a intensidade não chega tem de sair com o TOM de alerta."""
    tons = dict((frase, tom) for tom, frase in _tela.textos_do_estado(SEM_VPAD))
    alcance = _ra.texto_do_alcance_da_intensidade(SEM_VPAD)
    assert alcance, "o dublê deixou de acender o aviso: a régua mediria o vazio"
    assert tons.get(alcance) == _tela.ALERTA, (
        f"o aviso de alcance saiu como {tons.get(alcance)!r}, não como alerta")


def test_o_que_nao_se_aplica_nao_e_montado():
    """Daemon calado sobre vibração → linha nenhuma, e HTML vazio."""
    assert _tela.textos_do_estado(MUDA) == []
    assert _tela.html_do_estado([]) == ""


def test_o_alvo_padrao_desta_aba_e_todos():
    """Sem alvo por controle, a confissão "grava aqui, manda ali" não aparece."""
    frase = _ra.TEXTO_ONDE_GRAVA_E_ONDE_MANDA
    assert frase not in [f for _t, f in _tela.textos_do_estado(QUIETA)]
    com_alvo = _tela.textos_do_estado(
        QUIETA, alvo=AlvoDeEdicao(estado=EstadoDoAlvo.CONTROLE, uniq=UNIQ))
    assert frase in [f for _t, f in com_alvo], (
        "com alvo por controle a confissão tem de sair — se não sai, a chamada "
        "à `texto_de_onde_grava_e_onde_manda` virou linha morta")


def test_o_multiplicador_pedido_vem_da_tabela_do_produto():
    """``_pedido_da_politica`` é a conta da janela estável, degrau por degrau.

    A conta da estável é UMA LINHA, ``rumble_actions._pintar_a_linha_do_teto``::

        pedido = custom_mult if policy == "custom" else _POLICY_MULT.get(policy)

    e ``_POLICY_MULT`` é ``{**RUMBLE_POLICY_MULT, "auto": 1.0}`` — *"a única
    cópia autorizada em ``app/``"* (``rumble_actions.py:315``). Um número
    digitado aqui divergiria no dia em que o produto mudar um degrau, e a linha
    "limitado a 30% pelo orçamento" passaria a mentir por dentro.

    **ESTE CASO CIMENTAVA UM DEFEITO — 02/09/2026.** Ele afirmava
    ``_pedido_da_politica({"rumble_policy": "auto"}) is None`` e nunca importava
    ``_POLICY_MULT``: comparava o adaptador contra a tabela do DAEMON, que tem três
    chaves, quando a tela tem quatro botões. Um teste que grava a divergência é
    pior que teste nenhum — ele impede a próxima pessoa de consertar.
    """
    escada = _ra._POLICY_MULT
    degraus = _tela.degraus_da_forca()
    assert set(escada) - {_tela.FORCA_SEM_MULTIPLICADOR} == set(degraus), (
        "os degraus da tela deixaram de ser os da escada sem o `auto`")
    assert _tela.FORCA_SEM_MULTIPLICADOR not in degraus, (
        f"o degrau que saiu da tela voltou à lista dos botões: {degraus}")
    com_valor = [escada[k] for k in degraus]
    assert com_valor == sorted(com_valor), (
        f"os degraus com valor deixaram de subir: {degraus} -> {com_valor}")
    for chave, mult in escada.items():
        assert _tela._pedido_da_politica({"rumble_policy": chave}) == mult, (
            f"o degrau {chave!r} pede um número que a estável não pede")
    assert _tela._pedido_da_politica(
        {"rumble_policy": "custom", "rumble_mult_applied": 0.7}) == 0.7
    assert _tela._pedido_da_politica({"rumble_policy": "nao-existe"}) is None
    assert _tela._pedido_da_politica({"rumble_policy": "custom"}) is None


@pytest.mark.parametrize("orcamento", ORCAMENTOS)
def test_o_teto_e_a_mesma_frase_que_a_janela_estavel_escreve(orcamento):
    """Para os QUATRO degraus, a frase do teto é a da estável — inclusive `Auto`."""
    for policy, mult in _ra._POLICY_MULT.items():
        da_estavel = _ra.texto_do_teto_do_orcamento(mult, orcamento)
        da_aba = _ra.texto_do_teto_do_orcamento(
            _tela._pedido_da_politica({"rumble_policy": policy}), orcamento)
        assert da_aba == da_estavel, (
            f"degrau {policy!r} · orçamento {orcamento!r}: a estável escreve "
            f"{da_estavel!r} e a aba escreve {da_aba!r}")


def test_a_confissao_de_onde_grava_sai_no_tom_de_info():
    """A quarta frase é INFO, como na estável — explica, não alarma.

    Lá ela é pintada com ``#8be9fd`` (``rumble_actions.py:483``), e o comentário
    ao lado diz por quê: *"a frase explica, não alarma — quem alarma é o aviso
    de alcance, em laranja"*. Ela saía daqui como ``diz``, o cinza do rótulo
    comum, e o tom só aparece no dia em que a ``MIGRA-VIBRACAO-04`` ligar o
    alvo por controle — tarde demais para alguém notar.
    """
    com_alvo = _tela.textos_do_estado(
        QUIETA, alvo=AlvoDeEdicao(estado=EstadoDoAlvo.CONTROLE, uniq=UNIQ))
    tons = {frase: tom for tom, frase in com_alvo}
    assert tons.get(_ra.TEXTO_ONDE_GRAVA_E_ONDE_MANDA) == _tela.INFO, (
        f"a confissão saiu como {tons.get(_ra.TEXTO_ONDE_GRAVA_E_ONDE_MANDA)!r}")
    assert _tela.INFO != _tela.ALERTA


def test_o_html_escapa_o_que_vier():
    """Uma frase com ``<`` ou ``&`` não pode sumir da tela sem dizer nada."""
    saiu = _tela.html_do_estado([(_tela.ALERTA, 'a & b <script>x</script>')])
    assert "<script>" not in saiu
    assert "&amp;" in saiu and "&lt;script&gt;" in saiu


def test_a_aspa_reta_nao_vira_entidade():
    """Nada que sai daqui pode voltar DIFERENTE do ``innerHTML`` do navegador."""
    saiu = _tela.html_do_estado([(_tela.ALERTA, 'clique "Testar"')])
    assert "&quot;" not in saiu, (
        f"a entidade voltou ao HTML — o bloco repintaria a cada tique: {saiu!r}")
    assert 'clique "Testar"' in saiu


def test_o_tom_e_escapado_como_atributo(monkeypatch):
    """O ``tom`` cai dentro de ``class="…"``, e ali a aspa reta QUEBRA a tela."""
    from html.parser import HTMLParser

    veneno = 'diz" onmouseover="x'
    saiu = _tela.html_do_estado([(veneno, "uma frase qualquer")])

    achados: list[tuple[str, list]] = []

    class Leitor(HTMLParser):
        def handle_starttag(self, tag, attrs):
            achados.append((tag, attrs))

    Leitor().feed(saiu)
    divs = [a for t, a in achados if t == "div"]
    assert len(divs) == 1, f"o HTML deixou de ser uma div por linha: {saiu!r}"
    nomes = sorted(nome for nome, _valor in divs[0])
    assert nomes == ["class"], (
        f"o tom escapou do atributo e criou {nomes} — uma aspa reta no tom "
        f"fecha a `class` e o resto do valor vira markup: {saiu!r}")
    assert dict(divs[0])["class"] == f"est {veneno}", (
        "o valor do atributo chegou ao navegador diferente do tom emitido")


def test_o_pacote_emite_o_bloco_do_estado():
    """O pacote da aba manda o bloco, com o HTML do MESMO emissor."""
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


def test_a_bancada_tem_o_bloco():
    """A página que ELA olha tem o endereço do bloco e a frase do produto."""
    import onde

    doc = onde.pagina(PAGINA).read_text(encoding="utf-8")
    assert 'id="vib-estado"' in doc, "o bloco do estado sumiu do desenho"
    assert ".vib-estado:empty{display:none}" in doc, (
        "sem o `:empty` a linha vazia deixa um vão no meio da aba")
    cena = _tela.textos_do_estado(
        {"rumble_policy": "economia",
         "rumble_ff": {"plays": 0, "nao_nulos": 0, "vpads": 1}})
    assert cena == [], (
        f"a faixa voltou a acender linha permanente no desenho: {cena}")
    assert 'id="vib-estado"></div>' in doc, (
        "a faixa não nasce vazia no desenho — o que estiver ali é prosa "
        "cravada, e ela chega à página que ELA olha")


CHAVES_DAS_DUAS_ABAS = (
    "vibracao.rumble.esquerdo",
    "vibracao.rumble.direito",
    "vibracao.rumble.passthrough",
    "gatilho.esquerdo.adaptativo",
    "gatilho.direito.adaptativo",
)


@pytest.mark.parametrize("chave", CHAVES_DAS_DUAS_ABAS)
def test_as_duas_abas_nao_tem_o_que_apagar_por_transporte(chave):
    """Cabo e rádio acionam o mesmo: a coluna não tem o que apagar por transporte.

    A-TELA-PERGUNTA-AO-DONO-01, 28/09/2026. O `pacotes/mapa.py` nasceu em 01/09
    para a Vibração e os Gatilhos apagarem o que o transporte de agora não
    aciona, e nenhuma aba o chamou. Medido no mapa: para o DualSense, que é o
    único controle que estas duas abas mostram (o daemon numera os externos e
    não os adota), cada peça que elas acionam responde `sim` no cabo e no rádio.
    Apagar por transporte não mudaria um pixel, e o módulo saiu.

    ESTA RÉGUA GUARDA A PREMISSA, e pergunta ao leitor que o produto usa
    (`mesa_viva.aciona`). No dia em que o mapa disser que um transporte não
    aciona uma destas peças, ela reprova nomeando a peça: é a hora de a aba
    perguntar a `mesa_viva.aciona` por coluna, como a cor e o giroscópio já
    perguntam.

    A MORDIDA: troque o `radio_aciona` da linha `vibracao.rumble.esquerdo` do
    DualSense por `não` no CSV, e ela reprova.
    """
    import mesa_viva

    no_cabo = mesa_viva.aciona(chave, "usb")
    no_radio = mesa_viva.aciona(chave, "bt")
    assert no_cabo == no_radio == "sim", (
        f"o mapa diz que `{chave}` aciona {no_cabo!r} no cabo e {no_radio!r} no "
        "rádio. A coluna da aba mostra a peça igual nos dois transportes: ela "
        "tem de perguntar a `mesa_viva.aciona` por coluna e apagar o que o "
        "transporte de agora não aciona.")
