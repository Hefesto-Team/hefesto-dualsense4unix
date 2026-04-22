#!/usr/bin/env python3
"""generate_glyph_active.py — gera versoes _active.svg substituindo fill/stroke
de '#f8f8f2' (fg Dracula) por '#bd93f9' (roxo Dracula — estado pressionado).

Uso:
    python3 scripts/generate_glyph_active.py

Saida: assets/glyphs/<nome>_active.svg para cada assets/glyphs/<nome>.svg.
"""
from __future__ import annotations

import pathlib
import sys

FG_PADRAO = "#f8f8f2"
FG_ATIVO = "#bd93f9"

GLYPHS_DIR = pathlib.Path(__file__).parent.parent / "assets" / "glyphs"


def gerar(svg_path: pathlib.Path) -> pathlib.Path:
    """Substitui a cor padrao pela cor ativa e salva como _active.svg."""
    conteudo = svg_path.read_text(encoding="utf-8")
    conteudo_ativo = conteudo.replace(FG_PADRAO, FG_ATIVO)
    destino = svg_path.with_name(svg_path.stem + "_active.svg")
    destino.write_text(conteudo_ativo, encoding="utf-8")
    return destino


def main() -> int:
    """Ponto de entrada principal."""
    candidatos = sorted(GLYPHS_DIR.glob("*.svg"))
    # Excluir arquivos _active.svg existentes para não processar o proprio output.
    fontes = [p for p in candidatos if not p.stem.endswith("_active")]

    if not fontes:
        print(f"Nenhum SVG encontrado em {GLYPHS_DIR}", file=sys.stderr)
        return 1

    gerados = 0
    for svg in fontes:
        destino = gerar(svg)
        print(f"gerado: {destino.name}")
        gerados += 1

    print(f"\n{gerados} versoes _active.svg geradas em {GLYPHS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
