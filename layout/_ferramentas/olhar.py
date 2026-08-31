#!/usr/bin/env python3
"""Abre a aba num Chrome de verdade (Playwright) e fotografa o que aparece.

Por que Playwright e não só `--screenshot`: o headless puro não roda o
JavaScript da página com o mesmo relógio, não espera fonte carregar, e não
deixa medir DEPOIS de tudo assentar. Aqui a foto sai da página já pronta.

Uso:  olhar.py 05-vibracao.html [altura]
"""
import sys, pathlib, json
from playwright.sync_api import sync_playwright

D = pathlib.Path(__file__).resolve().parent.parent
arq = sys.argv[1]
# FULL HD, como a TV dela: a janela do produto abre com 1180 px dentro de 1920x1080.
# Medir em 1230 escondia o que sobra de vão dos lados e o quanto a aba passa da dobra.
LARG, ALT = 1920, 1080

with sync_playwright() as pw:
    # `ignore_default_args=["--hide-scrollbars"]` — 30/08/2026, e não é detalhe.
    # O Playwright headless passa `--hide-scrollbars` por default, e com ele o
    # Chrome NÃO PINTA barra de rolagem nenhuma: `offsetWidth == clientWidth`
    # mesmo num contêiner que rola 300px. Medido no mesmo dia, numa varredura das
    # dez abas: nove agentes concluíram "não há barra" e um deles ia relatar como
    # DEFEITO GRAVE um comentário do gerador que estava certo. A régua não media  # (noqa-acento: verbo medir, imperfeito)
    # a tela — media o próprio flag.  # (noqa-acento: verbo medir, imperfeito)
    b = pw.chromium.launch(executable_path="/usr/bin/google-chrome",
                           args=["--no-sandbox"],
                           ignore_default_args=["--hide-scrollbars"])
    pg = b.new_page(viewport={"width": LARG, "height": ALT}, device_scale_factor=1)
    pg.goto(f"file://{D/arq}")
    pg.wait_for_load_state("networkidle")
    pg.add_style_tag(content=".nota{display:none}")
    pg.wait_for_timeout(400)
    cx = pg.evaluate("""() => {
      const d = document.documentElement, j = document.querySelector('.janela').getBoundingClientRect();
      return {larg: Math.round(j.width), alt: Math.round(j.height),
              passa_da_dobra: Math.max(0, Math.round(d.scrollHeight - 1080)),
              rolagem_lateral: d.scrollWidth > d.clientWidth};
    }""")
    out = f"/tmp/olhar-{arq[:2]}.png"
    # PÁGINA INTEIRA: o viewport de 1080 cortava tudo o que nasce abaixo da dobra,
    # e era justamente o que ela precisava ver.
    pg.screenshot(path=out, full_page=True)
    b.close()
print(json.dumps({"png": out, **cx}))
