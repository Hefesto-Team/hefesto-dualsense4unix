#!/usr/bin/env python3
"""gerar-indice-html.py — constrói `html/index.html`: a única página que ela abre.

O QUARTO IRMÃO, E POR QUE ELE É GERADO
--------------------------------------
Os outros três respondem cada um a uma pergunta; este responde *"qual deles eu
abro?"* — e diz, de cada um, **quando foi gerado e de qual commit**.

Ele é GERADO, nunca escrito à mão, e a razão é o defeito exato que a sprint
`A-CASA-ARRUMADA-01` veio curar: um índice escrito à mão vira a quarta página
que envelhece em silêncio. Escrito à mão, ele juraria que o `specs.html` existe
depois de alguém apagá-lo, e mostraria uma data de geração que ninguém
atualizou. Gerado, ele **lê o disco**: o que não está lá aparece como ausente, e
a data de cada cartão sai do carimbo da própria página.

A REGRA DOS IRMÃOS VALE AQUI: autocontido, zero rede, zero CDN, zero fonte web,
paleta de `scripts/paleta_da_casa.py`. O motivo continua sendo o que o
`gerar-mapa.py` registrou: *"um instrumento que só funciona com rede não serve
para depurar rádio."*

QUANDO OS QUATRO DISCORDAM, O ÍNDICE DIZ
----------------------------------------
É a metade útil do HTML-2. Cada página carimba o commit de que nasceu; este
compara os carimbos e, se dois divergirem, escreve isso no alto — em vez de a
divergência ser descoberta por acidente, meses depois, por alguém que acreditou
num número velho.

Uso:
    python3 scripts/gerar-indice-html.py          # escreve html/index.html
    python3 scripts/gerar-indice-html.py --check  # o publicado bate com o disco?

Ele lê o carimbo dos outros três, então **roda DEPOIS deles**. Rodar antes
publica um índice que descreve as páginas anteriores.
"""
from __future__ import annotations

import argparse
import re
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from carimbo_da_casa import CSS as CARIMBO_CSS
from carimbo_da_casa import MARCA, carimbo, sem_carimbo
from carimbo_da_casa import PASTA as PASTA_HTML
from paleta_da_casa import TOKENS

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / PASTA_HTML
SAIDA = PASTA / "index.html"

#: Os instrumentos, em ordem de uso: primeiro o que responde pelo aparelho,
#: depois o que responde pelo projeto, depois o que espera o olho dela.
#:
#: **Esta tupla é a fonte do índice.** Um cartão a menos aqui é um instrumento
#: que ela não acha; o teste `tests/unit/test_indice_html_leva_aos_tres.py`
#: reprova nomeando qual sumiu.
INSTRUMENTOS = (
    {
        "arquivo": "specs.html",
        "titulo": "Mapa de canais",
        "responde": "O que o aparelho entende, e por qual canal — cabo ou rádio.",
        "quando": "Antes de afirmar que uma feature funciona num transporte. "
                  "É rede contra regressão, não documentação: features "
                  "consolidadas no cabo já quebraram no rádio sem ninguém ver.",
        "gerador": "scripts/gerar-mapa.py",
        "fonte": "docs/data/mapa-controles.csv + os três desenhos SVG",
    },
    {
        "arquivo": "painel.html",
        "titulo": "Painel do projeto",
        "responde": "Onde o projeto está: portões, sprints, a fila da bancada.",
        "quando": "Ao chegar numa sessão, para saber o que está verde, o que "
                  "está aberto e há quanto tempo cada número caro foi medido. "
                  "Vazio aqui é <em>não medimos</em>, nunca <em>está tudo bem</em>.",
        "gerador": "scripts/gerar-painel.py",
        "fonte": "as sprints, docs/data/decisoes-dela.csv e o cache dos portões",
    },
    {
        "arquivo": "frases-de-tela.html",
        "titulo": "Frases de tela",
        "responde": "Que frases da interface mudaram e ainda não passaram por ela.",
        "quando": "Quando houver texto de tela esperando o olho dela. Cada "
                  "mudança traz o que saiu, o que entrou e por quê — e o voto "
                  "fica guardado no navegador dela.",
        "gerador": "scripts/gerar-frases-de-tela.py",
        "fonte": "docs/process/dados/frases-de-tela-25-08.json",
    },
)

#: Como se lê o carimbo de uma página irmã. A marca vem do dono único
#: (`carimbo_da_casa.MARCA`), então mudar o formato lá não deixa este regex
#: para trás em silêncio: sem casar, o cartão diz "carimbo não encontrado".
CARIMBO_NA_PAGINA = re.compile(
    r"gerado em ([^<·]+?)\s*·\s*commit <code>([^<]*)</code>"
    r"\s*na branch <code>([^<]*)</code>"
)

ESTILO = """
*,*::before,*::after{box-sizing:border-box}
body{margin:0;background:var(--color-paper);color:var(--color-ink);
  font-family:var(--font-corpo);font-size:var(--text-base);line-height:1.55}
.envelope{max-width:76ch;margin:0 auto;padding:var(--space-lg) var(--space-md) var(--space-xl)}
h1{font-size:var(--text-display);line-height:1.05;margin:0 0 var(--space-2xs);
  font-weight:400;letter-spacing:-.02em}
h1 b{font-weight:700;color:var(--color-accent)}
.lede{color:var(--color-ink-quiet);max-width:64ch;margin:0 0 var(--space-lg)}
.lede em{color:var(--color-ink);font-style:italic}
.discordia{border:var(--rule-hair) solid var(--color-lacuna);border-radius:var(--radius-md);
  background:var(--color-paper-2);padding:var(--space-sm);margin:0 0 var(--space-lg)}
.discordia h2{margin:0 0 var(--space-2xs);font-size:var(--text-lg);color:var(--color-lacuna)}
.discordia p{margin:0 0 var(--space-2xs);color:var(--color-ink-quiet)}
.discordia p:last-child{margin-bottom:0}
.concordia{color:var(--color-ok);font-family:var(--font-dado);
  font-size:var(--text-sm);margin:0 0 var(--space-lg)}
.cartoes{display:grid;gap:var(--space-md);margin:0 0 var(--space-lg)}
.cartao{border:var(--rule-hair) solid var(--color-rule);border-radius:var(--radius-md);
  background:var(--color-paper-2);padding:var(--space-sm) var(--space-md);
  transition:border-color var(--dur-base) var(--ease-out)}
.cartao:hover{border-color:var(--color-accent)}
.cartao.ausente{border-color:var(--color-alerta)}
.cartao h2{margin:0 0 var(--space-3xs);font-size:var(--text-xl);font-weight:600}
.cartao h2 a{color:var(--color-ink);text-decoration:none;
  border-bottom:1px solid var(--color-accent)}
.cartao h2 a:hover{color:var(--color-accent)}
.cartao .responde{margin:0 0 var(--space-2xs);color:var(--color-ink)}
.cartao .quando{margin:0 0 var(--space-xs);color:var(--color-ink-quiet);
  font-size:var(--text-sm)}
.cartao .quando em{color:var(--color-ink);font-style:italic}
.ficha{list-style:none;padding:0;margin:0;font-family:var(--font-dado);
  font-size:var(--text-xs);color:var(--color-ink-faint)}
.ficha li{margin:0;padding:.15rem 0;border-top:var(--rule-hair) solid var(--color-paper-3)}
.ficha li:first-child{border-top:0}
.ficha b{color:var(--color-ink-quiet);font-weight:400}
.ficha .falta{color:var(--color-alerta)}
.regra{color:var(--color-ink-quiet);font-size:var(--text-sm);max-width:64ch}
.regra strong{color:var(--color-ink)}
.regra code{font-family:var(--font-dado);color:var(--color-frio)}
@media (prefers-reduced-motion:reduce){*{transition:none!important}} /* noqa-acento */
"""


def le_carimbo(caminho: Path) -> dict[str, str]:
    """O que a página irmã declara de si mesma, ou a ausência, declarada.

    Nunca inventa: página sem carimbo devolve `commit` vazio, e o cartão diz
    isso na cara. É a regra da casa — ausência de medição é declarada, nunca
    preenchida com um valor plausível.
    """
    if not caminho.is_file():
        return {"existe": "", "quando": "", "commit": "", "branch": "", "kb": ""}
    texto = caminho.read_text(encoding="utf-8", errors="replace")
    kb = f"{caminho.stat().st_size / 1024:.0f} KB"
    linha = next((ln for ln in texto.splitlines() if MARCA in ln), "")
    achado = CARIMBO_NA_PAGINA.search(linha)
    if not achado:
        return {"existe": "sim", "quando": "", "commit": "", "branch": "", "kb": kb}
    return {
        "existe": "sim",
        "quando": achado.group(1).strip(),
        "commit": achado.group(2).strip(),
        "branch": achado.group(3).strip(),
        "kb": kb,
    }


def _cartao(inst: dict[str, str], selo: dict[str, str]) -> str:
    nome = inst["arquivo"]
    if not selo["existe"]:
        # SEM LINK de propósito: um índice que aponta para arquivo que não
        # existe é pior que um índice que diz que ele falta.
        titulo = f'<h2>{escape(inst["titulo"])}</h2>'
        ficha = (
            f'<li class="falta"><b>{escape(nome)}</b> — não está no disco. '
            f'Rode <b>python3 {escape(inst["gerador"])}</b>.</li>'
        )
        classe = "cartao ausente"
    else:
        titulo = f'<h2><a href="{escape(nome)}">{escape(inst["titulo"])}</a></h2>'
        quando = escape(selo["quando"]) if selo["quando"] else "carimbo não encontrado"
        commit = escape(selo["commit"]) if selo["commit"] else "?"
        branch = escape(selo["branch"]) if selo["branch"] else "?"
        ficha = (
            f'<li><b>arquivo</b> {escape(nome)} · {escape(selo["kb"])}</li>'
            f"<li><b>gerado em</b> {quando} · commit {commit} na branch {branch}</li>"
            f'<li><b>gerador</b> python3 {escape(inst["gerador"])}</li>'
            f'<li><b>fonte</b> {escape(inst["fonte"])}</li>'
        )
        classe = "cartao"
    return (
        f'<article class="{classe}">{titulo}'
        f'<p class="responde">{inst["responde"]}</p>'
        f'<p class="quando">{inst["quando"]}</p>'
        f'<ul class="ficha">{ficha}</ul></article>'
    )


def _concordancia(selos: list[dict[str, str]]) -> str:
    """O bloco que mostra a divergência de commits, ou declara que não há.

    É a razão de o carimbo existir (HTML-2): duas páginas irmãs geradas de
    commits diferentes descrevem estados diferentes do projeto, e até 25/08/2026
    isso só aparecia quando alguém acreditava num número velho.
    """
    commits = {s["commit"] for s in selos if s["existe"] and s["commit"]}
    faltam = [s for s in selos if not s["existe"] or not s["commit"]]
    if len(commits) <= 1 and not faltam:
        unico = escape(next(iter(commits))) if commits else "?"
        return (
            f'<p class="concordia">Os três falam a mesma coisa: gerados do '
            f"commit {unico}.</p>"
        )
    partes = ['<div class="discordia"><h2>Os instrumentos discordam</h2>']
    if len(commits) > 1:
        lista = ", ".join(sorted(escape(c) for c in commits))
        partes.append(
            f"<p>As páginas abaixo não nasceram do mesmo commit ({lista}). "
            "Números que uma mostra podem já ter mudado na outra — regere "
            "todas antes de acreditar em qualquer uma.</p>"
        )
    if faltam:
        partes.append(
            f"<p>{len(faltam)} página(s) sem carimbo ou fora do disco: o cartão "
            "vermelho abaixo diz qual, e qual gerador a devolve.</p>"
        )
    partes.append(
        "<p>Cure com: <b>python3 scripts/gerar-mapa.py &amp;&amp; "
        "python3 scripts/gerar-painel.py &amp;&amp; "
        "python3 scripts/gerar-frases-de-tela.py &amp;&amp; "
        "python3 scripts/gerar-indice-html.py</b></p></div>"
    )
    return "".join(partes)


def monta() -> str:
    selos = [le_carimbo(PASTA / i["arquivo"]) for i in INSTRUMENTOS]
    cartoes = "".join(_cartao(i, s) for i, s in zip(INSTRUMENTOS, selos, strict=True))
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hefesto · os instrumentos</title>
<style>
/* ARQUIVO GERADO por scripts/gerar-indice-html.py — não edite à mão.
 * Paleta: scripts/paleta_da_casa.py. Carimbo: scripts/carimbo_da_casa.py.
 * Autocontido: zero rede, zero CDN, zero fonte web. */
{TOKENS}{ESTILO}{CARIMBO_CSS}
</style>
</head>
<body>
<div class="envelope">

  <h1><b>Hefesto</b> · os instrumentos</h1>
  <p class="lede">Esta é a página para abrir. Os três instrumentos desta casa
     respondem a perguntas diferentes, dividem a mesma paleta e o mesmo carimbo,
     e cada um diz aqui <em>quando foi gerado e de qual commit</em>.</p>

  {_concordancia(selos)}

  <div class="cartoes">{cartoes}</div>

  <p class="regra"><strong>Os quatro abrem com duplo clique</strong> — sem
     servidor, sem venv, sem internet. A regra não é capricho: um instrumento que
     só funciona com rede não serve para depurar rádio.</p>
  <p class="regra">Nenhum deles se edita à mão. Cada cartão traz o gerador que o
     escreve; rodá-lo é o único jeito de mudar a página. O
     <code>--check</code> de cada gerador responde se o publicado ainda é o que
     as fontes produzem.</p>

  {carimbo("scripts/gerar-indice-html.py", indice=False)}

</div>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help="reprova se html/index.html não for o que este script produz hoje",
    )
    args = ap.parse_args()

    pagina = monta()

    if args.check:
        if not SAIDA.is_file():
            print("html/index.html: NÃO EXISTE — rode scripts/gerar-indice-html.py",
                  file=sys.stderr)
            return 1
        publicado = SAIDA.read_text(encoding="utf-8")
        if sem_carimbo(publicado) != sem_carimbo(pagina):
            print("html/index.html: DESATUALIZADO — ele não descreve as páginas "
                  "que estão no disco agora.", file=sys.stderr)
            print("  cure com: python3 scripts/gerar-indice-html.py", file=sys.stderr)
            return 1
        print("html/index.html: atualizado (confere com as três páginas irmãs)")
        return 0

    PASTA.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(pagina, encoding="utf-8")
    achados = sum(1 for i in INSTRUMENTOS if (PASTA / i["arquivo"]).is_file())
    print(f"{SAIDA.relative_to(RAIZ)}: {len(INSTRUMENTOS)} cartões, "
          f"{achados} página(s) no disco, sem rede e sem CDN.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
