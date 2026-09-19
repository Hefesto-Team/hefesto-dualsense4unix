"""Os 16 glifos da aba Controles encolhem quando a página estreita.

19/09/2026 — pedido dela: *"queria que os svgs da aba controles ficassem
menores a medida que a largura da página horizontal diminua pra comportar
ali"*.  <!-- noqa-acento: citação literal dela -->

O `glifo()` emite `width="38" height="38"` no `<svg>` e a grade é
`repeat(4,1fr)`: as colunas encolhem, o desenho não. Na foto dela o triângulo e
o R2 saíam cortados pela borda do quadro.

**MEDIDO COM A CURA E SEM ELA**, nas mesmas quatro larguras:

    janela 1600px · svg 38px   |  sem a cura: 38px
    janela 1200px · svg 38px   |  sem a cura: 38px
    janela  940px · svg 28px   |  sem a cura: 38px
    janela  820px · svg 22px   |  sem a cura: 38px

Esta régua lê o CSS publicado, e não o navegador: o portão de tela tem dono
próprio (`check_pecas_do_dualsense.py`), e uma régua de unidade que abre Chrome
paga 20 s por corrida em 24 partes.
"""

from __future__ import annotations

import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PAGINA = RAIZ / "src/hefesto_dualsense4unix/interface/paginas/02-controles.html"
GERADOR = RAIZ / "src/hefesto_dualsense4unix/interface/aba02.py"

#: A regra que faz o desenho seguir a coluna. `max-width` é o que guarda o
#: tamanho aprovado: a peça nunca fica MAIOR que os 38 do desenho.
REGRA = ".gb svg{width:100%;height:auto;max-width:38px;max-height:38px}"


def test_o_gerador_traz_a_regra() -> None:
    assert REGRA in GERADOR.read_text(encoding="utf-8"), (
        "sem esta regra o <svg> fica nos 38px do atributo e a coluna corta o desenho"
    )


def test_a_pagina_publicada_traz_a_regra() -> None:
    """Curar o gerador e não publicar deixa a tela dela igual."""
    if not PAGINA.exists():  # pragma: no cover — árvore sem a página publicada
        pytest.skip(f"{PAGINA.name} não está publicada nesta árvore")
    assert REGRA in PAGINA.read_text(encoding="utf-8"), (
        "o gerador mudou e a página não — falta "
        "`check_o_desenho_aprovado.py --publicar 02`"
    )


def test_o_gb_deixa_a_coluna_encolher() -> None:
    """`min-width:0` no item da grade, senão a coluna não encolhe abaixo do conteúdo.

    Item de grid/flex tem `min-width:auto` por padrão, que é o tamanho do
    conteúdo — o `width:100%` do svg mediria contra um piso que nunca desce.
    """
    fonte = GERADOR.read_text(encoding="utf-8")
    bloco = fonte[fonte.index("  .gb{") : fonte.index("  .gb{") + 260]
    assert "min-width:0" in bloco, (
        "`.gb` sem `min-width:0`: a coluna trava no tamanho do conteúdo e o "
        "`width:100%` do svg não tem para onde encolher"
    )
