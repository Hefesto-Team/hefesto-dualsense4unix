#!/usr/bin/env python3
"""assar_transforms_svg.py — o SVG dela vira PNG igual ao que ela desenhou.

DECISÃO DELA, 30/08/2026: *"então o nosso install sempre deve corrigir ele pra
ter o mesmo SVG em qualquer versão, PNG ou afins."*

O PROBLEMA, medido três vezes hoje. O editor dela (Boxy SVG) escreve rotação e
espelho com `transform-box` e `transform-origin` — atributos CSS que o
**navegador honra e o `librsvg` IGNORA**. Como é o `librsvg` que gera o ícone da
dock, o desenho saía mutilado: o anel e o martelo iam para fora da arte, e ela
via na dock um ícone que não era o dela.

A CURA NÃO É PEDIR QUE ELA MUDE O DESENHO. É o gerador de ícones assar os
transforms antes de rasterizar, e é o que este arquivo faz — em memória, sem
tocar no arquivo dela.

A CONTA: `transform-origin: (cx,cy)` com `transform: M` significa
``T(cx,cy) · M · T(-cx,-cy)``. Só a translação muda; a, b, c e d ficam:

    e' = cx + e - (a·cx + c·cy)
    f' = cy + f - (b·cx + d·cy)

E A ARMADILHA QUE CUSTOU UMA RODADA: com `transform-box: fill-box`, o `50% 50%`
é o centro da caixa REAL do elemento. Os quatro pontos de uma cúbica não são a
caixa dela — a curva passa pelo primeiro e pelo último e apenas TENDE aos dois
do meio. Usar os pontos de controle deslocou o anel em 6px em x e 8px em y, o
bastante para vazar do `viewBox` de 200×200. Os extremos saem das raízes da
derivada, e é isso que `_bbox_cubica` resolve.

    assar_transforms_svg.py entrada.svg [saida.svg]
    assar_transforms_svg.py --check entrada.svg    # só diz se precisa
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_NUM = r"-?\d+\.?\d*(?:[eE][-+]?\d+)?"


def _extremos_cubica(p0: float, p1: float, p2: float, p3: float) -> tuple[float, float]:
    """Mínimo e máximo de uma cúbica num eixo, pelas raízes da derivada."""
    vals = [p0, p3]
    a = -p0 + 3 * p1 - 3 * p2 + p3
    b = 2 * (p0 - 2 * p1 + p2)
    c = -p0 + p1

    def em(t: float) -> float:
        u = 1 - t
        return u**3 * p0 + 3 * u**2 * t * p1 + 3 * u * t**2 * p2 + t**3 * p3

    if abs(a) < 1e-12:
        if abs(b) > 1e-12:
            t = -c / b
            if 0 < t < 1:
                vals.append(em(t))
    else:
        disc = b * b - 4 * a * c
        if disc >= 0:
            raiz = disc**0.5
            for t in ((-b + raiz) / (2 * a), (-b - raiz) / (2 * a)):
                if 0 < t < 1:
                    vals.append(em(t))
    return min(vals), max(vals)


def bbox_do_path(d: str) -> tuple[float, float, float, float]:
    """Caixa real de um `d`, com M, L e C absolutos (o que o Boxy emite)."""
    toks = re.findall(rf"[MmCcLlZz]|{_NUM}", d)
    i, cur, xs, ys = 0, (0.0, 0.0), [], []
    while i < len(toks):
        t = toks[i]
        if t in "Mm":
            cur = (float(toks[i + 1]), float(toks[i + 2]))
            xs.append(cur[0]); ys.append(cur[1]); i += 3
        elif t in "Cc":
            pts = [cur] + [(float(toks[i + 1 + 2 * k]), float(toks[i + 2 + 2 * k])) for k in range(3)]
            x0, x1 = _extremos_cubica(*[p[0] for p in pts])
            y0, y1 = _extremos_cubica(*[p[1] for p in pts])
            xs += [x0, x1]; ys += [y0, y1]
            cur = pts[3]; i += 7
        elif t in "Ll":
            cur = (float(toks[i + 1]), float(toks[i + 2]))
            xs.append(cur[0]); ys.append(cur[1]); i += 3
        else:
            i += 1
    if not xs:
        raise ValueError("path sem ponto algum")
    return min(xs), min(ys), max(xs), max(ys)


def _assar_elemento(el: str, cx: float, cy: float) -> str | None:
    mm = re.search(rf'transform="matrix\(\s*({_NUM})\s*,\s*({_NUM})\s*,\s*({_NUM})\s*,'
                   rf'\s*({_NUM})\s*,\s*({_NUM})\s*,\s*({_NUM})\s*\)"', el)
    if not mm:
        return None
    a, b, c, d, e, f = (float(mm.group(k)) for k in range(1, 7))
    e2 = cx + e - (a * cx + c * cy)
    f2 = cy + f - (b * cx + d * cy)
    novo = re.sub(r'transform="matrix\([^)]*\)"',
                  f'transform="matrix({a}, {b}, {c}, {d}, {e2:.6f}, {f2:.6f})"', el)
    novo = re.sub(r"\s*transform-box:\s*[a-z-]+;?", "", novo)
    novo = re.sub(r"\s*transform-origin:\s*[^;\"]+;?", "", novo)
    novo = re.sub(r'\s*style="\s*"', "", novo)
    return novo


def assar(svg: str) -> tuple[str, int]:
    """Devolve o SVG com os transforms assados e quantos foram."""
    n = 0
    for m in list(re.finditer(rf'<[a-z]+[^>]*transform-origin:\s*({_NUM})px\s+({_NUM})px[^>]*>', svg)):
        novo = _assar_elemento(m.group(0), float(m.group(1)), float(m.group(2)))
        if novo:
            svg = svg.replace(m.group(0), novo, 1); n += 1
    for m in list(re.finditer(r'<path d="([^"]+)"[^>]*transform-box:\s*fill-box[^>]*>', svg)):
        x0, y0, x1, y1 = bbox_do_path(m.group(1))
        novo = _assar_elemento(m.group(0), (x0 + x1) / 2, (y0 + y1) / 2)
        if novo:
            svg = svg.replace(m.group(0), novo, 1); n += 1
    return svg, n


def precisa(svg: str) -> bool:
    return "transform-box" in svg or "transform-origin" in svg


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    so_checar = "--check" in argv
    if not args:
        print(__doc__.strip().splitlines()[-3], file=sys.stderr)
        return 2
    entrada = Path(args[0])
    svg = entrada.read_text(encoding="utf-8")
    if so_checar:
        print(f"{entrada}: {'PRECISA assar' if precisa(svg) else 'já está pronto'}")
        return 1 if precisa(svg) else 0
    saida = Path(args[1]) if len(args) > 1 else entrada
    novo, n = assar(svg)
    saida.write_text(novo, encoding="utf-8")
    print(f"{saida}: {n} transform(s) assado(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
