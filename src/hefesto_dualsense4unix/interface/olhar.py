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

ELE TAMBÉM PROCURA PALAVRA — 06/09/2026, A-PALAVRA-MESA-SAI-01

`--palavra mesa` lista, página por página, cada ocorrência que uma pessoa LÊ,
com o contexto e o ARQUIVO:LINHA de onde ela vem. Ele não abre navegador: a
leitura é a do `frases_que_ela_baniu`, que é a mesma que a régua usa —
instrumento e portão têm de responder o mesmo número, senão um dos dois mente.
O `--palavra` é o "antes" da sprint, e um `--palavra mesa` vazio é o "depois".

**E A LEITURA MUDA COM O ALVO — 06/09/2026, e não é detalhe.** A bancada ela
abre no navegador crua; o produto renderiza a mesma página com a folha do
piloto por cima, que apaga a `.nota` (o bilhete de projeto). Até esta data o
`--publicado` contava a `.nota` e dizia **"34 ocorrência(s) visível(eis) em o
produto"** sobre uma tela que não mostrava nenhuma — o instrumento respondia
sobre o ARQUIVO. Agora o modo publicado lê por `texto_visivel_no_produto`, que
pergunta à `interface.folha_da_casa` o que o produto esconde.

    interface/olhar.py --palavra mesa               # a bancada
    interface/olhar.py --palavra mesa --publicado   # o que o produto renderiza

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
        # O QUE SE ESCONDE VEM DA FOLHA DO PILOTO, e não deste arquivo —
        # 06/09/2026. Aqui estava `.nota{display:none}` digitado, a segunda
        # cópia de um valor que tem dono: a foto mostrava o que o produto
        # esconde HOJE e continuaria mostrando no dia em que a folha ganhasse a
        # segunda regra de esconder. Agora ela pergunta.
        from hefesto_dualsense4unix.interface.folha_da_casa import seletores_escondidos

        pg.add_style_tag(
            content="".join(f"{s}{{display:none}}" for s in seletores_escondidos())
        )
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


#: ONDE UMA FRASE DE TELA PODE TER NASCIDO: os dez geradores (o desenho e a
#: legenda) e os dez pacotes (o que o piloto escreve por tique). `app/` fica de
#: fora porque não é posse desta sprint — e quando a origem não está aqui, o
#: instrumento diz "não achei", que é a resposta honesta.
def _fontes() -> list[pathlib.Path]:
    aqui = pathlib.Path(__file__).resolve().parent
    return sorted(aqui.glob("aba??.py")) + sorted((aqui / "pacotes").glob("a??_*.py"))


def _de_onde(trecho: str) -> str:
    """O arquivo:linha do gerador que escreveu ``trecho``, ou por que não achei.

    DUAS COISAS SEPARAM O FONTE DA PÁGINA, e ignorar qualquer uma devolve "não
    achei" sobre um arquivo que está logo ali:

    * **a quebra de linha** — a mesma frase mora numa linha do HTML e em duas do
      fonte, com o recuo no meio. Por isso a busca é por regex com `\\s+` no
      lugar de todo espaço, e não por `str.find`;
    * **o tamanho** — a legenda é escrita em literais que o Python junta, e um
      pedaço de 60 letras pode cair bem no ponto da emenda. Ele tenta 60, 40,
      24 e 14, e para na primeira medida que casa.
    """
    for tamanho in (60, 40, 24, 14):
        alvo = trecho[:tamanho].strip()
        if len(alvo) < 8:
            continue
        # o último pedaço pode ter sido cortado no meio de uma palavra; o `\s+`
        # não ajuda aí, então a busca é do começo até o último espaço inteiro.
        agulha = re.compile(r"\s+".join(re.escape(p) for p in alvo.split()))
        achados = []
        for fonte in _fontes():
            texto = fonte.read_text(encoding="utf-8")
            m = agulha.search(texto)
            if m is not None:
                achados.append(f"{fonte.name}:{texto.count(chr(10), 0, m.start()) + 1}")
        if achados:
            return " · ".join(achados[:3])
    return "não achei no fonte (pode vir de `app/`, que não é desta posse)"


def _palavra(alvo: str, publicado: bool) -> int:
    """A palavra que uma pessoa LÊ, página por página, com origem e contexto."""
    from hefesto_dualsense4unix.interface.frases_que_ela_baniu import (
        _borda,
        texto_visivel,
        texto_visivel_no_produto,
    )

    # AS DUAS LEITURAS, e a diferença é o ponto inteiro deste instrumento:
    # a BANCADA ela abre no navegador crua, e ali a `.nota` é texto de verdade;
    # o PRODUTO renderiza com a folha do piloto por cima, que apaga a `.nota`.
    # Contar a `.nota` no modo `--publicado` deu 34 "ocorrências visíveis em o
    # produto" sobre uma tela que não mostrava nenhuma (06/09/2026).
    ler = texto_visivel_no_produto if publicado else texto_visivel

    paginas = [p for p in onde.paginas(publicado=publicado) if E_ABA.match(p.name)]
    if len(paginas) < 10:
        sys.exit(f"achei {len(paginas)} abas — o caminho mudou?")

    total = 0
    for p in paginas:
        cru = p.read_text(encoding="utf-8")
        visivel = ler(cru)
        achados = list(_borda(alvo).finditer(visivel))
        total += len(achados)
        print(f"\n{p.name}  —  {len(achados)} ocorrência(s) visível(eis)")
        for m in achados:
            linha = visivel.count("\n", 0, m.start()) + 1
            a, b = max(0, m.start() - 55), m.end() + 55
            contexto = " ".join(visivel[a:b].split())
            print(f"  linha {linha}: …{contexto}…")
            print(f"      vem de: {_de_onde(' '.join(cru[m.start():b].split()))}")
    print(f"\n{alvo!r}: {total} ocorrência(s) visível(eis) em "
          f"{'o produto' if publicado else 'a bancada'}")
    return 1 if total else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="fotografa a interface nova")
    p.add_argument("pagina", nargs="?",  # (noqa-acento)  (nome do argumento)
                   help="uma página, com extensão: 05-vibracao.html")
    p.add_argument("--publicado", action="store_true", help="o que o produto renderiza")
    p.add_argument("--todas", action="store_true", help="as dez abas de uma vez")
    p.add_argument("--doc", action="store_true", help="grava em docs/usage/assets/")
    p.add_argument("--palavra", metavar="PALAVRA",
                   help="lista onde esta palavra é LIDA nas dez abas, com a origem")
    a = p.parse_args(argv)
    if a.palavra:
        return _palavra(a.palavra, a.publicado)
    if a.todas:
        return _todas(a.publicado, a.doc)
    if not a.pagina:  # (noqa-acento)  (nome do argumento)
        p.error("diga a página, ou peça --todas")
    if a.doc:
        p.error("--doc é do modo --todas")
    return _uma(a.pagina, a.publicado)  # (noqa-acento)  (nome do argumento)


if __name__ == "__main__":
    sys.exit(main())
