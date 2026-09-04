#!/usr/bin/env python3
"""O AVISO DA VIBRAÇÃO CABE NA ABA — medido no WebKit, na janela do tamanho real.

POR QUE ELE EXISTE, e o defeito foi fotografado em 02/09/2026. A linha de estado
da aba 05 nasceu no mesmo dia e o aviso mais importante dela — *"a intensidade
não está chegando a jogo nenhum"* — tinha **211 caracteres**. Na caixa de texto
da ``.vib-estado``, que mede 1072 px, ele ocupava **1072 px**: quebrava em duas
sublinhas, o quadro passava a rolar 40 px e a segunda metade ficava **CORTADA**
pela borda de baixo do miolo. Para ler o aviso inteiro ela tinha de arrastar.

**E o estado não era excepcional:** ``rumble_ff.vpads == 0`` é o da máquina dela
com os dois controles na mesa. O custo caía exatamente sobre a frase que a linha
existe para dizer.

DECISÃO DELA, 02/09/2026 — *encurtar a frase, em vez de deixar a aba rolar*. E
ela é uma frase só, com um dono só (``rumble_actions.texto_do_alcance_da_
intensidade``): encurtar ali muda a janela GTK junto, de propósito.

POR QUE ESTA RÉGUA MEDE NO NAVEGADOR, e não conta caracteres: largura de texto
não é linear em caracteres — ``"iii"`` e ``"MMM"`` têm o mesmo comprimento e
larguras diferentes. Um teto de caracteres seria um PROXY, e um proxy fica verde
sobre a frase larga do dia em que alguém trocar as palavras. Aqui a pergunta é
feita ao motor que ela vai usar, com a fonte, o CSS e a largura reais.

A JANELA É ``Gtk.OffscreenWindow`` de ``gui/ponte_da_tela.TAMANHO_OCULTA`` —
**importado, nunca digitado**. Ele é o MIOLO da janela do produto: a janela na
tela pede ``TAMANHO_NA_TELA`` e a ``Gtk.HeaderBar`` come ``ALTURA_DA_BARRA`` do
alto, então o que sobra para a página é exatamente ``TAMANHO_OCULTA`` — e uma
``OffscreenWindow`` não tem barra nenhuma.

DUAS AFIRMAÇÕES DESTA DOCSTRING CAÍRAM EM 04/09/2026, e a régua andava com as
duas. Ela dizia *"a janela é 1180x757, o ``TAMANHO_NA_TELA``"* e *"medir na
``TAMANHO_OCULTA`` (1180x900) responderia 'não rola' sempre: são 143 px a mais
de altura"*:

1. **``TAMANHO_NA_TELA`` numa ``OffscreenWindow`` mede o miolo ERRADO.** Onde a
   janela de verdade dava 757 menos os 46 px da barra = 711 px de página, a
   régua lia 757. Eram 46 px de otimismo — e o número redigitado envelheceu
   calado: hoje ``TAMANHO_NA_TELA`` é ``(1212, 855)``.
2. **A ALTURA DA JANELA NÃO MUDA ESTA MEDIDA — nenhum pixel.** A ``.janela`` tem
   altura FIXA (``--alt-janela:777px``, ``interface/topo.html:592``), então o
   fundo do miolo cai em 733 px e a rolagem é 22 px a 757, a 809 e a 855 de
   viewport. Medido nos três em 04/09/2026.

**QUEM APERTA É A LARGURA**, e era ali que o tamanho errado cobrava: a
``.janela`` é ``width:1180px; max-width:100%`` (``topo.html:147``), e num
viewport de 1180 ela encolhia para 1148 px. A caixa da linha de estado tinha
**1087 px** em vez dos 1119 de hoje — a régua cobrava a frase contra uma caixa
32 px mais estreita que a do produto, e uma frase que coubesse na janela dela
podia ser reprovada aqui.

AS MORDIDAS:

* devolva a frase de 211 caracteres em ``texto_do_alcance_da_intensidade`` →
  ``test_o_aviso_nao_e_cortado_pela_borda_do_miolo`` reprova dizendo qual linha
  passou da borda, e ``test_cada_frase_da_linha_cabe_numa_sublinha`` reprova
  dizendo que ela ocupa 36 px em vez de 18;
* apague o bloco ``#vib-estado`` do pacote → as duas reprovam por linha nenhuma;
* troque ``TAMANHO_OCULTA`` por ``TAMANHO_NA_TELA`` na :data:`JANELA` →
  ``test_a_regua_mede_o_miolo_da_janela_do_produto`` reprova dizendo que o
  viewport medido tem 46 px de barra de título a mais do que a página recebe.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("VIBRAÇÃO-CABE-01 — o aviso medido no WebKit da janela real")

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.app.telas import vibracao as _tela

try:
    from hefesto_dualsense4unix.gui.ponte_da_tela import (
        ALTURA_DA_BARRA,
        ALTURA_DO_DESENHO,
        LARGURA_DO_DESENHO,
        TAMANHO_NA_TELA,
        TAMANHO_OCULTA,
    )
except (ImportError, ValueError) as _erro:  # pragma: no cover — ambiente sem WebKit
    pytest.skip(
        f"VIBRAÇÃO-CABE-01: a biblioteca da janela não importou ({_erro}). "
        "Falta gir1.2-webkit2-4.1?",
        allow_module_level=True,
    )

PAGINA = "05-vibracao.html"

#: MAC da faixa SINTÉTICA da casa — há dois portões de anonimato nesta árvore, e
#: um endereço mascarado ainda carrega o OUI do aparelho dela.
UNIQ = "aa:bb:cc:00:00:01"

#: O ESTADO DA MÁQUINA DELA em 02/09/2026: dois controles na mesa e
#: ``rumble_ff.vpads == 0``. Nele as DUAS primeiras frases acendem — a dos
#: pedidos e a do alcance —, e é a soma delas que empurra a tela.
SEM_VPAD = {"rumble_policy": "max", "rumble_mult_applied": 1.5,
            "native_mode": False,
            "rumble_ff": {"plays": 0, "nao_nulos": 0, "vpads": 0}}

#: O MIOLO da janela do produto — o que a página realmente recebe. É importado
#: de ``gui/ponte_da_tela`` porque **o que tem dono não se digita**: a conta
#: (``TAMANHO_NA_TELA`` menos a ``HeaderBar``) mora lá, e um número copiado para
#: cá envelheceria calado — foi exatamente o que aconteceu com o ``(1180, 757)``
#: que esta linha trazia até 04/09/2026.
JANELA = TAMANHO_OCULTA

#: O que o navegador devolve por linha da ``.vib-estado`` e pelo miolo que a
#: contém. ``base`` e ``fundo_do_miolo`` são coordenadas de viewport: a linha
#: cortada é a que tem ``base`` maior que o fundo.
#:
#: O ``viewport`` vem junto para a régua poder DECLARAR em que janela mediu — e
#: ``.janela > .miolo`` e não ``.miolo``: a classe se repete dentro do SVG do
#: controle (``interface/topo.html:562`` avisa disso), e ali ela é a bola do
#: polegar do analógico.
MEDIDA = r"""
(function(){
  var de = document.documentElement;
  var j = document.querySelector('.janela');
  var m = document.querySelector('.janela > .miolo');
  var e = document.querySelector('#vib-estado');
  return JSON.stringify({
    viewport: {larg: de.clientWidth, alt: de.clientHeight},
    tem_miolo: !!m, tem_estado: !!e,
    caixa_do_estado: e ? Math.round(e.getBoundingClientRect().width) : null,
    janela_larg: j ? Math.round(j.getBoundingClientRect().width) : null,
    rola: m ? (m.scrollHeight - m.clientHeight) : null,
    fundo_do_miolo: m ? Math.round(m.getBoundingClientRect().bottom) : null,
    linhas: e ? Array.prototype.map.call(e.querySelectorAll('.est'), function(d){
      var r = d.getBoundingClientRect();
      var rg = document.createRange(); rg.selectNodeContents(d);
      return {txt: d.textContent.trim(), alto: Math.round(r.height),
              caixa: Math.round(r.width),
              tinta: Math.round(rg.getBoundingClientRect().width),
              base: Math.round(r.bottom)};
    }) : []
  });
})()
"""


def _carga() -> dict:
    """A carga do tique, montada pelo PACOTE da aba — nunca HTML digitado aqui.

    Um dublê de bloco mediria a régua contra ela mesma: o que tem de caber é o
    que o produto emite, e quem o emite é ``a05_vibracao.pacote``.
    """
    import pacotes

    falso = {"uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
             "battery_pct": 95, "is_primary": True, "inputs": {}}
    mesa = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
             "via": "USB", "cor": "starlight-blue", "plastico": "#123456",
             "conectado": True}]
    ctx = pacotes.Contexto(state=dict(SEM_VPAD), mesa=mesa,
                           conectados=[falso], estados={})
    return pacotes.pacote_da_pagina(PAGINA, ctx) or {}


@pytest.fixture(scope="module")
def medido() -> dict:
    """Abre a aba publicada num WebKit offscreen, pinta a carga e mede o DOM.

    O ORÇAMENTO É INJETADO: ``_orcamento_da_maquina`` lê o ``maquina.json`` da
    máquina de quem roda, e com ele solto esta régua mediria a configuração da
    bancada em vez da tela. Com ``None`` a frase do teto cala, que é o silêncio
    documentado da própria ``texto_do_teto_do_orcamento``.
    """
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    from hefesto_dualsense4unix.interface import hefesto_vivo, onde

    original = _tela._orcamento_da_maquina
    _tela._orcamento_da_maquina = lambda: None
    try:
        carga = _carga()
    finally:
        _tela._orcamento_da_maquina = original
    pintar = hefesto_vivo.PEDIR_A_PINTURA.replace(
        "CARGA", json.dumps(carga, ensure_ascii=False))

    saiu: list[str] = []
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(*JANELA)
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def mediu(v, res):
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:
            saiu.append(f"ERRO na medida: {e}")
        Gtk.main_quit()

    def pintou(v, res):
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:
            saiu.append(f"ERRO na pintura: {e}")
            Gtk.main_quit()
            return
        v.evaluate_javascript(MEDIDA, -1, None, None, None, mediu)

    def instalou(v, res):
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:
            saiu.append(f"ERRO no bootstrap: {e}")
            Gtk.main_quit()
            return
        v.evaluate_javascript(pintar, -1, None, None, None, pintou)

    def carregou(v, evento):
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(hefesto_vivo.BOOTSTRAP, -1, None, None,
                                  None, instalou)

    view.connect("load-changed", carregou)
    view.load_uri(onde.pagina(PAGINA, publicado=True).as_uri())
    GLib.timeout_add(20000, Gtk.main_quit)
    Gtk.main()
    assert saiu, "o WebKit não respondeu em 20 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    lido = json.loads(saiu[0])
    assert lido["tem_miolo"] and lido["tem_estado"], (
        f"a página perdeu o miolo ou o #vib-estado: {lido}")
    assert lido["linhas"], (
        "a linha do estado ficou MUDA no estado sem gamepad virtual — não há o "
        "que medir, e a régua daria verde por vacuidade")
    return lido


#: A ALTURA DE UMA SUBLINHA na ``.vib-estado``, em pixels. É consequência do CSS
#: aprovado (``font-size:12px; line-height:1.5``), e a folga de 2 px é para o
#: arredondamento do motor — nunca para caber uma segunda sublinha, que custa 18.
UMA_SUBLINHA = 20


def test_a_regua_mede_o_miolo_da_janela_do_produto(medido):
    """O viewport MEDIDO tem de ser o que a página recebe. Não o que se digitou.

    Uma ``Gtk.OffscreenWindow`` **não tem HeaderBar**: pedir-lhe
    ``TAMANHO_NA_TELA`` dá à página os ``ALTURA_DA_BARRA`` px que a barra de
    título come na janela de verdade. Este caso é o que impede a régua de voltar
    a medir uma janela que não existe — e ele lê o viewport de dentro do motor,
    em vez de confiar no ``set_default_size``.
    """
    assert TAMANHO_OCULTA == (LARGURA_DO_DESENHO, ALTURA_DO_DESENHO), (
        "o dono mudou a conta do desenho e esta régua não foi junto: "
        f"TAMANHO_OCULTA={TAMANHO_OCULTA}")
    assert TAMANHO_NA_TELA[1] - ALTURA_DA_BARRA == ALTURA_DO_DESENHO, (
        "a janela na tela deixou de pedir o desenho MAIS a barra: "
        f"TAMANHO_NA_TELA={TAMANHO_NA_TELA} · ALTURA_DA_BARRA={ALTURA_DA_BARRA}")
    # O ALVO É `TAMANHO_OCULTA`, e NÃO a `JANELA` desta régua. Comparar a medida
    # com o que a própria régua pediu seria circular: trocar `JANELA` por
    # `TAMANHO_NA_TELA` passaria verde, que é o defeito de 02/09 intacto.
    assert medido["viewport"] == {"larg": TAMANHO_OCULTA[0], "alt": TAMANHO_OCULTA[1]}, (
        f"a página recebeu {medido['viewport']} e o miolo da janela do produto é "
        f"{TAMANHO_OCULTA}. Se a diferença na altura for {ALTURA_DA_BARRA} px, "
        "esta régua está pedindo `TAMANHO_NA_TELA` a uma `Gtk.OffscreenWindow`, "
        "que não tem HeaderBar — e mede uma janela que não existe")


def test_cada_frase_da_linha_cabe_numa_sublinha(medido):
    """Nenhuma das frases pode quebrar em duas — foi assim que o aviso sumiu.

    MEDIDO em 04/09/2026, no miolo real: a caixa da linha tem **1119 px** e a
    frase mais longa (163 caracteres) põe **957 px** de tinta — 162 px de folga.
    A frase de 211 caracteres de 02/09 enchia a caixa inteira e transbordava.

    NÚMEROS SUBSTITUÍDOS: esta docstring dizia *"a caixa de texto tem 1072 px …
    a de hoje ocupa 942, com 130 px de folga"*. Os 130 px eram a folga contra a
    caixa de **1087 px** que a janela errada (1180 de viewport) produzia; no
    produto a caixa é 32 px mais larga.
    """
    largas = [x for x in medido["linhas"] if x["alto"] > UMA_SUBLINHA]
    assert not largas, (
        "frase da linha de estado quebrando em mais de uma sublinha — a aba "
        "empurra e o fim do aviso sai da tela:\n" + "\n".join(
            f"  {x['alto']} px · {len(x['txt'])} caracteres · {x['txt']!r}"
            for x in largas))


def test_o_aviso_nao_e_cortado_pela_borda_do_miolo(medido):
    """A última linha tem de terminar DENTRO do miolo. Fotografado em 02/09.

    Antes: a segunda sublinha do alerta terminava em 740 e o miolo em 733 —
    sete pixels fora, com a barra de rolagem à direita.
    """
    fundo = medido["fundo_do_miolo"]
    fora = [x for x in medido["linhas"] if x["base"] > fundo]
    assert not fora, (
        f"linha da vibração cortada pela borda do miolo (fundo em {fundo} px), "
        "e é o aviso que a aba existe para dar:\n" + "\n".join(
            f"  termina em {x['base']} px · {x['txt']!r}" for x in fora))
