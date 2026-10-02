"""BUG-GUI-SWITCH-ICONE-QUEBRADO-01 — o quadrado vermelho ao lado dos switches."""

from __future__ import annotations

from pathlib import Path

from tests.conftest import exigir_gi_real

exigir_gi_real("switch sem ícone quebrado")

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

import pytest

pytest.importorskip("cairo")

from gi.repository import Gdk, Gtk

CSS = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "hefesto_dualsense4unix"
    / "gui"
    / "theme.css"
)

_R_MIN, _G_MAX, _B_MAX = 150, 90, 90


def _pixels_vermelhos(pixbuf) -> int:  # type: ignore[no-untyped-def]
    """Quantos pixels do pixbuf caem na faixa do `image-missing`."""
    dados = pixbuf.get_pixels()
    canais = pixbuf.get_n_channels()
    largura, altura = pixbuf.get_width(), pixbuf.get_height()
    passo = pixbuf.get_rowstride()

    total = 0
    for y in range(altura):
        base = y * passo
        for x in range(largura):
            i = base + x * canais
            r, g, b = dados[i], dados[i + 1], dados[i + 2]
            if r >= _R_MIN and g <= _G_MAX and b <= _B_MAX:
                total += 1
    return total


def _render_do_switch(*, com_o_css: bool, ligado: bool):  # type: ignore[no-untyped-def]
    """Um `GtkSwitch` desenhado numa `OffscreenWindow`, devolvido como pixbuf."""
    janela = Gtk.OffscreenWindow()
    janela.get_style_context().add_class("hefesto-dualsense4unix-window")

    interruptor = Gtk.Switch()
    interruptor.set_active(ligado)
    interruptor.set_margin_start(8)
    interruptor.set_margin_end(8)
    interruptor.set_margin_top(8)
    interruptor.set_margin_bottom(8)
    janela.add(interruptor)

    provedor = None
    if com_o_css:
        provedor = Gtk.CssProvider()
        provedor.load_from_path(str(CSS))
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provedor,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    janela.show_all()
    for _ in range(4):
        while Gtk.events_pending():
            Gtk.main_iteration()

    pixbuf = janela.get_pixbuf()

    if provedor is not None:
        Gtk.StyleContext.remove_provider_for_screen(
            Gdk.Screen.get_default(), provedor
        )
    janela.destroy()
    return pixbuf


@pytest.mark.parametrize("ligado", [False, True])
def test_o_switch_nao_desenha_o_icone_quebrado(ligado: bool) -> None:
    """A mordida: sem a regra do `switch image`, isto reprova nos dois estados."""
    pixbuf = _render_do_switch(com_o_css=True, ligado=ligado)

    vermelhos = _pixels_vermelhos(pixbuf)

    assert vermelhos == 0, (
        f"o GtkSwitch (ligado={ligado}) desenhou {vermelhos} pixels na faixa do "
        "`image-missing`. A regra `.hefesto-dualsense4unix-window switch image "
        "{ -gtk-icon-transform: scale(0); }` do theme.css saiu, deixou de casar, "
        "ou o GTK mudou a estrutura de nós do switch."
    )


def test_o_defeito_existe_de_verdade_sem_o_css_do_projeto() -> None:
    """Ancora a premissa ONDE ela vale: o quadrado é desenhado sem o CSS."""
    pixbuf = _render_do_switch(com_o_css=False, ligado=False)
    vermelhos = _pixels_vermelhos(pixbuf)

    if vermelhos == 0:
        pytest.skip(
            "este ambiente não desenha o `image-missing` na faixa vermelha "
            "(tema de ícones diferente do breeze-dark desta casa): não há o "
            "que ancorar aqui. A cura do `theme.css` continua coberta por "
            "`test_o_switch_nao_desenha_o_icone_quebrado`, que não depende do "
            "tema."
        )

    assert vermelhos > 0
