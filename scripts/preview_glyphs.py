#!/usr/bin/env python3
"""preview_glyphs.py — janela GTK3 com grade de todos os glyphs SVG."""
from __future__ import annotations

import pathlib
import sys

_RAIZ_TELA = str(pathlib.Path(__file__).resolve().parents[1] / "src")
if _RAIZ_TELA not in sys.path:
    sys.path.insert(0, _RAIZ_TELA)
from hefesto_dualsense4unix.utils import identidade
from hefesto_dualsense4unix.utils.tela_de_mentira import (
    garantir_tela_de_mentira,
)

garantir_tela_de_mentira()

REPO_ROOT = pathlib.Path(__file__).parent.parent
GLYPHS_DIR = REPO_ROOT / "assets" / "glyphs"

GLYPHS = [
    "cross", "circle", "square", "triangle",
    "dpad_up", "dpad_down", "dpad_left", "dpad_right",
    "l1", "r1", "l2", "r2",
    "touchpad", "share", "options", "ps",
    "stick_l", "stick_r", "mic",
]

TITULO = f"{identidade.atual().nome_longo} — Preview Glyphs SVG"
COLUNAS = 5
TAMANHO = 48


def _carregar_pixbuf(caminho: pathlib.Path, tamanho: int):
    """Carrega SVG como pixbuf GTK em tamanho quadrado."""
    from gi.repository import GdkPixbuf  # type: ignore[import]
    return GdkPixbuf.Pixbuf.new_from_file_at_scale(
        str(caminho), tamanho, tamanho, True
    )


def main() -> int:
    """Abre a janela de preview dos glyphs."""
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import Gtk  # type: ignore[import]
    except Exception as exc:
        print(f"GTK3 não disponivel: {exc}", file=sys.stderr)
        return 1

    janela = Gtk.Window(title=TITULO)
    janela.set_default_size(COLUNAS * (TAMANHO + 20), 400)
    janela.connect("destroy", Gtk.main_quit)

    grade = Gtk.Grid()
    grade.set_row_spacing(12)
    grade.set_column_spacing(12)
    grade.set_margin_top(16)
    grade.set_margin_bottom(16)
    grade.set_margin_start(16)
    grade.set_margin_end(16)

    for idx, nome in enumerate(GLYPHS):
        col = idx % COLUNAS
        row = (idx // COLUNAS) * 3

        svg_normal = GLYPHS_DIR / f"{nome}.svg"
        if svg_normal.exists():
            try:
                pb = _carregar_pixbuf(svg_normal, TAMANHO)
                img = Gtk.Image.new_from_pixbuf(pb)
            except Exception:
                img = Gtk.Label(label="?")
        else:
            img = Gtk.Label(label="ausente")
        grade.attach(img, col, row, 1, 1)

        svg_ativo = GLYPHS_DIR / f"{nome}_active.svg"
        if svg_ativo.exists():
            try:
                pb_a = _carregar_pixbuf(svg_ativo, TAMANHO)
                img_a = Gtk.Image.new_from_pixbuf(pb_a)
            except Exception:
                img_a = Gtk.Label(label="?")
        else:
            img_a = Gtk.Label(label="")
        grade.attach(img_a, col, row + 1, 1, 1)

        lbl = Gtk.Label(label=nome)
        lbl.set_xalign(0.5)
        grade.attach(lbl, col, row + 2, 1, 1)

    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.add(grade)
    janela.add(scroll)
    janela.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
