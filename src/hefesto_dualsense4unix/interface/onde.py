#!/usr/bin/env python3
"""Onde mora cada página: o MOCKUP e o PUBLICADO. Dono único das duas pastas."""
from __future__ import annotations

import os
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parents[3]

AQUI = pathlib.Path(__file__).resolve().parent

ENSAIO = RAIZ / "mockup"

PUBLICADO = AQUI / "paginas"  # (noqa-acento)


_DESVIO = "HEFESTO_ENSAIO"


def saida() -> pathlib.Path:
    """Para onde os geradores escrevem AGORA: o mockup, ou o desvio do portão."""
    desviado = os.environ.get(_DESVIO)
    return pathlib.Path(desviado) if desviado else ENSAIO


def pagina(nome: str, publicado: bool = False) -> pathlib.Path:
    """O caminho de uma página, no mockup (padrão) ou no publicado."""
    return (PUBLICADO if publicado else saida()) / nome


def paginas(publicado: bool = False) -> list[pathlib.Path]:
    """As páginas da pasta, em ordem. Só `.html`, sem os `.dc.html` do Design."""
    pasta = PUBLICADO if publicado else ENSAIO
    return sorted(
        p
        for p in pasta.glob("*.html")
        if not p.name.startswith(".") and not p.name.endswith(".dc.html")
    )


def gravar(nome: str, doc: str) -> pathlib.Path:
    """Grava uma página no mockup, SEM espaço sobrando no fim das linhas."""
    destino = pagina(nome)
    destino.write_text("\n".join(linha.rstrip() for linha in doc.split("\n")))
    return destino
