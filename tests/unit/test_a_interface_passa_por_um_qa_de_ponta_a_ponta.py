"""O QA da aba Perfis: nenhum endereço de rádio na guarda, e o Status respira na largura que sobra.

A-INTERFACE-PASSA-POR-UM-QA-DE-PONTA-A-PONTA-01 (26/10/2026).
"""

from __future__ import annotations

import pathlib
import re
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import aba10, onde
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from tests.unit.test_a_guarda_do_perfil_nao_apaga_a_tabela import MESA, _perfil_de_regua

ENDERECO = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b|\b[0-9A-Fa-f]{12}\b")

CHROME = pathlib.Path("/usr/bin/google-chrome")

GLIFO_PX = 15

VAO_DE_DENTRO_PX = 2


def _texto_visivel(html: str) -> str:
    sem = re.sub(r"<(style|script)\b.*?</\1>", " ", html, flags=re.S)
    sem = re.sub(r"<!--.*?-->", " ", sem, flags=re.S)
    return re.sub(r"<[^>]+>", " ", sem)


def _a_guarda(html: str) -> str:
    ini = html.index('<div class="guarda">')
    return html[ini:html.index("</table>", ini)]


@pytest.fixture
def emitidos(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    from hefesto_dualsense4unix.profiles import loader

    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: [_perfil_de_regua()])
    ctx = Contexto(state={"active_profile": "régua"}, mesa=list(MESA),
                   conectados=list(MESA), estados={})
    return dict(a10_perfis.pacote(ctx))


def test_a_guarda_do_desenho_nao_tem_coluna_de_endereco_nem_traco_no_lugar_vazio() -> None:
    """Prova da D-2610-O-ID-DA-PECA-SAI-DA-TELA."""
    guarda = _a_guarda(onde.pagina("10-perfis.html").read_text(encoding="utf-8"))
    assert "gd-id" not in guarda and 'data-coluna="id"' not in guarda, (
        "a coluna «ID da peça» voltou à guarda (D-2610-O-ID-DA-PECA-SAI-DA-TELA)")
    visivel = _texto_visivel(guarda)
    assert "ID da peça" not in visivel
    achados = ENDERECO.findall(visivel)
    assert not achados, f"endereço de rádio na guarda: {achados}"
    for linha in re.findall(r'<tr[^>]*class="fora".*?</tr>', guarda, flags=re.S):
        resto = _texto_visivel(linha).split()
        assert "—" not in resto and "-" not in resto, (
            f"o lugar sem controle mostra só um traço: {resto}")


def test_o_pacote_nao_pinta_endereco_de_radio_em_lugar_nenhum_da_guarda(
        emitidos: dict[str, Any]) -> None:
    nomes = emitidos.get("guarda.nome") or []
    assert len([n for n in nomes if n]) >= len(MESA), f"a guarda não foi pintada: {nomes}"
    assert "guarda.id" not in emitidos
    for chave, valor in emitidos.items():
        if not chave.startswith("guarda."):
            continue
        for texto in valor if isinstance(valor, list) else [valor]:
            assert not ENDERECO.search(str(texto)), f"{chave} pinta um endereço: {texto!r}"


def test_o_vao_do_status_e_medido_contra_as_secoes_da_guarda() -> None:
    """Prova da D-2610-O-VAO-DO-STATUS-CRESCE-COM-A-SOBRA."""
    glifos = sum(len(pecas) for _campo, pecas in aba10.SECOES)
    de_dentro = sum(len(pecas) - 1 for _campo, pecas in aba10.SECOES)
    largura = glifos * GLIFO_PX + de_dentro * VAO_DE_DENTRO_PX
    vaos = len(aba10.SECOES) - 1
    regra = re.search(r"\.gd-pecas \.gls\{[^}]*\}", aba10.CSS)
    assert regra, "a regra do vão do Status sumiu"
    assert f"calc((100% - {largura}px) / {vaos})" in regra.group(0), (
        f"as seções da guarda mudaram ({glifos} glifos, {vaos} vãos): o vão não divide a sobra "
        f"certa — {regra.group(0)}")
    assert "clamp(5px," in regra.group(0), "o vão mínimo de 5px saiu: a 1212 px a fileira estoura"


MEDIR_O_STATUS = """
() => {
  const linhas = [...document.querySelectorAll('.guarda tbody tr')].map((tr) => {
    const cel = tr.querySelector('.gd-pecas');
    const cs = getComputedStyle(cel);
    const dentro = cel.getBoundingClientRect().right - parseFloat(cs.paddingRight);
    const gc = [...tr.querySelectorAll('.gd-pecas .gc')].map((g) => g.getBoundingClientRect());
    return {vaos: gc.slice(1).map((r, i) => r.left - gc[i].right),
            sobra: dentro - gc[gc.length - 1].right};
  });
  const g = document.querySelector('.guarda');
  return {linhas, lateral: g.scrollWidth - g.clientWidth};
}
"""


def _mede(largura: int, altura: int) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = navegador.new_page(viewport={"width": largura, "height": altura})
            pg.goto(onde.pagina("10-perfis.html").as_uri())
            return dict(pg.evaluate(MEDIR_O_STATUS))
        finally:
            navegador.close()


@pytest.mark.skipif(not CHROME.exists(), reason="sem o Chrome do sistema: a régua não tem motor")
@pytest.mark.parametrize(("largura", "altura"), [(1212, 809), (1918, 840)])
def test_o_status_espalha_as_secoes_na_largura_que_sobra_sem_estourar(
        largura: int, altura: int) -> None:
    m = _mede(largura, altura)
    assert m["linhas"], "a guarda não tem linhas: a régua ficaria verde por ausência"
    assert m["lateral"] <= 0, f"a guarda rola de lado a {largura} px: {m}"
    for linha in m["linhas"]:
        vaos = linha["vaos"]
        assert min(vaos) >= 9, f"as seções do Status seguem apertadas a {largura} px: {vaos}"
        assert max(vaos) - min(vaos) <= 1, f"os vãos do Status não são iguais: {vaos}"
        assert linha["sobra"] >= -0.5, f"a fileira passa da célula a {largura} px: {linha}"
