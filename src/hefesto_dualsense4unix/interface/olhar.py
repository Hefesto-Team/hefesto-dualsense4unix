#!/usr/bin/env python3
"""Abre a aba num Chrome de verdade (Playwright) e fotografa o que aparece.

Por que Playwright e não só `--screenshot`: o headless puro não roda o
JavaScript da página com o mesmo relógio, não espera fonte carregar, e não
deixa medir DEPOIS de tudo assentar. Aqui a foto sai da página já pronta.

ONDE ELE OLHA: a BANCADA (`mockup/`), que é o desenho de hoje. Com
`--publicado` ele fotografa `interface/paginas/`, o que o produto renderiza —
serve para comparar o antes e o depois de uma publicação, e para mais nada. O
padrão é a bancada de propósito: instrumento apontado para a página congelada
dá **verde sobre o desenho velho**, que é a armadilha mais cara do
`COMO-OLHAR-A-TELA.md` e reincidiu quatro vezes só em 31/08.

ELE É O RETRATISTA DA INTERFACE NOVA — 05/09/2026
--------------------------------------------------

`scripts/gui-captura/retratar_abas.py` fotografa a JANELA GTK, e é ele que o
`CLAUDE.md` manda rodar antes de commitar. Só que a janela tem ONZE abas e o
produto tem DEZ páginas HTML — as fotos do README mostravam uma tela que não é
mais a que abre. Queixa dela, 05/09/2026:

    *"termos scripts no repo atual que ou apontam pro gtk ou só funcionam lá
    (…) o certo é ajustar ele pra comportar todas as features do html"*

O modo `--todas` é esse ajuste, e mora AQUI e não lá por uma razão de
dependência: o retratista da janela importa GTK na primeira linha, e um modo
que não precisa de GTK dentro dele obrigaria toda máquina a ter PyGObject para
fotografar HTML. Este arquivo já era o dono do Chrome e da receita da foto.

    interface/olhar.py --todas              # as dez, da bancada, em /tmp
    interface/olhar.py --todas --publicado --doc   # as dez do produto,
                                                   # para docs/usage/assets/

Uso:  olhar.py 05-vibracao.html [--publicado]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import onde  # noqa: E402

# FULL HD, como a TV dela: a janela do produto abre com 1180 px dentro de
# 1920x1080. Medir em 1230 escondia o que sobra de vão dos lados e o quanto a
# aba passa da dobra.
LARG, ALT = 1920, 1080

#: Onde as fotos da documentação moram — as mesmas que o README mostra.
DESTINO_DOC = onde.RAIZ / "docs" / "usage" / "assets"

#: O NOME DAS FOTOS NÃO SE INVENTOU — 05/09/2026. O
#: `docs/usage/AS-DEZ-ABAS-o-que-cada-uma-faz.md` já pedia
#: `assets/aba-01-jogar.png` nas dez seções, e as dez imagens NÃO EXISTIAM: o
#: documento publicava dez imagens quebradas desde que foi escrito. O prefixo é
#: o que ele já cita, e o `--doc` passa a preencher exatamente esses dez nomes.
#:
#: As `readme_*.png` são da janela GTK e continuam onde estão até a janela
#: morrer: apagá-las agora deixaria o `docs/usage/interface.md` com furo, e o
#: histórico de uma tela que existiu não é fato errado a substituir — é decisão
#: medida, e leva data.
PREFIXO_NOVO = "aba-"

#: Só as DEZ abas. As avulsas (`mapa-do-controle`, `calibrar-sensores`,
#: `mapa-das-portas`) abrem por fora da janela e não são aba de documentação.
E_ABA = re.compile(r"^\d\d-")


def _navegador(pw):
    # `ignore_default_args=["--hide-scrollbars"]` — 30/08/2026, e não é detalhe.
    # O Playwright headless passa `--hide-scrollbars` por default, e com ele o
    # Chrome NÃO PINTA barra de rolagem nenhuma: `offsetWidth == clientWidth`
    # mesmo num contêiner que rola 300px. Medido no mesmo dia, numa varredura das
    # dez abas: nove agentes concluíram "não há barra" e um deles ia relatar como
    # DEFEITO GRAVE um comentário do gerador que estava certo. A régua não media  # (noqa-acento: verbo medir, imperfeito)
    # a tela — media o próprio flag.  # (noqa-acento: verbo medir, imperfeito) verbo medir
    return pw.chromium.launch(
        executable_path="/usr/bin/google-chrome",
        args=["--no-sandbox"],
        ignore_default_args=["--hide-scrollbars"],
    )


def _retratar(navegador, alvo: pathlib.Path, saida: pathlib.Path,
              so_a_janela: bool = False) -> dict:
    """Uma página, já assentada, medida e fotografada.

    `so_a_janela` recorta na moldura em vez de gravar a página inteira, e é o
    modo da DOCUMENTAÇÃO: a janela do produto tem 777 px de altura dentro de um
    viewport de 1080, então a foto de página inteira publica 300 px de fundo
    vazio — que numa miniatura de README come um terço da imagem.
    """
    pg = navegador.new_page(viewport={"width": LARG, "height": ALT}, device_scale_factor=1)
    try:
        pg.goto(f"file://{alvo}")
        pg.wait_for_load_state("networkidle")
        pg.add_style_tag(content=".nota{display:none}")
        pg.wait_for_timeout(400)
        # AS DUAS FAMÍLIAS DE PÁGINA, e ele precisa saber medir as duas: as dez
        # ABAS moram numa `.janela`; as páginas AVULSAS que abrem por fora dela (o
        # mapa do controle, a calibração) moram numa `.cx`. Antes ele só conhecia
        # a primeira e ESTOURAVA na segunda, com `Cannot read properties of null`
        # — que ao menos é um erro barulhento. O caso perigoso é o silencioso, e
        # por isso o `else` abaixo devolve o motivo em vez de um número inventado:
        # seletor que casou ZERO elemento é ERRO, nunca medida.
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
            return {"erro": cx["erro"]}
        # PÁGINA INTEIRA: o viewport de 1080 cortava tudo o que nasce abaixo da
        # dobra, e era justamente o que ela precisava ver.
        saida.parent.mkdir(parents=True, exist_ok=True)
        moldura = pg.query_selector(".janela") or pg.query_selector(".cx")
        if so_a_janela and moldura is not None:
            moldura.screenshot(path=str(saida))
        else:
            pg.screenshot(path=str(saida), full_page=True)
        return {"png": str(saida), **cx}
    finally:
        pg.close()


def _uma(arq: str, publicado: bool) -> int:
    alvo = onde.pagina(arq, publicado=publicado)
    saida = pathlib.Path(f"/tmp/olhar-{arq[:2]}{'-publicado' if publicado else ''}.png")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = _navegador(pw)
        try:
            r = _retratar(nav, alvo, saida)
        finally:
            nav.close()
    if "erro" in r:
        sys.exit(f"ERRO ao medir {arq}: {r['erro']}")
    print(json.dumps({**r, "olhou": str(alvo.relative_to(onde.RAIZ))}))
    return 0


def _todas(publicado: bool, para_a_doc: bool) -> int:
    paginas = [p for p in onde.paginas(publicado=publicado) if E_ABA.match(p.name)]
    # RETRATISTA QUE ACHA ZERO NÃO É RETRATISTA VERDE: se a pasta mudar de
    # lugar, ele reprova em vez de dizer "pronto" sobre nenhuma foto.
    if len(paginas) < 10:
        sys.exit(f"achei {len(paginas)} abas em {'publicado' if publicado else 'bancada'} — o caminho mudou?")

    destino = DESTINO_DOC if para_a_doc else pathlib.Path("/tmp")
    from playwright.sync_api import sync_playwright

    saiu: list[dict] = []
    with sync_playwright() as pw:
        nav = _navegador(pw)
        try:
            for p in paginas:
                nome = f"{PREFIXO_NOVO}{p.stem}.png" if para_a_doc else f"olhar-{p.stem}.png"
                r = _retratar(nav, p, destino / nome, so_a_janela=para_a_doc)
                if "erro" in r:
                    sys.exit(f"ERRO ao medir {p.name}: {r['erro']}")
                saiu.append({"aba": p.name, **r})
        finally:
            nav.close()

    for r in saiu:
        dobra = f" · passa {r['passa_da_dobra']} px da dobra" if r["passa_da_dobra"] else ""
        print(f"{r['aba']:<20} {r['larg']}x{r['alt']}{dobra}  ->  {r['png']}")
    print(f"\n{len(saiu)} abas retratadas em {destino}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="fotografa a interface nova")
    p.add_argument("pagina", nargs="?",  # (noqa-acento)  (nome do argumento)
                   help="uma página, com extensão: 05-vibracao.html")
    p.add_argument("--publicado", action="store_true", help="o que o produto renderiza")
    p.add_argument("--todas", action="store_true", help="as dez abas de uma vez")
    p.add_argument("--doc", action="store_true", help="grava em docs/usage/assets/")
    a = p.parse_args(argv)
    if a.todas:
        return _todas(a.publicado, a.doc)
    if not a.pagina:  # (noqa-acento)  (nome do argumento)
        p.error("diga a página, ou peça --todas")
    if a.doc:
        p.error("--doc é do modo --todas")
    return _uma(a.pagina, a.publicado)  # (noqa-acento)  (nome do argumento)


if __name__ == "__main__":
    sys.exit(main())
