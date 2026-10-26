#!/usr/bin/env python3
"""A guarda da aba Perfis não rola de lado a 1212 px nem a 1918 px, e o ID da peça não volta.

20/10/2026: o ID da peça cedia nas larguras em que a tabela não cabia.
26/10/2026 (D-2610-O-ID-DA-PECA-SAI-DA-TELA, a validar pelo usuário): a coluna sai em toda
largura, porque a tela não mostra endereço de rádio, nem mascarado.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

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


def _mede(largura: int, altura: int, html: pathlib.Path | None = None) -> dict[str, Any]:
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


def test_a_1918_nada_rola_e_o_id_da_peca_nao_volta() -> None:
    m = _mede(*LARGA)
    assert not m["id_cabecalho"] and not m["id_celula"], f"o ID da peça voltou à tela: {m}"
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


def test_a_mordida_com_a_coluna_do_id_de_volta_a_1212_reprova(tmp_path: pathlib.Path) -> None:
    """Devolve a coluna de 114 px do ID à página e a mesma medição reprova: a régua morde."""
    texto = onde.pagina("10-perfis.html").read_text(encoding="utf-8")
    fecho = '<col data-coluna="status"></colgroup>'
    assert fecho in texto, "o `<colgroup>` da guarda mudou: a mordida não sabe onde pôr o ID"
    com_id = texto.replace(fecho, '<col data-coluna="status"><col style="width:114px"></colgroup>')
    ini = com_id.index('<div class="guarda">')
    fim = com_id.index("</table>", ini)
    guarda = com_id[ini:fim].replace("</th>\n                  </tr></thead>",
                                     "</th><th>ID da peça</th></tr></thead>")
    guarda = guarda.replace("</td>\n                  </tr>",
                            "</td><td>AA:BB:CC:00:00:01</td></tr>")
    arq = tmp_path / "10-perfis.html"
    arq.write_text(com_id[:ini] + guarda + com_id[fim:], encoding="utf-8")
    m = _mede(*ESTREITA, html=arq)
    assert m["lateral"] > 0, (
        f"com a coluna do ID a guarda continua cabendo a 1212 px: a régua não mede nada ({m})")
