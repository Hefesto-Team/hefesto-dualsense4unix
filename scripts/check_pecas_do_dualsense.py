#!/usr/bin/env python3
"""PORTÃO — o desenho, o nome e o glifo de cada peça do DualSense concordam?

O defeito que ele existe para pegar: o SVG chamava de `l2` e `r2` duas peças que
são o Share e o Options. Essas ficam ao lado do touchpad; o gatilho não fica. Isso
atravessou dois meses porque nenhuma régua comparava o NOME da peça com o seu LUGAR
no desenho — e o defeito apareceu ao passar o mouse por cima, em 27/08/2026.

Fonte da verdade: docs/data/pecas-do-dualsense.csv
Mapa que ele mede:  o publicado, que quem diz onde é `interface/onde.py`
                    (gerado por `interface/mapa.py`)

A régua do mapa — o cruzamento tem de valer nos DOIS sentidos, peça a peça.

Duas versões desta régua já mentiram, e as duas pela mesma causa: MIRAVAM ERRADO.
  1. o centro do bbox — no giroscópio o centro é o PS, que mora dentro dele;
  2. 12% da caixa — no L1 esse ponto cai dentro do alvo do L2, que é menor e por
     isso nasce por cima.
Agora a régua VARRE uma grade dentro da caixa e aceita o primeiro ponto onde o alvo
daquela peça é quem recebe o ponteiro. Se nenhum ponto serve, aí sim é falha: a
peça está inteiramente coberta e ninguém consegue apontá-la.
"""
import sys, csv, pathlib, re
from playwright.sync_api import sync_playwright

R = pathlib.Path(__file__).resolve().parents[1]

import sys as _sys
_sys.path.insert(0, str(R / "src"))
from hefesto_dualsense4unix.interface import onde as _onde
from hefesto_dualsense4unix.interface.mapa import SEM_BOTAO
from hefesto_dualsense4unix.interface.olhar import abrir_pronta
_MAPA = _onde.PUBLICADO / "mapa-do-controle.html"
ROSA = "rgb(255, 121, 198)"
PINTAVEL = ":is(.peca, rect, circle, path, ellipse)"

linhas = [l for l in (R / "docs/data/pecas-do-dualsense.csv").read_text().splitlines()
          if l and not l.startswith("#")]
pecas = list(csv.DictReader(linhas))
falhas = []

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1920, "height": 1080})
    abrir_pronta(pg, _MAPA.as_uri(), lambda **ir: pg.goto(f"file://{_MAPA}", **ir), seletor=".cx")
    print(f"=== o mapa · {len(pecas)} peças, cruzamento nos dois sentidos ===")
    for p in pecas:
        i = p["id"]; desenhada = p["x1"] != "-"
        if i in SEM_BOTAO:
            voltou = pg.evaluate(f"() => !!document.querySelector('.item-{i}, .a-{i}')")
            if voltou:
                falhas.append(i)
            print(("  FALHA" if voltou else "  OK   ") + f" {i:22} sem linha e sem alvo (não é botão)")
            continue
        if not pg.evaluate(f"() => !!document.querySelector('.item-{i}')"):
            print(f"  OK   {i:22} sem linha no mapa (mora em outra aba)")
            continue
        pg.hover(f".item-{i}"); pg.wait_for_timeout(70)
        ida = pg.evaluate(f"""() => {{const e=document.querySelector('#mp-{i} {PINTAVEL}');
            const g=document.querySelector('.s-{i}');
            const acesa = e && (getComputedStyle(e).stroke==='{ROSA}' || getComputedStyle(e).fill==='{ROSA}');
            const glifo = g && getComputedStyle(g).color==='rgb(248, 248, 242)';
            return (e||g) ? !!(acesa || glifo) : null;}}""")
        SEM_ALVO = {"feat-giroscopio", "feat-acelerometro", "feat-bateria"}
        volta = None
        if desenhada and i not in SEM_ALVO:
            ponto = pg.evaluate(f"""() => {{
              const alvos=[...document.querySelectorAll('.a-{i}')];
              for (const a of alvos) {{
                const b=a.getBoundingClientRect();
                for (let fy=0.04; fy<=0.96; fy+=0.06)
                  for (let fx=0.04; fx<=0.96; fx+=0.06) {{
                    const x=b.x+b.width*fx, y=b.y+b.height*fy;
                    const el=document.elementFromPoint(x,y);
                    // `closest`, e não `classList`: o alvo passou a ser a FORMA da
                    // peça, um <g> com o desenho dentro — e o ponteiro pousa no
                    // <path> filho, que não carrega a classe. Sem isso a régua
                    // reprovava as 27 peças com o alvo perfeito.
                    if (el && el.closest && el.closest('.a-{i}')) return [x,y];
                  }}
              }}
              return null;}}""")
            if ponto:
                pg.mouse.move(ponto[0], ponto[1]); pg.wait_for_timeout(70)
                volta = pg.evaluate(f"() => getComputedStyle(document.querySelector('.item-{i}')).borderTopColor==='{ROSA}'")
            else:
                volta = False
        ok = (ida is not False) and (volta is not False)
        if not ok: falhas.append(i)
        print(("  OK   " if ok else "  FALHA") + f" {i:22} glifo→peça={ida}  peça→glifo={volta}")

    abrir_pronta(pg, _MAPA.as_uri(), lambda **ir: pg.reload(**ir), seletor=".cx")
    fora = pg.evaluate("""() => {const cx=document.querySelector('.cx').getBoundingClientRect();
      return [...document.querySelectorAll('.item')].filter(e=>{const b=e.getBoundingClientRect();
        return b.right>cx.right+1 || b.left<cx.left-1 || b.width===0;})
        .map(e=>[...e.classList].find(c=>c.startsWith('item-')));}""")
    falhas.extend(fora)
    print(("  OK   " if not fora else "  FALHA") + f" toda linha da lista cabe na caixa — fora: {fora}")

    def luz(rgb):
        r, g, b = (int(n) / 255 for n in re.findall(r"\d+", rgb)[:3])
        lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    def contraste(a, b):
        x, y = sorted((luz(a), luz(b)), reverse=True)
        return (x + 0.05) / (y + 0.05)

    CLARO = "rgb(248, 248, 242)"
    ESCURO = pg.evaluate("""() => {const d=document.createElement('div');
      d.style.color='var(--app-bg)'; document.body.appendChild(d);
      const c=getComputedStyle(d).color; d.remove(); return c;}""")
    somem = []
    for k in pg.evaluate("() => [...document.querySelectorAll('.sobre')]"
                         ".map(g=>[...g.classList].find(c=>c.startsWith('s-')).slice(2))"):
        if not pg.evaluate(f"() => !!document.querySelector('.item-{k}')"):
            continue
        pg.hover(f".item-{k}"); pg.wait_for_timeout(80)
        v = pg.evaluate(f"""() => {{const g=document.querySelector('.s-{k}');
          const p=document.querySelector('#mp-{k} {PINTAVEL}');
          const cores=[];
          g.querySelectorAll('*').forEach(e=>{{ if(['svg','g','title','desc'].includes(e.tagName)) return;
            const cs=getComputedStyle(e); cores.push(cs.stroke, cs.fill); }});
          return cores.length?[p?getComputedStyle(p).fill:null, cores]:null;}}""")
        rgb = [c for c in (v[1] if v else []) if c.startswith("rgb(")]
        if not v or not v[0] or not v[0].startswith("rgb(") or not rgb:
            somem.append(k)
            continue
        melhor = max(contraste(CLARO, v[0]), contraste(ESCURO, v[0]))
        if max(contraste(c, v[0]) for c in rgb) < melhor * 0.95:
            somem.append(k)
    falhas.extend(somem)
    print(("  OK   " if not somem else "  FALHA")
          + f" o glifo segue visível no hover, na cor de maior contraste com a peça — falha em: {somem}")

    no_svg = pg.evaluate("() => [...document.querySelectorAll('.ds g[id]')].map(e=>e.id.replace('mp-',''))")
    b.close()

ids = {p["id"] for p in pecas}
sobra = [x for x in no_svg if x not in ids
         and not x.startswith(("led-jogador-", "titulo", "grupo-", "glifo-"))]
falta = [p["id"] for p in pecas if p["no_svg"] not in ("falta", "") and p["no_svg"] not in no_svg]
print()
print(("  OK   " if not sobra else "  FALHA") + f" toda peça do SVG está no CSV — fora: {sobra}")
print(("  OK   " if not falta else "  FALHA") + f" todo id do CSV existe no SVG — fora: {falta}")
sys.exit(1 if (falhas or sobra or falta) else 0)
