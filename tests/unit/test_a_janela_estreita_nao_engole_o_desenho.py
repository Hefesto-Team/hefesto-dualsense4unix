#!/usr/bin/env python3
"""A JANELA ESTREITA NÃO ENGOLE O DESENHO — as dez abas, medidas fora do tamanho.

**ESTE ARQUIVO NASCEU DE UMA FOTO.** Em 04/09/2026 ela mandou o retrato da
janela com ~940 px de largura e a frase *"tela do layout quebra direto"*. O
desenho pede **1212x809** (`gui/ponte_da_tela.LARGURA_DO_DESENHO` e
`ALTURA_DO_DESENHO`); a janela dela estava 272 px mais estreita.

**E RÉGUA NENHUMA DESTA CASA MEDIA ISSO** — conferido em 04/09/2026, uma a uma.
Todas as que olham geometria abrem um Chrome MAIOR que o desenho, onde a
`.janela` nasce no tamanho natural e nada aperta:

===============================  ==========  =======================
régua                            a janela    onde está o número
===============================  ==========  =======================
`interface/regua.py`             1260x2600   linha 320 (`--window-size`)
`interface/regua_estados.py`     1920x1080   linha 106
`interface/regua_popup.py`       1920x1080   linha 353
`interface/olhar.py`             1920x1080   linha 28 (`LARG, ALT`)
===============================  ==========  =======================

A mais apertada delas ainda é 48 px mais larga que o desenho. O que ninguém
mediu é o que ela usa: a janela **arrastada**.

E ela PODE ser arrastada até lá. O comentário de `gui/ponte_da_tela.py:158-162`
promete um piso — *"por isso a janela também ganhou um MÍNIMO (o
`set_size_request` lá embaixo), sem o qual ela pode ser arrastada até engolir o
desenho em silêncio"* — e **não existe `set_size_request` nenhum no arquivo**
(medido com `grep` em 04/09/2026: a única ocorrência é a do próprio comentário).
Enquanto não existir, o tamanho da janela é o que ela decidir com o rato, e o
único lugar onde o produto se defende é o CSS.

A REGRA QUE ESTA RÉGUA COBRA
----------------------------
**Numa janela menor que o desenho, o produto pode ROLAR e pode ENCOLHER. Não
pode SUMIR.** Em três artigos, e cada um é um teste:

1. **No seu próprio tamanho o desenho cabe inteiro** — nem uma reticência. É a
   linha de base: sem ela, uma régua que só olha janela apertada não distingue
   "quebrou ao encolher" de "já estava quebrado".
2. **O que não couber tem de continuar ALCANÇÁVEL.** Um pedaço cortado por um
   ancestral que recorta sem rolar (`overflow:hidden|clip`) só passa se o corte
   tiver AFORDÂNCIA: reticências (`text-overflow:ellipsis`) **com o texto
   inteiro guardado num `title`/`aria-label`**. Sem isso é informação que quem
   olha não tem como ler nem alcançar — é o *sumiço*.

   Essa não é uma regra inventada aqui: é a que a própria aba Sistema escreveu
   em `interface/aba09.py:389-392` — *"as reticências são o que sobra quando ele
   encolhe até o limite — e o `title` do valor guarda a frase inteira, para não
   perder informação no corte"*. Esta régua só a cobra das dez abas.
3. **A janela inteira continua alcançável.** As três faixas (`.tira`, `.miolo`,
   `.rodape`) cabem dentro da `.janela` — que tem `overflow:hidden` e por isso
   não rola nada —, e o que ficar fora da tela tem de ser alcançável rolando o
   documento. Rolar é aceitável; recortar sem barra não é.
4. **O campo de escolha continua dizendo o que foi escolhido.** Um `<option>`
   mede **0x0** no DOM — quem pinta a escolha é o controle de formulário —, e
   por isso os três artigos acima passam por cima dele. Este mede a largura que
   o texto escolhido PRECISA, num espelho com a fonte computada do `<select>`,
   contra a caixa de conteúdo dele.

   Aqui a exigência é mais branda de propósito: quem clica num `<select>` abre o
   menu nativo e lê a lista inteira, então o valor não se perde — fica ilegível
   **de relance**, no campo que existe para dizê-lo. A cura é a mesma linha de
   sempre: o `title` carregar a opção escolhida.

O QUE ELA MEDE, E POR QUE PELO DOM
----------------------------------
Pelo DOM porque a pergunta é geométrica: *quem está fora da caixa de quem*. Para
cada peça que carrega TEXTO PRÓPRIO dentro da `.janela`, a medida é dupla:

* **corte próprio** — a peça recorta a si mesma (`overflow:hidden` e
  `scrollWidth > clientWidth`); é o caso das reticências;
* **corte do ancestral** — a peça passa da caixa de cliente do primeiro
  ancestral que recorta. A subida PARA no primeiro ancestral que rola
  (`auto`/`scroll`): o que rola está alcançável, e não é sumiço.

**Só peças com texto próprio.** Sem esse filtro a régua acusaria o
`.luz-grade .moldura` da aba Iluminação, que tem `overflow:hidden` **de
propósito** para conter o SVG (`interface/aba04.py:533-534`) e come 9 px do
desenho **no tamanho certo também** — não é regressão de janela estreita, é
decisão tomada.

OS TAMANHOS, e cada um tem razão escrita em :data:`TAMANHOS`. A altura e a
largura são independentes, e isso foi MEDIDO: a `.janela` tem altura FIXA
(`--alt-janela:777px`, `interface/topo.html:592`), então encurtar a janela não
muda um pixel do miolo — o documento passa a rolar 209 px e o rodapé continua
inteiro. Quem aperta é a LARGURA, pelo `max-width:100%` da `.janela`.

AS DUAS MORDIDAS
----------------
* **o tamanho** — a mesma aba, a mesma régua, só a janela muda:
  `06-navegacao` no tamanho do desenho não corta nada; a 940 px corta quatro
  peças. É `test_no_tamanho_do_desenho_nada_e_cortado` verde ao lado de
  `test_nada_some_sem_afordancia` vermelho, e a diferença entre os dois é a
  largura da janela;
* **a afordância** — arranque o `title=` de `.est .val` na aba Sistema e as
  quatro peças que hoje passam pelo artigo 2 caem para o lado dos engolidos.
  Provado em 04/09/2026 numa cópia da bancada, e escrito em
  :func:`test_a_mordida_da_afordancia_sem_o_title_o_corte_vira_sumico`.

O QUE ELA **NÃO** MEDE: nada de pixel (a cor errada passa), nada de `:hover`,
e nada de widget GTK — a barra de título, os diálogos e o próprio piso da janela
ficam fora do WebView. E ela mede a **BANCADA** (`mockup/`), que é onde a cura
chega primeiro: apontá-la para o publicado a deixaria vermelha depois da cura,
até alguém rodar o `--publicar`. Hoje as duas cópias são byte a byte iguais.

**E ELA DECLARA A LETRA.** As dez abas pedem `Space Grotesk` e `JetBrains Mono`
ao Google Fonts, e sem rede o motor cai na pilha do sistema: a largura de todo
texto muda e um vermelho daqui passaria a significar outra coisa. Por isso toda
reprovação sai com o estado das duas fontes (:func:`_a_letra`) — *medir contra a
biblioteca errada produz alarme convincente e falso* é a armadilha nº 1 da casa.

CUSTO: cinco segundos para as trinta medidas — UMA janela por tamanho, navegando
pelas dez abas. Abrir uma janela por medida custaria 38 s, e foi assim que este
arquivo começou.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
from typing import Any, NamedTuple

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("JANELA-ESTREITA-01 — as dez abas fora do tamanho do desenho")

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))

if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
    pytest.skip(
        "JANELA-ESTREITA-01: sem servidor gráfico. `Gtk.OffscreenWindow` ainda "
        "precisa de um GDK display — sem ele não há WebView para medir.",
        allow_module_level=True,
    )

try:
    from hefesto_dualsense4unix.gui.ponte_da_tela import (
        ALTURA_DO_DESENHO,
        FOLHA_DA_CASA,
        LARGURA_DO_DESENHO,
    )
    from hefesto_dualsense4unix.interface import onde
except (ImportError, ValueError) as _erro:  # pragma: no cover — ambiente sem WebKit
    pytest.skip(
        f"JANELA-ESTREITA-01: a biblioteca da janela não importou ({_erro}). "
        "Falta gir1.2-webkit2-4.1?",
        allow_module_level=True,
    )

try:
    import regua_de_tela
except (ImportError, ValueError) as _erro:  # pragma: no cover — ambiente sem WebKit
    pytest.skip(
        f"JANELA-ESTREITA-01: a régua de tela não importou ({_erro}).",
        allow_module_level=True,
    )


class Tamanho(NamedTuple):
    """Uma janela para medir, com a razão de ela estar na lista."""

    rotulo: str
    largura: int
    altura: int
    razao: str


#: OS TRÊS TAMANHOS. O primeiro é a linha de base e os outros dois são as duas
#: formas de a janela ficar menor que o desenho — uma por eixo, porque os eixos
#: são independentes (a `.janela` tem altura fixa; só a largura a aperta).
TAMANHOS: tuple[Tamanho, ...] = (
    Tamanho(
        "desenho",
        LARGURA_DO_DESENHO,
        ALTURA_DO_DESENHO,
        "o miolo da janela do produto — `TAMANHO_NA_TELA` menos a `HeaderBar`. "
        "Aqui nada pode ser cortado: é o tamanho para o qual o desenho foi feito",
    ),
    Tamanho(
        "estreita",
        940,
        ALTURA_DO_DESENHO,
        "a largura da FOTO DELA de 04/09/2026 — 272 px a menos que o desenho. "
        "É a janela em que ela escreveu 'tela do layout quebra direto'",
    ),
    Tamanho(
        "baixa",
        LARGURA_DO_DESENHO,
        600,
        "209 px mais baixa que o desenho. O produto tem de ROLAR o documento e "
        "manter o rodapé inteiro — encurtar não pode comer a barra que decide",
    ),
)

#: AS DEZ ABAS, da bancada. A leitura é do disco e não de uma lista digitada:
#: uma aba nova entra na régua sozinha, que é o contrário do defeito de 03/09
#: (*as pastas mudaram de nome e as réguas não foram junto*).
ABAS: tuple[str, ...] = tuple(
    p.name for p in sorted(onde.BANCADA.glob("[0-9][0-9]-*.html"))
)

if len(ABAS) < 10:
    pytest.skip(
        f"JANELA-ESTREITA-01: achei {len(ABAS)} aba(s) em {onde.BANCADA} e o "
        "produto tem DEZ. Medir menos que isso seria verde por vacuidade.",
        allow_module_level=True,
    )

#: A FOLHA DE USUÁRIO DO PRODUTO, posta à mão. `ponte_da_tela` a injeta pela
#: `UserContentManager` e a `regua_de_tela` monta a dela sem folha nenhuma — sem
#: isto a régua mediria as legendas `.nota` do mockup, que o produto esconde, e
#: concluiria que o documento rola quando ele não rola.
POR_A_FOLHA = (
    "(function(){var s=document.createElement('style');"
    f"s.textContent={json.dumps(FOLHA_DA_CASA)};"
    "document.head.appendChild(s);return 'FOLHA-POSTA';})()"
)

#: A MEDIDA, em pixels de viewport. Devolve as três faixas, o quanto o documento
#: rola em cada eixo, e a lista de peças CORTADAS — cada uma com o retrato de
#: quem a corta, para o Python decidir se o corte tem afordância.
MEDIDA = r"""
(function(){
  var TOL = 1;
  function txt(s){ return (s||'').replace(/\s+/g,' ').trim(); }
  function soMeuTexto(el){
    var s = '';
    for (var n = el.firstChild; n; n = n.nextSibling)
      if (n.nodeType === 3) s += n.nodeValue;
    return txt(s);
  }
  // O `title` QUE O MOUSE ALCANÇA, e não só o do próprio elemento: o
  // navegador sobe a árvore para achar o tooltip, e um `title` no pai atende o
  // filho recortado. Medido em 06/09/2026 — a linha do giroscópio da aba 02 põe
  // a frase no `<span class="no-jogo">` de fora (é lá que mora o alvo
  // `atributo` do piloto) e recorta no `.no-jogo-t` de dentro; lendo só o
  // próprio elemento, a régua acusava sumiço sobre uma frase que o hover
  // devolve. A subida para no `.janela`: acima dela é a página, não o desenho.
  function tituloAlcancavel(el){
    for (var p = el; p; p = p.parentElement){
      var v = p.getAttribute('title');
      if (v) return v;
      if (p.classList && p.classList.contains('janela')) return null;
    }
    return null;
  }
  function retrato(el){
    var e = getComputedStyle(el);
    return {tag: el.tagName.toLowerCase(),
            cls: (el.getAttribute('class')||'').slice(0,48),
            id: el.id || '',
            titulo: tituloAlcancavel(el),
            rotulo: el.getAttribute('aria-label'),
            reticencias: e.textOverflow,
            texto: txt(el.textContent).slice(0,90)};
  }
  // O primeiro ancestral que RECORTA. A subida para no primeiro que ROLA: o que
  // rola está alcançável, e alcançável não é sumiço.
  function recortador(el, eixo){
    for (var p = el.parentElement; p; p = p.parentElement){
      var s = getComputedStyle(p);
      var v = (eixo === 'x') ? s.overflowX : s.overflowY;
      if (v === 'auto' || v === 'scroll') return null;
      if (v === 'hidden' || v === 'clip') return p;
      if (p === document.body) return null;
    }
    return null;
  }
  var j = document.querySelector('.janela');
  if (!j) return JSON.stringify({erro: 'a página não tem .janela'});

  // O <select> NÃO TEM GEOMETRIA DE DOM PARA A OPÇÃO ESCOLHIDA: o <option> mede
  // 0x0 e quem pinta o texto é o controle de formulário. Nenhuma conta de caixa
  // o alcança — por isso aqui a largura do texto é medida num ESPELHO com a
  // fonte computada do próprio <select>, e comparada com a caixa de conteúdo.
  var espelho = document.createElement('span');
  espelho.style.cssText =
    'position:absolute;visibility:hidden;white-space:pre;left:-9999px;top:0';
  document.body.appendChild(espelho);
  var selects = j.querySelectorAll('select');
  var apertados = [], selects_vistos = 0;
  for (var k = 0; k < selects.length; k++){
    var sel = selects[k];
    var es = getComputedStyle(sel);
    if (es.display === 'none' || es.visibility === 'hidden') continue;
    if (sel.getBoundingClientRect().width === 0) continue;
    selects_vistos++;
    var op = sel.options[sel.selectedIndex >= 0 ? sel.selectedIndex : 0];
    if (!op) continue;
    var escolhido = txt(op.textContent);
    espelho.style.font = es.font;
    espelho.style.letterSpacing = es.letterSpacing;
    espelho.textContent = escolhido;
    var precisa = espelho.getBoundingClientRect().width;
    var cabe = sel.clientWidth - parseFloat(es.paddingLeft) - parseFloat(es.paddingRight);
    if (precisa > cabe + TOL)
      apertados.push({texto: escolhido, precisa: Math.round(precisa),
                      cabe: Math.round(cabe), sobra: Math.round(precisa - cabe),
                      titulo: sel.getAttribute('title'),
                      rotulo: sel.getAttribute('aria-label'),
                      campo: sel.getAttribute('data-campo') || '',
                      cls: (sel.getAttribute('class')||'').slice(0,48)});
  }
  espelho.remove();

  var cortados = [];
  var todos = [j].concat(Array.prototype.slice.call(j.querySelectorAll('*')));
  for (var i = 0; i < todos.length; i++){
    var el = todos[i];
    if (el.closest('svg')) continue;
    var s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden') continue;
    if (!soMeuTexto(el)) continue;          // só o que se LÊ; o SVG tem dono e regra próprios
    var b = el.getBoundingClientRect();
    if (b.width === 0 && b.height === 0) continue;
    ['x','y'].forEach(function(eixo){
      var v = (eixo === 'x') ? s.overflowX : s.overflowY;
      var sobra = (eixo === 'x') ? (el.scrollWidth - el.clientWidth)
                                 : (el.scrollHeight - el.clientHeight);
      if ((v === 'hidden' || v === 'clip') && sobra > TOL){
        cortados.push({tipo:'ele-mesmo', eixo:eixo, sobra:sobra,
                       peca:retrato(el), corta:retrato(el)});
        return;
      }
      var p = recortador(el, eixo);
      if (!p) return;
      var pb = p.getBoundingClientRect();
      var ini = (eixo === 'x') ? (pb.left + p.clientLeft) : (pb.top + p.clientTop);
      var fim = ini + ((eixo === 'x') ? p.clientWidth : p.clientHeight);
      var a = (eixo === 'x') ? b.left : b.top;
      var z = (eixo === 'x') ? b.right : b.bottom;
      if (z > fim + TOL || a < ini - TOL)
        cortados.push({tipo:'ancestral', eixo:eixo,
                       sobra: Math.round(Math.max(z - fim, ini - a)),
                       peca:retrato(el), corta:retrato(p)});
    });
  }
  function cx(el){
    var b = el.getBoundingClientRect();
    return {esq:Math.round(b.left), topo:Math.round(b.top),
            dir:Math.round(b.right), base:Math.round(b.bottom),
            larg:Math.round(b.width), alt:Math.round(b.height)};
  }
  var de = document.documentElement;
  var nota = document.querySelector('.nota');
  var faixas = {};
  ['tira','miolo','rodape'].forEach(function(nome){
    var el = j.querySelector(':scope > .' + nome);
    faixas[nome] = el ? cx(el) : null;
  });
  return JSON.stringify({
    viewport: {larg: de.clientWidth, alt: de.clientHeight},
    documento: {rola_x: de.scrollWidth - de.clientWidth,
                rola_y: de.scrollHeight - de.clientHeight},
    // A LETRA VAI JUNTO DA MEDIDA. As dez abas pedem 'Space Grotesk' e
    // 'JetBrains Mono' ao Google Fonts (`<link>` no topo de cada página): sem
    // rede o motor cai na pilha de sistema, a largura de todo texto muda, e um
    // vermelho desta régua passaria a significar outra coisa.
    letra: (typeof document.fonts === 'undefined') ? null : {
      estado: document.fonts.status,
      texto: document.fonts.check('12px "Space Grotesk"'),
      mono: document.fonts.check('12px "JetBrains Mono"')
    },
    folha_posta: nota ? getComputedStyle(nota).display === 'none' : null,
    janela: Object.assign(cx(j), {ox: getComputedStyle(j).overflowX,
                                  oy: getComputedStyle(j).overflowY}),
    faixas: faixas,
    cortados: cortados,
    n_selects: selects_vistos,
    selects_apertados: apertados
  });
})()
"""


def tem_afordancia(corte: dict[str, Any]) -> bool:
    """O corte é aceitável? Reticências **e** o texto inteiro guardado.

    Reticências sozinhas dizem "tem mais" e não dizem O QUÊ — quem olha vê
    ``"P2 • Starlight Bl…"`` e não tem como chegar ao nome. O `title` é o que
    devolve a frase, e é a cura que a própria aba Sistema já aplicou ao
    ``.est .val`` (``interface/aba09.py:389-394``).

    Vale só no eixo X: ``text-overflow`` é horizontal, e não existe reticência
    que salve um corte por baixo.
    """
    if corte["eixo"] != "x":
        return False
    peca, corta = corte["peca"], corte["corta"]
    if not any(str(x.get("reticencias") or "").startswith("ellipsis")
               for x in (peca, corta)):
        return False
    inteiro = peca["texto"]
    if not inteiro:
        return False
    return any(
        inteiro in (x.get(chave) or "").strip()
        for x in (peca, corta)
        for chave in ("titulo", "rotulo")
    )


def engolidos(leitura: dict[str, Any]) -> list[dict[str, Any]]:
    """As peças cortadas SEM afordância — o que some da tela sem aviso."""
    return [c for c in leitura["cortados"] if not tem_afordancia(c)]


def selects_mudos(leitura: dict[str, Any]) -> list[dict[str, Any]]:
    """Os ``<select>`` cuja opção escolhida não cabe e não está guardada.

    O ``<select>`` tem UMA recuperação que o ``<span>`` não tem: quem clica abre
    o menu nativo e lê a lista inteira. Por isso o defeito aqui não é *perder* o
    valor — é o valor escolhido ficar ilegível **de relance**, no campo que
    existe para dizê-lo. A cura é a mesma linha: o `title` do campo carregar a
    opção escolhida, e não só o nome do campo.

    E é preciso o texto DA OPÇÃO: a aba Gatilhos tem `title="Efeito pronto do
    gatilho esquerdo"` num campo que mostra ``"Recuo do MK — pesado no fim"``.
    O `title` existe e não devolve nada do que foi cortado.
    """
    return [
        s for s in leitura["selects_apertados"]
        if not any(s["texto"] in (s.get(chave) or "").strip()
                   for chave in ("titulo", "rotulo"))
    ]


def _a_letra(leitura: dict[str, Any]) -> str:
    """A letra com que esta medida foi feita, para toda reprovação declarar.

    *Medir contra a biblioteca errada produz alarme convincente e falso* é a
    armadilha nº 1 desta casa. Aqui a "biblioteca" é a FONTE: sem rede as duas
    do Google Fonts não chegam, o motor cai na pilha do sistema e a largura de
    todo texto muda.
    """
    letra = leitura.get("letra")
    if not letra:
        return " · a letra desta medida: o motor não respondeu (`document.fonts`)"
    return (f" · a letra desta medida: Space Grotesk={letra['texto']} "
            f"JetBrains Mono={letra['mono']} ({letra['estado']})")


def _contar_selects(apertados: list[dict[str, Any]]) -> str:
    """O relatório dos campos de escolha: o valor, o que falta, e o `title`."""
    return "\n".join(
        f"  +{s['sobra']} px (precisa {s['precisa']}, cabe {s['cabe']}) · "
        f"campo={s['campo'] or s['cls']!r} · escolhido={s['texto']!r} · "
        f"title={s['titulo']!r}"
        for s in apertados
    )


def _contar(cortes: list[dict[str, Any]]) -> str:
    """O relatório de uma reprovação: peça, quanto sumiu, e quem cortou."""
    return "\n".join(
        f"  {c['eixo']} +{c['sobra']} px · {c['tipo']} · "
        f"<{c['peca']['tag']} class={c['peca']['cls']!r}> "
        f"texto={c['peca']['texto'][:56]!r} title={c['peca']['titulo']!r} "
        f"— recortado por <{c['corta']['tag']} class={c['corta']['cls']!r}> "
        f"(text-overflow={c['corta']['reticencias']!r})"
        for c in cortes
    )


def medir(tamanho: Tamanho, abas: tuple[str, ...] = ABAS,
          pasta: pathlib.Path | None = None) -> dict[str, dict[str, Any]]:
    """Abre UMA janela do tamanho pedido e navega pelas abas, medindo cada uma.

    Uma janela por medida custaria 38 s para as trinta; assim custa 4,5 s. O
    preço é ter de esperar a navegação COM AS PRÓPRIAS MÃOS: o ajudante
    ``window.__REGUA`` não sobrevive a `load_uri`, e ``Tela.esperar_ate`` com
    uma pergunta em texto passa por ele.

    E o `titulo_esperado` não é enfeite. MEDIDO em 04/09/2026: sem ele, a
    PRIMEIRA `Tela` de um processo confirma a carga contra `about:blank` —
    `readyState` já é `complete` ali — e a régua mede uma página em branco.
    """
    pasta = pasta or onde.BANCADA
    fora: dict[str, dict[str, Any]] = {}
    with regua_de_tela.Tela(pasta / abas[0], titulo_esperado="Hefesto",
                            largura=tamanho.largura, altura=tamanho.altura) as tela:
        for nome in abas:
            if nome != abas[0]:
                tela.view.load_uri((pasta / nome).as_uri())

            def chegou(nome: str = nome) -> bool:
                try:
                    estado = tela._cru(
                        "[document.readyState, location.href,"
                        " !!document.querySelector('.janela')]")
                except regua_de_tela.ErroDeRegua:
                    return False
                return bool(estado[0] == "complete"
                            and str(estado[1]).endswith(nome)
                            and estado[2])

            tela.esperar_ate(chegou, prazo=15,
                             motivo=f"{nome} não terminou de carregar")
            tela.executar(POR_A_FOLHA)
            lido = json.loads(tela._cru(MEDIDA.strip()))
            assert "erro" not in lido, f"{nome} em {tamanho.rotulo}: {lido['erro']}"
            fora[nome] = lido
    return fora


@pytest.fixture(scope="module")
def medido() -> dict[tuple[str, str], dict[str, Any]]:
    """As trinta medidas — as dez abas nos três tamanhos, medidas uma vez só."""
    fora: dict[tuple[str, str], dict[str, Any]] = {}
    for tamanho in TAMANHOS:
        for nome, leitura in medir(tamanho).items():
            fora[(nome, tamanho.rotulo)] = leitura
    return fora


#: O QUE JÁ ESTÁ QUEBRADO, com a cura escrita. **Não é isenção** — é o registro
#: datado de um defeito que esta régua achou e que não é de quem a escreveu
#: consertar (ONDA-J, 04/09/2026: os geradores têm outro dono nesta leva).
#:
#: São `xfail(strict=True)`: no dia em que a cura entrar, o caso passa, o
#: `strict` reprova o XPASS, e quem curar é obrigado a apagar a linha daqui. Uma
#: marca que sobrevive à cura é a mentira seguinte.
ESPERADO_VERMELHO: dict[tuple[str, str], str] = {
    ("06-navegacao.html", "estreita"): (
        "DEFEITO VIVO — `.nav-rot` (interface/aba06.py:285-286) tem "
        "`text-overflow:ellipsis` e NENHUM `title`. A 940 px o nome do controle "
        "vira 'P2 • Starlight Bl…' e o resto não é alcançável por caminho "
        "nenhum. CURA: o gerador (aba06.py:1215 e 1263) emitir "
        "`title=\"{rótulo inteiro}\"` no `.nav-rot`, como a aba Sistema já faz "
        "no `.est .val`"
    ),
    ("09-sistema.html", "estreita"): (
        "DEFEITO VIVO — o `<span>` de dentro de `.saude .txt` "
        "(interface/aba09.py:511, emitido em `saude()` na linha 648) recorta com "
        "reticências e não guarda `title`. A 940 px 'Steam Input estava ligado em "
        "2 jogos — desliguei' perde 123 px. E a MESMA aba já resolveu isto no "
        "`.est .val` (aba09.py:389-394), com o `title` guardando a frase inteira: "
        "CURA é aplicar ali a decisão que ela mesma escreveu"
    ),
}

#: O MESMO REGISTRO, para o artigo 4 (os campos de escolha). Tabela separada
#: porque o defeito é outro e a cura cai noutro lugar do gerador.
ESPERADO_VERMELHO_SELECT: dict[tuple[str, str], str] = {
    ("03-gatilhos.html", "estreita"): (
        "DEFEITO VIVO — três campos da aba Gatilhos escondem a escolha a 940 px, "
        "e dois deles TÊM `title`: ele diz o nome do campo ('Efeito pronto do "
        "gatilho esquerdo') e não o valor escolhido ('Recuo do MK — pesado no "
        "fim'), que é o que sumiu. CURA: o `title` do campo passar a carregar a "
        "opção escolhida, como a aba Conexões faz nos dez `<select>` dela"
    ),
    ("06-navegacao.html", "estreita"): (
        "DEFEITO VIVO — dois `<select>` sem `title` nenhum: 'Sobe um degrau no "
        "Modo de conexão' perde 18 px e 'Ligada — cada controle navega o Hefesto' "
        "perde 20 px. É o mesmo campo que a FOTO desta régua mostra cortado em "
        "'Modo de cone'"
    ),
}


def _casos(esperado: dict[tuple[str, str], str] | None = None) -> list[Any]:
    """Os trinta casos (aba x tamanho), com a marca vinda da TABELA.

    A marca nunca é digitada solta no meio de um teste: quem quiser saber o que
    está esperado-vermelho lê uma tabela só, com a razão e a cura ao lado.
    """
    return [
        pytest.param(
            aba, tamanho.rotulo,
            marks=(
                [pytest.mark.xfail(strict=True, reason=esperado[(aba, tamanho.rotulo)])]
                if esperado and (aba, tamanho.rotulo) in esperado
                else []
            ),
            id=f"{aba.removesuffix('.html')}-{tamanho.rotulo}",
        )
        for tamanho in TAMANHOS
        for aba in ABAS
    ]


CASOS = _casos(ESPERADO_VERMELHO)
CASOS_SELECT = _casos(ESPERADO_VERMELHO_SELECT)

#: Os mesmos trinta, sem marca nenhuma — para os artigos que hoje passam em
#: todos. Marcar um caso verde de `xfail` o faria reprovar por XPASS.
CASOS_SEM_MARCA = _casos()


# ---------------------------------------------------------------------------
# O PISO — sem ele todos os artigos abaixo passam por vacuidade
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(("aba", "rotulo"), CASOS_SEM_MARCA)
def test_a_pagina_abriu_inteira_e_no_tamanho_pedido(medido, aba, rotulo):
    """Zero é resposta legítima do DOM — e por isso tem de ser proibida aqui.

    Uma página que não carregou não corta nada, e a régua diria VERDE. Foi assim
    que a `regua_de_tela` deu verde sobre dois botões mortos em 29/08. O piso
    são as três faixas, a folha do produto posta, e o viewport que se pediu.
    """
    lido = medido[(aba, rotulo)]
    tamanho = next(t for t in TAMANHOS if t.rotulo == rotulo)
    assert lido["viewport"] == {"larg": tamanho.largura, "alt": tamanho.altura}, (
        f"{aba}: pedi {tamanho.largura}x{tamanho.altura} e a janela oculta deu "
        f"{lido['viewport']} — a medida inteira seria de outro tamanho")
    assert lido["folha_posta"] is True, (
        f"{aba}: a folha do produto (`FOLHA_DA_CASA`) não pegou, e as legendas "
        "`.nota` do mockup entram na conta. O produto as esconde")
    faltando = [n for n, v in lido["faixas"].items() if not v]
    assert not faltando, (
        f"{aba} em {rotulo}: a janela perdeu {faltando}. A página abriu pela "
        "metade, ou o desenho mudou de vocabulário")
    assert isinstance(lido.get("selects_apertados"), list), (
        f"{aba} em {rotulo}: a medida dos `<select>` não voltou, e sem ela o "
        "artigo 4 passa sem olhar para campo nenhum")


def test_os_campos_de_escolha_existem_para_serem_medidos(medido):
    """A soma dos `<select>` das dez abas, no tamanho do desenho.

    O artigo 4 mede campos de escolha; se um dia não houver nenhum para medir
    ele fica verde sem tocar em nada. Este caso é o piso dele — e não crava o
    número: exige que existam, e nomeia quantos achou.
    """
    por_aba = {aba: medido[(aba, "desenho")]["n_selects"] for aba in ABAS}
    total = sum(por_aba.values())
    assert total > 0, (
        "nenhum `<select>` visível nas dez abas — o artigo 4 mediria o vazio. "
        f"Por aba: {por_aba}")


# ---------------------------------------------------------------------------
# ARTIGO 1 — no tamanho do desenho, o desenho cabe
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("aba", ABAS)
def test_no_tamanho_do_desenho_nada_e_cortado(medido, aba):
    """A LINHA DE BASE, e ela é mais dura que o artigo 2: nem reticência.

    No tamanho para o qual o desenho foi feito não existe corte aceitável —
    reticências aqui seriam texto que não coube onde ele foi desenhado para
    caber. É esta régua que separa *quebrou ao encolher* de *já estava quebrado*,
    e é a metade verde da mordida do tamanho.
    """
    lido = medido[(aba, "desenho")]
    assert not lido["cortados"], (
        f"{aba} corta conteúdo no PRÓPRIO tamanho do desenho "
        f"({LARGURA_DO_DESENHO}x{ALTURA_DO_DESENHO}), o que nenhuma janela "
        f"estreita explica{_a_letra(lido)}:\n" + _contar(lido["cortados"]))
    assert not lido["selects_apertados"], (
        f"{aba} tem `<select>` cuja opção escolhida não cabe no PRÓPRIO tamanho "
        f"do desenho{_a_letra(lido)}:\n" + _contar_selects(lido["selects_apertados"]))


# ---------------------------------------------------------------------------
# ARTIGO 2 — o que não cabe ou rola, ou avisa. Nunca some.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(("aba", "rotulo"), CASOS)
def test_nada_some_sem_afordancia(medido, aba, rotulo):
    """O CORAÇÃO DA RÉGUA. Rolar é aceitável; reticências com `title` também.

    Cortar em silêncio não: quem olha não vê que falta nada, e não há gesto que
    devolva o que foi cortado. `.janela` tem `overflow:hidden`
    (`interface/topo.html:149`) — dentro dela, o que passa da caixa não corta
    nem rola: **some**.
    """
    lido = medido[(aba, rotulo)]
    fora = engolidos(lido)
    tamanho = next(t for t in TAMANHOS if t.rotulo == rotulo)
    assert not fora, (
        f"{aba} em janela {rotulo} ({tamanho.largura}x{tamanho.altura}) engole "
        f"{len(fora)} peça(s) de texto, sem barra de rolagem e sem guardar a "
        f"frase num `title`{_a_letra(lido)}:\n" + _contar(fora))


# ---------------------------------------------------------------------------
# ARTIGO 4 — o campo de escolha continua dizendo o que foi escolhido
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(("aba", "rotulo"), CASOS_SELECT)
def test_o_select_estreito_nao_esconde_o_valor_escolhido(medido, aba, rotulo):
    """O BURACO QUE A GEOMETRIA NÃO VÊ, e ele custou uma foto para aparecer.

    Um `<option>` mede **0x0** no DOM: quem pinta o texto da escolha é o
    controle de formulário, e nenhuma conta de caixa o alcança. Foi assim que a
    aba Navegação passou verde pelo artigo 2 com *"Sobe um degrau no Modo de
    conexão"* aparecendo como *"…Modo de cone"* na foto de 940 px.

    A medida aqui é outra: a largura que o texto escolhido PRECISA, num espelho
    com a fonte computada do próprio `<select>`, contra a caixa de conteúdo dele.

    São 36 campos de escolha nas dez abas, e no tamanho do desenho **nenhum**
    aperta — o que faz deste um defeito de janela estreita, e não de desenho.
    """
    lido = medido[(aba, rotulo)]
    mudos = selects_mudos(lido)
    tamanho = next(t for t in TAMANHOS if t.rotulo == rotulo)
    assert not mudos, (
        f"{aba} em janela {rotulo} ({tamanho.largura}x{tamanho.altura}): "
        f"{len(mudos)} campo(s) de escolha escondem o valor escolhido, e o "
        f"`title` não o devolve{_a_letra(lido)}:\n" + _contar_selects(mudos))


# ---------------------------------------------------------------------------
# ARTIGO 3 — a janela inteira continua alcançável
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(("aba", "rotulo"), CASOS_SEM_MARCA)
def test_as_tres_faixas_cabem_dentro_da_janela(medido, aba, rotulo):
    """`.tira`, `.miolo` e `.rodape` dentro da `.janela`, que não rola nada.

    O rodapé é a barra que DECIDE (Aplicar, Guardar, Importar, Exportar). Ele
    ficar meio pixel fora da `.janela` é a diferença entre um botão que se clica
    e um botão que não existe — e a `.janela` não tem barra de rolagem para
    devolvê-lo.
    """
    lido = medido[(aba, rotulo)]
    j = lido["janela"]
    fora = [
        f"  .{nome}: {v} contra a janela {j}"
        for nome, v in lido["faixas"].items()
        if v and (v["dir"] > j["dir"] + 1 or v["esq"] < j["esq"] - 1
                  or v["base"] > j["base"] + 1 or v["topo"] < j["topo"] - 1)
    ]
    assert not fora, (
        f"{aba} em janela {rotulo}: faixa passando da `.janela`, que tem "
        f"`overflow:{j['ox']}/{j['oy']}` e portanto não rola nada:\n"
        + "\n".join(fora))


@pytest.mark.parametrize(("aba", "rotulo"), CASOS_SEM_MARCA)
def test_o_que_fica_fora_da_tela_se_alcanca_rolando(medido, aba, rotulo):
    """Janela maior que a tela é ACEITÁVEL — desde que o documento role.

    É o caso `baixa`: a `.janela` tem altura fixa (777 px), então numa tela de
    600 ela passa 193 px da dobra e o documento rola 209. Rolar é a afordância
    legítima. O que este teste proíbe é a outra saída — ficar fora da tela **e**
    não haver rolagem, que é o rodapé inalcançável.
    """
    lido = medido[(aba, rotulo)]
    j, vp, rola = lido["janela"], lido["viewport"], lido["documento"]
    queixas = []
    if j["dir"] > vp["larg"] + 1 and rola["rola_x"] <= 0:
        queixas.append(
            f"a janela termina em {j['dir']} px numa tela de {vp['larg']} e o "
            "documento NÃO rola na horizontal")
    if j["base"] > vp["alt"] + 1 and rola["rola_y"] <= 0:
        queixas.append(
            f"a janela termina em {j['base']} px numa tela de {vp['alt']} e o "
            "documento NÃO rola na vertical")
    assert not queixas, f"{aba} em janela {rotulo}: " + " · ".join(queixas)


# ---------------------------------------------------------------------------
# A MORDIDA DA AFORDÂNCIA — a régua tem de sentir o `title` sair
# ---------------------------------------------------------------------------
#: O ALVO DA MORDIDA. A aba Sistema é a única das dez em que o artigo 2 SALVA
#: alguma coisa: a 940 px ela corta doze peças e quatro passam porque o
#: `.est .val` guarda a frase inteira num `title`.
ABA_DA_MORDIDA = "09-sistema.html"


def test_a_mordida_da_afordancia_sem_o_title_o_corte_vira_sumico(tmp_path):
    """ARRANCA A CURA: sem o `title`, o que hoje passa cai para os engolidos.

    Copia a aba Sistema para um diretório temporário, troca todo ``title=`` por
    um atributo inerte e mede de novo, na MESMA janela de 940 px. Se a régua não
    sentir, ela não está lendo o `title` que diz ler — e estaria dando verde
    sobre a aba inteira sem ninguém ver.

    A cópia é fora da bancada de propósito: a bancada é o arquivo DELA.
    """
    inteira = medir(TAMANHOS[1], (ABA_DA_MORDIDA,))[ABA_DA_MORDIDA]
    salvos = [c for c in inteira["cortados"] if tem_afordancia(c)]
    assert salvos, (
        f"{ABA_DA_MORDIDA} deixou de ter corte COM afordância a 940 px, e sem "
        "ele esta mordida não morde nada. Reveja o alvo antes de crer no verde")

    (tmp_path / ABA_DA_MORDIDA).write_text(
        (onde.BANCADA / ABA_DA_MORDIDA).read_text(encoding="utf-8")
        .replace(' title="', ' data-title-arrancado="'),
        encoding="utf-8")
    mordida = medir(TAMANHOS[1], (ABA_DA_MORDIDA,), pasta=tmp_path)[ABA_DA_MORDIDA]

    assert not [c for c in mordida["cortados"] if tem_afordancia(c)], (
        "arranquei todo `title=` da aba e a régua continuou dando afordância a "
        "algum corte:\n" + _contar(
            [c for c in mordida["cortados"] if tem_afordancia(c)]))
    assert len(engolidos(mordida)) == len(engolidos(inteira)) + len(salvos), (
        f"com o `title` arrancado os {len(salvos)} cortes salvos tinham de virar "
        f"engolidos: eram {len(engolidos(inteira))} e viraram "
        f"{len(engolidos(mordida))}")
