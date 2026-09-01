#!/usr/bin/env python3
"""Régua dos ESTADOS: a mesma aba, medida em cada posição do acordeão.

POR QUE ELA EXISTE, e o buraco que ela fecha (28/08/2026). A `regua.py` abre a
página, mede e fecha — **um estado só**, o que vem marcado no HTML. As abas com
acordeão têm CINCO (`Todos`, `P1`…`P4`), e o que rola por dentro muda com eles.

Medido: a Controles, no estado **Todos**, esconde 794px e mostra **um dos
quatro** controles (P1 inteiro, P2 pela metade, P3 e P4 com zero pixel). A
`regua.py` devolvia rc=0 para essa mesma aba, porque no estado que ela visita —
`P1` — não rola nada. É o mesmo defeito que fez a régua ganhar a conta do que
rola por dentro ("na Controles, a aba que É sobre os controles mostrava um e
meio dos quatro"): ele não voltou, ele nunca saiu — mudou de estado.

Ela NÃO reprova: quanto cada estado pode esconder é decisão de desenho, e é
dela. Esta régua põe o número na mesa, aba por aba e estado por estado.

Uso:  regua_estados.py 02-controles.html 08-conexoes.html
      regua_estados.py            # todas as que têm acordeão
"""
import pathlib
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import onde  # noqa: E402

# MEDE A BANCADA (`mockup/`) — 31/08/2026. Este caminho era `parent.parent`,
# que resolvia para `layout/`; apontá-lo lá hoje mediria a página congelada.
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
        # SEM `--hide-scrollbars`: o Playwright liga essa bandeira por padrão, e
        # ela esconde justamente a barra que diz que há mais coisa embaixo.
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
