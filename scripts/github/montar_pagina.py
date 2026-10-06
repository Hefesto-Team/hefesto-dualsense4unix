#!/usr/bin/env python3
"""Monta a página do produto (a que o GitHub Pages publica) a partir do README e das fotos.

  montar_pagina.py --saida _site

O `README.md` vira o `index.html`; as imagens que ele cita (`docs/usage/assets/`, `assets/appimage/`)
são copiadas com o mesmo caminho, e o texto não muda: a página e o README dizem a mesma coisa.
Precisa do `markdown-it-py` (o produto já o traz pelo `textual`).
"""
from __future__ import annotations

import argparse
import html
import re
import shutil
import sys
from pathlib import Path

from markdown_it import MarkdownIt

RAIZ = Path(__file__).resolve().parents[2]
# Onde moram as imagens do README, relativas à raiz do repositório.
PASTAS_DE_IMAGEM = ("docs/usage/assets", "assets/appimage")
REPO = "https://github.com/Hefesto-Team/hefesto-dualsense4unix"
CABECA = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titulo}</title>
<meta name="description" content="{descricao}">
<meta property="og:title" content="{titulo}">
<meta property="og:description" content="{descricao}">
<style>
:root {{ --fundo: #fff; --texto: #1f2328; --suave: #59636e; --borda: #d1d9e0; --link: #0969da; --bloco: #f6f8fa; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --fundo: #0d1117; --texto: #e6edf3; --suave: #9198a1; --borda: #3d444d; --link: #4493f8; --bloco: #151b23; }}
}}
body {{ margin: 0; background: var(--fundo); color: var(--texto);
  font: 16px/1.6 system-ui, -apple-system, "Segoe UI", sans-serif; }}
main {{ max-width: 860px; margin: 0 auto; padding: 24px 16px 48px; }}
a {{ color: var(--link); }}
img {{ max-width: 100%; height: auto; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid var(--borda); padding: 6px 10px; vertical-align: top; }}
pre, code {{ background: var(--bloco); border-radius: 6px; }}
pre {{ padding: 12px; overflow-x: auto; }}
code {{ padding: 2px 5px; }}
pre code {{ padding: 0; }}
nav {{ display: flex; flex-wrap: wrap; gap: 8px 20px; padding: 12px 16px; border-bottom: 1px solid var(--borda);
  justify-content: center; }}
footer {{ border-top: 1px solid var(--borda); color: var(--suave); text-align: center; padding: 16px; }}
</style>
</head>
<body>
<nav>
<a href="{repo}">Código</a>
<a href="{repo}/releases">Versões</a>
<a href="{repo}/issues/new/choose">Relatar um problema</a>
<a href="{repo}/discussions">Discussões</a>
<a href="{repo}/wiki">Wiki</a>
</nav>
<main>
"""
PE = """</main>
<footer>Feito por pessoas, sem financiamento. Quer ajudar? Veja <a href="{repo}/blob/main/.github/CONTRIBUTING.md">como contribuir</a>.</footer>
</body>
</html>
"""


def titulo_e_descricao(markdown: str) -> tuple[str, str]:
    """O primeiro título e o primeiro parágrafo de texto do README."""
    titulo = next((m.group(1) for m in re.finditer(r"^# (.+)$", markdown, re.MULTILINE)), "Hefesto")
    for linha in markdown.splitlines():
        texto = linha.strip()
        if texto and not texto.startswith(("#", "<", "[", "!", "|", "-", "*")):
            return titulo, texto
    return titulo, titulo


def imagens_citadas(pagina: str) -> list[str]:
    """Os caminhos relativos de `src="..."` na página (os de rede ficam de fora)."""
    return [s for s in re.findall(r'src="([^"]+)"', pagina) if not re.match(r"[a-z]+://|//|data:", s)]


def links_para_o_repositorio(pagina: str) -> str:
    """Os links relativos do README (`docs/usage/x.md`) passam a apontar para o arquivo no repositório:
    a página não tem essas pastas, e o link relativo cairia num 404."""
    def troca(m: re.Match[str]) -> str:
        alvo = m.group(1)
        if re.match(r"[a-z][a-z0-9+.-]*:|//|#", alvo):
            return m.group(0)
        tipo = "tree" if alvo.endswith("/") else "blob"
        return f'href="{REPO}/{tipo}/main/{alvo.removeprefix("./")}"'

    return re.sub(r'href="([^"]+)"', troca, pagina)


def links_relativos(pagina: str) -> list[str]:
    """Os `href` que continuam relativos na página (deviam ser nenhum)."""
    return [h for h in re.findall(r'href="([^"]+)"', pagina) if not re.match(r"[a-z][a-z0-9+.-]*:|//|#", h)]


def montar(raiz: Path, saida: Path) -> list[str]:
    """Escreve `saida/index.html` e copia as imagens; devolve as que o README cita e não existem."""
    markdown = (raiz / "README.md").read_text(encoding="utf-8")
    corpo = MarkdownIt("commonmark", {"html": True}).enable("table").render(markdown)
    titulo, descricao = titulo_e_descricao(markdown)
    pagina = (CABECA.format(titulo=html.escape(titulo), descricao=html.escape(descricao, quote=True), repo=REPO)
              + links_para_o_repositorio(corpo) + PE.format(repo=REPO))
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "index.html").write_text(pagina, encoding="utf-8")
    for pasta in PASTAS_DE_IMAGEM:
        origem = raiz / pasta
        if origem.is_dir():
            shutil.copytree(origem, saida / pasta, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("*.txt", "maximizada"))
    return [s for s in imagens_citadas(pagina) if not (saida / s).is_file()]


def principal(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--raiz", type=Path, default=RAIZ)
    a = ap.parse_args(argv)
    faltam = montar(a.raiz, a.saida)
    if faltam:
        print("montar_pagina: o README cita imagem que não está na página: " + ", ".join(faltam),
              file=sys.stderr)
        return 1
    print(f"montar_pagina: {a.saida / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
