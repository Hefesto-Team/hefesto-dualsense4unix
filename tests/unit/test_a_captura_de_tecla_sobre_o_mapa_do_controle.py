"""A captura de tecla se faz sobre o mapa do controle: «Gravar tecla» escuta, e o que a pessoa
aperta vira o botão.

Absorve A-CAPTURA-DE-TECLA-SE-FAZ-SOBRE-O-MAPA-DO-CONTROLE-01. A página, no Chrome, com o clique
do gesto interceptado: o que a captura entregaria ao piloto (`#mapa-captura`) é o que se lê.

MORDIDAS: arrancar o ouvinte de `keydown` (a tecla não grava), o de `keyup` do modificador
sozinho, o de `mousedown` (o botão do mouse não grava), o `MutationObserver` do botão do controle
e o `Esc` que cancela reprovam; a escuta que sobrevive ao fechar o seletor também.

A-CAPTURA-DE-TECLA-RESPONDE-A-TECLA-QUE-NAO-CONHECE-01: a pontuação e o teclado numérico gravam, a
tecla sem nome manda o `code` cru e o a13 responde com a frase da recusa, e a barra de gravar vira
laranja com o motivo curto (tirar o observador da recusa ou o `code` cru do envio reprova).
"""

from __future__ import annotations

import pathlib
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.integrations.uinput_keyboard import SUPPORTED_KEYS
from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a13_mapa_do_controle as a13
from hefesto_dualsense4unix.profiles.schema import _e_combinacao_de_teclas

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


def test_a_pontuacao_e_o_teclado_numerico_gravam(aberta: Any) -> None:
    for code, tecla in (("Minus", "KEY_MINUS"), ("Slash", "KEY_SLASH"), ("Numpad7", "KEY_KP7"),
                        ("Backquote", "KEY_GRAVE"), ("CapsLock", "KEY_CAPSLOCK")):
        aberta.evaluate("window.__entregas.length = 0")
        _escutando(aberta)
        aberta.evaluate(f"window.__tecla('{code}')")
        assert aberta.evaluate("window.__entregas") == [{"tecla": tecla, "troca": None}], code


def test_a_tecla_sem_nome_manda_o_code_cru_em_vez_de_ficar_calada(aberta: Any) -> None:
    _escutando(aberta)
    aberta.evaluate("window.__tecla('Pause')")
    assert aberta.evaluate("window.__entregas") == [{"tecla": "Pause", "troca": None}]
    _escutando(aberta, "l1")
    aberta.evaluate("window.__tecla('Pause', {ctrlKey: true})")
    assert aberta.evaluate("window.__entregas")[-1]["tecla"] == "KEY_LEFTCTRL+Pause"


def test_a_recusa_do_a13_deixa_a_barra_laranja_com_o_motivo(aberta: Any) -> None:
    _escutando(aberta, "cross")
    aberta.evaluate("window.__tecla('Pause')")
    assert not aberta.evaluate("window.__aberto()")
    aberta.evaluate("document.getElementById('mapa-captura').classList.add('hef-recusou')")
    assert aberta.evaluate("window.__aberto()"), "a recusa não reabriu o seletor do botão"
    barra = aberta.evaluate("""() => {
      const g = document.querySelector('.op3.gravar:not(.seq-grava)');
      return {classe: g.classList.contains('recusou'), texto: g.textContent.trim(), dica: g.title,
              cor: getComputedStyle(g).borderTopColor}; }""")
    assert barra["classe"] and barra["texto"] == "Pause não está no teclado virtual", barra
    assert barra["dica"] == "A tecla Pause não está entre as do teclado virtual: escolha outra"
    assert barra["cor"] != "rgb(255, 85, 85)", "a barra continua vermelha"


def test_gravar_de_novo_tira_o_laranja(aberta: Any) -> None:
    _escutando(aberta, "cross")
    aberta.evaluate("window.__tecla('Pause')")
    aberta.evaluate("document.getElementById('mapa-captura').classList.add('hef-recusou')")
    aberta.evaluate("window.__gravar()")
    assert not aberta.evaluate(
        "document.querySelector('.op3.gravar:not(.seq-grava)').classList.contains('recusou')")
    assert aberta.evaluate("window.__ouvindo()")


def test_a_recusa_sem_envio_nao_mexe_na_barra(aberta: Any) -> None:
    aberta.evaluate("document.getElementById('mapa-captura').classList.add('hef-recusou')")
    assert not aberta.evaluate("window.__aberto()")


NOME = "Regua"


@pytest.fixture
def mapa() -> Any:
    a13._largar()
    yield a13
    a13._largar()


def _ctx() -> Any:
    return Contexto(state={"active_profile": NOME}, mesa=[], conectados=[], escolhido="")


@pytest.fixture
def perfil_no_disco() -> None:
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile

    loader.save_profile(Profile(name=NOME, match=MatchManual()))


def _grava(mapa: Any, tecla: str) -> Any:
    ctx = _ctx()
    mapa.mapa_botao(ctx, {"b": "cross"}, None)
    return mapa.mapa_gravar_tecla(ctx, {"tecla": tecla}, MagicMock())


@pytest.mark.parametrize("code,tecla", [
    ("Minus", "KEY_MINUS"), ("Equal", "KEY_EQUAL"), ("Slash", "KEY_SLASH"),
    ("Semicolon", "KEY_SEMICOLON"), ("Quote", "KEY_APOSTROPHE"), ("BracketLeft", "KEY_LEFTBRACE"),
    ("Backslash", "KEY_BACKSLASH"), ("Backquote", "KEY_GRAVE"), ("CapsLock", "KEY_CAPSLOCK"),
    ("Numpad0", "KEY_KP0"), ("NumpadAdd", "KEY_KPPLUS"), ("KeyW", "KEY_W"), ("F5", "KEY_F5"),
])
def test_o_code_cru_grava_a_tecla_do_motor(
        mapa: Any, perfil_no_disco: None, code: str, tecla: str) -> None:
    """D-2011-A-CAPTURA-DE-TECLA-RESPONDE-A-TECLA-QUE-NAO-CONHECE: toda tecla tem resposta."""
    _grava(mapa, code)

    assert mapa._estado()["edicoes"]["cross"] == (mapa.ACAO, tecla)


def test_a_combinacao_com_code_cru_traduz_cada_parte(mapa: Any, perfil_no_disco: None) -> None:
    _grava(mapa, "KEY_LEFTCTRL+Minus")

    assert mapa._estado()["edicoes"]["cross"] == (mapa.ACAO, "KEY_LEFTCTRL+KEY_MINUS")


@pytest.mark.parametrize("tecla,nome", [
    ("Pause", "Pause"), ("IntlBackslash", "IntlBackslash"), ("KEY_OK", "Ok"),
    ("KEY_LEFTCTRL+Pause", "Pause"),
])
def test_a_tecla_que_o_motor_nao_emite_devolve_a_frase_da_recusa(
        mapa: Any, perfil_no_disco: None, tecla: str, nome: str) -> None:
    with pytest.raises(RuntimeError) as erro:
        _grava(mapa, tecla)

    assert str(erro.value) == a13.FRASE_DA_RECUSA.format(nome)
    assert "cross" not in mapa._estado()["edicoes"]


def test_toda_tecla_que_o_a13_traduz_o_motor_aceita() -> None:
    for code, tecla in a13.CODIGO_DA_TECLA.items():
        assert tecla in SUPPORTED_KEYS, f"{code} vira {tecla}, que o motor não emite"
        assert _e_combinacao_de_teclas(tecla)


def test_a_pagina_nasce_da_mesma_tabela() -> None:
    texto = MOCKUP.read_text(encoding="utf-8")
    for code, tecla in a13.CODIGO_DA_TECLA.items():
        assert f'"{code}": "{tecla}"' in texto, code
    assert "NOMEADA" not in texto


def test_a_tecla_gravada_aparece_no_botao_pelo_nome(mapa: Any, perfil_no_disco: None) -> None:
    """D-2011-A-CAPTURA-DE-TECLA-RESPONDE-A-TECLA-QUE-NAO-CONHECE: a tecla em palavras."""
    _grava(mapa, "Minus")

    assert mapa._texto_do_valor(mapa._estado()["edicoes"]["cross"], "cross") == "Menos"
    for tecla in set(a13.CODIGO_DA_TECLA.values()):
        texto = mapa._texto_do_valor((mapa.ACAO, tecla), "cross")
        assert texto != tecla.removeprefix("KEY_"), f"{tecla} aparece no botão com o nome cru"
