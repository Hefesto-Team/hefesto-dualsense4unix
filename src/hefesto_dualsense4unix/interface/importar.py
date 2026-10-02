#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""O CAMINHO DE VOLTA: lê o SVG que ela arrumou e traz para o mapa."""
import csv, io, pathlib, re, subprocess, sys

import sys as _sys, pathlib as _pathlib
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parent))
from onde import RAIZ as R  # noqa: E402

DADOS_DO_REPO = R / "docs/data"
LIMPO = R / "src/hefesto_dualsense4unix/interface/ds_limpo.svg"
PROD = R / "assets/control-svg/dualsense.svg"
CSV = DADOS_DO_REPO / "pecas-do-dualsense.csv"


def svg_editado() -> pathlib.Path:
    """A OUTRA PONTA DO MESMO CAMINHO — casa com `exportar.svg_para_editar()`."""
    return pathlib.Path.home() / "Imagens" / "dualsense-para-editar.svg"


def grupos(texto):
    """Os grupos com id, e o conteúdo de desenho de cada um."""
    fora = {}
    for m in re.finditer(r'<g\b[^>]*\bid="([^"]+)"[^>]*>', texto):
        pid = m.group(1)
        if pid.startswith("grupo-") or pid == "fundo":
            continue
        i = m.start()
        prof, j = 0, i
        while True:
            n = re.search(r"<g\b|</g>", texto[j:])
            if not n:
                break
            j += n.end()
            prof += 1 if n.group(0) == "<g" else -1
            if prof == 0:
                break
        fora[pid] = texto[i:j]
    return fora


def medir_matriz(caminho):
    """A matriz de cada glifo no espaço do viewBox, e o `--lado` que ele declara."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 1200, "height": 900})
        pg.goto(f"file://{caminho}")
        pg.wait_for_timeout(500)
        r = pg.evaluate("""() => {const R=n=>Math.round(n*100000)/100000, o={};
          const raiz=document.querySelector('svg');
          document.querySelectorAll('[id^="glifo-"]').forEach(g=>{
            const m = raiz.getScreenCTM().inverse().multiply(g.getScreenCTM());
            const lado = getComputedStyle(g).getPropertyValue('--lado').trim();
            o[g.id.slice(6)] = {
              transform: `matrix(${R(m.a)},${R(m.b)},${R(m.c)},${R(m.d)},${R(m.e)},${R(m.f)})`,
              lado: parseFloat(lado) || 5.2};});
          return o;}""")
        b.close()
    return r


def medir_glifo_contra_peca(caminho):
    """Quantos px separam o centro de cada glifo do centro da peça dele."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 1200, "height": 900})
        pg.goto(f"file://{caminho}")
        pg.wait_for_timeout(500)
        r = pg.evaluate("""() => {const o={};
          document.querySelectorAll('[id^="glifo-"]').forEach(g=>{
            const pid=g.id.slice(6);
            const p=document.getElementById(pid); if(!p) return;
            const a=g.getBoundingClientRect(), z=p.getBoundingClientRect();
            if(!a.width || !z.width) return;
            o[pid]=Math.hypot((a.x+a.width/2)-(z.x+z.width/2),
                              (a.y+a.height/2)-(z.y+z.height/2));});
          return o;}""")
        b.close()
    return r


def medir_no_mapa():
    """Quais glifos ficaram longe da peça DEPOIS de o mapa ser gerado."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        pg.goto(f"file://{R}/layout/mapa-do-controle.html")
        pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(500)
        r = pg.evaluate("""() => {const o={};
          document.querySelectorAll('.sobre').forEach(g=>{
            const id=[...g.classList].find(c=>c.startsWith('s-')).slice(2);
            const p=document.getElementById('mp-'+id); if(!p) return;
            const a=g.getBoundingClientRect(), z=p.getBoundingClientRect();
            const d=Math.hypot((a.x+a.width/2)-(z.x+z.width/2),(a.y+a.height/2)-(z.y+z.height/2));
            if(d>4) o[id]=Math.round(d*10)/10;});
          return o;}""")
        b.close()
    return r


def caixas(caminho):
    """A caixa de cada peça, medida no navegador — é o único jeito honesto."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 1200, "height": 900})
        pg.goto(f"file://{caminho}")
        pg.wait_for_timeout(500)
        r = pg.evaluate("""() => {const R=n=>Math.round(n*100)/100, o={};
          const raiz = document.querySelector('svg');
          document.querySelectorAll('svg g[id]').forEach(g=>{
            if(g.id.startsWith('grupo-') || g.id.startsWith('glifo-')) return;
            let b; try{ b=g.getBBox(); }catch(e){ return; }
            if(!b.width && !b.height) return;
            // A CAIXA NO ESPAÇO DO SVG, não no espaço local do grupo.
            // Ela fez o L1 e o L2 espelhando os direitos com uma matriz; lendo o
            // bbox local, os dois voltavam com as coordenadas do LADO DIREITO —
            // e o CSV teria gravado o L1 em cima do R1.
            // do espaço LOCAL do grupo para o espaço do viewBox: a tela é a
            // única referência comum, e as duas pontas se cancelam nela.
            const m = raiz.getScreenCTM().inverse().multiply(g.getScreenCTM());
            const pt = (x,y) => { const p=raiz.createSVGPoint(); p.x=x; p.y=y;
                                  return p.matrixTransform(m); };
            const cs = [pt(b.x,b.y), pt(b.x+b.width,b.y),
                        pt(b.x,b.y+b.height), pt(b.x+b.width,b.y+b.height)];
            const xs = cs.map(p=>p.x), ys = cs.map(p=>p.y);
            o[g.id]=[R(Math.min(...xs)),R(Math.min(...ys)),
                     R(Math.max(...xs)),R(Math.max(...ys))];});
          return o;}""")
        b.close()
    return r


def main():
    gravar = "--gravar" in sys.argv
    if not svg_editado().exists():
        sys.exit(f"não achei {svg_editado()} — rode o exportar.py primeiro")

    import xml.etree.ElementTree as ET
    try:
        ET.parse(svg_editado())
    except Exception as exc:
        sys.exit(f"o SVG editado não é XML válido: {exc}\n"
                 "nada foi lido. Conserte no editor e salve de novo.")

    novo = grupos(svg_editado().read_text())
    velho = grupos(LIMPO.read_text())
    faltam = [k for k in velho if k not in novo]
    if faltam:
        sys.exit(f"o arquivo editado perdeu peças: {faltam}\n"
                 "os `id` dos grupos não podem ser renomeados nem apagados.")

    cx_novo, cx_velho = caixas(svg_editado()), caixas(LIMPO)
    mudou = {k: (cx_velho.get(k), cx_novo[k]) for k in cx_novo
             if cx_velho.get(k) != cx_novo[k]}
    print(f"=== {len(novo)} peças lidas · {len(mudou)} mudaram de lugar ===")
    for k, (a, z) in sorted(mudou.items()):
        print(f"  {k:22} {a} -> {z}")
    if not mudou:
        print("  nada mudou.")
        return
    if not gravar:
        print("\n(nada foi gravado — rode com --gravar)")
        return

    for pid in [k for k in novo if k.startswith("feat-")]:
        novo[pid] = re.sub(r'\s(opacity="[^"]*"|style="[^"]*opacity[^"]*")', "",
                           novo[pid], count=1)

    for alvo in (LIMPO, PROD):
        s = alvo.read_text()
        for pid, bloco in novo.items():
            if pid not in velho:
                if pid.startswith("glifo-"):
                    s = s.replace("</svg>", "  " + bloco + "\n</svg>", 1)
                continue
            i = s.index(f'id="{pid}"'); ini = s.rindex("<g ", 0, i)
            prof, j = 0, ini
            while True:
                n = re.search(r"<g\b|</g>", s[j:])
                if not n:
                    break
                j += n.end(); prof += 1 if n.group(0) == "<g" else -1
                if prof == 0:
                    break
            s = s[:ini] + bloco + s[j:]
        alvo.write_text(s)
        print(f"  ok  {alvo.name}")
    subprocess.run(["cp", str(LIMPO), "/tmp/ds_limpo.svg"], check=True)

    _glifos = medir_matriz(svg_editado())
    t = CSV.read_text()
    for pid, cx in cx_novo.items():
        alvo = [l for l in t.splitlines() if l.startswith(pid + ",")]
        if not alvo:
            continue
        c = next(csv.reader([alvo[0]]))
        c[7], c[8], c[9], c[10] = (f"{v}" for v in cx)
        buf = io.StringIO(); csv.writer(buf, lineterminator="").writerow(c)
        t = t.replace(alvo[0], buf.getvalue())
    CSV.write_text(t)
    print(f"  ok  {CSV.name}")

    subprocess.run([sys.executable, str(R / "scripts/gerar_cores_do_dualsense.py")],
                   check=True)

    print("\nagora: python3 mapa.py && ../../.venv/bin/python "
          "../../scripts/check_pecas_do_dualsense.py "
          "&& ../../.venv/bin/python ../../scripts/check_cores_do_dualsense.py")


if __name__ == "__main__":
    main()
