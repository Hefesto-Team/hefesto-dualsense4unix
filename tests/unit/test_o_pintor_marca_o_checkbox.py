#!/usr/bin/env python3
"""O DÉCIMO ALVO — ``marcado``, o único que escreve ``el.checked``."""
from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

PILOTO = RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"

PAGINA = """<html><body>
<div data-controle="p1">
  <input type="checkbox" id="acordeao" data-campo="saida-aberta"
         data-hef-alvo="marcado">
  <label for="acordeao">Alto-falante</label>
  <div class="corpo">o miolo do acorde&atilde;o</div>
  <input type="radio" name="g" data-campo="rota-fone" data-hef-alvo="marcado">
  <input type="checkbox" data-campo="ja-aceso" data-hef-alvo="marcado" checked>
</div>
</body></html>"""


def _constante(nome: str) -> str:
    """O BOOTSTRAP e o LER_CAMPOS lidos do FONTE do piloto, e não importados."""
    fonte = PILOTO.read_text(encoding="utf-8")
    achou = re.search(rf'^{nome} = r"""(.*?)"""$', fonte, re.S | re.M)
    assert achou, f"o piloto perdeu o {nome} — não há o que testar"
    return achou.group(1)


ROTEIRO = """
(function(){
  const fora = {};
  const cx = document.getElementById('acordeao');
  fora.virgem = JSON.parse(LEITOR_AQUI);
  fora.checked_virgem = cx.checked;

  fora.n_acende = window.__hef.pintar({colunas: {p1: {
      'saida-aberta': 'sim', 'rota-fone': 'sim', 'ja-aceso': 'sim'}}});
  fora.aceso = JSON.parse(LEITOR_AQUI);
  fora.checked_aceso = cx.checked;

  // O SEGUNDO TIQUE COM O MESMO VALOR: o pintor tem de devolver zero.
  fora.n_denovo = window.__hef.pintar({colunas: {p1: {
      'saida-aberta': 'sim', 'rota-fone': 'sim', 'ja-aceso': 'sim'}}});

  // O VAZIO APAGA — e o travessão do lugar sem dono também.
  fora.n_apaga = window.__hef.pintar({colunas: {p1: {
      'saida-aberta': '', 'rota-fone': '\\u2014', 'ja-aceso': ''}}});
  fora.apagado = JSON.parse(LEITOR_AQUI);
  fora.checked_apagado = cx.checked;

  // E QUALQUER OUTRA PALAVRA TAMBÉM APAGA: a língua deste alvo é `sim`, e nada
  // mais. `true` chegando de um pacote não pode acender por acidente.
  fora.n_true = window.__hef.pintar({colunas: {p1: {'saida-aberta': 'true'}}});
  fora.checked_true = cx.checked;
  return JSON.stringify(fora);
})()
"""


@pytest.fixture(scope="module")
def medido() -> dict:
    """Abre um WebKit offscreen, instala o BOOTSTRAP e roda o roteiro."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    leitor = _constante("LER_CAMPOS").strip()
    roteiro = ROTEIRO.replace("LEITOR_AQUI", f"({leitor})")
    saiu: list[str] = []
    janela = Gtk.OffscreenWindow()
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def guardou(v, res):
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:
            saiu.append(f"ERRO {e}")
        Gtk.main_quit()

    def instalou(v, res):
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:
            saiu.append(f"ERRO no bootstrap: {e}")
            Gtk.main_quit()
            return
        v.evaluate_javascript(roteiro, -1, None, None, None, guardou)

    def carregou(v, evento):
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(_constante("BOOTSTRAP"), -1, None, None,
                                  None, instalou)

    view.connect("load-changed", carregou)
    view.load_html(PAGINA, "file:///")
    guarda = GLib.timeout_add(20000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert saiu, "o WebKit não respondeu em 20 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    return json.loads(saiu[0])


def _campos(linhas: list) -> dict[str, str]:
    """``{endereço: valor}`` da leitura de tela do próprio piloto."""
    return {str(x[0]): str(x[3]) for x in linhas}


def test_o_checkbox_acende(medido: dict) -> None:
    assert medido["checked_virgem"] is False, (
        "a página de ensaio nasceu com o acordeão aberto — não há o que medir")
    assert medido["checked_aceso"] is True, (
        "`marcado=sim` não marcou o checkbox. É o defeito inteiro: dos nove "
        "alvos que o pintor tinha, nenhum escrevia `el.checked`, e o acordeão "
        "do alto-falante da aba 02 não tinha como saber o estado da saída.")
    assert medido["n_acende"] >= 2, (
        f"o pintor contou {medido['n_acende']} pinturas ao acender dois "
        f"checkbox e um radio. O contador é O instrumento com que esta casa "
        f"prova que um endereço existe.")


def test_o_radio_tambem(medido: dict) -> None:
    """O mesmo alvo, o mesmo nó do HTML, outro `type`. Zero linha a mais."""
    assert _campos(medido["aceso"])["rota-fone"] == "sim", (
        "o `radio` não acendeu. O alvo vale para todo checkbox E radio das dez "
        "abas — se ele parasse no checkbox, metade do que ele destrava ficaria "
        "sem canal, e ninguém veria.")


def test_o_vazio_apaga(medido: dict) -> None:
    assert medido["checked_apagado"] is False, (
        "`marcado=''` não desmarcou. Um acordeão que fica aberto depois de o "
        "controle sair da mesa é a tela afirmando o que não é.")


def test_o_travessao_apaga(medido: dict) -> None:
    """O `—` é o que o molde escreve num lugar SEM DONO (`pacotes.TRAVESSAO`)."""
    assert _campos(medido["apagado"])["rota-fone"] == "", (
        "o travessão do lugar sem dono deixou o radio aceso")


def test_so_a_palavra_sim_acende(medido: dict) -> None:
    """A língua deste alvo é `sim`, e é a MESMA do alvo `classe` booleano."""
    assert medido["checked_true"] is False, (
        "a palavra `true` acendeu o checkbox. O alvo entende `sim`, e só.")


def test_o_segundo_tique_igual_conta_zero(medido: dict) -> None:
    assert medido["n_denovo"] == 0, (
        f"o mesmo valor pintado de novo contou {medido['n_denovo']}. Um alvo "
        f"que devolve 1 sempre infla a contagem de pinturas de toda aba que o "
        f"use — e é essa contagem que prova que um endereço existe.")


def test_a_leitura_fala_a_lingua_da_escrita(medido: dict) -> None:
    """`sim` / `""`, nunca `true` / `false`."""
    aceso = _campos(medido["aceso"])
    apagado = _campos(medido["apagado"])
    assert aceso["saida-aberta"] == "sim", aceso
    assert apagado["saida-aberta"] == "", apagado
    assert aceso["saida-aberta"] not in ("true", "True"), (
        "a leitura devolveu um booleano em vez da palavra do contrato")


def test_o_que_ja_nascia_aceso_continua_aceso(medido: dict) -> None:
    """Um checkbox com `checked` no HTML lido ANTES de qualquer pintura."""
    assert _campos(medido["virgem"])["ja-aceso"] == "sim", (
        "o leitor não viu o `checked` que o arquivo cravou — e é ele que separa "
        "o que o produto pintou do que o desenho já trazia")
    assert _campos(medido["virgem"])["saida-aberta"] == "", (
        "o leitor viu marcado um checkbox que o arquivo deixou fechado")
