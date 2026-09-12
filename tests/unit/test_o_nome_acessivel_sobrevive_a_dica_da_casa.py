#!/usr/bin/env python3
"""F7 — o NOME ACESSÍVEL sobrevive à colheita da dica.

**11/09/2026, e esta régua nasce de uma dívida DECLARADA, não de uma queixa.**
A ``TOOLTIP-C1`` curou a dica que não abria do único jeito que funcionava: a
camada ``DICA_DA_CASA`` colhe todo ``title`` para ``data-hef-dica`` e **esvazia
o ``title`` no DOM vivo** — sem ele o popup do compositor não tem de que
nascer. A própria C1 escreveu o preço no mesmo dia:

    o ``title`` era também o **nome acessível** do elemento.

Esvaziado, um botão de ícone vira *«botão»* para quem usa leitor de tela. É a
mesma queixa dela — *«somem os textos»* — com outro nome e outra pessoa, e a
ordem dela de hoje é exatamente sobre essa outra pessoa:

    *"a ideia é que todas as features mesmo*  # noqa-acento: citação dela
    *do app funcionem nao so pra mim mas pra*  # noqa-acento: citação dela
    *qualquer outro user"*  # noqa-acento: citação dela

O QUE ESTA RÉGUA MEDE, E POR QUE NO DOM VIVO
--------------------------------------------
Nenhuma régua de fonte vê este defeito: no arquivo publicado o ``title`` está
lá, inteiro, nas treze páginas. O nome só some **depois** que a camada roda —
então a medição tem de ser a mesma que a pessoa recebe: a página carregada num
``WebKit2.WebView``, a camada aplicada, e a conta do HTML-AAM feita sobre o que
sobrou. É ``Gtk.OffscreenWindow`` porque ela tem UMA tela.

AS TRÊS MEDIDAS, e cada uma morde num lugar
-------------------------------------------
* **ninguém fica mudo** — todo elemento que aceita nome acessível e teve o
  ``title`` colhido tem nome por alguma via;
* **ninguém fala duas vezes** — um botão que já diz «Aplicar» dentro NÃO ganha
  ``aria-label``. Um nome redundante faz o leitor de tela ler duas vezes, e
  isso é pior do que não fazer nada;
* **A MORDIDA** — com as duas funções da cura neutralizadas, a página volta a
  ficar muda. Se esta última passar, a régua não mede a cura.

O NÚMERO DE PARTIDA, medido nas treze páginas publicadas em 11/09/2026, com a
camada da C1 de pé e sem a cura desta sprint:

====================================  =====
o que                                 quantos
====================================  =====
``title`` colhidos com texto            693
 … já tinham nome pelo conteúdo         357
 … já tinham ``aria-label`` da aba       31
 … são casca sem papel (span/div)       215
 … **ficavam MUDOS**                  **90**
``<title>`` de SVG esvaziados         1.930
 … **ficavam MUDOS**               **1.930**
**total sem nome**                **2.020**
====================================  =====

Os 90: 52 botões de ícone, 14 deslizantes, 12 campos de digitar, 12 listas.
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

#: ONDE A MORDIDA SE MEDE, e a escolha é pelo tamanho do sinal: a
#: ``04-iluminacao`` é a página com mais gente muda sem a cura — 44 elementos de
#: HTML e 304 ``<title>`` de desenho. Uma mordida num alvo magro passa por acaso.
PAGINA_DA_MORDIDA = "04-iluminacao.html"

#: O piso da mordida. Bem abaixo dos 348 medidos: o número exato é da página de
#: hoje, e esta régua não pode reprovar porque alguém acrescentou um botão.
MUDOS_SEM_A_CURA = 40

#: Quanto o laço do GTK pode demorar por página antes de a régua desistir.
MS_DE_GUARDA = 30000


#: O CENSO, e ele é a conta do HTML-AAM podada ao que existe nestas páginas.
#:
#: **A PODA QUE DECIDE:** ``texto_que_nomeia`` não é ``textContent``. Um
#: ``<title>`` de SVG está DENTRO do elemento e não é texto de tela — contá-lo
#: faria todo botão de ícone passar por botão com rótulo, que é justamente o
#: botão que perde o nome aqui. Sem esta poda a régua ficaria verde sobre 52
#: botões mudos.
#:
#: E ``aria-hidden="true"`` não é ausência de nome: é a declaração de que o
#: elemento está FORA da árvore de acessibilidade de propósito — o ícone
#: decorativo ao lado do texto que já o nomeia.
_JS_CENSO = r"""
(function(){
  var SVG = 'http://www.w3.org/2000/svg';
  function texto(no, d){
    if(!no || d > 12) return '';
    if(no.nodeType === 3) return no.nodeValue || '';
    if(no.nodeType !== 1) return '';
    if(no.namespaceURI === SVG
       && (no.localName === 'title' || no.localName === 'desc')) return '';
    if(no.getAttribute && no.getAttribute('aria-hidden') === 'true') return '';
    var s = '', f = no.firstChild;
    while(f){ s += texto(f, d + 1); f = f.nextSibling; }
    return s;
  }
  function porLabelledby(el){
    var v = String(el.getAttribute('aria-labelledby') || '').trim();
    if(!v) return false;
    var ids = v.split(/\s+/);
    for(var i = 0; i < ids.length; i++){
      var o = document.getElementById(ids[i]);
      if(o && texto(o, 0).trim()) return true;
    }
    return false;
  }
  function rotulado(el){
    if(el.id){
      var id = (window.CSS && CSS.escape) ? CSS.escape(el.id) : el.id;
      var l = document.querySelector('label[for="' + id + '"]');
      if(l && texto(l, 0).trim()) return true;
    }
    var p = el.parentElement, n = 0;
    while(p && n < 8){
      if(p.localName === 'label' && texto(p, 0).trim()) return true;
      p = p.parentElement; n += 1;
    }
    return false;
  }
  var NOMEAVEL = {a:1, button:1, input:1, select:1, textarea:1, summary:1,
    img:1, area:1, iframe:1, meter:1, progress:1, output:1, details:1,
    dialog:1, fieldset:1, optgroup:1, option:1, audio:1, video:1, th:1,
    table:1, svg:1};
  var DO_CONTEUDO = {a:1, button:1, summary:1, th:1, td:1, option:1,
    optgroup:1, legend:1};
  var PAPEL_DO_CONTEUDO = {button:1, link:1, tab:1, menuitem:1,
    menuitemcheckbox:1, menuitemradio:1, option:1, checkbox:1, radio:1,
    switch:1, heading:1, treeitem:1, gridcell:1, cell:1, columnheader:1,
    rowheader:1, tooltip:1};
  function nomeProprio(el){
    var tag = el.localName;
    var papel = String(el.getAttribute('role') || '').trim().toLowerCase();
    if(tag === 'img' || tag === 'area') return el.hasAttribute('alt');
    if(tag === 'input'){
      var t = String(el.getAttribute('type') || 'text').toLowerCase();
      if(t === 'button' || t === 'submit' || t === 'reset'){
        return !!String(el.getAttribute('value') || '').trim();
      }
      if(t === 'image') return !!String(el.getAttribute('alt') || '').trim();
      return rotulado(el);
    }
    if(tag === 'select' || tag === 'textarea' || tag === 'meter'
       || tag === 'progress') return rotulado(el);
    if(tag === 'option' && String(el.getAttribute('label') || '').trim()){
      return true;
    }
    if(papel ? PAPEL_DO_CONTEUDO[papel] : DO_CONTEUDO[tag]){
      return !!texto(el, 0).trim();
    }
    return false;
  }
  function aceitaNome(el){
    if(el.getAttribute('aria-hidden') === 'true') return false;
    var papel = String(el.getAttribute('role') || '').trim().toLowerCase();
    if(papel) return !(papel === 'presentation' || papel === 'none'
                       || papel === 'generic');
    return !!NOMEAVEL[el.localName];
  }

  var fora = {colhidos: 0, mudos: [], redundantes: [], escondidos: 0,
              desenhos: 0, desenhosMudos: [], papelImg: 0};
  var lista = document.querySelectorAll('[data-hef-dica]');
  for(var i = 0; i < lista.length; i++){
    var el = lista[i];
    var d = String(el.getAttribute('data-hef-dica') || '').trim();
    // O `<title>` DO DESENHO: quem tem de ter o nome é o DONO dele.
    if(el.namespaceURI === SVG && el.localName === 'title'){
      if(!d) continue;
      fora.desenhos += 1;
      var dono = el.parentElement;
      if(!dono) continue;
      if(dono.getAttribute('aria-hidden') === 'true'){
        fora.escondidos += 1;
        continue;
      }
      if(dono.localName === 'svg'
         && String(dono.getAttribute('role') || '') === 'img'){
        fora.papelImg += 1;
      }
      if(!String(dono.getAttribute('aria-label') || '').trim()
         && !porLabelledby(dono)){
        if(fora.desenhosMudos.length < 12){
          fora.desenhosMudos.push(dono.localName + ' :: ' + d.slice(0, 48));
        } else { fora.desenhosMudos.push(''); }
      }
      continue;
    }
    // O `data-hef-dica=""` é SILÊNCIO DECLARADO pela página, não nome perdido.
    if(!d) continue;
    fora.colhidos += 1;
    if(!aceitaNome(el)) continue;
    var rotulo = String(el.getAttribute('aria-label') || '').trim();
    var jaNomeia = nomeProprio(el);
    if(!rotulo && !porLabelledby(el) && !jaNomeia){
      if(fora.mudos.length < 12){
        fora.mudos.push(el.localName
          + (el.localName === 'input'
             ? '[' + String(el.getAttribute('type') || 'text') + ']' : '')
          + ' :: ' + d.slice(0, 48));
      } else { fora.mudos.push(''); }
    }
    // FALAR DUAS VEZES: um nome nosso por cima de um nome que já existia.
    if(rotulo && rotulo === d && jaNomeia){
      if(fora.redundantes.length < 12){
        fora.redundantes.push(el.localName + ' :: ' + d.slice(0, 48));
      } else { fora.redundantes.push(''); }
    }
  }
  return JSON.stringify(fora);
})()
"""


def _censo(pagina: pathlib.Path, camada: str) -> dict[str, Any]:
    """Carrega a página, aplica ``camada`` e conta quem ficou sem nome.

    ``Gtk.OffscreenWindow`` e não ``Gtk.Window``: sob Xvfb não há gerenciador de
    janelas e uma janela comum fica 1x1 para sempre — e offscreen também porque
    ela tem UMA tela, e janela de teste não nasce na frente dela (TELA-DELA-01).
    """
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:  # pragma: no cover — sem sessão gráfica
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    fora: dict[str, Any] = {"erro": "", "arquivo": pagina.name}
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(1400, 900)
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def responder(res: Any) -> str:
        return view.evaluate_javascript_finish(res).to_string()

    def leu(_v: Any, res: Any) -> None:
        try:
            fora.update(json.loads(responder(res)))
        except Exception as e:  # pragma: no cover
            fora["erro"] = f"o censo não respondeu: {e}"
        Gtk.main_quit()

    def instalou(_v: Any, res: Any) -> None:
        try:
            responder(res)
        except Exception as e:  # pragma: no cover
            fora["erro"] = f"a camada da dica não instalou: {e}"
            Gtk.main_quit()
            return
        view.evaluate_javascript(_JS_CENSO, -1, None, None, None, leu)

    def carregou(v: Any, evento: Any) -> None:
        if evento != WebKit2.LoadEvent.FINISHED:
            return
        v.evaluate_javascript(camada, -1, None, None, None, instalou)

    view.connect("load-changed", carregou)
    view.load_uri(pagina.as_uri())
    # O `timeout_add` PENDENTE DE OUTRO TESTE mata este laço com um `main_quit`
    # armado lá atrás — já custou onze medições nesta casa. A guarda própria sai
    # no `finally`.
    guarda = GLib.timeout_add(MS_DE_GUARDA, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
    return fora


def _paginas() -> list[pathlib.Path]:
    from hefesto_dualsense4unix.interface import onde
    return sorted(onde.paginas(publicado=True))


@pytest.fixture(scope="module")
def com_a_cura() -> list[dict[str, Any]]:
    """As treze páginas publicadas, com a camada como ela é hoje."""
    from hefesto_dualsense4unix.interface import hefesto_vivo
    return [_censo(p, hefesto_vivo.DICA_DA_CASA) for p in _paginas()]


@pytest.fixture(scope="module")
def sem_a_cura() -> dict[str, Any]:
    """A MORDIDA: as duas funções que vestem o nome saem de circulação.

    Não se apaga o bloco inteiro — as chamadas continuam lá, e é por isso que a
    mordida prova o CAMINHO e não só a existência do código: se um dia alguém
    tirar a chamada de dentro do ``colher()``, este teste continua vermelho
    quando devia, porque com as funções neutras o número tem de subir.
    """
    from hefesto_dualsense4unix.interface import hefesto_vivo

    inteira = hefesto_vivo.DICA_DA_CASA
    mordida = inteira
    for assinatura in ("function vestir_nome(el, t){",
                       "function vestir_nome_do_desenho(dono, t){"):
        assert mordida.count(assinatura) == 1, (
            f"a mordida não achou {assinatura!r} na camada — a cura mudou de "
            "forma e esta régua passou a medir outra coisa")
        mordida = mordida.replace(assinatura, assinatura + " return;")
    assert mordida != inteira
    return _censo(RAIZ / "src/hefesto_dualsense4unix/interface/paginas"
                  / PAGINA_DA_MORDIDA, mordida)


def test_a_colheita_aconteceu_nas_treze(com_a_cura: list[dict[str, Any]]) -> None:
    """Sem colheita não há o que medir — a régua ficaria verde por vacuidade."""
    for m in com_a_cura:
        assert not m["erro"], f"{m['arquivo']}: {m['erro']}"
    colhidos = sum(m["colhidos"] for m in com_a_cura)
    desenhos = sum(m["desenhos"] for m in com_a_cura)
    assert colhidos > 400 and desenhos > 1200, (
        f"a camada colheu de menos ({colhidos} atributos, {desenhos} desenhos) "
        "— ou as páginas mudaram de forma, ou a camada não rodou")


def test_ninguem_fica_mudo_no_html(com_a_cura: list[dict[str, Any]]) -> None:
    """Os 90 que a C1 emudeceu: 52 botões, 14 deslizantes, 12 campos, 12 listas."""
    mudos = {m["arquivo"]: [x for x in m["mudos"] if x]
             for m in com_a_cura if m["mudos"]}
    total = sum(len(m["mudos"]) for m in com_a_cura)
    assert total == 0, (
        f"{total} elementos perderam o nome acessível com a colheita da dica "
        f"— um leitor de tela anuncia *«botão»* e mais nada:\n"
        + json.dumps(mudos, ensure_ascii=False, indent=2))


def test_ninguem_fica_mudo_no_desenho(com_a_cura: list[dict[str, Any]]) -> None:
    """Os 1.930 ``<title>`` de SVG, que a camada esvazia para calar o popup."""
    mudos = {m["arquivo"]: [x for x in m["desenhosMudos"] if x]
             for m in com_a_cura if m["desenhosMudos"]}
    total = sum(len(m["desenhosMudos"]) for m in com_a_cura)
    assert total == 0, (
        f"{total} donos de `<title>` de SVG ficaram sem nome — o desenho "
        f"emudeceu junto com a dica:\n"
        + json.dumps(mudos, ensure_ascii=False, indent=2))


def test_ninguem_fala_duas_vezes(com_a_cura: list[dict[str, Any]]) -> None:
    """O botão que já diz «Aplicar» NÃO ganha um «Aplicar» por cima.

    É a metade negativa da regra, e sem ela a cura seria um ``aria-label`` em
    tudo — 357 elementos passariam a ser lidos duas vezes, que é pior do que o
    defeito que esta sprint fecha.
    """
    sobra = {m["arquivo"]: [x for x in m["redundantes"] if x]
             for m in com_a_cura if m["redundantes"]}
    total = sum(len(m["redundantes"]) for m in com_a_cura)
    assert total == 0, (
        f"{total} elementos ganharam um nome que já tinham — o leitor de tela "
        f"lê duas vezes:\n" + json.dumps(sobra, ensure_ascii=False, indent=2))


def test_o_icone_decorativo_sai_da_arvore(com_a_cura: list[dict[str, Any]]) -> None:
    """Medidos 63 dos 222 ``<svg>`` de ícone: o nome deles já está no texto ao lado.

    ``<svg><title>Cruz</title></svg>`` ao lado da palavra «Cruz» não precisa de
    nome nenhum — precisa sair da árvore, senão a frase vem dobrada.
    """
    escondidos = sum(m["escondidos"] for m in com_a_cura)
    assert escondidos > 0, (
        "nenhum ícone decorativo foi escondido — ou as páginas pararam de "
        "repetir o nome do ícone no texto ao lado, ou a regra do eco caiu")


def test_o_papel_img_so_no_icone(com_a_cura: list[dict[str, Any]]) -> None:
    """``role="img"`` torna a subárvore apresentacional — e isso tem preço.

    Num ``<svg>`` que é só um ícone o papel é a verdade. Num desenho com zonas
    ele **engoliria** os nomes de dentro: os 1.708 pedaços do DualSense
    virariam um nome só. Então o papel entra onde há um ``<title>`` e mais
    nada, e esta régua prende a conta: nenhum ``<svg>`` com ``role="img"``
    guarda zona nomeada dentro.
    """
    com_papel = sum(m["papelImg"] for m in com_a_cura)
    assert com_papel > 0, "nenhum ícone ganhou `role=img` — a regra caiu"
    # Um `<svg role=img>` só é contado uma vez por `<title>`; se um desenho com
    # zonas tivesse ganho o papel, o mesmo `<svg>` apareceria dezenas de vezes.
    desenhos = sum(m["desenhos"] for m in com_a_cura)
    assert com_papel < desenhos, (
        f"{com_papel} de {desenhos} `<title>` estão sob um `role=img` — um "
        "desenho com zonas ganhou o papel e engoliu os nomes de dentro")


def test_a_mordida_sem_a_cura_a_pagina_emudece(sem_a_cura: dict[str, Any]) -> None:
    """A MORDIDA. Com as duas funções neutras, volta o defeito que a C1 deixou.

    Se este teste passar, a régua acima não mede a cura — mede outra coisa, que
    é a família de defeito que esta casa nomeou em 04/09/2026.
    """
    m = sem_a_cura
    assert not m["erro"], m["erro"]
    mudos = len(m["mudos"]) + len(m["desenhosMudos"])
    assert mudos >= MUDOS_SEM_A_CURA, (
        f"sem a cura a {PAGINA_DA_MORDIDA} deveria ficar muda e ficaram só "
        f"{mudos} elementos sem nome — a mordida não morde, e a régua verde "
        "acima não prova nada")
    assert m["escondidos"] == 0, (
        "sem a cura nenhum ícone deveria estar escondido — a mordida está "
        "medindo uma página que já vinha vestida")


# ---------------------------------------------------------------------------
# O NOME QUE TROCA DE TEXTO — e ele não precisa de ponteiro nem de página real.
#
# O alvo `atributo` do piloto escreve `title` em 66 endereços das dez abas (9
# deles em `<button>`), e a camada desvia esse texto para `data-hef-dica`. Se o
# nome acessível não for junto, quem usa leitor de tela fica com a frase do
# instante em que a página carregou — que é o mesmo defeito da dica congelada
# que a C1 curou do lado de quem vê.
# ---------------------------------------------------------------------------

#: OS QUATRO CASOS, e o primeiro é a forma exata dos 52 botões que emudeceram:
#: um ``<button>`` cujo único conteúdo é um desenho. O ``<title>`` do desenho
#: está DENTRO do botão e some no ``textContent`` de quem não o podar — é por
#: ele que uma régua ingênua daria verde sobre um botão mudo.
_PAGINA_DE_ENSAIO = """<!doctype html><html><body>
<button id="mudo" title="Ignora este conselho"><svg width="8" height="8">
  <title>Proibido</title><path d="M0 0h4v4H0z"/></svg></button>
<button id="falante" title="Aplica o perfil">Aplicar</button>
<button id="dono" aria-label="O nome da aba" title="Uma dica qualquer"><svg
  width="8" height="8"><title>Proibido</title><path d="M0 0h4v4H0z"/></svg></button>
<svg id="icone" width="16" height="16"><title>Cruz</title><path d="M0 0h4v4H0z"/></svg>
</body></html>"""

_JS_ENSAIO = r"""
(function(){
  function ler(id){
    var el = document.getElementById(id);
    return {rotulo: el.getAttribute('aria-label'),
            dica: el.getAttribute('data-hef-dica'),
            title: el.getAttribute('title')};
  }
  var fora = {depois_da_colheita: {}, depois_da_troca: {}, depois_do_vazio: {}};
  ['mudo', 'falante', 'dono', 'icone'].forEach(function(id){
    fora.depois_da_colheita[id] = ler(id);
  });
  window.__hefDica.trocar(document.getElementById('mudo'), 'Ignora ESTE conselho');
  window.__hefDica.trocar(document.getElementById('dono'), 'Outra dica');
  ['mudo', 'dono'].forEach(function(id){ fora.depois_da_troca[id] = ler(id); });
  window.__hefDica.trocar(document.getElementById('mudo'), '');
  fora.depois_do_vazio.mudo = ler('mudo');
  return JSON.stringify(fora);
})()
"""


@pytest.fixture(scope="module")
def ensaio() -> dict[str, Any]:
    """Uma página de quatro casos, com a camada de pé e o texto trocando."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:  # pragma: no cover
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    from hefesto_dualsense4unix.interface import hefesto_vivo

    fora: dict[str, Any] = {"erro": ""}
    janela = Gtk.OffscreenWindow()
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def leu(_v: Any, res: Any) -> None:
        try:
            fora.update(json.loads(view.evaluate_javascript_finish(res).to_string()))
        except Exception as e:  # pragma: no cover
            fora["erro"] = f"o ensaio não respondeu: {e}"
        Gtk.main_quit()

    def instalou(_v: Any, res: Any) -> None:
        try:
            view.evaluate_javascript_finish(res)
        except Exception as e:  # pragma: no cover
            fora["erro"] = f"a camada não instalou: {e}"
            Gtk.main_quit()
            return
        view.evaluate_javascript(_JS_ENSAIO, -1, None, None, None, leu)

    def carregou(v: Any, evento: Any) -> None:
        if evento != WebKit2.LoadEvent.FINISHED:
            return
        v.evaluate_javascript(hefesto_vivo.DICA_DA_CASA, -1, None, None, None,
                              instalou)

    view.connect("load-changed", carregou)
    view.load_html(_PAGINA_DE_ENSAIO, "about:blank")
    guarda = GLib.timeout_add(MS_DE_GUARDA, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
    return fora


def test_o_botao_de_icone_ganha_o_nome(ensaio: dict[str, Any]) -> None:
    """O caso dos 52: um botão sem texto próprio fica com o texto da dica."""
    assert not ensaio["erro"], ensaio["erro"]
    m = ensaio["depois_da_colheita"]["mudo"]
    assert m["title"] is None, "a colheita não tirou o `title` — o popup volta"
    assert m["rotulo"] == "Ignora este conselho", (
        f"o botão de ícone continuou mudo: {m}")


def test_o_botao_com_texto_nao_ganha_nada(ensaio: dict[str, Any]) -> None:
    """O caso dos 357: quem já diz «Aplicar» dentro não ganha nome por cima."""
    assert not ensaio["erro"], ensaio["erro"]
    m = ensaio["depois_da_colheita"]["falante"]
    assert m["rotulo"] is None, (
        f"o botão «Aplicar» ganhou um nome que já tinha — lido duas vezes: {m}")
    assert m["dica"] == "Aplica o perfil", (
        "a dica do botão com texto se perdeu na colheita")


def test_o_icone_de_svg_ganha_nome_e_papel(ensaio: dict[str, Any]) -> None:
    """O caso dos 222: um ``<svg>`` de ícone sem zonas vira ``role="img"``."""
    assert not ensaio["erro"], ensaio["erro"]
    m = ensaio["depois_da_colheita"]["icone"]
    assert m["rotulo"] == "Cruz", f"o ícone do desenho ficou sem nome: {m}"


def test_o_nome_segue_a_dica_que_o_tique_troca(ensaio: dict[str, Any]) -> None:
    """66 endereços trocam de `title` em voo; o nome tem de ir junto.

    Quem chama ``trocar()`` no produto é o ramo ``title`` do ``escrever()``,
    que ANTES já gravou o texto novo em ``data-hef-dica`` — por isso a régua
    mede o ``aria-label`` e não a dica: aqui a chamada é direta, e o
    ``data-hef-dica`` continua sendo o da carga da página de propósito.
    """
    assert not ensaio["erro"], ensaio["erro"]
    m = ensaio["depois_da_troca"]["mudo"]
    assert m["rotulo"] == "Ignora ESTE conselho", (
        f"o nome congelou no texto da carga da página: {m}")


def test_a_dica_que_some_leva_o_nome_junto(ensaio: dict[str, Any]) -> None:
    """Dica vazia é dica que não existe — e um nome vazio seria pior que nenhum."""
    assert not ensaio["erro"], ensaio["erro"]
    m = ensaio["depois_do_vazio"]["mudo"]
    assert m["rotulo"] is None, f"sobrou um nome sem dica: {m}"


def test_o_nome_que_a_aba_escreveu_manda_mais(ensaio: dict[str, Any]) -> None:
    """A posse é declarada: mexer só no que a camada vestiu.

    Um ``aria-label`` que o gerador da aba escreveu é decisão de quem desenhou a
    tela. A camada não o toca nem na colheita nem na troca — e sem esta guarda
    a dívida da C1 se pagaria estragando os 31 nomes que já existiam.
    """
    assert not ensaio["erro"], ensaio["erro"]
    antes = ensaio["depois_da_colheita"]["dono"]
    depois = ensaio["depois_da_troca"]["dono"]
    assert antes["rotulo"] == "O nome da aba", f"a colheita mexeu no alheio: {antes}"
    assert depois["rotulo"] == "O nome da aba", (
        f"a troca da dica sobrescreveu o nome que a aba escreveu: {depois}")
