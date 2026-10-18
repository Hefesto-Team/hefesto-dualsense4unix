#!/usr/bin/env python3
"""A VIBRAÇÃO TEM OS TRÊS LADO A LADO — A-VIBRACAO-TEM-OS-TRES-LADO-A-LADO-01.

Pedido de 06/10/2026: os três degraus da Força na mesma linha e com a mesma
largura, o mesmo para os três do «Testar agora», e o «Parar» com fundo vermelho
e letra branca.

A régua mede no WebKit, na janela do tamanho do produto (`TAMANHO_OCULTA`,
importado), a página da BANCADA (`mockup/05-vibracao.html`) pintada pelo pacote
da aba: o `--publicar` copia a bancada byte a byte e é um passo à parte, então a
medida vale antes e depois dele.

AS MORDIDAS (rodadas em 07/10/2026 e devolvidas):

* `repeat(3,1fr)` → `repeat(2,1fr)` no `.vib .seg` (e o `span 2` de volta no
  terceiro) → os degraus saem em duas linhas e a régua reprova;
* o `.acoes-col` de volta a `1fr 1fr auto` → as larguras ficam diferentes;
* o `.acoes-col .btn.vermelho` sem fundo → o «Parar» perde o vermelho.
"""
from __future__ import annotations

import itertools
import json
import pathlib
import sys
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("A-VIBRACAO-TEM-OS-TRES-LADO-A-LADO-01 — a Força e o Testar medidos no WebKit")

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

try:
    from hefesto_dualsense4unix.interface.janela import TAMANHO_OCULTA
except (ImportError, ValueError) as _erro:  # pragma: no cover — ambiente sem WebKit
    pytest.skip(f"a biblioteca da janela não importou ({_erro})",
                allow_module_level=True)

PAGINA = "05-vibracao.html"
UNIQS = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02")
VERMELHO = "rgb(255, 85, 85)"
BRANCO = "rgb(255, 255, 255)"

MEDIDA = r"""
(function(){
  function caixa(b){
    var r = b.getBoundingClientRect();
    return {txt: (b.textContent || '').trim(), top: Math.round(r.top * 10) / 10,
            larg: Math.round(r.width * 10) / 10, estoura: b.scrollWidth > b.clientWidth,
            esq: Math.round(r.left * 10) / 10, dir: Math.round(r.right * 10) / 10};
  }
  var colunas = {};
  document.querySelectorAll('.vib .ctrl').forEach(function(c){
    if (c.classList.contains('off')) { return; }
    var parar = c.querySelector('.acoes-col [data-papel="parar"]');
    var cs = parar ? getComputedStyle(parar) : null;
    var ctrl = c.getBoundingClientRect();
    colunas[c.getAttribute('data-controle')] = {
      degraus: Array.prototype.map.call(c.querySelectorAll('.seg button'), caixa),
      testes: Array.prototype.map.call(c.querySelectorAll('.acoes-col .btn'), caixa),
      parar_fundo: cs ? cs.backgroundColor : null,
      parar_letra: cs ? cs.color : null,
      coluna: {esq: Math.round(ctrl.left), dir: Math.round(ctrl.right)}
    };
  });
  var m = document.querySelector('.janela > .miolo');
  var de = document.documentElement;
  return JSON.stringify({
    colunas: colunas,
    viewport: {larg: de.clientWidth, alt: de.clientHeight},
    rola_miolo: m ? (m.scrollHeight - m.clientHeight) : null,
    rola_pagina: de.scrollHeight - de.clientHeight
  });
})()
"""


def _carga() -> dict[str, Any]:
    """A carga do tique, montada pelo PACOTE da aba — nunca HTML digitado aqui."""
    from hefesto_dualsense4unix.app.telas import vibracao as _tela

    import pacotes

    conectados, mesa = [], []
    for n, uniq in enumerate(UNIQS, start=1):
        conectados.append({"uniq": uniq, "player": n, "connected": True,
                           "transport": "usb" if n == 1 else "bt",
                           "battery_pct": 90, "is_primary": n == 1, "inputs": {}})
        mesa.append({"pref": f"p{n}", "jogador": n, "uniq": uniq, "nome": f"DualSense {n}",
                     "via": "USB" if n == 1 else "BT", "cor": "starlight-blue",
                     "plastico": "#123456", "conectado": True})
    ctx = pacotes.Contexto(state={"rumble_policy": "max", "rumble_mult_applied": 1.5,
                                  "native_mode": False},
                           mesa=mesa, conectados=conectados, estados={})
    original = _tela._orcamento_da_maquina
    _tela._orcamento_da_maquina = lambda: None
    try:
        return pacotes.pacote_da_pagina(PAGINA, ctx) or {}
    finally:
        _tela._orcamento_da_maquina = original


@pytest.fixture(scope="module")
def medido() -> dict[str, Any]:
    """Abre a bancada da aba num WebKit offscreen, pinta a carga e mede o DOM."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    from hefesto_dualsense4unix.interface import hefesto_vivo, onde

    pintar = hefesto_vivo.PEDIR_A_PINTURA.replace(
        "CARGA", json.dumps(_carga(), ensure_ascii=False))
    saiu: list[str] = []
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(*TAMANHO_OCULTA)
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def mediu(v: Any, res: Any) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:
            saiu.append(f"ERRO na medida: {e}")
        Gtk.main_quit()

    def pintou(v: Any, res: Any) -> None:
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:
            saiu.append(f"ERRO na pintura: {e}")
            Gtk.main_quit()
            return
        GLib.timeout_add(600, lambda: (v.evaluate_javascript(
            MEDIDA, -1, None, None, None, mediu), False)[1])

    def instalou(v: Any, res: Any) -> None:
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:
            saiu.append(f"ERRO no bootstrap: {e}")
            Gtk.main_quit()
            return
        v.evaluate_javascript(pintar, -1, None, None, None, pintou)

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(hefesto_vivo.BOOTSTRAP, -1, None, None, None, instalou)

    view.connect("load-changed", carregou)
    # o PUBLICADO, desde 18/10/2026: a bancada tirou os três degraus (r3b-05-12) e o produto os
    # mantém até a segunda passagem de A-INTENSIDADE-DA-VIBRACAO-E-DO-GATILHO-SAI-DO-FIRMWARE-
    # COMO-NO-PS5-01, que aposenta este arquivo com eles
    view.load_uri(onde.pagina(PAGINA, publicado=True).as_uri())
    guarda = GLib.timeout_add(20000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
    assert saiu, "o WebKit não respondeu em 20 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    lido: dict[str, Any] = json.loads(saiu[0])
    assert set(lido["colunas"]) == {"p1", "p2"}, (
        f"a régua mediria o vazio: colunas {sorted(lido['colunas'])}")
    return lido


def _lado_a_lado(botoes: list[dict[str, Any]], quem: str) -> None:
    assert len(botoes) == 3, f"{quem}: {len(botoes)} botões, e são três: {botoes}"
    tops = {b["top"] for b in botoes}
    assert max(tops) - min(tops) <= 1, f"{quem}: não estão na mesma linha: {botoes}"
    larguras = [b["larg"] for b in botoes]
    assert max(larguras) - min(larguras) <= 1, f"{quem}: larguras diferentes: {botoes}"
    ordem = sorted(botoes, key=lambda b: b["esq"])
    assert [b["txt"] for b in ordem] == [b["txt"] for b in botoes], (
        f"{quem}: a ordem na linha não é a do desenho: {botoes}")
    for a, b in itertools.pairwise(ordem):
        assert a["dir"] <= b["esq"] + 0.5, f"{quem}: sobrepostos: {botoes}"
    estourados = [b["txt"] for b in botoes if b["estoura"]]
    assert not estourados, f"{quem}: o texto passa do botão: {estourados} · {botoes}"


@pytest.mark.parametrize("pref", ["p1", "p2"])
def test_os_tres_degraus_da_forca_lado_a_lado(medido: dict[str, Any], pref: str) -> None:
    """MORDIDA: `repeat(2,1fr)` no `.vib .seg` — o terceiro desce para a segunda linha."""
    _lado_a_lado(medido["colunas"][pref]["degraus"], f"{pref}: os degraus da Força")


@pytest.mark.parametrize("pref", ["p1", "p2"])
def test_os_tres_do_testar_agora_lado_a_lado(medido: dict[str, Any], pref: str) -> None:
    """MORDIDA: o `.acoes-col` de volta a `1fr 1fr auto` — o «Parar» fica estreito."""
    _lado_a_lado(medido["colunas"][pref]["testes"], f"{pref}: o Testar agora")


@pytest.mark.parametrize("pref", ["p1", "p2"])
def test_o_parar_tem_fundo_vermelho_e_letra_branca(medido: dict[str, Any], pref: str) -> None:
    """MORDIDA: tirar o fundo do `.btn.vermelho` do `.acoes-col`."""
    c = medido["colunas"][pref]
    assert c["parar_fundo"] == VERMELHO, f"{pref}: o «Parar» tem fundo {c['parar_fundo']}"
    assert c["parar_letra"] == BRANCO, f"{pref}: o «Parar» tem letra {c['parar_letra']}"


def test_a_pagina_nao_rola_na_vertical(medido: dict[str, Any]) -> None:
    """Toda tela sem rolagem vertical: nem o miolo nem a página."""
    assert medido["viewport"] == {"larg": TAMANHO_OCULTA[0], "alt": TAMANHO_OCULTA[1]}
    assert (medido["rola_miolo"] or 0) <= 0, f"o miolo rola {medido['rola_miolo']} px"
    assert medido["rola_pagina"] <= 0, f"a página rola {medido['rola_pagina']} px"
