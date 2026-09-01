#!/usr/bin/env python3
"""Abre a aba num Chrome de verdade (Playwright) e fotografa o que aparece.

Por que Playwright e não só `--screenshot`: o headless puro não roda o
JavaScript da página com o mesmo relógio, não espera fonte carregar, e não
deixa medir DEPOIS de tudo assentar. Aqui a foto sai da página já pronta.

ONDE ELE OLHA: a BANCADA (`mockup/`), que é o desenho de hoje. Com
`--publicado` ele fotografa `layout/`, o que o produto renderiza — serve para
comparar o antes e o depois de uma publicação, e para mais nada. O padrão é a
bancada de propósito: instrumento apontado para a página congelada dá **verde
sobre o desenho velho**, que é a armadilha mais cara do `COMO-OLHAR-A-TELA.md`
e reincidiu quatro vezes só em 31/08.

Uso:  olhar.py 05-vibracao.html [--publicado]
"""
import sys, pathlib, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import onde
from playwright.sync_api import sync_playwright

argv = [a for a in sys.argv[1:] if a != "--publicado"]
PUBLICADO = "--publicado" in sys.argv
arq = argv[0]
ALVO = onde.pagina(arq, publicado=PUBLICADO)
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
    # a tela — media o próprio flag.  # (noqa-acento: verbo medir, imperfeito) verbo medir
    b = pw.chromium.launch(executable_path="/usr/bin/google-chrome",
                           args=["--no-sandbox"],
                           ignore_default_args=["--hide-scrollbars"])
    pg = b.new_page(viewport={"width": LARG, "height": ALT}, device_scale_factor=1)
    pg.goto(f"file://{ALVO}")
    pg.wait_for_load_state("networkidle")
    pg.add_style_tag(content=".nota{display:none}")
    pg.wait_for_timeout(400)
    # AS DUAS FAMÍLIAS DE PÁGINA, e ele precisa saber medir as duas: as dez ABAS
    # moram numa `.janela`; as páginas AVULSAS que abrem por fora dela (o mapa do
    # controle, a calibração) moram numa `.cx`. Antes ele só conhecia a primeira e
    # ESTOUAVA na segunda, com `Cannot read properties of null` — que ao menos é
    # um erro barulhento. O caso perigoso é o silencioso, e por isso o `else`
    # abaixo devolve o motivo em vez de um número inventado: seletor que casou
    # ZERO elemento é ERRO, nunca medida.
    cx = pg.evaluate("""() => {
      const d = document.documentElement;
      const cx = document.querySelector('.janela') || document.querySelector('.cx');
      if (!cx) return {erro: 'nem .janela nem .cx nesta página — não há o que medir'};
      const j = cx.getBoundingClientRect();
      return {caixa: cx.className, larg: Math.round(j.width), alt: Math.round(j.height),
              passa_da_dobra: Math.max(0, Math.round(d.scrollHeight - 1080)),
              rolagem_lateral: d.scrollWidth > d.clientWidth};
    }""")
    if cx.get("erro"):
        sys.exit(f"ERRO ao medir {arq}: {cx['erro']}")
    out = f"/tmp/olhar-{arq[:2]}{'-publicado' if PUBLICADO else ''}.png"
    # PÁGINA INTEIRA: o viewport de 1080 cortava tudo o que nasce abaixo da dobra,
    # e era justamente o que ela precisava ver.
    pg.screenshot(path=out, full_page=True)
    b.close()
print(json.dumps({"png": out, "olhou": str(ALVO.relative_to(onde.RAIZ)), **cx}))
