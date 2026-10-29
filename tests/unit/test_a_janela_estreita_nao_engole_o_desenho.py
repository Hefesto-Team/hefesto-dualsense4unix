#!/usr/bin/env python3
"""A JANELA ESTREITA NÃO ENGOLE O DESENHO — as dez abas, medidas fora do tamanho."""
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
    from hefesto_dualsense4unix.interface.janela import (
        ALTURA_DO_DESENHO,
        FOLHA_DA_CASA,
        LARGURA_DO_DESENHO,
    )
    from hefesto_dualsense4unix.interface import onde
except (ImportError, ValueError) as _erro:  # pragma: no cover
    pytest.skip(
        f"JANELA-ESTREITA-01: a biblioteca da janela não importou ({_erro}). "
        "Falta gir1.2-webkit2-4.1?",
        allow_module_level=True,
    )

try:
    import regua_de_tela
except (ImportError, ValueError) as _erro:  # pragma: no cover
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

ABAS: tuple[str, ...] = tuple(
    p.name for p in sorted(onde.BANCADA.glob("[0-9][0-9]-*.html"))
)

if len(ABAS) < 10:
    pytest.skip(
        f"JANELA-ESTREITA-01: achei {len(ABAS)} aba(s) em {onde.BANCADA} e o "
        "produto tem DEZ. Medir menos que isso seria verde por vacuidade.",
        allow_module_level=True,
    )

POR_A_FOLHA = (
    "(function(){var s=document.createElement('style');"
    f"s.textContent={json.dumps(FOLHA_DA_CASA)};"
    "document.head.appendChild(s);return 'FOLHA-POSTA';})()"
)

LETRA_LARGA = "*{letter-spacing:.5px !important}"
POR_A_LETRA_LARGA = (
    "(function(){var s=document.createElement('style');"
    f"s.textContent={json.dumps(LETRA_LARGA)};"
    "document.head.appendChild(s);return 'LETRA-LARGA';})()"
)

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
      // `data-dica` é o `title` da base comum (A-BASE-COMUM-DAS-ABAS-01): a dica da casa abre
      // com o ponteiro no elemento ou em quem o contém, como o tooltip do navegador.
      var v = p.getAttribute('title') || p.getAttribute('data-dica');
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
            no_topo: !!el.closest('.fita-linha'),
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
                      titulo: sel.getAttribute('title') || sel.getAttribute('data-dica'),
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
    // A LETRA VAI JUNTO DA MEDIDA. As dez abas trazem 'Space Grotesk' e
    // 'JetBrains Mono' do pacote (`@font-face` no topo de cada página): sem
    // elas o motor cai na pilha de sistema, a largura de todo texto muda, e um
    // vermelho desta régua passaria a significar outra coisa.
    letra: (typeof document.fonts === 'undefined') ? null : {
      estado: document.fonts.status,
      texto: document.fonts.check('12px "Space Grotesk"'),
      mono: document.fonts.check('12px "JetBrains Mono"')
    },
    folha_posta: nota ? getComputedStyle(nota).display === 'none' : null,
    entreletra: getComputedStyle(document.body).letterSpacing,
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
    """O corte é aceitável? Reticências **e** o texto inteiro guardado."""
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
    """Os ``<select>`` cuja opção escolhida não cabe e não está guardada."""
    return [
        s for s in leitura["selects_apertados"]
        if not any(s["texto"] in (s.get(chave) or "").strip()
                   for chave in ("titulo", "rotulo"))
    ]


def _a_letra(leitura: dict[str, Any]) -> str:
    """A letra com que esta medida foi feita, para toda reprovação declarar."""
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
          pasta: pathlib.Path | None = None,
          letra_larga: bool = False) -> dict[str, dict[str, Any]]:
    """Abre UMA janela do tamanho pedido e navega pelas abas, medindo cada uma."""
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
            if letra_larga:
                tela.executar(POR_A_LETRA_LARGA)
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


CORTE_CONHECIDO_NO_DESENHO: dict[tuple[str, str], str] = {
    # fica: é o desenho decidido (a frase longa corta e a dica guarda a inteira), não um defeito
    ("07-lancadores.html", "Os jogos do KytyPS5"): (
        "D-2110-A-FRASE-DA-EXTENSAO-CORTA-COM-A-DICA — nas duas colunas do desenho de 21/10 a "
        "frase da extensão corta com reticências e a dica guarda a inteira, como a do efeito"
    ),
}

CASOS = [
    pytest.param(aba, tamanho.rotulo, id=f"{aba.removesuffix('.html')}-{tamanho.rotulo}")
    for tamanho in TAMANHOS
    for aba in ABAS
]


@pytest.mark.parametrize(("aba", "rotulo"), CASOS)
def test_a_pagina_abriu_inteira_e_no_tamanho_pedido(medido, aba, rotulo):
    """Zero é resposta legítima do DOM — e por isso tem de ser proibida aqui."""
    lido = medido[(aba, rotulo)]
    tamanho = next(t for t in TAMANHOS if t.rotulo == rotulo)
    assert lido["viewport"] == {"larg": tamanho.largura, "alt": tamanho.altura}, (
        f"{aba}: pedi {tamanho.largura}x{tamanho.altura} e a janela oculta deu "
        f"{lido['viewport']} — a medida inteira seria de outro tamanho")
    assert lido["folha_posta"] is not False, (
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
    """A soma dos `<select>` das dez abas, no tamanho do desenho."""
    por_aba = {aba: medido[(aba, "desenho")]["n_selects"] for aba in ABAS}
    total = sum(por_aba.values())
    assert total > 0, (
        "nenhum `<select>` visível nas dez abas — o artigo 4 mediria o vazio. "
        f"Por aba: {por_aba}")


@pytest.mark.parametrize("aba", ABAS)
def test_no_tamanho_do_desenho_nada_e_cortado(medido, aba):
    """A LINHA DE BASE, e ela é mais dura que o artigo 2: nem reticência.

    A prova da D-2110-A-FRASE-DA-EXTENSAO-CORTA-COM-A-DICA.
    """
    lido = medido[(aba, "desenho")]
    cortados = list(lido["cortados"])
    for (pagina, comeco), razao in CORTE_CONHECIDO_NO_DESENHO.items():
        if pagina != aba:
            continue
        conhecidos = [c for c in cortados
                      if str(c["peca"].get("titulo") or "").startswith(comeco)]
        assert conhecidos, (
            f"{aba}: «{comeco}…» deixou de ser cortada no tamanho do desenho — a "
            "cura entrou, e a linha dela sai de `CORTE_CONHECIDO_NO_DESENHO`. "
            f"({razao})")
        cortados = [c for c in cortados if c not in conhecidos]
    assert not cortados, (
        f"{aba} corta conteúdo no PRÓPRIO tamanho do desenho "
        f"({LARGURA_DO_DESENHO}x{ALTURA_DO_DESENHO}), o que nenhuma janela "
        f"estreita explica{_a_letra(lido)}:\n" + _contar(cortados))
    assert not lido["selects_apertados"], (
        f"{aba} tem `<select>` cuja opção escolhida não cabe no PRÓPRIO tamanho "
        f"do desenho{_a_letra(lido)}:\n" + _contar_selects(lido["selects_apertados"]))


@pytest.mark.parametrize(("aba", "rotulo"), CASOS)
def test_nada_some_sem_afordancia(medido, aba, rotulo):
    """O CORAÇÃO DA RÉGUA. Rolar é aceitável; reticências com `title` também.

    Prova da D-1710-A-JANELA-ESTREITA-NAO-ENGOLE-O-DESENHO.
    """
    lido = medido[(aba, rotulo)]
    fora = engolidos(lido)
    tamanho = next(t for t in TAMANHOS if t.rotulo == rotulo)
    assert not fora, (
        f"{aba} em janela {rotulo} ({tamanho.largura}x{tamanho.altura}) engole "
        f"{len(fora)} peça(s) de texto, sem barra de rolagem e sem guardar a "
        f"frase num `title`{_a_letra(lido)}:\n" + _contar(fora))


@pytest.mark.parametrize(("aba", "rotulo"), CASOS)
def test_o_select_estreito_nao_esconde_o_valor_escolhido(medido, aba, rotulo):
    """O BURACO QUE A GEOMETRIA NÃO VÊ, e ele custou uma foto para aparecer."""
    lido = medido[(aba, rotulo)]
    mudos = selects_mudos(lido)
    tamanho = next(t for t in TAMANHOS if t.rotulo == rotulo)
    assert not mudos, (
        f"{aba} em janela {rotulo} ({tamanho.largura}x{tamanho.altura}): "
        f"{len(mudos)} campo(s) de escolha escondem o valor escolhido, e o "
        f"`title` não o devolve{_a_letra(lido)}:\n" + _contar_selects(mudos))


@pytest.mark.parametrize(("aba", "rotulo"), CASOS)
def test_as_tres_faixas_cabem_dentro_da_janela(medido, aba, rotulo):
    """`.tira`, `.miolo` e `.rodape` dentro da `.janela`, que não rola nada."""
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


@pytest.mark.parametrize(("aba", "rotulo"), CASOS)
def test_o_que_fica_fora_da_tela_se_alcanca_rolando(medido, aba, rotulo):
    """Janela maior que a tela é ACEITÁVEL — desde que o documento role."""
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


ABA_DA_MORDIDA = "07-lancadores.html"


def test_a_mordida_da_afordancia_sem_o_title_o_corte_vira_sumico(tmp_path):
    """ARRANCA A CURA: sem o `title`, o que hoje passa cai para os engolidos."""
    inteira = medir(TAMANHOS[1], (ABA_DA_MORDIDA,))[ABA_DA_MORDIDA]
    salvos = [c for c in inteira["cortados"] if tem_afordancia(c)]
    assert salvos, (
        f"{ABA_DA_MORDIDA} deixou de ter corte COM afordância a 940 px, e sem "
        "ele esta mordida não morde nada. Reveja o alvo antes de crer no verde")

    (tmp_path / ABA_DA_MORDIDA).write_text(
        (onde.BANCADA / ABA_DA_MORDIDA).read_text(encoding="utf-8")
        .replace(' title="', ' data-title-arrancado="')
        .replace(' data-dica="', ' data-dica-arrancada="'),
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


QUATRO_NA_FITA = r"""
(function(PLASTICOS, PERFIL){
  const f = document.querySelector('.fita');
  const modelo = f.querySelector('.chip.plastico');
  f.querySelectorAll('.chip.plastico').forEach(c => c.remove());
  const pt = ' <span class="pt">•</span> ';
  PLASTICOS.forEach((p, i) => { const c = modelo.cloneNode(true);
    c.innerHTML = 'P' + (i + 1) + pt + p + pt + (i % 2 ? 'BT' : 'USB'); f.appendChild(c); });
  const nome = document.querySelector('.pa-nome');
  nome.textContent = PERFIL;
  const n = nome.getBoundingClientRect();
  const p = document.querySelector('.perfil-ativo').getBoundingClientRect();
  return JSON.stringify({larg: Math.round(n.width), dir: Math.round(n.right),
                         dir_da_pilula: Math.round(p.right)});
})(@@PLASTICOS@@, @@PERFIL@@)
"""


@pytest.mark.parametrize("largura", [940, LARGURA_DO_DESENHO])
@pytest.mark.parametrize("perfil", ["—", "Freestyle"])
def test_com_quatro_controles_o_nome_do_perfil_ativo_fica_a_vista(
    largura: int, perfil: str
) -> None:
    """O nome do perfil ativo nunca some da fita, nem com quatro controles de nome longo.

    Prova da D-1710-A-JANELA-ESTREITA-NAO-ENGOLE-O-DESENHO depois do cadeado da moldura
    (O-BOTAO-QUE-TRAVA-A-NAVEGACAO-DOS-CONTROLES-01): quem cede primeiro é o rótulo «Perfil ativo»,
    e o nome guarda um piso de 3em dentro da pílula.

    MORDIDAS (26/10/2026): o ``topo.html`` de ``08a6ff5ac`` reprova com o nome em 0 px; tirar o
    ``min-width:min-content`` da pílula reprova com o nome passando da borda dela.

    Prova da D-2610-O-ROTULO-DO-PERFIL-ATIVO-CEDE-ANTES-DO-NOME.
    """
    from tests.unit.test_as_telas_de_16_10_no_webkit import _no_webkit

    plasticos = ["Galactic Purple", "Starlight Blue"] * 2
    passo = (QUATRO_NA_FITA.replace("@@PLASTICOS@@", json.dumps(plasticos))
             .replace("@@PERFIL@@", json.dumps(perfil)))
    uri = onde.pagina("03-gatilhos.html", publicado=False).as_uri()
    lido: dict[str, Any] = _no_webkit(uri, (largura, ALTURA_DO_DESENHO), [passo])[0]
    assert lido["larg"] >= 30, f"o nome do perfil ativo sumiu da fita: {lido}"
    assert lido["dir"] <= lido["dir_da_pilula"] + 1, (
        f"o nome do perfil ativo passa da borda da pílula, que o recorta: {lido}")


CASOS_DA_LETRA_LARGA = [
    pytest.param(aba, tamanho.rotulo, id=f"{aba.removesuffix('.html')}-{tamanho.rotulo}")
    for tamanho in TAMANHOS[:2]
    for aba in ABAS
]


@pytest.fixture(scope="module")
def medido_com_a_letra_larga() -> dict[tuple[str, str], dict[str, Any]]:
    """As dez abas no tamanho do desenho e na estreita, com meio pixel a mais entre as letras."""
    fora: dict[tuple[str, str], dict[str, Any]] = {}
    for tamanho in TAMANHOS[:2]:
        for nome, leitura in medir(tamanho, letra_larga=True).items():
            fora[(nome, tamanho.rotulo)] = leitura
    return fora


@pytest.mark.parametrize(("aba", "rotulo"), CASOS_DA_LETRA_LARGA)
def test_com_a_letra_mais_larga_o_cabecalho_nao_engole_nada(
        medido_com_a_letra_larga: dict[tuple[str, str], dict[str, Any]], aba: str, rotulo: str
) -> None:
    """O cabeçalho cabe com a letra de qualquer computador, nas dez abas.

    O-CABECALHO-TEM-FOLGA-PARA-A-LETRA-DE-QUALQUER-COMPUTADOR-01. A mesma Space Grotesk mede
    cerca de +0,24 px por letra no ubuntu-26.04 (freetype 2.14, harfbuzz 12), e a linha do topo,
    que cabia com 4 px na mesa, cortava o nome do controle só lá. A passada põe
    ``*{letter-spacing:.5px}`` em todo texto e mede de novo: reproduz em qualquer máquina o que
    aquela pilha faz, sem fixar fonte nem imagem. Só o que mora na ``.fita-linha`` conta.
    """
    lido = medido_com_a_letra_larga[(aba, rotulo)]
    assert lido["entreletra"] == "0.5px", (
        f"{aba}: a letra larga não pegou (letter-spacing do corpo {lido['entreletra']!r}), "
        "e a passada mediria a letra comum")
    fora = [c for c in engolidos(lido) if c["peca"].get("no_topo")]
    tamanho = next(t for t in TAMANHOS if t.rotulo == rotulo)
    assert not fora, (
        f"{aba} em janela {rotulo} ({tamanho.largura}x{tamanho.altura}), com meio pixel a mais "
        f"por letra, corta {len(fora)} peça(s) do cabeçalho sem guardar a frase{_a_letra(lido)}:\n"
        + _contar(fora))


CONTADOR_DE_VOLTA = r"""
(function(FOLHA, LARGA){
  var s = document.createElement('style'); s.textContent = FOLHA; document.head.appendChild(s);
  if (LARGA) {
    var t = document.createElement('style'); t.textContent = LARGA; document.head.appendChild(t);
  }
  var pa = document.querySelector('.perfil-ativo');
  var d = document.createElement('div');
  d.className = 'conectado';
  d.innerHTML = '<span class="bolinha">●</span> <b>1 USB · 1 BT</b>';
  pa.parentNode.insertBefore(d, pa);
  var cortes = [].map.call(document.querySelectorAll('.fita .chip.plastico'),
                           function(c){ return c.scrollWidth - c.clientWidth; });
  return JSON.stringify({cortes: cortes,
                         entreletra: getComputedStyle(document.body).letterSpacing});
})(@@FOLHA@@, @@LARGA@@)
"""


def test_a_mordida_da_letra_larga_ve_o_corte_que_a_comum_nao_ve() -> None:
    """A passada larga morde: com o contador de volta no topo, a régua dela acusa o chip cortado.

    O contador «● N USB · N BT» saiu do topo com a
    A-ABA-JOGAR-JUNTA-OS-CONTROLES-E-O-MODO-GERE-TUDO-01. Posto de volta pelo teste, a linha da 03
    em 940 px cabe com a letra comum da mesa e corta os dois chips com meio pixel a mais por letra:
    é a cegueira que deixava o vermelho só para o CI. A prova passa pela MEDIDA e pelo
    ``engolidos`` da passada, e não por uma conta à parte: é a régua que tem de ver o corte.
    """
    from tests.unit.test_as_telas_de_16_10_no_webkit import _no_webkit

    uri = onde.pagina("03-gatilhos.html", publicado=False).as_uri()
    lidos = {}
    no_topo = {}
    for nome, larga in (("comum", ""), ("larga", LETRA_LARGA)):
        passo = (CONTADOR_DE_VOLTA.replace("@@FOLHA@@", json.dumps(FOLHA_DA_CASA))
                 .replace("@@LARGA@@", json.dumps(larga)))
        lidos[nome], medida = _no_webkit(uri, (940, ALTURA_DO_DESENHO), [passo, MEDIDA.strip()])
        no_topo[nome] = [c for c in engolidos(medida) if c["peca"].get("no_topo")]
    comum, larga_lida = lidos["comum"], lidos["larga"]
    assert len(larga_lida["cortes"]) >= 2 and larga_lida["entreletra"] == "0.5px", (
        f"a mordida não mediu o que devia: {lidos}")
    assert sum(larga_lida["cortes"]) > 0 and sum(larga_lida["cortes"]) > sum(comum["cortes"]), (
        f"com o contador de volta, a letra larga tinha de cortar o chip mais que a comum: {lidos}")
    vistos = [c["peca"]["texto"] for c in no_topo["larga"]]
    assert any("Cosmic Red" in t or "Starlight Blue" in t for t in vistos), (
        f"a passada larga não acusou o chip que corta {larga_lida['cortes']} px: {vistos}")
    assert (sum(c["sobra"] for c in no_topo["larga"])
            > sum(c["sobra"] for c in no_topo["comum"])), (
        f"a régua larga tinha de ver mais corte que a comum: {no_topo}")
