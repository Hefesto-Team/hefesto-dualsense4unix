#!/usr/bin/env python3
"""Monta a página do produto (a que o GitHub Pages publica) a partir do README e das fotos.

  montar_pagina.py --saida _site

O `README.md` vira o `index.html`; as imagens que ele cita (`docs/usage/assets/`, `assets/appimage/`)
são copiadas com o mesmo caminho, e o texto não muda: a página e o README dizem a mesma coisa.
Precisa do `markdown-it-py` (o produto já o traz pelo `textual`).

Ao fim da página entra a seção «Apoie», lida do `.github/FUNDING.yml` (o dono único das chaves): `github` (GitHub
Sponsors), `ko_fi`, `patreon` e `custom` (o PIX, com o QR code). Chave comentada ou vazia não aparece; nenhum
endereço nem QR nasce de outra fonte, então preencher a chave basta. Um `custom` que é endereço `https://` vira o
link e o QR dele; um que é o código «copia e cola» do PIX (`000201...`) vira o QR e o texto para copiar.
"""
from __future__ import annotations

import argparse
import html
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from markdown_it import MarkdownIt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qr_svg import svg_do_qr

RAIZ = Path(__file__).resolve().parents[2]
# Onde moram as imagens do README, relativas à raiz do repositório.
PASTAS_DE_IMAGEM = ("docs/usage/assets", "assets/appimage")
REPO = "https://github.com/Hefesto-Team/hefesto-dualsense4unix"
FUNDING = ".github/FUNDING.yml"
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
#apoie {{ margin-top: 40px; padding-top: 8px; border-top: 1px solid var(--borda); }}
#apoie ul {{ padding-left: 20px; }}
#apoie figure {{ display: inline-block; margin: 12px 24px 12px 0; text-align: center; vertical-align: top; }}
#apoie figure svg {{ width: 168px; height: 168px; border: 1px solid var(--borda); border-radius: 6px; }}
#apoie figcaption {{ color: var(--suave); font-size: 14px; max-width: 220px; }}
#apoie textarea {{ width: 100%; box-sizing: border-box; background: var(--bloco); color: var(--texto);
  border: 1px solid var(--borda); border-radius: 6px; font: 13px/1.4 ui-monospace, monospace; padding: 8px; }}
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
<a href="{repo}/wiki">Wiki</a>{apoiar}
</nav>
<main>
"""
PE = """</main>
<footer>Quer ajudar? Veja <a href="{repo}/blob/main/.github/CONTRIBUTING.md">como contribuir</a>.</footer>
</body>
</html>
"""


@dataclass(frozen=True)
class Apoio:
    """Uma forma de apoiar: o rótulo, o endereço (se houver), o QR em SVG (se houver) e o código a copiar."""

    rotulo: str
    url: str | None = None
    qr: str | None = None
    codigo: str | None = None


_USUARIO = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
_URL = re.compile(r"https://[^\s\"'<>]+")
_COPIA_E_COLA = re.compile(r"000201[ -~]{20,}")


def chaves_do_funding(texto: str) -> dict[str, list[str]]:
    """As chaves ATIVAS do `FUNDING.yml` (a forma plana que o GitHub aceita) e seus valores; comentário e chave
    vazia ficam de fora. Sem PyYAML: a página monta no Pages, que só instala o `markdown-it-py`."""
    chaves: dict[str, list[str]] = {}
    atual: str | None = None

    def valor(cru: str) -> str:
        cru = re.sub(r"\s+#.*$", "", cru).strip()
        return cru[1:-1] if len(cru) >= 2 and cru[0] == cru[-1] and cru[0] in "\"'" else cru

    for linha in texto.splitlines():
        if not linha.strip() or linha.lstrip().startswith("#"):
            continue
        item = re.match(r"\s+-\s*(.*)$", linha)
        if item and atual is not None:
            if valor(item.group(1)):
                chaves[atual].append(valor(item.group(1)))
            continue
        chave = re.match(r"([a-z_]+):\s*(.*)$", linha)
        if not chave:
            continue
        atual = chave.group(1)
        chaves.setdefault(atual, [])
        resto = re.sub(r"\s+#.*$", "", chave.group(2)).strip()
        if resto.startswith("["):
            chaves[atual] += [valor(v) for v in resto.strip("[]").split(",") if valor(v)]
        elif resto:
            chaves[atual].append(valor(resto))
    return {k: v for k, v in chaves.items() if v}


def _usuario(chave: str, valor: str) -> str:
    if not _USUARIO.fullmatch(valor):
        raise ValueError(f"{FUNDING}: `{chave}` não é um nome de conta válido: {valor!r}")
    return valor


def _crc_do_pix_confere(codigo: str) -> bool:
    """O código «copia e cola» termina no campo `63` (`6304` + 4 hex): o CRC-16/CCITT do texto até o `6304`.
    Um código copiado pela metade vira um QR que o aplicativo do banco recusa, e ninguém o lê antes de publicar."""
    if len(codigo) < 8 or codigo[-8:-4] != "6304":
        return False
    crc = 0xFFFF
    for byte in codigo[:-4].encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}" == codigo[-4:].upper()


def apoios(raiz: Path) -> list[Apoio]:
    """As formas de apoiar que o `FUNDING.yml` da raiz tem ativas, na ordem da página. Valor que não é nome de
    conta, endereço `https://` nem código PIX levanta `ValueError`: nada é adivinhado nem arrumado."""
    arquivo = raiz / FUNDING
    if not arquivo.is_file():
        return []
    chaves = chaves_do_funding(arquivo.read_text(encoding="utf-8"))
    saida: list[Apoio] = []
    contas = chaves.get("github", [])
    for conta in contas:
        nome = _usuario("github", conta)
        rotulo = "GitHub Sponsors" if len(contas) == 1 else f"GitHub Sponsors ({nome})"
        saida.append(Apoio(rotulo, f"https://github.com/sponsors/{nome}"))
    for conta in chaves.get("ko_fi", []):
        saida.append(Apoio("Ko-fi", f"https://ko-fi.com/{_usuario('ko_fi', conta)}"))
    for conta in chaves.get("patreon", []):
        saida.append(Apoio("Patreon", f"https://www.patreon.com/{_usuario('patreon', conta)}"))
    for alvo in chaves.get("custom", []):
        if _URL.fullmatch(alvo):
            saida.append(Apoio("PIX", alvo, svg_do_qr(alvo, "QR code do PIX")))
        elif _COPIA_E_COLA.fullmatch(alvo):
            if not _crc_do_pix_confere(alvo):
                raise ValueError(f"{FUNDING}: o código PIX não fecha com o CRC do fim (copiado pela metade?)")
            saida.append(Apoio("PIX", None, svg_do_qr(alvo, "QR code do PIX"), alvo))
        else:
            raise ValueError(f"{FUNDING}: `custom` não é um endereço https nem um código PIX: {alvo[:40]!r}")
    return saida


def secao_de_apoio(formas: list[Apoio]) -> str:
    """A seção «Apoie» da página (vazia, se não há forma ativa)."""
    if not formas:
        return ""
    itens, qrs = [], []
    for f in formas:
        e = html.escape
        if f.url:
            itens.append(f'<li><a href="{e(f.url, quote=True)}">{e(f.rotulo)}</a></li>')
        else:
            itens.append(f"<li>{e(f.rotulo)}: leia o QR code abaixo ou copie o código.</li>")
        if f.qr:
            # O código PIX se lê pelo aplicativo do banco; o QR de um endereço, pela câmera do celular.
            leitor = "do aplicativo do banco" if f.codigo else "do celular"
            legenda = f"{e(f.rotulo)}: aponte a câmera {leitor}"
            qrs.append(f"<figure>{f.qr}<figcaption>{legenda}</figcaption></figure>")
        if f.codigo:
            qrs.append(f'<p><label>Código copia e cola do PIX<br><textarea readonly rows="3">'
                       f"{e(f.codigo)}</textarea></label></p>")
    return ('<section id="apoie">\n<h2>Apoie o Hefesto</h2>\n'
            "<p>O Hefesto é livre. Se ele te ajuda, você pode apoiar o trabalho por qualquer um destes caminhos:</p>\n"
            "<ul>\n" + "\n".join(itens) + "\n</ul>\n" + "\n".join(qrs) + "\n</section>\n")


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
    formas = apoios(raiz)
    apoiar = '\n<a href="#apoie">Apoiar</a>' if formas else ""
    pagina = (CABECA.format(titulo=html.escape(titulo), descricao=html.escape(descricao, quote=True), repo=REPO,
                            apoiar=apoiar)
              + links_para_o_repositorio(corpo) + secao_de_apoio(formas) + PE.format(repo=REPO))
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
    try:
        faltam = montar(a.raiz, a.saida)
    except ValueError as erro:
        print(f"montar_pagina: {erro}", file=sys.stderr)
        return 1
    if faltam:
        print("montar_pagina: o README cita imagem que não está na página: " + ", ".join(faltam),
              file=sys.stderr)
        return 1
    print(f"montar_pagina: {a.saida / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
