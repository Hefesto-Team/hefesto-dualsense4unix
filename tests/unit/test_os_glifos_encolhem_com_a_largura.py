"""Os 16 glifos da aba Controles encolhem quando a página estreita."""

from __future__ import annotations

import pathlib


RAIZ = pathlib.Path(__file__).resolve().parents[2]
GERADOR = RAIZ / "src/hefesto_dualsense4unix/interface/aba02.py"

REGRA = ".gb svg{width:100%;height:auto;max-width:38px;max-height:38px}"


def test_o_gerador_traz_a_regra() -> None:
    assert REGRA in GERADOR.read_text(encoding="utf-8"), (
        "sem esta regra o <svg> fica nos 38px do atributo e a coluna corta o desenho"
    )


def test_o_gb_deixa_a_coluna_encolher() -> None:
    """`min-width:0` no item da grade, senão a coluna não encolhe abaixo do conteúdo."""
    fonte = GERADOR.read_text(encoding="utf-8")
    bloco = fonte[fonte.index("  .gb{") : fonte.index("  .gb{") + 260]
    assert "min-width:0" in bloco, (
        "`.gb` sem `min-width:0`: a coluna trava no tamanho do conteúdo e o "
        "`width:100%` do svg não tem para onde encolher"
    )
