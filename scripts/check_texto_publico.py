#!/usr/bin/env python3
"""check_texto_publico.py — o texto que quem usa lê fala com quem usa."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

RAIZ_PADRAO = Path(__file__).resolve().parents[1]

ARQUIVOS = (
    "README.md",
    "NOTICE",
    "CHANGELOG.md",
    "flatpak/io.github.hefesto_team.hefesto_dualsense4unix.metainfo.xml",
)

PASTAS = (
    ("docs/usage", ()),
    (".github", (".github/workflows",)),
)

EXCLUIDOS: dict[str, str] = {
    "docs/usage/assets/CONFERIDO-EM.txt": "recibo das fotos: o commit conferido e o que se mediu",
    "docs/usage/assets/CONFERIDO-EM.md": "recibo das fotos, a versão legível do .txt",
    "docs/usage/assets/PROVA-DA-FOTO.txt": "recibo que o retratista escreve junto com as fotos",
    "docs/usage/assets/maximizada/PROVA-DA-FOTO.txt": "o mesmo recibo, da vista maximizada",
}

SUFIXOS_DE_TEXTO = frozenset({".md", ".txt", ".xml", ".yml", ".yaml", ""})

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
    """O que a lista promete varrer e não está no disco."""
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
