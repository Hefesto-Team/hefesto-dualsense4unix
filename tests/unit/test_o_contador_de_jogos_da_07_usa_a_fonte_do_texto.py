#!/usr/bin/env python3
"""O contador de jogos de cada lançador da 07 usa a fonte do texto, a mesma do nome da linha.

O-CONTADOR-DE-JOGOS-DA-07-USA-A-FONTE-DO-TEXTO-01: o «0 jogos» saía na família mono ao lado do
nome do lançador na fonte do texto. O número pode ser tabular, nunca a família mono.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _pasta in ("src", "src/hefesto_dualsense4unix/interface"):
    if str(RAIZ / _pasta) not in sys.path:
        sys.path.insert(0, str(RAIZ / _pasta))

from hefesto_dualsense4unix.interface import desenho_da_experimental, onde

CHROME = pathlib.Path("/usr/bin/google-chrome")

OS_CONTADORES = """
() => Array.from(document.querySelectorAll('.lf .lf-n')).filter((n) => n.textContent.trim())
  .map((n) => {
    const rotulo = n.closest('.lf').querySelector('.lanc-nome');
    return {texto: n.textContent.trim(), fonte: getComputedStyle(n).fontFamily,
            numeros: getComputedStyle(n).fontVariantNumeric,
            rotulo: rotulo ? getComputedStyle(rotulo).fontFamily : null};
  })
"""


def _regra_do_contador(css: str) -> str:
    achada = re.search(r"\.lf-nome-2 \.lf-n \{[^}]*\}", css)
    assert achada is not None, "a regra do contador de jogos sumiu do CSS da 07"
    return achada.group(0)


def test_a_regra_do_contador_nao_usa_a_familia_mono() -> None:
    """Prova da D-2610-O-CONTADOR-USA-A-FONTE-DO-TEXTO."""
    regra = _regra_do_contador(desenho_da_experimental.CSS)
    assert "font-family" not in regra and "Mono" not in regra, regra
    assert "tabular-nums" in regra, regra


def test_a_bancada_da_07_tem_a_regra_do_gerador() -> None:
    pagina = onde.pagina("07-lancadores.html").read_text(encoding="utf-8")
    assert _regra_do_contador(pagina) == _regra_do_contador(desenho_da_experimental.CSS)


@pytest.mark.skipif(not CHROME.exists(), reason="sem o Chrome do sistema: a régua não tem motor")
@pytest.mark.parametrize("largura", [1212, 1918])
def test_o_contador_tem_a_fonte_do_nome_da_linha(largura: int) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = navegador.new_page(viewport={"width": largura, "height": 900})
            pg.goto(onde.pagina("07-lancadores.html").as_uri())
            contadores = pg.evaluate(OS_CONTADORES)
        finally:
            navegador.close()
    assert contadores, "a 07 não mostrou contador de jogos nenhum"
    for c in contadores:
        assert c["rotulo"] is not None, c
        assert c["fonte"] == c["rotulo"], f"a {largura} px, o contador saiu noutra fonte: {c}"
        assert "Mono" not in c["fonte"], c
        assert c["numeros"] == "tabular-nums", c
