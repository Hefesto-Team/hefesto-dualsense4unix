"""A "barra quebrada" que atravessava o círculo do L3/R3 na aba Status."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("barra quebrada no círculo do stick")

import math
from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

pytest.importorskip("cairo")

import cairo
from gi.repository import Gtk

from hefesto_dualsense4unix.gui.widgets.stick_preview_gtk import (
    BORDA_COLOR,
    StickPreviewGtk,
)


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _gtk_pronto(), reason="sem GTK/display utilizável")

_janelas_vivas: list[Any] = []

LADOS = (90, 120, 160)

FOLGA_DO_ANEL = 6


def _pintar(label: str, lado: int) -> Any:
    """Renderiza o desenho do analógico numa superfície de verdade."""
    preview = StickPreviewGtk(label=label)
    preview.set_size_request(lado, lado)
    janela = Gtk.OffscreenWindow()
    janela.add(preview)
    janela.set_size_request(lado, lado)
    janela.show_all()
    _janelas_vivas.append(janela)
    while Gtk.events_pending():
        Gtk.main_iteration()

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, lado, lado)
    ctx = cairo.Context(surface)
    preview._on_draw(preview, ctx)
    surface.flush()
    return surface


def _tinta_opaca_da_borda_no_miolo(surface: Any, lado: int) -> list[tuple[int, int]]:
    """Pixels de cor de borda PURA e opaca dentro do miolo do círculo."""
    dados = bytes(surface.get_data())
    stride = surface.get_stride()
    alvo = tuple(round(canal * 255) for canal in BORDA_COLOR)
    cx = cy = lado / 2
    raio_do_miolo = lado / 2 - 4 - FOLGA_DO_ANEL

    achados: list[tuple[int, int]] = []
    for y in range(lado):
        for x in range(lado):
            if math.hypot(x - cx, y - cy) > raio_do_miolo:
                continue
            base = y * stride + x * 4
            b, g, r, a = (
                dados[base],
                dados[base + 1],
                dados[base + 2],
                dados[base + 3],
            )
            if a == 255 and (r, g, b) == alvo:
                achados.append((x, y))
    return achados


@pytest.mark.parametrize("lado", LADOS)
def test_o_circulo_do_stick_nao_tem_barra_atravessando(lado: int) -> None:
    """O miolo do círculo não tem um só pixel opaco da cor do anel."""
    achados = _tinta_opaca_da_borda_no_miolo(_pintar("L3", lado), lado)

    assert not achados, (
        f"o miolo do círculo {lado}x{lado} tem {len(achados)} pixels opacos da "
        f"cor da borda (ex.: {achados[:5]}): o ponto corrente deixado pelo "
        "`show_text` da marca d'água voltou a ser ligado ao início do arco"
    )


@pytest.mark.parametrize("lado", LADOS)
def test_sem_rotulo_o_circulo_ja_saia_limpo(lado: int) -> None:
    """A hipótese explica o que JÁ funcionava."""
    achados = _tinta_opaca_da_borda_no_miolo(_pintar("", lado), lado)

    assert not achados, (
        f"sem rótulo o miolo {lado}x{lado} já sai sujo ({len(achados)} pixels): "
        "a barra não vem do `show_text`, e a hipótese está errada"
    )


def test_a_marca_dagua_devolve_o_contexto_sem_ponto_corrente() -> None:
    """O contrato da auxiliar: quem suja o caminho é quem limpa."""
    lado = 120
    preview = StickPreviewGtk(label="R3")
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, lado, lado)
    ctx = cairo.Context(surface)

    preview._desenhar_marca_dagua(ctx, lado / 2, lado / 2, lado / 2 - 4, BORDA_COLOR)

    assert not ctx.has_current_point(), (
        "`_desenhar_marca_dagua` devolveu o contexto com ponto corrente: o "
        "próximo `ctx.arc` vai ligar esse ponto ao início do arco com um "
        "segmento de reta"
    )
