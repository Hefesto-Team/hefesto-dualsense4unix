#!/usr/bin/env python3
"""O X DO VIZINHO É QUADRADO — medido no WebKit, na página que o produto abre."""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("DICA-DA-COR-01 — o X do vizinho medido no WebKit da janela real")

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

try:
    from hefesto_dualsense4unix.gui.ponte_da_tela import TAMANHO_OCULTA
except (ImportError, ValueError) as _erro:  # pragma: no cover — ambiente sem WebKit
    pytest.skip(
        f"DICA-DA-COR-01: a biblioteca da janela não importou ({_erro}). "
        "Falta gir1.2-webkit2-4.1?",
        allow_module_level=True,
    )

from hefesto_dualsense4unix.interface.olhar import VISTA_DELA

PAGINA = "04-iluminacao.html"

UNIQS = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02")

VISTAS = {"janela": TAMANHO_OCULTA, "dela": VISTA_DELA}

TETO_DO_X = 12.0
PISO_DO_X = 8.0
FOLGA = 0.5

MEDIDA = r"""
(function(){
  var de = document.documentElement;
  var Matriz = window.DOMMatrix || window.WebKitCSSMatrix;
  var px = function(v){ return parseFloat(v) || 0; };
  return JSON.stringify({
    viewport: [de.clientWidth, de.clientHeight],
    lugares: Array.prototype.map.call(
      document.querySelectorAll('[data-controle] .guia .tom.tomado'), function(el){
        var r = el.getBoundingClientRect();
        var s = getComputedStyle(el);
        var a = getComputedStyle(el, '::after');
        var m = (a.transform && a.transform !== 'none') ? new Matriz(a.transform) : new Matriz();
        var w = px(a.width), h = px(a.height);
        return {
          controle: el.closest('[data-controle]').getAttribute('data-controle'),
          content: a.content,
          pilula: [r.width, r.height],
          dentro: [r.width - px(s.borderLeftWidth) - px(s.borderRightWidth),
                   r.height - px(s.borderTopWidth) - px(s.borderBottomWidth)],
          x: [w, h],
          canto: [px(a.left) + m.m41, px(a.top) + m.m42]
        };
      })
  });
})()
"""


def _carga() -> dict:
    """A carga do tique, montada pelo PACOTE da aba e traduzida como o piloto traduz."""
    import pacotes
    from pacotes import a04_iluminacao as a04

    tons = a04.tons_da_guia()
    conectados, lugares = [], []
    for i, uniq in enumerate(UNIQS):
        conectados.append({"uniq": uniq, "player": i + 1, "player_slot": i + 1,
                           "connected": True, "transport": "usb",
                           "battery_pct": 90, "is_primary": i == 0, "inputs": {},
                           "lightbar_rgb": list(tons[2 + 3 * i]),
                           "lightbar_on": True})
        lugares.append({"pref": f"p{i + 1}", "jogador": i + 1, "uniq": uniq,
                        "nome": "DualSense", "via": "USB", "cor": "midnight-black",
                        "plastico": "#1c1c1c", "conectado": True})
    ctx = pacotes.Contexto(state={"active_profile": "regua"}, mesa=lugares,
                           conectados=conectados, estados={})
    pacote = pacotes.pacote_da_pagina(PAGINA, ctx) or {}
    return pacotes.normalizar(pacote, {m["uniq"]: m["pref"] for m in lugares})


def _medir_na_vista(tamanho: tuple[int, int], pintar: str) -> dict:
    """Abre a 04 publicada num WebKit offscreen do tamanho pedido, pinta e mede."""
    from gi.repository import GLib, Gtk, WebKit2

    from hefesto_dualsense4unix.interface import hefesto_vivo, onde

    saiu: list[str] = []
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(*tamanho)
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def mediu(v, res):
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:
            saiu.append(f"ERRO na medida: {e}")
        Gtk.main_quit()

    def pintou(v, res):
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:
            saiu.append(f"ERRO na pintura: {e}")
            Gtk.main_quit()
            return
        v.evaluate_javascript(MEDIDA, -1, None, None, None, mediu)

    def instalou(v, res):
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:
            saiu.append(f"ERRO no bootstrap: {e}")
            Gtk.main_quit()
            return
        v.evaluate_javascript(pintar, -1, None, None, None, pintou)

    def carregou(v, evento):
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(hefesto_vivo.BOOTSTRAP, -1, None, None,
                                  None, instalou)

    view.connect("load-changed", carregou)
    view.load_uri(onde.pagina(PAGINA, publicado=True).as_uri())
    guarda = GLib.timeout_add(20000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert saiu, f"o WebKit não respondeu em 20 s na vista {tamanho}"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    return json.loads(saiu[0])


@pytest.fixture(scope="module")
def medido() -> dict[str, dict]:
    """As duas vistas, medidas uma depois da outra no mesmo processo."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import Gtk

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    from hefesto_dualsense4unix.interface import hefesto_vivo

    pintar = hefesto_vivo.PEDIR_A_PINTURA.replace(
        "CARGA", json.dumps(_carga(), ensure_ascii=False))
    return {nome: _medir_na_vista(tamanho, pintar) for nome, tamanho in VISTAS.items()}


def _os_x(medido: dict[str, dict], vista: str) -> list[dict]:
    lugares = medido[vista]["lugares"]
    assert lugares, (
        f"nenhum tom tomado na vista {vista} — sem X não há o que medir, e a "
        "régua daria verde por vacuidade")
    return lugares


def _rotulo(x: dict) -> str:
    w, h = x["x"]
    lw, lh = x["pilula"]
    return f"{x['controle']}: X {w:.2f} x {h:.2f} px numa pílula {lw:.2f} x {lh:.2f}"


def test_a_regua_mede_as_vistas_que_pediu(medido):
    """O viewport medido tem de ser a vista importada — lido de dentro do motor."""
    for nome, tamanho in VISTAS.items():
        assert medido[nome]["viewport"] == list(tamanho), (
            f"a vista {nome} pediu {tamanho} e a página recebeu "
            f"{medido[nome]['viewport']}")


@pytest.mark.parametrize("vista", sorted(VISTAS))
def test_cada_controle_ligado_tem_um_x_na_cor_do_outro(medido, vista):
    """Dois ligados, cores diferentes: um X por coluna ligada, nenhum nos vazios."""
    lugares = _os_x(medido, vista)
    assert sorted(x["controle"] for x in lugares) == ["p1", "p2"], (
        f"na vista {vista} o X caiu em {[x['controle'] for x in lugares]}")
    assert all(x["content"] not in ("", "none", "normal") for x in lugares), (
        f"o `::after` do tom tomado perdeu o conteúdo e não desenha nada: {lugares}")


@pytest.mark.parametrize("vista", sorted(VISTAS))
def test_o_x_e_quadrado(medido, vista):
    """Um X de 4,5 por 14 é uma tira — foi o que a janela mostrava ao abrir."""
    tortos = [x for x in _os_x(medido, vista) if abs(x["x"][0] - x["x"][1]) > FOLGA]
    assert not tortos, (
        f"o X não é quadrado na vista {vista}:\n" + "\n".join(map(_rotulo, tortos)))


@pytest.mark.parametrize("vista", sorted(VISTAS))
def test_o_x_tem_corpo(medido, vista):
    """Os dois lados passam do piso — um X de 4 px não se lê como X."""
    finos = [x for x in _os_x(medido, vista) if min(x["x"]) < PISO_DO_X]
    assert not finos, (
        f"o X tem menos de {PISO_DO_X:g} px num dos lados na vista {vista}:\n"
        + "\n".join(map(_rotulo, finos)))


@pytest.mark.parametrize("vista", sorted(VISTAS))
def test_o_x_cabe_no_teto_e_na_pilula(medido, vista):
    """O X não passa do desenho e não vaza da pílula que o carrega."""
    fora = []
    for x in _os_x(medido, vista):
        (w, h), (cx, cy), (dl, da) = x["x"], x["canto"], x["dentro"]
        if (max(w, h) > TETO_DO_X + FOLGA or cx < -FOLGA or cy < -FOLGA
                or cx + w > dl + FOLGA or cy + h > da + FOLGA):
            fora.append(f"{_rotulo(x)} · canto {cx:.2f},{cy:.2f} · caixa {dl:.2f} x {da:.2f}")
    assert not fora, (
        f"o X passa do teto de {TETO_DO_X:g} px ou vaza da pílula na vista "
        f"{vista}:\n" + "\n".join(fora))


@pytest.mark.parametrize("vista", sorted(VISTAS))
def test_o_x_e_centrado_na_pilula(medido, vista):
    """O centro do X é o centro da pílula, nos dois eixos."""
    tortos = []
    for x in _os_x(medido, vista):
        (w, h), (cx, cy), (dl, da) = x["x"], x["canto"], x["dentro"]
        if abs(cx + w / 2 - dl / 2) > FOLGA or abs(cy + h / 2 - da / 2) > FOLGA:
            tortos.append(f"{_rotulo(x)} · centro {cx + w / 2:.2f},{cy + h / 2:.2f} "
                          f"· centro da pílula {dl / 2:.2f},{da / 2:.2f}")
    assert not tortos, (
        f"o X saiu do centro da pílula na vista {vista}:\n" + "\n".join(tortos))
