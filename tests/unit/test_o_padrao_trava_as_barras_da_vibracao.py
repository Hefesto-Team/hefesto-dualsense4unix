"""O «Padrão» trava as barras da aba Vibração (desenho aprovado em 04/10/2026).

O-DESLIGADO-DEIXA-O-JOGO-DECIDIR-01, item 1 da seção «A decisão dela de 04/10». Ela:
*«se balanceado é o original. então não tem pq ter original»*; aprovado: *«Perfeito só vamos trocar
o rótulo do botão para Padrão»*. Com o degrau Padrão as três barras do controle (Sensor Háptico,
Motor esquerdo, Motor direito) ficam inteiras verdes e travadas, com a palavra no lugar do número; o
que ela guardou espera a Economia ou o Máximo.

A página sob prova é a da BANCADA (``mockup/05-vibracao.html``), no WebKit fora da tela, com o
BOOTSTRAP do piloto: o pintor de verdade acende a classe, e a folha de estilo de verdade trava.

MORDIDAS: a regra ``.forca.padrao ~ .motor .trilho.arrasta{display:none}`` (a barra de arrasto
continua na tela), o campo do plano em ``a05_vibracao.pacote``, o rótulo «Padrão» do degrau.
"""

from __future__ import annotations

import gc
import json
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("abre a página num WebKit")

from hefesto_dualsense4unix.interface import aba05, onde

PAGINA = "05-vibracao.html"

#: lê a coluna do P1: o estado das três barras (arrasto, trava, palavra), o do degrau e a foto
LER = r"""
(function(){
  const forca = document.querySelector('[data-campo="padrao"]');
  const linhas = [];
  for (let e = forca.nextElementSibling; e; e = e.nextElementSibling) {
    if (e.classList.contains('motor') && e.querySelector('input.trilho.arrasta')) linhas.push(e);
  }
  const estilo = el => getComputedStyle(el);
  const visivel = el => estilo(el).display !== 'none' && el.offsetWidth > 0;
  const fora = {
    classe_forca: document.querySelector('[data-campo="padrao"]').className,
    degraus: [...document.querySelectorAll('[data-campo="degrau-herdado"] button, '
      + '.forca .seg button')].map(b => b.textContent.trim()),
    linhas: linhas.map(l => {
      const arrasto = l.querySelector('input.trilho.arrasta');
      const trava = l.querySelector('.trilho.travada');
      let focou = false;
      if (arrasto) { arrasto.focus(); focou = document.activeElement === arrasto; }
      return {
        campo: (arrasto || {dataset: {}}).dataset.campo || '',
        arrasto_visivel: arrasto ? visivel(arrasto) : false,
        trava_visivel: trava ? visivel(trava) : false,
        aria: trava ? trava.getAttribute('aria-disabled') : null,
        cor: trava ? estilo(trava).backgroundColor : '',
        cursor: trava ? estilo(trava).cursor : '',
        focou: focou,
        num: l.querySelector('.num').textContent.trim(),
      };
    }),
  };
  return JSON.stringify(fora);
})()
"""


def _pintar(padrao: bool, numeros: dict[str, str]) -> str:
    plano = {"padrao": "1" if padrao else "", **numeros}  # (noqa-acento) campo
    return ("window.__hef.pintar(" + json.dumps({"colunas": {"p1": plano}, "mesa": {}}) + ")")


def _na_pagina(passos: list[str]) -> list[Any]:
    try:
        return _na_pagina_sem_recolher(passos)
    finally:
        gc.collect()
        from gi.repository import Gtk

        while Gtk.events_pending():
            Gtk.main_iteration_do(False)


def _na_pagina_sem_recolher(passos: list[str]) -> list[Any]:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    from hefesto_dualsense4unix.interface import hefesto_vivo

    respostas: list[str] = []
    view = WebKit2.WebView()
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(1500, 1100)
    janela.add(view)
    janela.show_all()
    fila = [hefesto_vivo.BOOTSTRAP, *passos]

    def seguinte() -> bool:
        if not fila:
            GLib.timeout_add(300, lambda: (Gtk.main_quit(), False)[1])
            return False
        js = fila.pop(0)

        def respondeu(v: Any, res: Any, _u: Any = None) -> None:
            try:
                respostas.append(v.evaluate_javascript_finish(res).to_string())
            except Exception as erro:
                respostas.append(f"ERRO {erro}")
            GLib.idle_add(seguinte)

        view.evaluate_javascript(js, -1, None, None, None, respondeu, None)
        return False

    def carregou(_v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            seguinte()

    view.connect("load-changed", carregou)
    view.load_uri(onde.pagina(PAGINA, publicado=False).as_uri())
    guarda = GLib.timeout_add(30000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert len(respostas) == len(passos) + 1, f"o WebKit parou no meio: {respostas}"
    assert respostas[0] == "ok", f"o BOOTSTRAP do piloto não instalou: {respostas[0]}"
    return [json.loads(r) if r.startswith(("{", "[")) else r for r in respostas[1:]]


def test_o_degrau_se_chama_padrao_e_a_chave_continua_balanceado() -> None:
    assert [r for r, _ in aba05.FORCA] == ["Economia", "Padrão", "Máximo"]
    assert [c for _, c in aba05.FORCA] == ["economia", "balanceado", "max"]


def test_em_padrao_as_tres_barras_ficam_verdes_travadas_e_sem_teclado() -> None:
    lidas = _na_pagina([
        LER,
        _pintar(True, {"barra-h-pct": "Padrão", "barra-e-pct": "Padrão", "barra-d-pct": "Padrão"}),
        LER,
    ])
    antes, _n, depois = lidas
    assert "padrao" not in antes["classe_forca"]  # (noqa-acento) campo
    assert all(x["arrasto_visivel"] and not x["trava_visivel"] for x in antes["linhas"]), antes
    acesa = "padrao" in depois["classe_forca"].split()  # (noqa-acento) campo
    assert acesa, "o pintor não acendeu o Padrão"
    assert len(depois["linhas"]) == 3, "o Sensor Háptico e os dois motores"
    for linha in depois["linhas"]:
        assert not linha["arrasto_visivel"], f"a barra ainda aceita arrasto: {linha}"
        assert not linha["focou"], f"a barra ainda recebe o teclado: {linha}"
        assert linha["trava_visivel"] and linha["aria"] == "true", linha
        assert linha["cursor"] == "not-allowed", linha
        assert linha["cor"] != "rgba(0, 0, 0, 0)", f"a barra travada não é verde: {linha}"
        assert linha["num"] == "Padrão", f"a palavra não ocupa o lugar do número: {linha}"


def test_economia_e_maximo_destravam_e_o_numero_guardado_volta() -> None:
    lidas = _na_pagina([
        _pintar(True, {"barra-e-pct": "Padrão"}),
        _pintar(False, {"barra-e-pct": "50"}),
        LER,
    ])
    depois = lidas[-1]
    assert "padrao" not in depois["classe_forca"].split()  # (noqa-acento) campo
    esquerdo = next(x for x in depois["linhas"] if x["campo"] == "barra-e")
    assert esquerdo["arrasto_visivel"] and not esquerdo["trava_visivel"], esquerdo
    assert esquerdo["num"] == "50", "o 50% que ela guardou volta ao destravar"
