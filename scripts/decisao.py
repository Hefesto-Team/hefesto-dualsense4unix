#!/usr/bin/env python3
"""A consulta curta ao registro de decisões: `decisao.py <termo>... [--inteira] [--csv ARQ]`.

Imprime, de cada decisão cuja linha casa com todos os termos (sem caixa nem acento), o id, o estado,
o título, a escolha (cortada em 400 letras; `--inteira` a mostra toda) e a decisão que esta revoga. A
deliberação (`caminhos`, `preco_do_outro_lado` e as outras colunas) não sai. rc=0 com decisão
achada, rc=1 sem nenhuma.
"""
from __future__ import annotations

import argparse
import csv
import pathlib
import sys
import unicodedata

RAIZ = pathlib.Path(__file__).resolve().parents[1]
CSV_DAS_DECISOES = RAIZ / "docs" / "data" / "decisoes-de-produto.csv"
CORTE_DA_ESCOLHA = 400


def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.casefold())
                   if unicodedata.category(c) != "Mn")


def consultar(termos: list[str], caminho: pathlib.Path = CSV_DAS_DECISOES) -> list[dict[str, str]]:
    procurados = [sem_acento(t) for t in termos]
    with caminho.open(encoding="utf-8", newline="") as f:
        linhas = list(csv.DictReader(f))
    return [d for d in linhas
            if all(t in sem_acento(" ".join(v or "" for v in d.values())) for t in procurados)]


def linha_curta(d: dict[str, str], inteira: bool = False) -> str:
    escolha = d.get("escolha") or ""
    if not inteira and len(escolha) > CORTE_DA_ESCOLHA:
        escolha = escolha[:CORTE_DA_ESCOLHA].rsplit(" ", 1)[0] + " … (--inteira)"
    texto = f"{d.get('id', '')} [{d.get('estado', '')}] {d.get('titulo', '')}\n  escolha: {escolha}"
    if (d.get("revoga") or "").strip():
        texto += f"\n  revoga: {d['revoga']}"
    return texto


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("termo", nargs="+")
    ap.add_argument("--inteira", action="store_true")
    ap.add_argument("--csv", type=pathlib.Path, default=CSV_DAS_DECISOES)
    a = ap.parse_args(argv)
    achadas = consultar(a.termo, a.csv)
    for d in achadas:
        print(linha_curta(d, a.inteira))
    print(f"{len(achadas)} decisão(ões) casam {' '.join(a.termo)!r}")
    return 0 if achadas else 1


if __name__ == "__main__":
    sys.exit(main())
