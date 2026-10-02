#!/usr/bin/env python3
"""TELA-TRES-01 — a altura dos dois quadros da Sistema, e CABO/RÁDIO na fita."""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"), str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

CHROME = pathlib.Path("/usr/bin/google-chrome")

pytestmark = pytest.mark.skipif(
    not CHROME.exists(), reason="sem o Chrome do sistema não há geometria a medir")


def _no_chrome(pagina: pathlib.Path, js: str, largura: int = 1600):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = nav.new_page(viewport={"width": largura, "height": 900})
            pg.goto(pagina.as_uri())
            pg.wait_for_timeout(250)
            return pg.evaluate(js)
        finally:
            nav.close()


def test_as_colunas_da_sistema_fecham_na_mesma_linha_e_o_registro_cresce():
    """§1 — medido no navegador, na forma de 25/09/2026 (A-09-SISTEMA-EM-TRES-"""
    import onde

    r = _no_chrome(onde.pagina("09-sistema.html", publicado=True), """() => {
      const bases = s => [...document.querySelectorAll(s)].map(
        e => Math.round(e.getBoundingClientRect().bottom));
      const log = document.querySelector('.registro .log');
      const corpo = document.querySelector('.quadro.estica');
      return {colunas: bases('.avancadas > .coluna'),
              status: bases('.status3 .col-lista'),
              log: log ? Math.round(log.getBoundingClientRect().height) : null,
              fundo_log: log ? Math.round(log.getBoundingClientRect().bottom) : null,
              fundo_quadro: corpo ? Math.round(corpo.getBoundingClientRect().bottom) : null};
    }""")

    assert len(r["colunas"]) == 4, r
    assert len(set(r["colunas"])) == 1, (
        f"as quatro colunas não fecham na mesma linha: {r['colunas']}")
    assert len(r["status"]) == 3 and len(set(r["status"])) == 1, (
        f"as três colunas do Status não fecham na mesma linha: {r['status']}")
    assert r["log"] and r["log"] >= 120, f"o registro encolheu: {r['log']}px"
    assert r["fundo_quadro"] - r["fundo_log"] <= 20, (
        f"sobra {r['fundo_quadro'] - r['fundo_log']}px vazios embaixo do registro — "
        "ele devia ocupar a altura que sobra")


def test_a_via_do_chip_nao_sobe_de_caixa_no_navegador():
    """§2 — REVOGADO em 11/09/2026: a via do chip NÃO sobe mais de caixa."""
    import onde

    r = _no_chrome(onde.pagina("04-iluminacao.html", publicado=True), """() => {
      const vias = [...document.querySelectorAll('.fita .chip .via')];
      const chips = [...document.querySelectorAll('.fita .chip')];
      return {
        quantas: vias.length,
        chips: chips.length,
        caixa: vias.map(e => getComputedStyle(e).textTransform),
        caixa_do_chip: chips.map(e => getComputedStyle(e).textTransform),
        texto: vias.map(e => e.textContent),
      };
    }""")

    assert r["quantas"] >= 1, (
        "nenhum chip da fita tem o span da via — o endereço da via sumiu do "
        "rótulo, e com ele a régua da maiúscula perde onde olhar")
    assert set(r["caixa"]) <= {"none"}, (
        f"a via do chip voltou a subir de caixa: {r['caixa']} — na tela viva "
        f"isso escreve «CABO» na fita com «cabo» no cartão logo abaixo, que é "
        f"exatamente o que ela mandou não repetir em 11/09/2026")
    assert set(r["caixa_do_chip"]) <= {"none"}, (
        f"o chip INTEIRO subiu de caixa e o nome do plástico foi junto: "
        f"{r['caixa_do_chip']}")
    assert all(t.strip() for t in r["texto"]), (
        f"um chip ficou com a via vazia: {r['texto']}")


def test_o_dono_do_texto_continua_sendo_rotulo():
    """`rotulo_do_chip` MARCA o que `rotulo` devolveu — não remonta."""
    import monta

    c = {"jogador": 2, "nome": "Galactic Purple", "via": "rádio", "pref": "p2"}
    marcado = monta.rotulo_do_chip(c)

    assert '<span class="via">rádio</span>' in marcado
    assert marcado.replace('<span class="via">rádio</span>', "rádio") == \
        monta.rotulo(c, "curta")


def test_sem_via_o_rotulo_volta_como_veio():
    """Queda silenciosa: marcar por posição fixa quebraria na ordem nova."""
    import monta

    c = {"jogador": 3, "nome": "White", "via": "", "pref": "p3"}

    assert monta.rotulo_do_chip(c) == monta.rotulo(c, "curta")
    assert 'class="via"' not in monta.rotulo_do_chip(c)
