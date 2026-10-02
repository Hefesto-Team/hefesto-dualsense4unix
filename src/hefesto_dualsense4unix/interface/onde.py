#!/usr/bin/env python3
"""Onde mora cada página: a BANCADA e o PUBLICADO. Dono único das duas pastas."""
from __future__ import annotations

import os
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parents[3]

AQUI = pathlib.Path(__file__).resolve().parent

BANCADA = RAIZ / "mockup"

PUBLICADO = AQUI / "paginas"  # noqa-acento (`paginas` e o nome da PASTA; caminho nao leva acento)


#: um diretório temporário, `pagina()` e `gravar()` passam a escrever lá  # (noqa-acento): função
_DESVIO = "HEFESTO_BANCADA"


def saida() -> pathlib.Path:
    """Para onde os geradores escrevem AGORA: a bancada, ou o desvio do portão."""
    desviado = os.environ.get(_DESVIO)
    return pathlib.Path(desviado) if desviado else BANCADA


def pagina(nome: str, publicado: bool = False) -> pathlib.Path:
    """O caminho de uma página, na bancada (padrão) ou no publicado."""
    return (PUBLICADO if publicado else saida()) / nome


def paginas(publicado: bool = False) -> list[pathlib.Path]:
    """As páginas da pasta, em ordem. Só `.html`, sem os `.dc.html` do Design."""
    pasta = PUBLICADO if publicado else BANCADA
    return sorted(
        p
        for p in pasta.glob("*.html")
        if not p.name.startswith(".") and not p.name.endswith(".dc.html")
    )


def gravar(nome: str, doc: str) -> pathlib.Path:
    """Grava uma página na bancada, SEM espaço sobrando no fim das linhas."""
    destino = pagina(nome)
    destino.write_text("\n".join(linha.rstrip() for linha in doc.split("\n")))
    return destino
