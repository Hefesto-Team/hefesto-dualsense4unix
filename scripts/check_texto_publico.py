#!/usr/bin/env python3
"""check_texto_publico.py — o texto que quem usa lê fala com quem usa.

O DEFEITO, medido em 27/09/2026
-------------------------------
As páginas de uso, o README, os modelos de issue e o metainfo são o que chega a
quem instala o Hefesto. Elas vinham carregando o vocabulário de quem o
constrói: o ID da tarefa que fez cada mudança, a data da decisão, «dela», o
caminho de `docs/process/` (que nem viaja no clone), «desta casa», «réguas»,
«portão», «bancada». Quem lê a página não sabe o que é nada disso, e cada linha
assim é uma linha a menos sobre o que o produto faz.

O QUE ELE VARRE
---------------
`README.md`, `docs/usage/` (inteiro, menos os recibos abaixo), `.github/`
(menos `workflows/`, que é código da esteira e ninguém lê como texto),
`NOTICE`, `CHANGELOG.md` e o metainfo do Flatpak. Varre o DISCO, e não o
`git ls-files`: uma página nova é vista antes do `git add`.

AS EXPRESSÕES, e por que cada `\\b`
----------------------------------
O `\\b` dos dois lados é o que separa a palavra do pedaço de palavra: sem ele,
«bancada» pega «desbancada» e «dela» pega «delator». E não há `leva` na lista,
de propósito: «Clicar num cartão leva a fita» é o verbo, e uma régua que
reprovasse isso empurraria quem escreve bem a escrever pior.

O ID é `\\b[A-Z]{2,}(-[A-Z0-9]+)*-[0-9]{2}\\b`: duas maiúsculas ou mais, trechos
opcionais, e o sufixo de dois dígitos. `ADR-009`, `SHA-256`, `CVE-2026-31431`
e `GE-Proton11-7` não casam, e medido em 28/09/2026 nenhum deles aparece como
falso positivo.

OS FALSOS POSITIVOS SE DECLARAM AQUI, pelo arquivo e pelo texto da linha, com a
razão. Uma declaração que deixou de casar reprova também: declaração velha é
lista que mente sobre o que isenta. Em 28/09/2026 a lista está vazia, porque as
páginas foram reescritas e nenhuma ocorrência sobrou.

Saída: 0 limpo, 1 com achado. `--raiz DIR` mede outra árvore (a mordida usa).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

RAIZ_PADRAO = Path(__file__).resolve().parents[1]

#: Arquivos soltos que chegam a quem usa.
ARQUIVOS = (
    "README.md",
    "NOTICE",
    "CHANGELOG.md",
    "flatpak/io.github.hefesto_team.hefesto_dualsense4unix.metainfo.xml",
)

#: Pastas varridas por inteiro, e o que fica de fora de cada uma.
PASTAS = (
    ("docs/usage", ()),
    (".github", (".github/workflows",)),
)

#: FICAM DE FORA, cada um com a razão. Os recibos das fotos são escritos pelo
#: retratista e pela costura de cada entrega: dizem que foto foi conferida em
#: qual commit, e o vocabulário deles é o de quem constrói de propósito. Ninguém
#: os lê como página.
EXCLUIDOS: dict[str, str] = {
    "docs/usage/assets/CONFERIDO-EM.txt": "recibo das fotos: o commit conferido e o que se mediu",
    "docs/usage/assets/CONFERIDO-EM.md": "recibo das fotos, a versão legível do .txt",
    "docs/usage/assets/PROVA-DA-FOTO.txt": "recibo que o retratista escreve junto com as fotos",
    "docs/usage/assets/maximizada/PROVA-DA-FOTO.txt": "o mesmo recibo, da vista maximizada",
}

#: Só texto. Imagem, fonte e afins não têm frase.
SUFIXOS_DE_TEXTO = frozenset({".md", ".txt", ".xml", ".yml", ".yaml", ""})

#: (nome, expressão). As de palavra ignoram a caixa; o ID não, porque é a caixa
#: que o define.
EXPRESSOES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("dela", re.compile(r"\bdela\b", re.IGNORECASE)),
    ("desta casa", re.compile(r"\bdesta casa\b", re.IGNORECASE)),
    ("nesta casa", re.compile(r"\bnesta casa\b", re.IGNORECASE)),
    ("sprint", re.compile(r"\bsprints?\b", re.IGNORECASE)),
    ("régua", re.compile(r"\bréguas?\b", re.IGNORECASE)),
    ("portão", re.compile(r"\bportão\b|\bportões\b", re.IGNORECASE)),
    ("bancada", re.compile(r"\bbancada\b", re.IGNORECASE)),
    ("quem coordena", re.compile(r"quem coordena", re.IGNORECASE)),
    ("docs/process", re.compile(r"docs/process")),
    ("ID", re.compile(r"\b[A-Z]{2,}(?:-[A-Z0-9]+)*-[0-9]{2}\b")),
)

#: OS FALSOS POSITIVOS DECLARADOS: (arquivo, texto exato da linha sem as pontas
#: em branco) -> razão. Vazia em 28/09/2026.
DECLARADOS: dict[tuple[str, str], str] = {}


@dataclass(frozen=True)
class Achado:
    arquivo: str
    linha: int
    expressao: str
    texto: str

    def __str__(self) -> str:
        return f"{self.arquivo}:{self.linha}: [{self.expressao}] {self.texto[:120]}"


def arquivos_varridos(raiz: Path) -> list[Path]:
    """Os arquivos de texto que chegam a quem usa, lidos do disco."""
    achados: list[Path] = []
    for relativo in ARQUIVOS:
        caminho = raiz / relativo
        if caminho.is_file():
            achados.append(caminho)
    for pasta, fora in PASTAS:
        base = raiz / pasta
        if not base.is_dir():
            continue
        for caminho in sorted(base.rglob("*")):
            if not caminho.is_file():
                continue
            relativo = caminho.relative_to(raiz).as_posix()
            if any(relativo == f or relativo.startswith(f + "/") for f in fora):
                continue
            if caminho.suffix.lower() not in SUFIXOS_DE_TEXTO:
                continue
            achados.append(caminho)
    return [c for c in achados if c.relative_to(raiz).as_posix() not in EXCLUIDOS]


def ausentes(raiz: Path) -> list[str]:
    """O que a lista promete varrer e não está no disco.

    Um arquivo renomeado (o metainfo muda de nome junto com o id do Flatpak,
    por exemplo) sairia da varredura calado, e o portão seguiria verde sobre um
    texto que ele não lê mais. Na árvore do projeto isso reprova; na árvore de
    mentira da mordida, não, porque ela só monta o que o caso pede.
    """
    faltam = [r for r in ARQUIVOS if not (raiz / r).is_file()]
    faltam += [p for p, _ in PASTAS if not (raiz / p).is_dir()]
    return faltam


def medir(
    raiz: Path,
    declarados: dict[tuple[str, str], str] | None = None,
) -> tuple[list[Achado], list[tuple[str, str]]]:
    """Os achados não declarados, e as declarações que não casam mais nada."""
    isentos = DECLARADOS if declarados is None else declarados
    usados: set[tuple[str, str]] = set()
    achados: list[Achado] = []
    for caminho in arquivos_varridos(raiz):
        relativo = caminho.relative_to(raiz).as_posix()
        texto = caminho.read_text(encoding="utf-8", errors="replace")
        for numero, linha in enumerate(texto.splitlines(), 1):
            for nome, expressao in EXPRESSOES:
                if not expressao.search(linha):
                    continue
                chave = (relativo, linha.strip())
                if chave in isentos:
                    usados.add(chave)
                    continue
                achados.append(Achado(relativo, numero, nome, linha.strip()))
    velhas = sorted(set(isentos) - usados)
    return achados, velhas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--raiz", type=Path, default=RAIZ_PADRAO)
    args = parser.parse_args(argv)
    raiz = args.raiz.resolve()
    achados, velhas = medir(raiz)
    faltam = ausentes(raiz) if raiz == RAIZ_PADRAO else []
    for achado in achados:
        print(achado)
    for arquivo, linha in velhas:
        print(f"{arquivo}: declaração que não casa mais nada: {linha[:120]}")
    for relativo in faltam:
        print(
            f"{relativo}: está na lista do que se varre e não existe; se mudou de "
            "nome, corrija ARQUIVOS ou PASTAS neste script"
        )
    if faltam and not (achados or velhas):
        return 1
    if achados or velhas:
        print(
            f"\n{len(achados)} trecho(s) do texto público com o vocabulário de quem "
            "constrói. Reescreva para quem usa: diga o que o produto faz, sem o ID, "
            "sem a data da decisão e sem caminho de docs/process. Se for um falso "
            "positivo, declare em DECLARADOS, com a razão, neste script."
        )
        return 1
    print(f"OK: {len(arquivos_varridos(args.raiz.resolve()))} arquivo(s) do texto público limpos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
