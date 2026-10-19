"""A Navegação Interna nasce ligada, a lista dá a volta e quem escolhe ganha o anel oposto.

A-NAVEGACAO-INTERNA-NASCE-LIGADA-01, com os pedidos de 19/10/2026 na bancada: a lista do
efeito volta ao primeiro depois do último, e o controle dentro da lista ganha uma borda a mais,
na cor oposta à do plástico.

MORDIDAS:
  * devolva o `False` ao `load_navegacao_interna` sem arquivo: o primeiro teste reprova;
  * devolva o `Math.max(0, Math.min(...))` ao passo da `escolha`: a lista para no último;
  * tire o `box-shadow` da moldura `dentro`: o anel some.
"""
from __future__ import annotations

import json
import pathlib
from collections.abc import Iterator
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

CHROME = pathlib.Path("/usr/bin/google-chrome")

PAGINA = """<!doctype html><html><body style="margin:40px">
<select data-hef-gesto="gatilhos.efeito"><option>Resistência</option><option>Gatilho</option>
<option>Vibração</option></select></body></html>"""


def test_sem_arquivo_a_interna_nasce_ligada() -> None:
    from hefesto_dualsense4unix.utils.session import load_navegacao_interna

    assert load_navegacao_interna() == (True, "interna")


@pytest.mark.parametrize(("texto", "esperado"), [
    ('{"ligada": false, "tipo": "interna"}', False),
    ('{"ligada": true, "tipo": "interna"}', True),
    ('{"tipo": "interna"}', True),
    ("isto não é json", True),
])
def test_a_escolha_gravada_vale_e_o_malformado_conta_como_nunca(texto: str,
                                                                 esperado: bool) -> None:
    from hefesto_dualsense4unix.utils.session import config_dir, load_navegacao_interna

    flag = config_dir() / "navegacao_interna.flag"
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.write_text(texto, encoding="utf-8")
    assert load_navegacao_interna()[0] is esperado


def test_o_dono_no_daemon_nasce_ligado() -> None:
    from hefesto_dualsense4unix.daemon.subsystems.navegacao_interna import NavegacaoInterna

    assert NavegacaoInterna().ligada is True
    assert NavegacaoInterna.da_sessao().bloco()["interna_ligada"] is True


@pytest.fixture(scope="module")
def pagina() -> Iterator[Any]:
    exigir_gi_real("importa `interface.hefesto_vivo`, que carrega o GTK")
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    playwright = pytest.importorskip("playwright.sync_api")
    from hefesto_dualsense4unix.interface import hefesto_vivo

    with playwright.sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = nav.new_page()
            pg.set_content(PAGINA)
            pg.evaluate(hefesto_vivo.NAV_INSTALAR)
            yield pg
        finally:
            nav.close()


def _endereco(pg: Any) -> str:
    caixas = json.loads(pg.evaluate("window.__hefNav.ler()"))["caixas"]
    return next(c["endereco"] for c in caixas if c.get("tipo") == "lista")


def _passo(pg: Any, passo: int) -> int:
    pg.evaluate("([e, p]) => window.__hefNav.aplicar([{op: 'escolha', endereco: e, passo: p}], [])",
                [_endereco(pg), passo])
    return int(pg.evaluate("document.querySelector('select').selectedIndex"))


def test_a_lista_da_a_volta_nos_dois_sentidos(pagina: Any) -> None:
    pagina.evaluate("document.querySelector('select').selectedIndex = 2")
    assert _passo(pagina, 1) == 0, "do último, o passo seguinte não voltou ao primeiro"
    assert _passo(pagina, -1) == 2, "do primeiro, o anterior não foi ao último"
    assert _passo(pagina, -1) == 1


def _sombra(pg: Any, *, dentro: bool, cor: str) -> str:
    pg.evaluate("([e, d, c]) => window.__hefNav.aplicar([], "
                "[{endereco: e, pref: 'p1', cor: c, dentro: d}])",
                [_endereco(pg), dentro, cor])
    moldura = "document.querySelector('.hef-nav-moldura')"
    return str(pg.evaluate(f"getComputedStyle({moldura}).boxShadow"))


def test_dentro_da_lista_o_anel_e_da_cor_oposta(pagina: Any) -> None:
    assert "rgb(0, 255, 255)" in _sombra(pagina, dentro=True, cor="#ff0000")
    assert "rgb(0, 0, 0)" in _sombra(pagina, dentro=True, cor="#ffffff"), (
        "no plástico White o anel tem de ser escuro, não branco")
    assert _sombra(pagina, dentro=False, cor="#ff0000") == "none", (
        "o controle que só anda ganhou o anel de quem escolhe")
