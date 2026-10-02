"""tests/unit/test_button_glyph.py — testes do widget ButtonGlyph e SVGs."""
from __future__ import annotations

import pathlib
import xml.dom.minidom

import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
GLYPHS_DIR = REPO_ROOT / "assets" / "glyphs"

GLYPHS_ESPERADOS = [
    "cross",
    "circle",
    "square",
    "triangle",
    "dpad_up",
    "dpad_down",
    "dpad_left",
    "dpad_right",
    "l1",
    "r1",
    "l2",
    "r2",
    "touchpad",
    "share",
    "options",
    "ps",
    "stick_l",
    "stick_r",
    "mic",
]


@pytest.mark.parametrize("nome", GLYPHS_ESPERADOS)
def test_svg_existe(nome: str) -> None:
    """Verifica que o SVG base existe em assets/glyphs/."""
    arquivo = GLYPHS_DIR / f"{nome}.svg"
    assert arquivo.exists(), f"SVG ausente: {arquivo}"


@pytest.mark.parametrize("nome", GLYPHS_ESPERADOS)
def test_svg_xml_valido(nome: str) -> None:
    """Verifica que o SVG e XML bem formado."""
    arquivo = GLYPHS_DIR / f"{nome}.svg"
    if not arquivo.exists():
        pytest.skip(f"SVG não encontrado: {arquivo}")
    try:
        xml.dom.minidom.parse(str(arquivo))
    except Exception as exc:
        pytest.fail(f"XML invalido em {arquivo}: {exc}")


def _tem_gtk() -> bool:
    """Retorna True se GTK3 esta disponivel no ambiente."""
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk  # noqa: F401
        return True
    except Exception:
        return False


