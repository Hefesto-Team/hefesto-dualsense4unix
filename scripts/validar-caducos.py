#!/usr/bin/env python3
"""validar-caducos.py — o fato declarado caduco não pode continuar publicado."""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CADUCOS_RELATIVO = "docs/data/caducos.csv"
CADUCOS_CAMINHO = RAIZ / CADUCOS_RELATIVO

RAIZES_VIVAS = ("README.md", "docs/usage", "docs/protocol", "src", "po")

EXTENSOES = {".md", ".py", ".html", ".rst", ".txt", ".glade", ".po"}


@dataclass(frozen=True)
class Caduco:
    id: str
    literais: tuple[str, ...]
    explicacao: str
    caducou_em: str
    substituto: str
    onde_pode_ficar: str


class LedgerAusente(Exception):
    """O livro-caixa não está no disco — e isso NÃO é uma varredura limpa."""


def carrega_caducos(caminho: Path) -> list[Caduco]:
    if not caminho.exists():
        raise LedgerAusente(str(caminho))
    with caminho.open(encoding="utf-8", newline="") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    caducos: list[Caduco] = []
    for linha in linhas:
        celula = (linha.get("o_que_caducou") or "").strip()
        literais_txt, separador, explicacao = celula.partition(" — ")
        if not separador:
            literais_txt, explicacao = celula, ""
        literais = tuple(parte.strip() for parte in literais_txt.split("|") if parte.strip())
        caducos.append(
            Caduco(
                id=(linha.get("id") or "").strip(),
                literais=literais,
                explicacao=explicacao.strip(),
                caducou_em=(linha.get("caducou_em") or "").strip(),
                substituto=(linha.get("substituto") or "").strip(),
                onde_pode_ficar=(linha.get("onde_pode_ficar") or "").strip(),
            )
        )
    return caducos


def _arquivos_vivos(raiz: Path) -> list[Path]:
    achados: list[Path] = []
    for relativo in RAIZES_VIVAS:
        caminho = raiz / relativo
        if caminho.is_file():
            achados.append(caminho)
        elif caminho.is_dir():
            for arquivo in sorted(caminho.rglob("*")):
                if not arquivo.is_file():
                    continue
                if "__pycache__" in arquivo.parts:
                    continue
                if arquivo.suffix.lower() not in EXTENSOES:
                    continue
                achados.append(arquivo)
    return achados


def varre(raiz: Path, caducos: list[Caduco]) -> list[str]:
    problemas: list[str] = []
    arquivos = _arquivos_vivos(raiz)
    for arquivo in arquivos:
        try:
            texto = arquivo.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        texto_baixo = texto.lower()
        relativo = str(arquivo.relative_to(raiz))
        for caduco in caducos:
            for literal in caduco.literais:
                if literal.lower() not in texto_baixo:
                    continue
                for numero, linha_txt in enumerate(texto.split("\n"), start=1):
                    if literal.lower() in linha_txt.lower():
                        problemas.append(
                            f"{relativo}:{numero}: publica o literal caduco "
                            f"{literal!r} — declarado caduco em "
                            f"{caduco.caducou_em} ({caduco.id}). "
                            f"{caduco.explicacao} "
                            + (
                                f"Substituto: {caduco.substituto}."
                                if caduco.substituto
                                else "Sem substituto ainda — publique a AUSÊNCIA "
                                "declarada, não um número novo."
                            )
                        )
    return problemas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="roda a varredura (o único modo hoje)")
    parser.add_argument("--raiz", type=Path, default=RAIZ)
    args = parser.parse_args(argv)
    if not args.all:
        parser.error("passe --all")

    raiz = args.raiz.resolve()
    try:
        caducos = carrega_caducos(raiz / CADUCOS_RELATIVO)
    except LedgerAusente:
        print(
            f"FALHA: {CADUCOS_RELATIVO} não existe em '{raiz}' — este portão "
            "acabou de ficar CEGO, e sem o livro-caixa ele não tem o que "
            "procurar. Devolva o arquivo (ou aponte --raiz para a árvore certa); "
            "verde por ausência de fonte é o selo mais caro desta casa."
        )
        return 1
    if not caducos:
        print(
            f"A RÉGUA NÃO MEDIU NADA: {CADUCOS_RELATIVO} existe e está SEM "
            "LINHA nenhuma. Nenhum fato caduco declarado significa nenhuma "
            "busca feita — não confunda isto com uma árvore limpa."
        )
        return 0

    problemas = varre(raiz, caducos)
    if problemas:
        print(f"FALHA: {len(problemas)} publicação(ões) de fato caduco:")
        for problema in problemas:
            print(f"  {problema}")
        return 1

    print(
        f"OK: nenhum dos {len(caducos)} fato(s) caduco(s) de {CADUCOS_RELATIVO} "
        "está publicado nas superfícies vivas "
        f"({', '.join(RAIZES_VIVAS)})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
