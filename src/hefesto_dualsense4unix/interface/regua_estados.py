#!/usr/bin/env python3
"""Régua dos ESTADOS: a mesma aba, medida em cada posição do acordeão."""
import pathlib
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import onde  # noqa: E402

D = onde.BANCADA

SONDA = r"""
() => {
  const R = o => Math.round(o * 10) / 10;
  const out = [];
  document.querySelectorAll('.miolo, .miolo *').forEach(e => {
    const cs = getComputedStyle(e), esconde = e.scrollHeight - e.clientHeight;
    if (esconde <= 2 || e.clientHeight === 0) return;
    // SÓ QUEM ROLA DE VERDADE: `scrollHeight > clientHeight` também é verdade
    // num elemento de `overflow:visible`, que não esconde nada — o filho
    // simplesmente transborda à vista. Sem este filtro a régua acusa as barras
    // de bateria de cada aba.
    if (!/auto|scroll/.test(cs.overflowY)) return;
    const b = e.getBoundingClientRect();
    const filhos = [...e.children].map(k => {
      const r = k.getBoundingClientRect();
      // O CLIPE É NA PADDING BOX, não na content box: o `padding-bottom` de uma
      // caixa que rola continua mostrando o conteúdo que passa por ele. Medido
      // com `elementFromPoint` nos 18px finais do miolo da Conexões — há texto
      // pintado ali. Descontar o padding acusaria um sumiço que não existe.
      const vis = Math.max(0, Math.min(r.bottom, b.bottom) - Math.max(r.top, b.top));
      const rot = k.querySelector('.quadro-titulo, .card-nome, .gc-nome, h2, h3');
      return {quem: (rot ? rot.textContent : (k.className || k.tagName))
                    .toString().trim().replace(/\s+/g, ' ').slice(0, 30),
              h: R(r.height), visivel: R(vis),
              pct: r.height ? Math.round(100 * vis / r.height) : null};
    }).filter(k => k.h > 5);
    out.push({onde: (e.className || e.tagName).toString().split(' ')[0],
              esconde: R(esconde), filhos: filhos});
  });
  return out;
}
"""


def estados(pg):
    """Os rádios que comandam o acordeão, na ordem em que aparecem."""
    return pg.evaluate(
        "() => [...document.querySelectorAll('input[type=radio]')].map(r => r.id)")


def medir(pg, arq):
    linhas, ruim = [], False
    ids = estados(pg) or [None]
    for i in ids:
        if i:
            pg.evaluate(f'() => document.getElementById("{i}").click()')
            pg.wait_for_timeout(250)
        for caixa in pg.evaluate(SONDA):
            for k in caixa["filhos"]:
                if k["pct"] == 100:
                    continue
                ruim = ruim or k["pct"] == 0
                linhas.append(f'   [{i or "único"}] {caixa["onde"]} esconde '
                              f'{caixa["esconde"]}px · "{k["quem"]}" mostra '
                              f'{k["visivel"]} de {k["h"]}px ({k["pct"]}%)'
                              + ("  <<< ZERO" if k["pct"] == 0 else ""))
    print(f"\n=== {arq} === {len(ids)} estado(s)")
    for x in linhas:
        print(x)
    if not linhas:
        print("   ✓ em todos os estados, tudo o que existe aparece inteiro")
    return ruim


if __name__ == "__main__":
    alvos = sys.argv[1:] or sorted(p.name for p in D.glob("[0-9][0-9]-*.html"))
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/usr/bin/google-chrome",
                               args=["--no-sandbox"],
                               ignore_default_args=["--hide-scrollbars"])
        for arq in alvos:
            pg = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
            pg.goto(f"file://{D / arq}")
            pg.wait_for_load_state("networkidle")
            pg.add_style_tag(content=".nota{display:none}")
            pg.wait_for_timeout(300)
            medir(pg, arq)
            pg.close()
        b.close()
