"""COR-QUE-NAO-PINTAVA-01 (19/08/2026) — a classe de cor que o GTK ignorava."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("COR-QUE-NAO-PINTAVA-01 (a cor que o GTK resolvia)")

from pathlib import Path

import gi
import pytest

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk

RAIZ = Path(__file__).resolve().parents[2]
THEME = RAIZ / "src/hefesto_dualsense4unix/gui/theme.css"

PROMESSAS = {
    "hefesto-dualsense4unix-status-ok": (0x50, 0xFA, 0x7B),
    "hefesto-dualsense4unix-status-warn": (0xF1, 0xFA, 0x8C),
    "hefesto-dualsense4unix-status-err": (0xFF, 0x55, 0x55),
    "hefesto-dualsense4unix-accent-purple": (0xBD, 0x93, 0xF9),
    "hefesto-dualsense4unix-accent-pink": (0xFF, 0x79, 0xC6),
}


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _gtk_pronto(), reason="sem GTK/display utilizável"
)


def _cor_resolvida(classe: str) -> tuple[int, int, int]:
    """A cor que o GTK REALMENTE resolve para um label dentro da janela."""
    provider = Gtk.CssProvider()
    provider.load_from_path(str(THEME))
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
    janela = Gtk.OffscreenWindow()
    janela.get_style_context().add_class("hefesto-dualsense4unix-window")
    caixa = Gtk.Box()
    rotulo = Gtk.Label(label="texto")
    rotulo.get_style_context().add_class(classe)
    caixa.add(rotulo)
    janela.add(caixa)
    janela.show_all()
    while Gtk.events_pending():
        Gtk.main_iteration()
    rgba = rotulo.get_style_context().get_color(Gtk.StateFlags.NORMAL)
    return (
        round(rgba.red * 255),
        round(rgba.green * 255),
        round(rgba.blue * 255),
    )


class TestAClassePinta:
    @pytest.mark.parametrize("classe,esperado", sorted(PROMESSAS.items()))
    def test_a_cor_prometida_chega_ao_label(
        self, classe: str, esperado: tuple[int, int, int]
    ) -> None:
        """A MORDIDA. Tire o escopo da window no `theme.css` e isto reprova."""
        obtido = _cor_resolvida(classe)
        assert obtido == esperado, (
            f"a classe `{classe}` é aplicada e o GTK resolve {obtido}, não "
            f"{esperado}: a regra perdeu a disputa de especificidade para "
            "`.hefesto-dualsense4unix-window label`, e o texto sai na cor do "
            "tema — foi assim que dois rótulos do main.glade ficaram brancos"
        )
