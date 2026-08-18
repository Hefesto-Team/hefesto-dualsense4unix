#!/usr/bin/env python3
"""Reprova quando um documento cita arquivo, caminho ou script que não existe.

Motivação (sprint PORTÃO-VIVO-01, bloco F): a documentação deste projeto
descreve garantias que ninguém verifica. O caso canônico está em
`docs/adr/011-glyphs-vs-emojis.md`, que afirma duas vezes que o hook
"guardian.py" cobre os proibidos -- e esse arquivo não existe nesta árvore.
Uma decisão arquitetural inteira se apoia num arquivo imaginário.

Filosofia deste portão: FALSO POSITIVO EM MASSA TORNA O GATE INÚTIL. Por isso
ele é deliberadamente conservador e só reclama do que tem cara inequívoca de
caminho de arquivo DESTE repositório:

  - o texto precisa estar dentro de crase (`assim`) ou ser o alvo de um link
    markdown no formato [texto](alvo);
  - precisa terminar numa extensão da casa (.py, .sh, .md, .yml, .yaml, .toml,
    .glade, .rules);
  - nome solto, sem barra, só é cobrado para .py e .sh -- código executável que
    ou está no repositório ou não está. Nome solto de configuração
    (`daemon.toml`, `controllers.json`) é artefato de tempo de execução que
    vive em ~/.config, e por isso fica de fora;
  - caminho absoluto (/etc/...), caminho de HOME (~/...), variável de shell
    ($VAR), URL, glob, placeholder entre sinais de menor e maior, e `..` são
    ignorados;
  - bloco de código cercado por três crases é ignorado inteiro: ali mora
    comando de terminal, não referência a arquivo do repositório.

A verificação aceita SUFIXO: `gui/main.glade` casa com o caminho real
`src/hefesto_dualsense4unix/gui/main.glade`, porque a casa cita caminho
encurtado o tempo todo e cobrar o caminho completo seria ruído puro.

Escapes, para o portão não virar impossível de satisfazer:
  - `EXTERNOS`, abaixo: nomes que pertencem a projetos de fora;
  - marcador de linha `<!-- ref-externa -->` (ou `<!-- ref-externa: motivo -->`)
    no próprio documento, para a linha que fala de um arquivo ausente DE
    PROPÓSITO -- por exemplo uma sprint que documenta justamente a ausência.

Uso:
    python3 scripts/validar-referencias-docs.py --all
    python3 scripts/validar-referencias-docs.py docs/adr/011-glyphs-vs-emojis.md
    python3 scripts/validar-referencias-docs.py --root /outro/repo --all
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import NamedTuple

#: Extensões que contam como "arquivo desta casa" quando o texto tem barra.
EXTENSOES = frozenset(
    {".py", ".sh", ".md", ".yml", ".yaml", ".toml", ".glade", ".rules"}
)

#: Extensões cobradas também quando o nome vem solto, sem nenhuma barra.
#: Restrito a código executável de propósito: é o que gera afirmação falsa do
#: tipo "o hook guardian.py cobre isso".
EXTENSOES_NOME_SOLTO = frozenset({".py", ".sh"})

#: Diretórios que não entram no índice de arquivos existentes.
DIRS_IGNORADOS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "flatpak-repo",
        "flatpak-build-dir",
        "dist",
        "build",
        ".eggs",
    }
)

#: Documentos que não são varridos. `history/` e `research/` são arquivo morto
#: por definição -- descrevem o repositório como ele era, e cobrar deles o
#: presente é cobrar o impossível. É a mesma exclusão que o gate de acentuação
#: já aplica no .pre-commit-config.yaml.
PREFIXOS_IGNORADOS = ("docs/history/", "docs/research/")

#: Arquivos que existem, mas em OUTRO projeto. Citar `pydualsense.py` é citar a
#: biblioteca de terceiros; citar `universal-sanitizer.py` é citar a ferramenta
#: do ambiente da máquina. Nenhum dos dois deveria estar versionado aqui.
EXTERNOS = frozenset(
    {
        "pydualsense.py",
        "universal-sanitizer.py",
        "setup.py",
        "conftest.py",
    }
)

#: Marcador que a autora do documento pode escrever para dizer "eu sei que este
#: arquivo não existe, e o assunto do parágrafo é exatamente esse".
MARCADOR_ISENCAO = "<!-- ref-externa"

_CRASE = re.compile(r"`([^`\n]{1,120})`")
_LINK = re.compile(r"\]\(([^)\s]{1,200})\)")
_CERCA = re.compile(r"^\s*(```|~~~)")
_TOKEN_LIMPO = re.compile(r"[A-Za-z0-9._/+-]+")


class Achado(NamedTuple):
    """Uma referência morta: documento, linha e o texto citado."""

    documento: str
    linha: int
    alvo: str

    def __str__(self) -> str:
        return f"  {self.documento}:{self.linha}: {self.alvo}"


def indexar(raiz: Path) -> set[str]:
    """Devolve todo caminho do repositório mais todos os seus sufixos.

    Indexar sufixo é o que faz `gui/main.glade` casar com o caminho real
    `src/hefesto_dualsense4unix/gui/main.glade`. Diretório entra junto: a
    documentação cita `docs/process/sprints/` tanto quanto cita arquivo.

    Percorre o disco em vez de perguntar ao git de propósito: `git ls-files` é
    cego a arquivo novo ainda não adicionado ao índice, e o arquivo recém
    criado é justamente o que a documentação acabou de passar a citar.
    """
    sufixos: set[str] = set()
    for pasta, subpastas, arquivos in os.walk(raiz):
        subpastas[:] = [d for d in subpastas if d not in DIRS_IGNORADOS]
        base = Path(pasta)
        for nome in list(arquivos) + list(subpastas):
            try:
                relativo = (base / nome).relative_to(raiz).as_posix()
            except ValueError:  # pragma: no cover - defensivo
                continue
            partes = relativo.split("/")
            for corte in range(len(partes)):
                sufixos.add("/".join(partes[corte:]))
    return sufixos


def candidatos_da_linha(linha: str) -> list[str]:
    """Extrai da linha os textos com cara de caminho de arquivo.

    A origem importa. Texto entre crases é ambíguo -- pode ser nome de módulo,
    de comando ou de conceito -- e por isso passa pelo filtro estreito de
    `EXTENSOES_NOME_SOLTO`. Já o alvo de um link markdown é inequívoco: quem
    escreve [texto](alvo) está afirmando que existe algo naquele caminho. Um
    índice de sprints apontando para arquivo que não existe é justamente um
    dos defeitos que a sprint mandou pegar, e ele aparece só nessa forma.
    """
    brutos = [(m.group(1), True) for m in _CRASE.finditer(linha)]
    brutos += [(m.group(1), False) for m in _LINK.finditer(linha)]

    limpos: list[str] = []
    for bruto, veio_de_crase in brutos:
        texto = bruto.strip()
        if not texto or " " in texto:
            continue
        if texto.startswith(("http://", "https://", "mailto:", "#")):
            continue
        # `arquivo.py:551-567` e `doc.md#secao` citam trecho: fica só o caminho.
        texto = texto.split(":", 1)[0].split("#", 1)[0]
        if texto.startswith("./"):
            texto = texto[2:]
        if not texto:
            continue
        if texto[0] in "/~$":
            continue
        if any(ruim in texto for ruim in ("*", "?", "<", ">", "..", "{", "}")):
            continue
        if not _TOKEN_LIMPO.fullmatch(texto):
            continue
        extensao = Path(texto).suffix
        if extensao not in EXTENSOES:
            continue
        if veio_de_crase and "/" not in texto and extensao not in EXTENSOES_NOME_SOLTO:
            continue
        if Path(texto).name in EXTERNOS:
            continue
        limpos.append(texto)
    return limpos


def varrer_documento(caminho: Path, raiz: Path, sufixos: set[str]) -> list[Achado]:
    """Devolve as referências mortas de um documento."""
    try:
        conteudo = caminho.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    relativo_doc = caminho.resolve().relative_to(raiz).as_posix()
    achados: list[Achado] = []
    dentro_de_cerca = False

    for numero, linha in enumerate(conteudo.splitlines(), start=1):
        if _CERCA.match(linha):
            dentro_de_cerca = not dentro_de_cerca
            continue
        if dentro_de_cerca:
            continue
        if MARCADOR_ISENCAO in linha:
            continue

        for referencia in candidatos_da_linha(linha):
            if referencia in sufixos:
                continue
            # Última chance: link relativo ao diretório do próprio documento.
            vizinho = (caminho.parent / referencia).resolve()
            try:
                relativo = vizinho.relative_to(raiz).as_posix()
            except ValueError:
                relativo = None
            if relativo is not None and relativo in sufixos:
                continue
            achados.append(Achado(relativo_doc, numero, referencia))
    return achados


def documentos_de(raiz: Path) -> list[Path]:
    """Todos os .md sob docs/, menos o arquivo morto."""
    pasta = raiz / "docs"
    if not pasta.is_dir():
        return []
    encontrados = []
    for md in sorted(pasta.rglob("*.md")):
        relativo = md.relative_to(raiz).as_posix()
        if relativo.startswith(PREFIXOS_IGNORADOS):
            continue
        encontrados.append(md)
    return encontrados


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reprova documento que cita arquivo inexistente."
    )
    parser.add_argument("arquivos", nargs="*", type=Path, help="documentos a varrer")
    parser.add_argument("--all", action="store_true", help="varre docs/ inteiro")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="raiz do repositório (padrão: a deste script)",
    )
    args = parser.parse_args(argv)

    raiz = args.root.resolve()
    if not raiz.is_dir():
        print(f"ERRO: raiz inexistente: {raiz}")
        return 2

    if args.all:
        alvos = documentos_de(raiz)
    else:
        alvos = [p for p in args.arquivos if p.suffix == ".md" and p.is_file()]
    if not alvos:
        print("Nenhum documento para varrer.")
        return 0

    sufixos = indexar(raiz)
    achados: list[Achado] = []
    for alvo in alvos:
        achados.extend(varrer_documento(alvo, raiz, sufixos))

    if achados:
        print(f"{len(achados)} referência(s) morta(s) em {len(alvos)} documento(s):")
        for achado in achados:
            print(str(achado))
        print("")
        print("Cada linha acima cita um arquivo que NÃO existe nesta árvore.")
        print("Corrija o caminho, crie o arquivo, ou -- se a ausência for o")
        print("assunto do parágrafo -- marque a linha com o comentário")
        print("de isenção descrito no cabeçalho deste script.")
        return 1

    print(f"OK: {len(alvos)} documento(s) sem referência morta.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
