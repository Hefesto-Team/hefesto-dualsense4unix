#!/usr/bin/env python3
"""O cabeçalho de toda tabela das dez abas tem um tom só, sem fundo próprio por coluna.

A régua é a D-2610-O-CABECALHO-TEM-UM-TOM-SO: o `thead` de cada tabela pinta todas as colunas
com o mesmo fundo, o da opção C que o usuário escolheu no QA de 26/10 (o roxo a 16%).
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.interface import aba10, onde

CHROME = pathlib.Path("/usr/bin/google-chrome")
O_TOM = "color-mix(in srgb, var(--purple) 16%, transparent)"
FUNDO_POR_COLUNA = re.compile(
    r"th:nth-(?:child|of-type|last-child)\([^)]*\)[^{]*\{[^}]*background", re.S)

ABAS = sorted(p for p in onde.paginas() if p.name[:2].isdigit())

OS_CABECALHOS = """
() => Array.from(document.querySelectorAll('table')).map((t) => {
  const ths = Array.from(t.querySelectorAll('thead th'));
  return ths.map((th) => {
    const s = getComputedStyle(th);
    return {texto: th.textContent.trim(), cor: s.backgroundColor, imagem: s.backgroundImage};
  });
}).filter((linha) => linha.length > 0)
"""


def _estilos(html: str) -> str:
    return "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S))


def test_as_dez_abas_estao_na_bancada() -> None:
    assert len(ABAS) == 10, [p.name for p in ABAS]


@pytest.mark.parametrize("arquivo", ABAS, ids=[p.stem for p in ABAS])
def test_nenhuma_coluna_do_cabecalho_tem_fundo_proprio(arquivo: pathlib.Path) -> None:
    achados = FUNDO_POR_COLUNA.findall(_estilos(arquivo.read_text(encoding="utf-8")))
    assert not achados, f"{arquivo.name}: coluna do cabeçalho com fundo próprio: {achados}"


def test_o_gerador_da_10_pinta_o_cabecalho_num_tom_so() -> None:
    assert not FUNDO_POR_COLUNA.search(aba10.CSS), "o gerador da 10 voltou a pintar por coluna"
    regra = re.search(r"\.tab thead th\{[^}]*\}", aba10.CSS)
    assert regra is not None, "a regra do cabeçalho de coluna sumiu do gerador da 10"
    assert f"background-image:linear-gradient({O_TOM},{O_TOM})" in regra.group(0), regra.group(0)


@pytest.mark.skipif(not CHROME.exists(), reason="sem o Chrome do sistema: a régua não tem motor")
@pytest.mark.parametrize("largura", [1212, 1918])
def test_a_cor_do_cabecalho_e_a_mesma_em_toda_coluna(largura: int) -> None:
    from playwright.sync_api import sync_playwright

    pagina = onde.pagina("10-perfis.html")
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = navegador.new_page(viewport={"width": largura, "height": 900})
            pg.goto(pagina.as_uri())
            tabelas = pg.evaluate(OS_CABECALHOS)
        finally:
            navegador.close()
    assert len(tabelas) >= 2, f"a 10 tem {len(tabelas)} tabela(s) com cabeçalho, e são duas"
    imagens = set()
    for colunas in tabelas:
        pinturas = {(c["cor"], c["imagem"]) for c in colunas}
        assert len(pinturas) == 1, f"a {largura} px, colunas com fundos diferentes: {colunas}"
        imagens |= {c["imagem"] for c in colunas}
    assert len(imagens) == 1, f"a {largura} px, as tabelas não têm o mesmo tom: {imagens}"
    assert "gradient" in next(iter(imagens)), f"o cabeçalho perdeu o tom: {imagens}"
