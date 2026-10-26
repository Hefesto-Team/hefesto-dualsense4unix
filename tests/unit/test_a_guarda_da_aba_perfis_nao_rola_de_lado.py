#!/usr/bin/env python3
"""A guarda da aba Perfis não rola de lado a 1212 px: o ID da peça cede o lugar (20/10/2026).

A escolha, pelo chat: entre encolher o respiro, quebrar as seções em duas linhas e esconder o ID,
esconder o ID da peça nas larguras em que a tabela não cabe. Acima delas, nada muda.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.interface import onde

CHROME = pathlib.Path("/usr/bin/google-chrome")
pytestmark = pytest.mark.skipif(
    not CHROME.exists(), reason="sem o Chrome do sistema: a régua não tem motor")

ESTREITA = (1212, 809)
LARGA = (1918, 840)

A_GUARDA = """
() => {
  const g = document.querySelector('.guarda');
  const id = document.querySelector('.guarda th.gd-id');
  const td = document.querySelector('.guarda td.gd-id');
  const d = document.documentElement;
  const mostra = (e) => !!e && getComputedStyle(e).display !== 'none'
    && e.getBoundingClientRect().width > 0;
  return {
    existe: !!g,
    lateral: g ? g.scrollWidth - g.clientWidth : null,
    documento_lateral: d.scrollWidth - d.clientWidth,
    documento_vertical: d.scrollHeight - d.clientHeight,
    id_cabecalho: mostra(id),
    id_celula: mostra(td),
    colunas_vivas: [...document.querySelectorAll('.guarda thead th')]
      .filter(mostra).map((t) => t.className || t.textContent.trim().slice(0, 8)),
  };
}
"""


def _mede(largura: int, altura: int, html: pathlib.Path | None = None) -> dict:
    """Abre a aba 10 do desenho (`mockup/`) no Chrome do sistema e devolve o que a guarda mediu."""
    from playwright.sync_api import sync_playwright

    alvo = html or onde.pagina("10-perfis.html")
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = navegador.new_page(viewport={"width": largura, "height": altura})
            pg.goto(alvo.as_uri())
            medido = pg.evaluate(A_GUARDA)
        finally:
            navegador.close()
    assert medido["existe"], "a `.guarda` sumiu da aba 10: a régua ficaria verde por ausência"
    return dict(medido)


def test_a_1212_a_guarda_nao_rola_de_lado_e_o_id_da_peca_cede() -> None:
    m = _mede(*ESTREITA)
    assert m["lateral"] <= 0, f"a guarda rola {m['lateral']} px para o lado a 1212 px: {m}"
    assert m["documento_lateral"] <= 0, m
    assert m["documento_vertical"] <= 0, f"o documento rola na vertical a 1212 px: {m}"
    assert not m["id_cabecalho"] and not m["id_celula"], f"o ID da peça segue à mostra: {m}"


def test_a_1918_o_id_da_peca_segue_visivel_e_nada_rola() -> None:
    m = _mede(*LARGA)
    assert m["id_cabecalho"] and m["id_celula"], f"o ID da peça sumiu na vista larga: {m}"
    assert m["lateral"] <= 0, m
    assert m["documento_vertical"] <= 0, m


@pytest.mark.parametrize("largura", [1100, 1212, 1213, 1226, 1239, 1240, 1259, 1260, 1280, 1366])
def test_em_nenhuma_largura_em_volta_do_corte_a_guarda_rola_de_lado(largura: int) -> None:
    """O corte não pode cair onde a tabela ainda não cabe.

    Medido em 20/10/2026 pelo conferente: com o corte a 1212, a guarda rolava 13 px a 1213 e só
    cabia a 1240. A lista pega os dois lados do corte e o meio do trecho que rolava.

    A prova da D-2010-A-GUARDA-DA-PERFIS-ESCONDE-O-ID-NA-JANELA-ESTREITA.
    """
    m = _mede(largura, 809)
    assert m["lateral"] <= 0, f"a guarda rola de lado a {largura} px: {m}"


def test_a_mordida_sem_a_regra_de_largura_a_1212_reprova(tmp_path: pathlib.Path) -> None:
    """Tira a regra da folha da página e a mesma medição reprova: a régua morde."""
    texto = onde.pagina("10-perfis.html").read_text(encoding="utf-8")
    marca = "@media (max-width:1259px){"
    assert texto.count(marca) == 1, (
        "a regra do corte sumiu da aba 10: a guarda volta a rolar de lado")
    ini = texto.index(marca)
    n, i = 0, texto.index("{", ini)
    for j in range(i, len(texto)):
        n += texto[j] == "{"
        n -= texto[j] == "}"
        if n == 0:
            fim_bloco = j + 1
            break
    sem = texto[:ini] + texto[fim_bloco:]
    arq = tmp_path / "10-perfis.html"
    arq.write_text(sem, encoding="utf-8")
    m = _mede(*ESTREITA, html=arq)
    assert m["lateral"] > 0, (
        f"sem a regra a guarda continua cabendo a 1212 px: a régua não mede nada ({m})")
