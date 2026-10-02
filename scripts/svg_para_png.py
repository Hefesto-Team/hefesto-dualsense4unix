#!/usr/bin/env python3
"""svg_para_png.py — rasteriza o SVG dela com o MOTOR QUE ELA VÊ."""
from __future__ import annotations

import pathlib
import sys

_RAIZ_TELA = str(pathlib.Path(__file__).resolve().parents[1] / 'src')
if _RAIZ_TELA not in sys.path:
    sys.path.insert(0, _RAIZ_TELA)
from hefesto_dualsense4unix.utils.tela_de_mentira import (
    garantir_tela_de_mentira,
)

garantir_tela_de_mentira()

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("WebKit2", "4.1")

from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, WebKit2

_PASSOS_CARGA = 500
_PASSOS_PINTURA = 80


def rasterizar(svg: pathlib.Path, png: pathlib.Path, tamanho: int = 512) -> None:
    _BASE = 512
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
