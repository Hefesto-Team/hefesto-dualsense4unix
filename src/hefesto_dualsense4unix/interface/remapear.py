#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Devolve ids e agrupamentos ao SVG que ELA editou, sem tocar na geometria."""
import pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from onde import RAIZ as R  # noqa: E402

DADOS_DO_REPO = R / "docs/data"


def bloco_do_grupo(s, i):
    """Do `<g` que abre em `i` até o `</g>` que o fecha."""
    prof, j = 0, i
    while True:
        n = re.search(r"<g\b|</g>", s[j:])
        if not n:
            return len(s)
        j += n.end()
        prof += 1 if n.group(0) == "<g" else -1
        if prof == 0:
            return j


def renomeia(s, de, para, extra=""):
    i = s.index(f'id="{de}"')
    ini = s.rindex("<g ", 0, i)
    fim = s.index(">", ini)
    cab = s[ini:fim]
    cab = re.sub(r'\bid="[^"]*"', f'id="{para}"', cab)
    cab = re.sub(r'\sdata-entrada="[^"]*"', "", cab)
    cab = re.sub(r'\sdata-feature="[^"]*"', "", cab)
    return s[:ini] + cab + f' data-entrada="{para}"{extra}' + s[fim:]


def envolve(s, achador, pid, titulo, extra=""):
    """Põe um elemento solto dentro de um <g> com id e title."""
    m = achador(s)
    if not m:
        return s, False
    return (s[:m.start()]
            + f'<g id="{pid}" data-entrada="{pid}"{extra}><title>{titulo}</title>'
            + m.group(0) + "</g>" + s[m.end():], True)


def main():
    if len(sys.argv) < 2:
        sys.exit("uso: remapear.py <svg-dela> [--gravar]")
    alvo = pathlib.Path(sys.argv[1])
    s = alvo.read_text()
    feito = []

    for de, para, ex in (("group-1", "l1", ""),
                         ("group-3", "l2", ' data-feature="gatilho-adaptativo-esquerdo"')):
        if f'id="{de}"' in s:
            s = renomeia(s, de, para, ex)
            feito.append(f"{de} -> {para}")

    def acha_stick_r(t):
        """O <path> do analógico direito, solto dentro de grupo-analogicos."""
        i = t.index('id="grupo-analogicos"')
        ini = t.rindex("<g ", 0, i)
        fim = bloco_do_grupo(t, ini)
        dentro_de_stick_l = None
        if 'id="stick_l"' in t[ini:fim]:
            k = t.index('id="stick_l"', ini)
            k0 = t.rindex("<g ", 0, k)
            dentro_de_stick_l = (k0, bloco_do_grupo(t, k0))
        for m in re.finditer(r"<path\b[^>]*?/>", t[ini:fim]):
            a0 = ini + m.start()
            if dentro_de_stick_l and dentro_de_stick_l[0] <= a0 < dentro_de_stick_l[1]:
                continue
            d = re.search(r'\sd="\s*M\s+(-?[\d.]+)', m.group(0))
            if d and float(d.group(1)) > 64:
                class M:
                    pass
                r = M()
                r.start = lambda a0=a0: a0
                r.end = lambda m=m: ini + m.end()
                r.group = lambda *_, m=m: m.group(0)
                return r
        return None
    s, ok = envolve(s, acha_stick_r, "stick_r", "Analógico Direito (R3)", ' data-clique="r3"')
    if ok:
        feito.append("o <path> solto do lado direito -> stick_r")

    for cx, pid, rot in ((45.5, "stick_l", "esquerdo"), (78.5, "stick_r", "direito")):
        m = re.search(rf'<ellipse\b[^>]*\bcx="{cx}"[^>]*/>', s)
        if not m or f'id="{pid}"' not in s:
            continue
        el = m.group(0)
        s = s[:m.start()] + s[m.end():]
        i = s.index(f'id="{pid}"')
        ini = s.rindex("<g ", 0, i)
        fim = bloco_do_grupo(s, ini)
        s = (s[:fim - 4]
             + f'<g class="miolo"><title>Analógico {rot} — bola do polegar</title>{el}</g>'
             + s[fim - 4:])
        feito.append(f"a bola do polegar entra em {pid}")

    for x, pid, titulo in (("37.043", "share", "Share (Create)"),
                           ("-37.043", "options", "Options")):
        m = re.search(rf'<rect\b[^>]*\bx="{re.escape(x)}"[^>]*/>', s)
        if not m:
            continue
        s = (s[:m.start()] + f'<g id="{pid}" data-entrada="{pid}"><title>{titulo}</title>'
             + m.group(0) + "</g>" + s[m.end():])
        feito.append(f"o <rect> em x={x} -> {pid}")

    i = s.find('id="glifo-stick_l"')
    if i > 0:
        fim = bloco_do_grupo(s, s.rindex("<g ", 0, i))
        bloco = s[s.rindex("<g ", 0, i):fim]
        mr = re.search(r'<text\b[^>]*>\s*(?:<tspan[^>]*>)?\s*R\s*(?:</tspan>)?\s*</text>', bloco)
        if mr:
            novo = bloco.replace(mr.group(0), "")
            s = s[:s.rindex("<g ", 0, i)] + novo + s[fim:]
            s = s.replace("</svg>",
                          f'  <g id="glifo-stick_r"><title>Glifo — Analógico Direito</title>'
                          f'{mr.group(0)}</g>\n</svg>')
            feito.append("a letra R saiu do glifo do analógico esquerdo e virou glifo-stick_r")

    print(f"=== {len(feito)} remapeamentos ===")
    for f in feito:
        print("  ·", f)
    ids = set(re.findall(r'\bid="([^"]+)"', s))
    import csv
    linhas = [l for l in (DADOS_DO_REPO / "pecas-do-dualsense.csv").read_text().splitlines()
              if l and not l.startswith("#")]
    esperadas = [p["id"] for p in csv.DictReader(linhas)]
    faltam = [p for p in esperadas if p not in ids]
    print(f"\npeças reconhecidas: {len(esperadas)-len(faltam)}/{len(esperadas)}")
    if faltam:
        print(f"  ainda faltam: {faltam}")
    if "--gravar" in sys.argv:
        alvo.write_text(s)
        print(f"\n  ok  {alvo} gravado")
    else:
        print("\n(nada gravado — rode com --gravar)")


if __name__ == "__main__":
    main()
