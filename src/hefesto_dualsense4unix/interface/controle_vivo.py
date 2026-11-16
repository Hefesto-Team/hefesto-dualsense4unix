"""O controle vivo da janela de uma extensão: o desenho do Mapa dos controles com as peças que
a extensão mexe acesas, o clima da cena e a faixa «Ao vivo», uma linha por canal escrito.

O desenho é o MESMO do Mapa (``mapa.controle``, com as cores, os glifos e as ondas da háptica de lá,
e as regras de tinta do ``mapa.CSS_BASE``): nenhuma cópia redesenhada. Ele entra uma vez na página
publicada, num ``<template>``, e a janela o põe no lugar e acende as peças pelo que a extensão
escreveu de fato.
"""
from __future__ import annotations

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
JUNTA_MS = 600

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
    x = x.replace("<svg ", '<svg data-colorway="" ', 1)
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
    zonas = mapa.css_da_zona([p["id"] for p in mapa.le_csv()]) + "\n" + mapa.css_do_contraste()
    zonas = zonas.replace(".mc svg.ds", f"{escopo} svg.cv-ds")
    tintas = re.search(r"--luz-apagada:[^;]+;\s*--led-apagado:[^;]+;\s*--led-aceso:[^;]+;"
                       r"\s*--sem-plastico:[^;]+;", mapa.CSS_BASE)
    branco = re.search(r"--branco:[^;]+;", mapa.CSS_BASE)
    if not tintas or not branco:
        raise ValueError("as cores do desenho sumiram do mapa.CSS_BASE")
    variaveis = f"{escopo} svg.cv-ds{{{branco.group(0)}{' '.join(tintas.group(0).split())}}}"
    pinta = ":is(.peca, rect, circle, path, ellipse){fill:var(--%s) !important;stroke:var(--%s) !important}"
    acesas = [f"{escopo} svg.cv-ds #mp-{peca}.cv-aceso {pinta % ('pink', 'pink')}\n"
              f"{escopo} svg.cv-ds.foco #mp-{peca}.em-foco {pinta % ('cyan', 'cyan')}"
              for pecas in PECAS_DO_CANAL.values() for peca in pecas]
    return "\n".join([variaveis, *regras, zonas.strip(), *acesas]) + "\n"


def acesos_de(marcas: Iterable[Marca], agora_ms: int = 0) -> set[str]:
    """Os canais com escrita nos últimos ``ACESO_POR_MS``."""
    return {m.canal for m in marcas if m.ate_ms - agora_ms <= ACESO_POR_MS}


def juntar(escritas: Iterable[tuple[str, int]], cor: str) -> list[Marca]:
    """As escritas ``(canal, ha_ms)`` de um controle em trechos: as de um canal a menos de
    ``JUNTA_MS`` uma da outra viram um trecho só."""
    por_canal: dict[str, list[int]] = {}
    for canal, ha in escritas:
        if canal in ROTULO_DO_CANAL and 0 <= ha <= JANELA_DA_FAIXA_MS:
            por_canal.setdefault(canal, []).append(int(ha))
    marcas: list[Marca] = []
    for canal, has in por_canal.items():
        has.sort(reverse=True)
        de = ate = has[0]
        for ha in has[1:]:
            if ate - ha <= JUNTA_MS:
                ate = ha
                continue
            marcas.append(Marca(canal, de, ate, cor))
            de = ate = ha
        marcas.append(Marca(canal, de, ate, cor))
    return marcas


def _pct(ha_ms: int) -> float:
    return round(100 - 100 * min(max(ha_ms, 0), JANELA_DA_FAIXA_MS) / JANELA_DA_FAIXA_MS, 2)


def faixa_html(canais: Sequence[str], marcas: Iterable[Marca], *, ident: str = "") -> str:
    """A faixa «Ao vivo»: uma linha por canal que a extensão pode escrever, com o que a extensão
    escreveu nos últimos 30 s, na cor do plástico de cada controle; o agora é a ponta direita."""
    por_canal: dict[str, list[Marca]] = {}
    for m in marcas:
        por_canal.setdefault(m.canal, []).append(m)
    linhas = []
    for canal in canais:
        trechos = "".join(
            f'<i class="cv-mk" style="left:{_pct(m.de_ms)}%;'
            f'width:{max(_pct(m.ate_ms) - _pct(m.de_ms), 0.6)}%;--plastico:{html.escape(m.cor)}"></i>'
            for m in por_canal.get(canal, ()))
        linhas.append(
            f'<span class="cv-rot" data-canal="{canal}">{ROTULO_DO_CANAL[canal]}</span>'
            f'<span class="cv-pista" data-canal="{canal}">{trechos}</span>')
    atributo = f' id="{ident}"' if ident else ""
    return (f'<div class="mj-faixa cv-faixa"><div class="cv-faixa-topo"><span class="pc-sub">'
            f'Ao vivo</span><span class="cv-30">30 s</span></div>'
            f'<div class="cv-linhas" style="--cv-n:{max(len(canais), 1)}"{atributo}>'
            f'{"".join(linhas)}</div></div>')


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


def chips_html(controles: Sequence[Mapping[str, Any]], escolhido: str, gesto: str, mod: str) -> str:
    """Um chip por controle, na cor do plástico; o clique troca o controle do desenho."""
    if len(controles) < 2:
        return ""
    itens = []
    for c in controles:
        ident = html.escape(str(c.get("id") or ""))
        nome = html.escape(str(c.get("nome") or ""))
        cor = html.escape(str(c.get("cor") or "var(--texto-mudo)"))
        on = " on" if c.get("id") == escolhido else ""
        dorme = " dorme" if c.get("ligado") is False else ""
        itens.append(f'<span class="cv-pl{on}{dorme}" style="--plastico:{cor}" data-gesto="{gesto}" '
                     f'data-v="{html.escape(mod)}" data-controle="{ident}">{nome}</span>')
    return f'<div class="cv-pls">{"".join(itens)}</div>'


CSS = """#mod-janela .cv-lugar { display:block;width:100%;max-width:250px;margin:0 auto }
#mod-janela .cv-lugar svg.cv-ds { width:100%;height:auto;display:block }
#mod-janela svg.cv-ds .alvo, #mod-janela svg.cv-ds .alvo * { pointer-events:none;cursor:default }
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
  function oDesenho(){ return document.querySelector('#mod-janela .cv-ds'); }
  document.addEventListener('mouseover', function(e){
    var ds = oDesenho(); if (!ds) return;
    var c = e.target.closest('#mod-janela [data-canal]');
    var dentro = c && c.closest('svg');
    ds.querySelectorAll('.em-foco').forEach(function(x){ x.classList.remove('em-foco'); });
    if (!c || dentro){ ds.classList.remove('foco'); return; }
    var canal = c.getAttribute('data-canal');
    var achou = false;
    ds.querySelectorAll('[data-canal="' + canal + '"]').forEach(function(x){ x.classList.add('em-foco'); achou = true; });
    ds.classList.toggle('foco', achou);
  });
})();
"""
