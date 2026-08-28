#!/usr/bin/env python3
"""PORTÃO — o desenho, o nome e o glifo de cada peça do DualSense concordam?

O defeito que ele existe para pegar: o SVG chamava de `l2` e `r2` duas peças que
são o Share e o Options. Elas ficam ao lado do touchpad; o gatilho não fica. Isso
atravessou dois meses porque nenhuma régua comparava o NOME da peça com o LUGAR
dela — e quem viu foi ela, passando o mouse por cima, em 27/08/2026.

Fonte da verdade: docs/data/pecas-do-dualsense.csv
Mapa que ele mede:  novo-layout/mapa-do-controle.html (gerado por _ferramentas/mapa.py)

A régua do mapa — o cruzamento tem de valer nos DOIS sentidos, peça a peça.

Duas versões desta régua já mentiram, e as duas pela mesma causa: MIRAVAM ERRADO.
  1. o centro do bbox — no giroscópio o centro é o PS, que mora dentro dele;
  2. 12% da caixa — no L1 esse ponto cai dentro do alvo do L2, que é menor e por
     isso nasce por cima.
Agora ela VARRE uma grade dentro da caixa e aceita o primeiro ponto onde o alvo
daquela peça é quem recebe o ponteiro. Se nenhum ponto serve, aí sim é falha: a
peça está inteiramente coberta e ninguém consegue apontá-la.
"""
import sys, csv, pathlib
from playwright.sync_api import sync_playwright

R = pathlib.Path("/mnt/Apate/Desenvolvimento/hefesto-dualsense4unix")
ROSA = "rgb(255, 121, 198)"
PINTAVEL = ":is(.peca, rect, circle, path, ellipse)"

linhas = [l for l in (R / "docs/data/pecas-do-dualsense.csv").read_text().splitlines()
          if l and not l.startswith("#")]
pecas = list(csv.DictReader(linhas))
falhas = []

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1920, "height": 1080})
    pg.goto(f"file://{R}/novo-layout/mapa-do-controle.html")
    pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(400)
    print(f"=== o mapa · {len(pecas)} peças, cruzamento nos dois sentidos ===")
    for p in pecas:
        i = p["id"]; desenhada = p["x1"] != "-"
        pg.hover(f".item-{i}"); pg.wait_for_timeout(70)
        # O PS não tem tinta na PEÇA: o glifo é o botão (decisão dela, 27/08), e
        # portanto quem tem de acender é o glifo. A régua olha os dois e aceita
        # qualquer um — senão reprovaria a peça justamente por ela estar certa.
        ida = pg.evaluate(f"""() => {{const e=document.querySelector('#mp-{i} {PINTAVEL}');
            const g=document.querySelector('.s-{i}');
            const acesa = e && (getComputedStyle(e).stroke==='{ROSA}' || getComputedStyle(e).fill==='{ROSA}');
            const glifo = g && getComputedStyle(g).color==='rgb(248, 248, 242)';
            return (e||g) ? !!(acesa || glifo) : null;}}""")
        # As peças cuja região É o corpo (giroscópio e acelerômetro) não têm alvo
        # próprio: três alvos sobre a mesma área viram sorteio. Elas acendem pela
        # lista, que é o sentido que importa. Está escrito no gerador, em SEM_ALVO.
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

    # NENHUMA LINHA PODE CAIR FORA DA CAIXA. A linha "Corpo" ficou invisível e
    # inalcançável por semanas — a lista transbordava para uma coluna recortada,
    # e recorte também mata o hit-test. Contar itens não pegava: eram 28 no DOM.
    fora = pg.evaluate("""() => {const cx=document.querySelector('.cx').getBoundingClientRect();
      return [...document.querySelectorAll('.item')].filter(e=>{const b=e.getBoundingClientRect();
        return b.right>cx.right+1 || b.left<cx.left-1 || b.width===0;})
        .map(e=>[...e.classList].find(c=>c.startsWith('item-')));}""")
    falhas.extend(fora)
    print(("  OK   " if not fora else "  FALHA") + f" toda linha da lista cabe na caixa — fora: {fora}")

    # NO HOVER, O GLIFO NÃO PODE SUMIR. Ele estava CRAVADO em cinza claro — a
    # troca para `currentColor` só cobria dois hexadecimais, e o glifo escrito com
    # outra cor ficava com a dele. Sobre a peça acesa em rosa, sumia por baixo
    # contraste. Ela viu antes de qualquer régua: "ao passar o mouse em cima de um
    # botão o glifo some."
    CLARO = "rgb(248, 248, 242)"
    somem = []
    for k in pg.evaluate("() => [...document.querySelectorAll('.sobre')]"
                         ".map(g=>[...g.classList].find(c=>c.startsWith('s-')).slice(2))"):
        pg.hover(f".item-{k}"); pg.wait_for_timeout(80)
        # TODOS os descendentes, não só o primeiro: o glifo do PS que ela desenhou
        # tem o path dentro de um <g> de transform, e olhar só o primeiro filho
        # encontra o grupo — que não pinta nada — em vez da tinta.
        v = pg.evaluate(f"""() => {{const g=document.querySelector('.s-{k}');
          const cores=[];
          g.querySelectorAll('*').forEach(e=>{{ if(e.tagName==='svg'||e.tagName==='g') return;
            const cs=getComputedStyle(e); cores.push(cs.stroke, cs.fill); }});
          return cores.length?cores:null;}}""")
        if not v or CLARO not in v:
            somem.append(k)
    falhas.extend(somem)
    print(("  OK   " if not somem else "  FALHA")
          + f" o glifo continua visível no hover — some em: {somem}")

    no_svg = pg.evaluate("() => [...document.querySelectorAll('.ds g[id]')].map(e=>e.id.replace('mp-',''))")
    b.close()

ids = {p["id"] for p in pecas}
# os `grupo-*` organizam a árvore no editor dela e os `glifo-*` são os símbolos:
# nenhum dos dois é PEÇA, e por isso não têm linha na fonte da verdade.
sobra = [x for x in no_svg if x not in ids
         and not x.startswith(("led-jogador-", "titulo", "grupo-", "glifo-"))]
falta = [p["id"] for p in pecas if p["no_svg"] not in ("falta", "") and p["no_svg"] not in no_svg]
print()
print(("  OK   " if not sobra else "  FALHA") + f" toda peça do SVG está no CSV — fora: {sobra}")
print(("  OK   " if not falta else "  FALHA") + f" todo id do CSV existe no SVG — fora: {falta}")
sys.exit(1 if (falhas or sobra or falta) else 0)
