"""A captura de tecla se faz sobre o mapa do controle: «Gravar tecla» escuta, e o que a pessoa
aperta vira o botão.

Absorve A-CAPTURA-DE-TECLA-SE-FAZ-SOBRE-O-MAPA-DO-CONTROLE-01. A página, no Chrome, com o clique
do gesto interceptado: o que a captura entregaria ao piloto (`#mapa-captura`) é o que se lê.

MORDIDAS: arrancar o ouvinte de `keydown` (a tecla não grava), o de `keyup` do modificador
sozinho, o de `mousedown` (o botão do mouse não grava), o `MutationObserver` do botão do controle
e o `Esc` que cancela reprovam; a escuta que sobrevive ao fechar o seletor também.
"""

from __future__ import annotations

import pathlib
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup" / "mapa-do-controle.html"
CHROME = pathlib.Path("/usr/bin/google-chrome")

PREPARA = """() => {
  window.__entregas = [];
  const c = document.getElementById('mapa-captura');
  c.addEventListener('click', e => { e.preventDefault();
    window.__entregas.push({tecla: c.dataset.tecla || null, troca: c.dataset.troca || null}); });
  window.__abre = b => document.querySelector('.b2[data-b="' + b + '"]').click();
  window.__aba = a => document.querySelector('.seg2 [data-aba="' + a + '"]').click();
  window.__gravar = () => document.querySelector('.op3.gravar').click();
  window.__ouvindo = () => document.querySelector('.op3.gravar').classList.contains('ouvindo');
  window.__aberto = () => !document.querySelector('.sel2').hidden;
  window.__tecla = (code, extra) => {
    const dados = Object.assign({code: code, bubbles: true, cancelable: true}, extra || {});
    document.dispatchEvent(new KeyboardEvent('keydown', dados));
    document.dispatchEvent(new KeyboardEvent('keyup', dados));
  };
  return true;
}"""


@pytest.fixture(scope="module")
def pagina() -> Any:
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        pg = nav.new_page(viewport={"width": 1212, "height": 809})
        yield pg
        nav.close()


@pytest.fixture
def aberta(pagina: Any) -> Any:
    pagina.goto(MOCKUP.as_uri())
    pagina.evaluate(PREPARA)
    return pagina


def _escutando(pg: Any, botao: str = "dpad_up") -> None:
    """Abre o seletor do botão, vai à aba Teclado e arma o «Gravar tecla»."""
    pg.evaluate(f"window.__abre('{botao}')")
    pg.evaluate("window.__aba('teclado')")
    pg.evaluate("window.__gravar()")
    assert pg.evaluate("window.__ouvindo()"), "o «Gravar tecla» não ficou escutando"


def test_a_tecla_apertada_grava_e_fecha_o_seletor(aberta: Any) -> None:
    _escutando(aberta)
    aberta.evaluate("window.__tecla('KeyW')")
    assert aberta.evaluate("window.__entregas") == [{"tecla": "KEY_W", "troca": None}]
    assert not aberta.evaluate("window.__aberto()"), "o seletor ficou aberto depois de gravar"
    assert not aberta.evaluate("window.__ouvindo()")


def test_a_combinacao_leva_os_modificadores_na_frente(aberta: Any) -> None:
    _escutando(aberta, "l1")
    aberta.evaluate("window.__tecla('KeyW', {ctrlKey: true, shiftKey: true})")
    (entrega,) = aberta.evaluate("window.__entregas")
    assert entrega["tecla"] == "KEY_LEFTCTRL+KEY_LEFTSHIFT+KEY_W", entrega


def test_o_modificador_sozinho_grava_quando_solta(aberta: Any) -> None:
    _escutando(aberta, "square")
    aberta.evaluate("""() => {
      document.dispatchEvent(new KeyboardEvent('keydown', {code: 'ControlLeft', ctrlKey: true,
                                                           bubbles: true, cancelable: true}));
    }""")
    assert aberta.evaluate("window.__entregas") == [], "gravou o Ctrl antes de a pessoa soltar"
    aberta.evaluate("""() => {
      document.dispatchEvent(new KeyboardEvent('keyup', {code: 'ControlLeft',
                                                         bubbles: true, cancelable: true}));
    }""")
    assert aberta.evaluate("window.__entregas") == [{"tecla": "KEY_LEFTCTRL", "troca": None}]


def test_o_esc_cancela_a_escuta_e_nao_grava_nada(aberta: Any) -> None:
    _escutando(aberta)
    aberta.evaluate("window.__tecla('Escape')")
    assert aberta.evaluate("window.__entregas") == []
    assert not aberta.evaluate("window.__ouvindo()")


def test_o_botao_do_mouse_grava_quando_a_escuta_esta_armada(aberta: Any) -> None:
    _escutando(aberta)
    aberta.mouse.click(450, 45, button="right")
    assert aberta.evaluate("window.__entregas") == [{"tecla": "BTN_RIGHT", "troca": None}]


def test_o_botao_do_controle_que_acende_vira_a_troca(aberta: Any) -> None:
    """O piloto marca `pisca` na linha do botão que o controle aperta; a captura o lê."""
    _escutando(aberta, "cross")
    aberta.evaluate("""() => {
      const r2 = document.querySelector('.b2[data-b="r2"]');
      r2.dataset.estado = (r2.dataset.estado || '') + ' pisca';
    }""")
    aberta.wait_for_function("window.__entregas.length > 0")
    (entrega,) = aberta.evaluate("window.__entregas")
    assert entrega["tecla"] is None and entrega["troca"] == "r2", entrega


def test_sem_a_escuta_armada_a_tecla_nao_grava_nada(aberta: Any) -> None:
    aberta.evaluate("window.__abre('dpad_up')")
    aberta.evaluate("window.__tecla('KeyW')")
    aberta.mouse.click(450, 45, button="right")
    assert aberta.evaluate("window.__entregas") == []


def test_fechar_o_seletor_larga_a_escuta(aberta: Any) -> None:
    _escutando(aberta)
    aberta.evaluate("document.querySelector('.sel2-x').click()")
    assert not aberta.evaluate("window.__ouvindo()")
    aberta.evaluate("window.__tecla('KeyW')")
    assert aberta.evaluate("window.__entregas") == []
