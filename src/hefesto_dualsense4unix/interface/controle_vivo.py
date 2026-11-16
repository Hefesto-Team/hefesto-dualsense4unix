"""O controle vivo da janela de uma extensão: o desenho do Mapa dos controles com as peças que
a extensão mexe acesas, o clima da cena e a faixa «Ao vivo», uma linha por canal escrito.

O desenho é o MESMO do Mapa (``mapa.controle``, com as cores, os glifos e as ondas da háptica de lá,
e as regras de tinta do ``mapa.CSS_BASE``): nenhuma cópia redesenhada. Ele entra uma vez na página
publicada, num ``<template>``, e a janela o põe no lugar e acende as peças pelo que a extensão
escreveu de fato.
"""
from __future__ import annotations

import functools
import html
import pathlib
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, NamedTuple

_AQUI = pathlib.Path(__file__).resolve().parent
if str(_AQUI) not in sys.path:
    sys.path.insert(0, str(_AQUI))

ID_DO_MOLDE = "cv-molde"
JANELA_DA_FAIXA_MS = 30_000
ACESO_POR_MS = 1_500

CANAIS = ("haptica", "vibracao", "gatilho", "luz", "leds", "som", "mira")

PECAS_DO_CANAL: dict[str, tuple[str, ...]] = {
    "haptica": ("feat-haptica",),
    "vibracao": ("feat-rumble-esquerdo", "feat-rumble-direito"),
    "gatilho": ("l2", "r2"),
    "luz": ("lightbar",),
    "leds": ("led-jogador",),
    "som": ("alto-falante",),
    "mira": ("feat-giroscopio",),
    "microfone": ("mic",),
}

ROTULO_DO_CANAL = {
    "haptica": "Vibração fina", "vibracao": "Motores", "gatilho": "Gatilhos",
    "luz": "Barra de luz", "leds": "Luzes de jogador", "som": "Alto-falante", "mira": "Mira",
}

CANAL_DA_PERMISSAO = {f"escrever:{c}": c for c in CANAIS}


class Marca(NamedTuple):
    """Um trecho da faixa: o canal, de quanto tempo atrás começou e acabou (ms) e a cor."""

    canal: str
    de_ms: int
    ate_ms: int
    cor: str


_FOLHA = re.compile(r'<style id="(?:mp-)?cores-do-dualsense-folha">.*?</style>', re.S)
_GRADIENTE_DO_MODELO = re.compile(r'<linearGradient id="(?:mp-)?casca-[^"]*".*?</linearGradient>', re.S)
_REGRA_DO_MODELO = r'svg\[data-colorway="{}"\]\{{([^}}]*)\}}'
_REGRA_DA_ZONA = re.compile(r'svg\[data-colorway="[^"]+"\] (\.z-[a-z_-]+)( [^{]*)?\{([^:]+):var\((--z-[a-z_-]+)\)')


def _marcar(x: str, gid: str, canal: str) -> str:
    alvo = f'<g id="{gid}"'
    if x.count(alvo) != 1:
        raise ValueError(f"a peça {gid!r} não está uma vez só no desenho do Mapa")
    fim = x.index(">", x.index(alvo))
    return x[:fim] + f' data-canal="{canal}"' + x[fim:]


def molde_svg() -> str:
    """O desenho do Mapa, com cada peça marcada pelo canal que a acende (``data-canal``)."""
    import mapa

    x = mapa.controle(mapa.le_csv())
    x = re.sub(r"<\?xml[^>]*\?>\s*", "", x)
    x = re.sub(r'(<svg\b[^>]*?)\swidth="[^"]*"\s+height="[^"]*"', r"\1", x, count=1)
    if not x.startswith('<svg data-colorway="') and 'class="ds"' not in x[:x.index(">")]:
        raise ValueError("o desenho do Mapa mudou de forma: sem o <svg class=\"ds\">")
    x = x.replace('class="ds"', 'class="ds cv-ds" role="img" aria-label="O controle"', 1)
    topo = x[:x.index(">")]
    x = re.sub(r'\sdata-colorway="[^"]*"', "", topo) + x[len(topo):]
    x = _FOLHA.sub("", x, count=1)
    x = _GRADIENTE_DO_MODELO.sub("", x)
    x = re.sub(r'\s(?:data-campo|data-hef-[a-z-]+)="[^"]*"', "", x)
    for canal, pecas in PECAS_DO_CANAL.items():
        for peca in pecas:
            x = _marcar(x, f"mp-{peca}", canal)
    return re.sub(r">\s+<", "><", x).strip()


def molde_html() -> str:
    """O ``<template>`` que a página publicada leva uma vez: a janela o clona no lugar dele."""
    return f'<template id="{ID_DO_MOLDE}">{molde_svg()}</template>'


def _da_tinta(regra: str) -> bool:
    r = regra.strip()
    return r.startswith((".ds", ".sobre", ".alvo"))


def css_do_molde(escopo: str = "#mod-janela") -> str:
    """As regras de tinta do desenho do Mapa (as do ``mapa.CSS_BASE``, as da zona e as do
    contraste dos glifos), no escopo da janela."""
    import mapa

    regras = []
    for linha in re.split(r"\n(?=  [.:])", mapa.CSS_BASE):
        if not _da_tinta(linha):
            continue
        r = linha.strip()
        r = re.sub(r"(^|,)\s*\.ds\b", lambda m: f"{m.group(1)}{escopo} svg.cv-ds", r)
        r = re.sub(r"(^|,)\s*\.(sobre|alvo)\b", lambda m: f"{m.group(1)}{escopo} svg.cv-ds .{m.group(2)}", r)
        regras.append(r)
    contraste = mapa.css_do_contraste().splitlines()[0]
    zonas = mapa.css_da_zona([p["id"] for p in mapa.le_csv()]) + "\n" + contraste
    zonas = zonas.replace(".mc svg.ds", f"{escopo} svg.cv-ds")
    tintas = re.search(r"--luz-apagada:[^;]+;\s*--led-apagado:[^;]+;\s*--led-aceso:[^;]+;"
                       r"\s*--sem-plastico:[^;]+;", mapa.CSS_BASE)
    branco = re.search(r"--branco:[^;]+;", mapa.CSS_BASE)
    if not tintas or not branco:
        raise ValueError("as cores do desenho sumiram do mapa.CSS_BASE")
    variaveis = f"{escopo} svg.cv-ds{{{branco.group(0)}{' '.join(tintas.group(0).split())}}}"
    import monta

    vistas: dict[str, str] = {}
    for m in _REGRA_DA_ZONA.finditer(monta.DS):
        zona, alvo, prop, var = m.group(1), m.group(2) or "", m.group(3), m.group(4)
        vistas.setdefault(f"{zona}{alvo}", f"{escopo} svg.cv-ds {zona}{alvo}"
                          f"{{{prop}:var({var}, var(--sem-plastico)) !important}}")
    regras.extend(vistas.values())
    regras.append(f"{escopo} svg.cv-ds .cv-claro{{color:var(--app-bg) !important}}")
    pinta = ":is(.peca, rect, circle, path, ellipse){fill:var(--%s) !important;stroke:var(--%s) !important}"
    acesas = [f"{escopo} svg.cv-ds #mp-{peca}.cv-aceso {pinta % ('pink', 'pink')}\n"
              f"{escopo} svg.cv-ds.foco #mp-{peca}.em-foco {pinta % ('cyan', 'cyan')}"
              for pecas in PECAS_DO_CANAL.values() for peca in pecas]
    return "\n".join([variaveis, *regras, zonas.strip(), *acesas]) + "\n"


class ControleDoVivo(NamedTuple):
    """Um controle ligado: o número que acende, o nome do plástico, o modelo do desenho e a cor."""

    jogador: int | None
    nome: str
    colorway: str
    cor: str


class Vivo(NamedTuple):
    """O que o controle vivo desenha: os controles, o do desenho, os trechos da faixa, as peças
    acesas no do desenho, o clima e o limiar dele, e os canais que a extensão pode escrever."""

    controles: tuple[ControleDoVivo, ...] = ()
    escolhido: int | None = None
    marcas: tuple[Marca, ...] = ()
    acesos: frozenset[str] = frozenset()
    clima: tuple[int, ...] = ()
    limiar: int | None = None
    canais: tuple[str, ...] = ()


COR_SEM_PLASTICO = "var(--comment)"


def colorway_do_nome(nome: str) -> str:
    """O modelo do desenho para o nome do plástico (o da tabela das cores), ou vazio: o desenho
    sem cor sabida, nunca a cor de outro controle."""
    from hefesto_dualsense4unix.integrations.cor_do_plastico import TABELA

    alvo = nome.strip().casefold()
    if not alvo:
        return ""
    import monta

    slug = next((c.id for c in TABELA.values() if c.nome.casefold() == alvo and c.id), "")
    return slug if slug and monta.o_desenho_conhece(slug) else ""


@functools.lru_cache(maxsize=32)
def pintura_do_modelo(colorway: str) -> tuple[str, tuple[str, ...], str]:
    """O que pinta o desenho no modelo ``colorway``, dito pelo pacote no tique (a página nunca
    traz a cor de um modelo): as variáveis das zonas, com as hachuras no endereço do desenho do
    Mapa, os glifos que ficam escuros para contrastar com a tecla (os do ``mapa``) e o gradiente
    da casca de duas cores, quando o modelo tem um."""
    if not colorway:
        return "", (), ""
    import mapa
    import monta

    regra = re.search(_REGRA_DO_MODELO.format(re.escape(colorway)), monta.DS)
    if not regra:
        return "", (), ""
    variaveis = regra.group(1).replace("url(#", "url(#mp-")
    gradientes = "".join(
        m.group(0).replace(f'id="{ident}"', f'id="mp-{ident}"', 1)
        for ident in dict.fromkeys(re.findall(r"url\(#(casca-[a-z0-9-]+)\)", regra.group(1)))
        for m in [re.search(rf'<linearGradient id="{re.escape(ident)}".*?</linearGradient>',
                            monta.DS, re.S)] if m)
    claros: list[str] = []
    for linha in mapa.css_do_contraste().splitlines():
        if f'[data-colorway="{colorway}"]' in linha:
            claros += re.findall(r"\.s-([a-z0-9_]+)", linha.split("{", 1)[0])
    defs = (f'<svg class="cv-defs" width="0" height="0" aria-hidden="true"><defs>{gradientes}'
            '</defs></svg>') if gradientes else ""
    return variaveis, tuple(dict.fromkeys(claros)), defs


def _cor_de(colorway: str) -> str:
    import monta

    return (monta.cor_de_css(colorway) if colorway else "") or COR_SEM_PLASTICO


def _inteiro(valor: Any) -> int | None:
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def nome_do_controle(jogador: int | None, cor: str, posicao: int) -> str:
    """A cor do plástico; sem a cor, o número que o controle acende."""
    return cor.strip() or f"Jogador {jogador if jogador is not None else posicao}"


def vivo_de(estado: Mapping[str, Any] | None, canais: Sequence[str], escolhido: int | None,
            clima: Sequence[int] = ()) -> Vivo:
    """O ``Vivo`` do ``ao_vivo`` que o ``mods.agora`` devolve (os controles e os trechos do que a
    extensão escreveu): o do desenho é o ``escolhido`` se ainda está ligado, senão o primeiro."""
    estado = estado or {}
    ao = estado.get("ao_vivo") if isinstance(estado.get("ao_vivo"), Mapping) else {}
    controles = []
    for n, c in enumerate(x for x in ao.get("controles") or () if isinstance(x, Mapping)):
        jogador = _inteiro(c.get("jogador"))
        cor = str(c.get("cor") or "")
        colorway = colorway_do_nome(cor)
        controles.append(ControleDoVivo(jogador, nome_do_controle(jogador, cor, n + 1), colorway,
                                        _cor_de(colorway)))
    numeros = [c.jogador for c in controles]
    if escolhido not in numeros:
        escolhido = numeros[0] if numeros else None
    cor_de = {c.jogador: c.cor for c in controles}
    marcas, acesos = [], set()
    for t in ao.get("trechos") or ():
        if not isinstance(t, Mapping) or t.get("canal") not in ROTULO_DO_CANAL:
            continue
        de, ate, jogador = _inteiro(t.get("de_ms")), _inteiro(t.get("ate_ms")), _inteiro(t.get("jogador"))
        if de is None or ate is None:
            continue
        marcas.append(Marca(str(t["canal"]), de, ate, cor_de.get(jogador, COR_SEM_PLASTICO)))
        if ate <= ACESO_POR_MS and (jogador is None or jogador == escolhido):
            acesos.add(str(t["canal"]))
    limiar = _inteiro(estado.get("limiar"))
    return Vivo(tuple(controles), escolhido, tuple(marcas), frozenset(acesos),
                tuple(int(v) for v in clima), limiar,
                tuple(c for c in CANAIS if c in set(canais) and c in ROTULO_DO_CANAL))


def lugar_html(vivo: Vivo) -> str:
    """O lugar do desenho: a página põe nele o ``<template>`` do Mapa, pintado no modelo do
    controle escolhido (as variáveis das zonas e os glifos claros) e com as peças acesas que o
    ``data-acesos`` diz."""
    atual = next((c for c in vivo.controles if c.jogador == vivo.escolhido), None)
    variaveis, claros, defs = pintura_do_modelo(atual.colorway if atual else "")
    acesos = " ".join(sorted(vivo.acesos))
    estilo = f' style="{html.escape(variaveis)}"' if variaveis else ""
    return (f'{defs}<div class="cv-lugar"{estilo} data-acesos="{acesos}" '
            f'data-claros="{" ".join(claros)}"></div>')


def _pct(ha_ms: int) -> float:
    return round(100 - 100 * min(max(ha_ms, 0), JANELA_DA_FAIXA_MS) / JANELA_DA_FAIXA_MS, 2)


def linhas_da_faixa(canais: Sequence[str], marcas: Iterable[Marca]) -> str:
    """As linhas da faixa «Ao vivo», uma por canal, com os trechos de cada uma: o pedaço que o
    tique repinta."""
    por_canal: dict[str, list[Marca]] = {}
    for m in marcas:
        por_canal.setdefault(m.canal, []).append(m)
    linhas = []
    for canal in canais:
        trechos = "".join(
            f'<i class="cv-mk" style="left:{_pct(m.de_ms)}%;'
            f'width:{max(round(_pct(m.ate_ms) - _pct(m.de_ms), 2), 0.6)}%;'
            f'--plastico:{html.escape(m.cor)}"></i>'
            for m in por_canal.get(canal, ()))
        linhas.append(
            f'<span class="cv-rot" data-canal="{canal}">{ROTULO_DO_CANAL[canal]}</span>'
            f'<span class="cv-pista" data-canal="{canal}">{trechos}</span>')
    return "".join(linhas)


def faixa_html(canais: Sequence[str], marcas: Iterable[Marca], *, ident: str = "") -> str:
    """A faixa «Ao vivo»: uma linha por canal que a extensão pode escrever, com o que a extensão
    escreveu nos últimos 30 s, na cor do plástico de cada controle; o agora é a ponta direita.
    ``ident`` é o pedaço das linhas, o que o tique repinta."""
    atributo = f' id="{ident}"' if ident else ""
    return (f'<div class="mj-faixa cv-faixa"><div class="cv-faixa-topo"><span class="pc-sub">'
            f'Ao vivo</span><span class="cv-30">30 s</span></div>'
            f'<div class="cv-linhas"{atributo}>{linhas_da_faixa(canais, marcas)}</div></div>')


def clima_html(pontos: Sequence[int], limiar: int | None, maximo: int = 10) -> str:
    """O clima da cena: o nível dos últimos instantes numa curva, a linha tracejada no limiar
    (quando a extensão o diz) e «Tenso» quando o agora passa dele."""
    pts = [min(max(int(p), 0), maximo) for p in pontos][-60:]
    if not pts:
        return '<span class="cv-clima-vazio">—</span>'
    if len(pts) == 1:
        pts = pts * 2
    passo = 100 / (len(pts) - 1)
    xy = [(round(i * passo, 2), round(30 - 26 * p / maximo, 2)) for i, p in enumerate(pts)]
    curva = " ".join(f"{x},{y}" for x, y in xy)
    area = f"0,30 {curva} 100,30"
    linha = ""
    if limiar is not None:
        y = round(30 - 26 * min(max(limiar, 0), maximo) / maximo, 2)
        linha = f'<line class="cv-limiar" x1="0" y1="{y}" x2="100" y2="{y}"/>'
    tenso = limiar is not None and pts[-1] >= limiar
    fim = xy[-1]
    return (f'<svg class="cv-clima" viewBox="0 0 100 32" preserveAspectRatio="none" '
            f'aria-hidden="true"><polygon class="cv-area" points="{area}"/>{linha}'
            f'<polyline class="cv-curva" points="{curva}"/>'
            f'<circle class="cv-agora" cx="{fim[0]}" cy="{fim[1]}" r="1.6"/></svg>'
            + ('<span class="cv-tenso">Tenso</span>' if tenso else ""))


def chips_html(vivo: Vivo, gesto: str, mod: str) -> str:
    """Um chip por controle, na cor do plástico; o clique troca o controle do desenho. Com um
    controle só, nenhum chip: não há o que escolher."""
    if len(vivo.controles) < 2:
        return ""
    itens = []
    for n, c in enumerate(vivo.controles):
        valor = str(c.jogador) if c.jogador is not None else f"p{n + 1}"
        on = " on" if c.jogador == vivo.escolhido else ""
        itens.append(f'<span class="cv-pl{on}" style="--plastico:{html.escape(c.cor)}" '
                     f'data-gesto="{gesto}" data-v="{html.escape(mod)}:{valor}" '
                     f'role="button">{html.escape(c.nome)}</span>')
    return f'<div class="cv-pls">{"".join(itens)}</div>'


CSS = """#mod-janela .cv-defs { position:absolute;width:0;height:0;overflow:hidden }
#mod-janela .cv-lugar { display:block;width:100%;max-width:250px;margin:0 auto }
#mod-janela .cv-lugar svg.cv-ds { width:100%;height:auto;display:block }
#mod-janela svg.cv-ds .alvo, #mod-janela svg.cv-ds .alvo * { pointer-events:none !important;cursor:default !important }
#mod-janela svg.cv-ds [data-canal] { transition:opacity .25s }
#mod-janela svg.cv-ds .oculta.cv-aceso { opacity:.95 !important }
#mod-janela svg.cv-ds .cv-aceso { animation:cv-pulsa 1.1s ease-in-out infinite }
#mod-janela svg.cv-ds.foco [data-canal]:not(.oculta) { opacity:.3 }
#mod-janela svg.cv-ds.foco [data-canal].em-foco { opacity:1 !important }
#mod-janela svg.cv-ds.calado { opacity:.45 }
#mod-janela svg.cv-ds.calado .cv-aceso { animation:none }
@keyframes cv-pulsa { 50% { opacity:.5 } }
@media (prefers-reduced-motion:reduce) { #mod-janela svg.cv-ds .cv-aceso { animation:none } }
#mod-janela .cv-pls { display:grid;grid-template-columns:1fr 1fr;gap:5px }
#mod-janela .cv-pl { display:inline-flex;align-items:center;gap:6px;padding:3px 9px;border:1px solid var(--border-forte);border-radius:999px;font-size:11.5px;color:var(--texto-suave);cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis }
#mod-janela .cv-pl::before { content:"";width:8px;height:8px;border-radius:50%;background:var(--plastico);flex:none }
#mod-janela .cv-pl.on { color:var(--fg);border-color:var(--plastico);background:var(--sel-bg, rgba(189,147,249,.16)) }
#mod-janela .cv-pl.dorme { opacity:.5 }
#mod-janela .cv-clima-linha { display:flex;align-items:center;gap:8px;min-height:30px }
#mod-janela .cv-clima-linha .ja-rot { flex:none }
#mod-janela .cv-clima { flex:1;height:30px;display:block;min-width:0 }
#mod-janela .cv-area { fill:rgba(255,184,108,.12) }
#mod-janela .cv-curva { fill:none;stroke:var(--orange);stroke-width:1.4;vector-effect:non-scaling-stroke }
#mod-janela .cv-limiar { stroke:var(--texto-mudo);stroke-dasharray:3 3;stroke-width:1;vector-effect:non-scaling-stroke }
#mod-janela .cv-agora { fill:var(--orange) }
#mod-janela .cv-tenso { font-size:11.5px;color:var(--orange) }
#mod-janela .cv-faixa { border:1px solid var(--border-sutil);border-radius:8px;background:var(--app-bg);padding:7px 12px 8px;display:flex;flex-direction:column;gap:4px }
#mod-janela .cv-faixa-topo { display:flex;align-items:center }
#mod-janela .cv-30 { margin-left:auto;font:500 11px 'JetBrains Mono',monospace;color:var(--texto-mudo) }
#mod-janela .cv-linhas { display:grid;grid-template-columns:118px minmax(0,1fr);gap:3px 10px }
#mod-janela .cv-rot { font-size:11px;color:var(--texto-suave);line-height:12px;white-space:nowrap }
#mod-janela .cv-pista { position:relative;height:12px;border-radius:3px;background:rgba(255,255,255,.03);overflow:hidden }
#mod-janela .cv-mk { position:absolute;top:2px;height:8px;border-radius:4px;background:var(--plastico);min-width:4px }
"""

JS = r"""(function(){
  var ds = null;
  function vestir(){
    var lugar = document.querySelector('#mod-janela .cv-lugar');
    if (!lugar) return;
    if (!ds){
      var molde = document.getElementById('cv-molde');
      if (!molde || !molde.content.firstElementChild) return;
      ds = molde.content.firstElementChild.cloneNode(true);
    }
    if (ds.parentNode !== lugar) lugar.appendChild(ds);
    var claros = (lugar.getAttribute('data-claros') || '').split(' ');
    ds.querySelectorAll('.sobre').forEach(function(g){
      var s = Array.prototype.find.call(g.classList, function(c){ return c.indexOf('s-') === 0; });
      g.classList.toggle('cv-claro', !!s && claros.indexOf(s.slice(2)) >= 0);
    });
    var acesos = (lugar.getAttribute('data-acesos') || '').split(' ');
    ds.querySelectorAll('[data-canal]').forEach(function(g){
      g.classList.toggle('cv-aceso', acesos.indexOf(g.getAttribute('data-canal')) >= 0);
    });
  }
  new MutationObserver(vestir).observe(document.documentElement, {childList:true, subtree:true});
  vestir();
  document.addEventListener('mouseover', function(e){
    if (!ds || !ds.isConnected) return;
    var c = e.target.closest('#mod-janela [data-canal]');
    ds.querySelectorAll('.em-foco').forEach(function(x){ x.classList.remove('em-foco'); });
    if (!c || c.closest('svg')){ ds.classList.remove('foco'); return; }
    var achou = false;
    ds.querySelectorAll('[data-canal="' + c.getAttribute('data-canal') + '"]').forEach(function(x){
      x.classList.add('em-foco'); achou = true;
    });
    ds.classList.toggle('foco', achou);
  });
})();
"""
