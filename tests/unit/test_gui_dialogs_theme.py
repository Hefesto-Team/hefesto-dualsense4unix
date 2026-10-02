"""GUI-05 (P4/P5) — tema dos diálogos + segmentado read-only da ficha."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("gui dialogs theme")

import contextlib
import re
from pathlib import Path



_APP_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "hefesto_dualsense4unix"
    / "app"
)

_THEME_MARKS = (
    "_apply_app_theme(",
    'add_class("hefesto-dualsense4unix-window")',
)


def _tem_tema(src: str) -> bool:
    compacto = re.sub(r"\s+", "", src)
    return any(mark in compacto for mark in _THEME_MARKS)


def test_varredura_nenhum_modulo_do_app_cria_dialogo_sem_tema() -> None:
    """Guarda de regressão: módulo do app/ que constrói Gtk.MessageDialog ou"""
    padrao = re.compile(r"Gtk\.(MessageDialog|Dialog)\(")
    problemas: list[str] = []
    for arquivo in sorted(_APP_DIR.rglob("*.py")):
        texto = arquivo.read_text(encoding="utf-8")
        if padrao.search(texto) and not _tem_tema(texto):
            problemas.append(str(arquivo.relative_to(_APP_DIR)))
    assert problemas == [], (
        "Módulos com diálogo GTK sem a classe de tema: "
        f"{problemas} — use gui_dialogs._apply_app_theme"
    )


_NINTENDO_USB = {
    "name": "Nintendo Co., Ltd. Pro Controller",
    "vid": "057e",
    "pid": "2009",
    "bus": "usb",
    "driver": "nintendo",
}
_DESCONHECIDO = {"name": "Marca Xpto Pad", "vid": "abcd", "pid": "0001", "bus": "usb"}


_DISPLAY_OK = False
with contextlib.suppress(Exception):
    import gi as _gi

    _gi.require_version("Gtk", "3.0")
    from gi.repository import Gdk as _Gdk

    _DISPLAY_OK = _Gdk.Display.get_default() is not None


