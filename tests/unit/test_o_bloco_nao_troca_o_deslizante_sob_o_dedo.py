#!/usr/bin/env python3
"""O bloco repintado a cada tique não troca o deslizante que o dedo segura.

A barra de cada aparelho mora no cartão dele, num bloco que o tique repinta (a pilha e a força
mudam o tempo todo). Trocar o nó sob o dedo perde o soltar: o ``change`` sai de um nó fora da
página e o valor arrastado nunca se grava. O pintor adia o bloco enquanto um deslizante dele está
apertado (``:active``) e o pinta no tique seguinte ao soltar.
"""
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
<div id="mod-aparelhos"><span class="bat">54%</span>
  <input type="range" id="preso" min="0" max="100" value="80"></div>
</body></html>"""

NOVO = '<span class="bat">53%</span><input type="range" id="preso" min="0" max="100" value="80">'

ROTEIRO = """
(function(){
  const fora = {};
  const preso = document.getElementById('preso');
  const original = HTMLInputElement.prototype.matches;
  HTMLInputElement.prototype.matches = function(s){
    return (s === ':active' && this === preso) || original.call(this, s);
  };
  window.__hef.pintar({blocos: {'#mod-aparelhos': NOVO_AQUI}});
  fora.ficou_sob_o_dedo = document.getElementById('preso') === preso;
  HTMLInputElement.prototype.matches = original;
  window.__hef.pintar({blocos: {'#mod-aparelhos': NOVO_AQUI}});
  fora.trocou_ao_soltar = document.getElementById('preso') !== preso;
  fora.pilha = document.querySelector('#mod-aparelhos .bat').textContent;
  return JSON.stringify(fora);
})()
"""


def _bootstrap() -> str:
    fonte = PILOTO.read_text(encoding="utf-8")
    achou = re.search(r'^BOOTSTRAP = r"""(.*?)"""$', fonte, re.S | re.M)
    assert achou, "o piloto perdeu o BOOTSTRAP: não há o que testar"
    return achou.group(1)


@pytest.fixture(scope="module")
def medido() -> dict:
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica: o WebKit não abre")

    roteiro = ROTEIRO.replace("NOVO_AQUI", json.dumps(NOVO))
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
            v.evaluate_javascript(_bootstrap(), -1, None, None, None, instalou)

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


def test_o_deslizante_apertado_segue_o_mesmo_no(medido: dict) -> None:
    """MORDIDA: sem o adiamento do ``:active`` no pintor, o nó sob o dedo é trocado."""
    assert medido["ficou_sob_o_dedo"] is True, "o tique trocou o deslizante sob o dedo"


def test_o_bloco_adiado_se_pinta_ao_soltar(medido: dict) -> None:
    assert medido["trocou_ao_soltar"] is True and medido["pilha"] == "53%", medido
