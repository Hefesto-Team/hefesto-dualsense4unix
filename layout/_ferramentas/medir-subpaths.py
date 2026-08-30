#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mede, no navegador, qual subpath de cada peça é o CONTORNO EXTERNO.

Por que medir e não calcular: os paths deste desenho usam arcos relativos
(`a r r ...`), e os números deles são raios e deltas, não coordenadas. Duas
heurísticas minhas erraram por isso — "o primeiro subpath" e "o de maior extensão
numérica" escolheram os dois o FURO do triângulo, e o alvo saiu do tamanho do
buraco: nenhuma das 27 peças respondia ao ponteiro.

O resultado vai para `subpath-externo.json`, e o mapa.py o lê ao gerar.

    python3 medir-subpaths.py
"""
import json, pathlib, re
from playwright.sync_api import sync_playwright

R = pathlib.Path(__file__).resolve().parents[2]
SVG = R / "layout/_ferramentas/ds_limpo.svg"
SAIDA = pathlib.Path(__file__).with_name("subpath-externo.json")

s = SVG.read_text()
alvos = []          # (peça, índice do elemento, índice do subpath, d)
for m in re.finditer(r'<g\b[^>]*\bid="([^"]+)"[^>]*>', s):
    pid = m.group(1)
    i = m.start(); prof, j = 0, i
    while True:
        n = re.search(r"<g\b|</g>", s[j:])
        if not n:
            break
        j += n.end(); prof += 1 if n.group(0) == "<g" else -1
        if prof == 0:
            break
    for k, mm in enumerate(re.finditer(r'<path\b[^>]*?\sd="([^"]*)"', s[i:j])):
        partes = [p for p in re.split(r"(?<=Z)\s*(?=M)|\s(?=M\s)", mm.group(1).strip()) if p.strip()]
        if len(partes) > 1:
            for q, d in enumerate(partes):
                alvos.append((pid, k, q, d))

html = ['<!doctype html><meta charset=utf-8><body style="margin:0">'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200">']
for n, (pid, k, q, d) in enumerate(alvos):
    html.append(f'<path id="p{n}" d="{d}" fill="none"/>')
html.append("</svg>")
pathlib.Path("/tmp/subpaths.html").write_text("\n".join(html))

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    pg = b.new_page(); pg.goto("file:///tmp/subpaths.html"); pg.wait_for_timeout(400)
    areas = pg.evaluate("""(n) => {const o=[];
      for(let i=0;i<n;i++){const e=document.getElementById('p'+i);
        let b; try{b=e.getBBox();}catch(err){o.push(0); continue;}
        o.push(Math.round(b.width*b.height*100)/100);}
      return o;}""", len(alvos))
    b.close()

escolha = {}
for (pid, k, q, _), a in zip(alvos, areas):
    chave = f"{pid}|{k}"
    if chave not in escolha or a > escolha[chave][1]:
        escolha[chave] = (q, a)

SAIDA.write_text(json.dumps({k: v[0] for k, v in escolha.items()},
                            indent=1, sort_keys=True))
print(f"  ok  {SAIDA.name}: {len(escolha)} paths de vários subpaths medidos")
nao_zero = [k for k, v in escolha.items() if v[0] != 0]
print(f"      em {len(nao_zero)} deles o externo NÃO é o primeiro: "
      + ", ".join(sorted(nao_zero)[:8]) + ("…" if len(nao_zero) > 8 else ""))
