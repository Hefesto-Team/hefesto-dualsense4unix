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


@pytest.mark.parametrize(
    ("nome", "varre", "lado"), [("l2", "0", "esquerda"), ("r2", "1", "direita")])
@pytest.mark.parametrize("aceso", ["", "_active"])
def test_o_gatilho_gira_como_na_mao(nome: str, varre: str, lado: str, aceso: str) -> None:
    """O L2 é o semicírculo da esquerda no anti-horário; o R2, o da direita no horário (19/10/2026).

    A decisão: D-1910-O-GLIFO-DO-GATILHO-GIRA-COMO-NA-MAO. MORDIDA: trocar o `sweep-flag` do arco
    de um dos dois, ou devolver a seta reta para baixo.
    """
    import re

    svg = (GLYPHS_DIR / f"{nome}{aceso}.svg").read_text(encoding="utf-8")
    arco = re.search(r'd="M([\d.]+) [\d.]+ A11 11 0 0 ([01]) ([\d.]+) ', svg)
    assert arco, f"o {nome} perdeu o arco"
    assert arco.group(2) == varre, f"o arco do {nome} gira no sentido errado"
    assert (float(arco.group(3)) < 16) == (lado == "esquerda"), f"a seta do {nome} saiu do lado"
    assert "<line " not in svg, f"a seta reta para baixo voltou ao {nome}"


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


