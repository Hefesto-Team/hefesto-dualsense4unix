"""A-JANELA-CALIBRAR-GIROSCOPIO-DO-TODO-01 (15/10/2026): a janela se chama «Calibrar giroscópio»,
sem «?» e sem `title=` nos passos, sem o liga do analógico virtual e com todo alvo de 24 px.

Seis coisas, cada uma com a sua mordida:

1. o `<title>` e o título da página dizem «Calibrar giroscópio», o mesmo texto do botão da 02;
2. a página não tem «?» nem `class="ajuda"`, e a frase dos passos mora em `data-dica`, sem `title`;
3. o selo «Giroscópio como analógico» (liga e lados) saiu: o analógico virtual mora na 02;
4. todo `[data-gesto]` mede 24 px ou mais, no Chrome;
5. as seis barras de leitura de um controle começam na mesma reta;
6. a coluna da mira cabe na janela estreita.

A MORDIDA: volte `TITULO` para «Calibrar sensores de movimento» e o caso 1 reprova; ponha
`title="…"` no `<label class="passo">` e o caso 2 reprova; devolva o liga ao gerador da
coluna e o caso 3 reprova; tire o `[data-gesto]{min-height:24px}` e o caso 4 reprova;
volte `.lin > .r` para 74 px e o caso 5 reprova.
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `aba02` e `calibrar`, que carregam o GTK")

import aba02
import calibrar

CHROME = pathlib.Path("/usr/bin/google-chrome")
PAGINA = RAIZ / "mockup" / "calibrar-sensores.html"


def _doc() -> str:
    return PAGINA.read_text(encoding="utf-8")


def _sem_estilo(doc: str) -> str:
    return re.sub(r"<style.*?</style>|<!--.*?-->|<svg.*?</svg>", "", doc, flags=re.S)


# 1. O NOME --------------------------------------------------------------------------------------

def test_a_janela_se_chama_calibrar_giroscopio_aqui_e_na_aba_controles() -> None:
    doc = _doc()
    assert calibrar.TITULO == "Calibrar giroscópio" == aba02.ROTULO_DO_CALIBRAR
    assert "<title>Hefesto — calibrar giroscópio</title>" in doc
    assert re.search(r'<h1><span class="p"[^>]*>Calibrar giroscópio</span></h1>', doc), (
        "o título da janela não diz «Calibrar giroscópio»")
    assert "sensores de movimento" not in _sem_estilo(doc) + re.search(
        r"<title>.*?</title>", doc).group(0), "o nome velho voltou à janela"


# 2. SEM «?» E SEM title -------------------------------------------------------------------------

def test_a_pagina_sai_sem_ponto_de_interrogacao() -> None:
    visivel = _sem_estilo(_doc())
    assert 'class="ajuda' not in visivel and ">?<" not in visivel and "?<span" not in visivel, (
        "um «?» voltou à janela: a ajuda mora em `data-dica` no título")
    assert re.search(r'<h1><span class="p" data-dica="[^"]+"', visivel), (
        "o título perdeu a dica curta")


def test_a_frase_dos_passos_mora_em_data_dica_e_nao_em_title() -> None:
    passos = re.findall(r'<label class="passo"([^>]*)>', _doc())
    assert len(passos) == 3
    for atributos in passos:
        assert "data-dica=" in atributos and "title=" not in atributos, atributos
    for _, _, dica in calibrar.PASSOS:
        assert len(dica.split()) <= 12, f"dica longa demais: {dica!r}"


# 3. O SELO --------------------------------------------------------------------------------------

def test_a_calibrar_nao_tem_o_selo_nem_o_liga_do_analogico_virtual() -> None:
    assert not hasattr(calibrar, "ROTULO_DA_MIRA") and not hasattr(calibrar, "LADOS")
    visivel = _sem_estilo(_doc())
    for saiu in ("Giroscópio como analógico", "Analógico virtual", "analogico-virtual",
                 "analogico-lado", "mira-ligada", "mira-lado"):
        assert saiu not in visivel, f"`{saiu}` voltou à Calibrar: o dono é a aba Controles"


# 4. OS ALVOS DE 24 PX ---------------------------------------------------------------------------

@pytest.mark.parametrize("largura", [940, 1212])
def test_todo_alvo_clicavel_mede_24_px_ou_mais(largura: int) -> None:
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema: a régua não tem motor")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = nav.new_page(viewport={"width": largura, "height": 809})
            pg.goto(PAGINA.as_uri())
            pg.wait_for_load_state("networkidle")
            lido: dict[str, Any] = pg.evaluate("""() => ({
              alvos: [...document.querySelectorAll('[data-gesto]')].filter(e => e.offsetParent)
                .map(e => [e.getAttribute('data-gesto'),
                           Math.round(e.getBoundingClientRect().height * 10) / 10]),
              barras: [...document.querySelectorAll('.ctr')].map(c =>
                [...c.querySelectorAll('.lin > .g')]
                  .map(g => Math.round(g.getBoundingClientRect().left)))})""")
        finally:
            nav.close()
    assert len(lido["alvos"]) >= 11, f"a régua mediu poucos alvos: {len(lido['alvos'])}"
    baixos = [a for a in lido["alvos"] if a[1] < 24]
    assert not baixos, f"alvos abaixo de 24 px a {largura} px: {sorted({tuple(b) for b in baixos})}"
    # 5. AS BARRAS COMEÇAM NA MESMA RETA
    for esquerdas in lido["barras"]:
        assert len(esquerdas) == 6 and len(set(esquerdas)) == 1, (
            f"as seis barras do cartão não começam juntas: {esquerdas}")


# 6. A JANELA ESTREITA ---------------------------------------------------------------------------

def test_a_coluna_da_mira_cabe_na_janela_estreita() -> None:
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema: a régua não tem motor")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = nav.new_page(viewport={"width": 940, "height": 809})
            pg.goto(PAGINA.as_uri())
            pg.wait_for_load_state("networkidle")
            sobra = pg.evaluate("""() => [...document.querySelectorAll('.mira')]
              .filter(m => m.scrollWidth > m.clientWidth).length""")
        finally:
            nav.close()
    assert sobra == 0, "a coluna da mira passa da largura da janela"
