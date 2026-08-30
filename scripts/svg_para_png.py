#!/usr/bin/env python3
"""svg_para_png.py — rasteriza o SVG dela com o MOTOR QUE ELA VÊ.

DECISÃO DELA, 30/08/2026: *"o nosso install sempre deve corrigir ele pra ter o
mesmo SVG em qualquer versão, PNG ou afins."*

POR QUE NÃO O `rsvg-convert`, e isto foi medido quatro vezes em 29 e 30/08: o
editor dela escreve rotação e espelho com `transform-box` e `transform-origin`,
e o **librsvg IGNORA os dois**. O ícone saía com o anel cortado e o martelo fora
da arte — ela apontou o defeito três vezes, e as três minhas tentativas de
"assar" os transforms na matriz erraram o alvo por geometria (o bounding box de
uma cúbica não são os pontos de controle dela).

A CURA NÃO É REESCREVER O DESENHO — é usar um motor que honra o que ela escreveu.
O WebKitGTK já está instalado nesta casa, porque é o motor da interface nova, e
ele renderiza **igual ao editor**: medido, o PNG que ele produz é o desenho que
ela vê no Boxy, anel completo e tudo dentro da moldura.

    svg_para_png.py entrada.svg saida.png [--tamanho 512]

O ARQUIVO DELA NUNCA É TOCADO. Este script só lê.
"""
from __future__ import annotations

import pathlib
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("WebKit2", "4.1")

from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, WebKit2  # noqa: E402

#: Quanto esperar a carga e a pintura, em passos de 10 ms. O WebKit avisa a
#: carga antes de pintar — daí os dois laços.
_PASSOS_CARGA = 500
_PASSOS_PINTURA = 80


def rasterizar(svg: pathlib.Path, png: pathlib.Path, tamanho: int = 512) -> None:
    # O PISO DA JANELA OFFSCREEN, medido em 30/08: abaixo de 512 ela CORTA em vez
    # de encolher — a 128 o anel da logo aparecia cortado embaixo. Rasteriza-se
    # sempre grande e reduz-se depois, que é como se faz ícone de qualquer forma.
    _BASE = 512
    # A página existe só para dar ao SVG um tamanho exato e fundo transparente.
    # `background: transparent` no WebView E no CSS: sem os dois, o ícone nasce
    # com o branco do navegador atrás e a dock mostra um quadrado.
    html = (
        "<html><head><style>"
        f"html,body{{margin:0;padding:0;background:transparent;"
        f"width:{_BASE}px;height:{_BASE}px;overflow:hidden}}"
        f"img{{width:{_BASE}px;height:{_BASE}px;display:block}}"
        "</style></head><body>"
        f'<img src="{svg.resolve().as_uri()}"></body></html>'
    )
    pagina = pathlib.Path(GLib.get_tmp_dir()) / f"hefesto-raster-{tamanho}.html"
    pagina.write_text(html, encoding="utf-8")

    janela = Gtk.OffscreenWindow()
    janela.set_default_size(_BASE, _BASE)
    view = WebKit2.WebView()
    view.set_background_color(Gdk.RGBA(0, 0, 0, 0))
    janela.add(view)
    janela.show_all()
    view.load_uri(pagina.as_uri())

    pronto = {"ok": False}
    view.connect(
        "load-changed",
        lambda _w, ev: pronto.update(ok=True) if ev == WebKit2.LoadEvent.FINISHED else None,
    )
    for _ in range(_PASSOS_CARGA):
        while Gtk.events_pending():
            Gtk.main_iteration()
        if pronto["ok"]:
            break
        GLib.usleep(10_000)
    for _ in range(_PASSOS_PINTURA):
        while Gtk.events_pending():
            Gtk.main_iteration()
        GLib.usleep(10_000)

    pixbuf = janela.get_pixbuf()
    if pixbuf is None:
        raise RuntimeError("o WebView não devolveu imagem")
    # A JANELA OFFSCREEN TEM PISO, e abaixo dele ela corta em vez de encolher —
    # medido em 30/08: a 512 o desenho sai inteiro, a 128 o anel aparece cortado.
    # Por isso a rasterização é SEMPRE grande e a redução vem depois, que é como
    # se faz ícone de qualquer forma: um raster nítido, reamostrado.
    if pixbuf.get_width() != tamanho or pixbuf.get_height() != tamanho:
        pixbuf = pixbuf.scale_simple(tamanho, tamanho, GdkPixbuf.InterpType.BILINEAR)
    png.parent.mkdir(parents=True, exist_ok=True)
    pixbuf.savev(str(png), "png", [], [])
    janela.destroy()
    pagina.unlink(missing_ok=True)


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    if len(args) < 2:
        print("uso: svg_para_png.py entrada.svg saida.png [--tamanho N]", file=sys.stderr)
        return 2
    tam = 512
    if "--tamanho" in argv:
        tam = int(argv[argv.index("--tamanho") + 1])
    rasterizar(pathlib.Path(args[0]), pathlib.Path(args[1]), tam)
    print(f"{args[1]}: {tam}x{tam}, pelo WebKit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
