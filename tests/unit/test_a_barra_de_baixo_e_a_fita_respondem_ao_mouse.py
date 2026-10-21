"""A barra de baixo e a fita respondem ao mouse (A-BARRA-DE-BAIXO-E-A-FITA-RESPONDEM-AO-MOUSE-01).

Medido em 20/10/2026, no piloto a 1212 px: nenhuma regra `:hover` alcançava os quatro botões da
barra de baixo nem os chips da fita «Selecionar». A cura mora na folha do topo (`topo.html`), que
as dez páginas do desenho copiam: o fundo leve da cor de cada botão de contorno, o Aplicar que
clareia, e o chip da fita que se clica com o tom da cor do plástico (o «Todos», a borda
`--texto-suave`). A fita `.inerte` não escolhe nada, e por isso não responde.

MORDIDA (executada em 21/10/2026): sem as regras no `topo.html` e as dez geradas de novo,
`test_cada_botao_da_barra_tem_hover` e `test_o_chip_da_fita_tem_hover` reprovam nas dez.
"""

from __future__ import annotations

import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
TOPO = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "topo.html"
DEZ = sorted((RAIZ / "mockup").glob("[01][0-9]-*.html"))
BOTOES = ("r-aplicar", "r-salvar", "r-importar", "r-exportar")
CHAVE = re.compile(r"[{}]")
COMENTARIO = re.compile(r"/\*.*?\*/", re.S)


def _regras_hover(texto: str) -> list[tuple[str, str]]:
    """As regras com `:hover` no seletor, numa passada só pelas chaves (uma regex com `[^{}]+`
    solto volta atrás em cada trecho sem chave, e numa página de 400 KB passa de cinco minutos)."""
    saida = []
    depois_da_ultima, seletor = 0, ""
    for chave in CHAVE.finditer(texto):
        trecho = texto[depois_da_ultima:chave.start()]
        if chave.group() == "{":
            seletor = COMENTARIO.sub("", trecho)
        elif ":hover" in seletor:
            saida.append((seletor.strip(), trecho))
            seletor = ""
        else:
            seletor = ""
        depois_da_ultima = chave.end()
    return saida


def test_sao_dez_paginas() -> None:
    assert len(DEZ) == 10, [p.name for p in DEZ]


@pytest.mark.parametrize("desenho", DEZ, ids=lambda p: p.name)
@pytest.mark.parametrize("botao", BOTOES)
def test_cada_botao_da_barra_tem_hover(desenho: pathlib.Path, botao: str) -> None:
    regras = _regras_hover(desenho.read_text(encoding="utf-8"))
    casam = [corpo for sel, corpo in regras if re.search(rf"\.rodape \.{botao}:hover\b", sel)]
    assert casam, f"{desenho.name}: nenhuma regra :hover para o .{botao}"
    assert all("background:" in corpo for corpo in casam), casam


@pytest.mark.parametrize("desenho", DEZ, ids=lambda p: p.name)
def test_o_chip_da_fita_tem_hover(desenho: pathlib.Path) -> None:
    regras = _regras_hover(desenho.read_text(encoding="utf-8"))
    chips = {sel: corpo for sel, corpo in regras if ".fita:not(.inerte) .chip" in sel}
    assert any(".chip.plastico:hover:not(.on)" in s and "var(--plastico" in c
               for s, c in chips.items()), f"{desenho.name}: o chip do plástico não ganha o tom"
    assert any(".chip:not(.plastico):hover:not(.on)" in s and "var(--texto-suave)" in c
               for s, c in chips.items()), f"{desenho.name}: o «Todos» não ganha a borda"


def test_a_fita_inerte_nao_responde() -> None:
    """Nenhuma regra :hover do topo alcança o chip de uma fita `.inerte` (ela não escolhe nada)."""
    for sel, _ in _regras_hover(TOPO.read_text(encoding="utf-8")):
        if ".chip" in sel and ".fita" in sel:
            assert ".fita:not(.inerte)" in sel, sel


def test_o_tom_sai_do_token_com_o_rgba_da_casa_antes() -> None:
    """O tema que troca o token leva o tom junto; o `rgba` antes vale no motor sem `color-mix`."""
    texto = TOPO.read_text(encoding="utf-8")
    for botao, token in (("r-salvar", "--purple"), ("r-importar", "--orange"),
                         ("r-exportar", "--comment"), ("r-aplicar", "--green")):
        corpo = next(c for s, c in _regras_hover(texto) if f".{botao}:hover" in s)
        assert f"color-mix(in srgb,var({token})" in corpo, (botao, corpo)
        primeiro = corpo.index("background:")
        assert "color-mix" not in corpo[primeiro:corpo.index(";", primeiro)], corpo
