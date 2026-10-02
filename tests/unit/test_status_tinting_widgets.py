"""tests/unit/test_status_tinting_widgets.py — tinting dos widgets (STATUS-03)."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("status tinting widgets")


import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

import pytest

pytest.importorskip("cairo")

import cairo
from gi.repository import Gtk

from hefesto_dualsense4unix.utils.color_contrast import (

    TROUGH_HEX,
    ensure_min_contrast,
    rgb_para_hex,
    tintar_progressbar,
)

COR_A = (16, 32, 72)
COR_B = (255, 0, 0)

_SVG_ATIVO_FAKE = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
  <rect x="0" y="0" width="32" height="32" fill="#bd93f9"/>
  <line x1="4" y1="4" x2="28" y2="28" stroke="#bd93f9" stroke-width="2"/>
</svg>
"""

_SVG_NORMAL_FAKE = _SVG_ATIVO_FAKE.replace("#bd93f9", "#f8f8f2")


def _drena_eventos() -> None:
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)


def _render_offscreen(
    janela: Gtk.OffscreenWindow, largura: int, altura: int
) -> tuple[bytes, int]:
    """Copia o surface da OffscreenWindow para um ImageSurface: (bytes, stride)."""
    _drena_eventos()
    origem = janela.get_surface()
    assert origem is not None
    img = cairo.ImageSurface(cairo.FORMAT_ARGB32, largura, altura)
    ctx = cairo.Context(img)
    ctx.set_source_surface(origem, 0, 0)
    ctx.paint()
    img.flush()
    return bytes(img.get_data()), img.get_stride()


def _pixel(dados: bytes, stride: int, x: int, y: int) -> tuple[int, int, int, int]:
    """Lê um pixel (r, g, b, a) de um buffer ARGB32 pré-multiplicado."""
    off = y * stride + x * 4
    b, g, r, a = dados[off], dados[off + 1], dados[off + 2], dados[off + 3]
    return (r, g, b, a)


def _hex_para_rgb(hex_cor: str) -> tuple[int, int, int]:
    return (
        int(hex_cor[1:3], 16),
        int(hex_cor[3:5], 16),
        int(hex_cor[5:7], 16),
    )


def test_tintar_progressbar_provider_por_widget_e_pixels() -> None:
    barra = Gtk.ProgressBar()
    barra.set_fraction(0.5)
    barra.set_size_request(200, 20)

    hex_aplicado = tintar_progressbar(barra, COR_A)
    assert hex_aplicado == rgb_para_hex(ensure_min_contrast(COR_A))

    off = Gtk.OffscreenWindow()
    off.add(barra)
    off.show_all()
    altura_img = 32
    dados, stride = _render_offscreen(off, 200, altura_img)

    esperado_fill = _hex_para_rgb(hex_aplicado)
    esperado_trough = _hex_para_rgb(TROUGH_HEX)

    def _coluna_contem(x: int, esperado: tuple[int, int, int]) -> bool:
        for y in range(altura_img):
            r, g, b, a = _pixel(dados, stride, x, y)
            if a == 255 and all(
                abs(c - e) <= 2 for c, e in zip((r, g, b), esperado, strict=True)
            ):
                return True
        return False

    assert _coluna_contem(20, esperado_fill), (
        f"coluna x=20 devia conter o fill {esperado_fill}"
    )
    assert _coluna_contem(180, esperado_trough), (
        f"coluna x=180 devia conter o trough {esperado_trough}"
    )
    off.destroy()


def test_tintar_progressbar_atualiza_so_quando_a_cor_muda() -> None:
    barra = Gtk.ProgressBar()

    hex_1 = tintar_progressbar(barra, COR_A)
    provider_1 = barra._hefesto_tint_provider

    hex_2 = tintar_progressbar(barra, COR_A)
    assert hex_2 == hex_1
    assert barra._hefesto_tint_provider is provider_1

    hex_3 = tintar_progressbar(barra, ensure_min_contrast(COR_A))
    assert hex_3 == hex_1
    assert barra._hefesto_tint_provider is provider_1

    hex_4 = tintar_progressbar(barra, COR_B)
    assert hex_4 != hex_1
    assert barra._hefesto_tint_provider is not provider_1
