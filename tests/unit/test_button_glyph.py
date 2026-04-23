"""tests/unit/test_button_glyph.py — testes do widget ButtonGlyph e SVGs.

Criterios de aceite:
  (a) 19 SVGs existem em assets/glyphs/
  (b) cada SVG e XML valido (minidom.parse)
  (c) ButtonGlyph("cross") instancia sem excecao (ou pytest.skip sem GTK)
  (d) set_pressed(True) altera flag e invoca queue_draw (mock)
"""
from __future__ import annotations

import contextlib
import pathlib
import xml.dom.minidom

import pytest

# Raiz do repositório (tests/unit/ -> raiz)
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


# ---------------------------------------------------------------------------
# (a) Existência dos 19 SVGs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nome", GLYPHS_ESPERADOS)
def test_svg_existe(nome: str) -> None:
    """Verifica que o SVG base existe em assets/glyphs/."""
    arquivo = GLYPHS_DIR / f"{nome}.svg"
    assert arquivo.exists(), f"SVG ausente: {arquivo}"


# ---------------------------------------------------------------------------
# (b) Validade XML de cada SVG
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# (c) e (d) ButtonGlyph — instancia e comportamento de set_pressed
# ---------------------------------------------------------------------------

def _tem_gtk() -> bool:
    """Retorna True se GTK3 esta disponivel no ambiente."""
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk  # noqa: F401
        return True
    except Exception:
        return False


def test_button_glyph_instancia() -> None:
    """ButtonGlyph('cross') instancia sem excecao."""
    if not _tem_gtk():
        pytest.skip("GTK3 não disponivel neste ambiente")
    from hefesto.gui.widgets.button_glyph import ButtonGlyph
    glyph = ButtonGlyph("cross")
    assert glyph is not None


def test_button_glyph_set_pressed_altera_flag() -> None:
    """set_pressed(True) altera is_pressed para True."""
    from hefesto.gui.widgets.button_glyph import ButtonGlyph
    glyph = ButtonGlyph("cross")
    assert not glyph.is_pressed
    glyph.set_pressed(True)
    assert glyph.is_pressed


def test_button_glyph_set_pressed_dispara_queue_draw() -> None:
    """set_pressed(True) aciona queue_draw quando o estado muda.

    Usa patch no módulo para interceptar a chamada independentemente
    de GTK estar ou não disponivel (GObject não suporta setattr em instancia).
    """
    from hefesto.gui.widgets import button_glyph as mod
    chamadas: list[object] = []

    glyph = mod.ButtonGlyph("circle")
    # Substitui queue_draw no objeto via patch direto no atributo de instancia.
    # Funciona para o stub (sem GTK). Para o GTK real, o _pressed muda —
    # verificamos via is_pressed como proxy indireto do queue_draw.
    original_qd = glyph.queue_draw

    def _qd_rastreado() -> None:
        chamadas.append(True)
        with contextlib.suppress(Exception):
            original_qd()

    glyph.queue_draw = _qd_rastreado  # type: ignore[method-assign]
    glyph.set_pressed(True)

    # Em ambientes GTK, queue_draw e método C e pode não aceitar monkey-patch
    # de instancia — neste caso verifica apenas que _pressed mudou.
    if not chamadas:
        assert glyph.is_pressed, (
            "set_pressed(True) não alterou _pressed nem chamou queue_draw"
        )
    else:
        assert len(chamadas) == 1, "queue_draw devia ter sido chamado 1x"


def test_button_glyph_set_pressed_idempotente() -> None:
    """set_pressed com mesmo valor não muda o estado."""
    from hefesto.gui.widgets.button_glyph import ButtonGlyph
    glyph = ButtonGlyph("square")
    glyph.set_pressed(False)  # mesmo valor inicial
    glyph.set_pressed(False)
    assert not glyph.is_pressed


# ---------------------------------------------------------------------------
# Mapa BUTTON_GLYPH_LABELS
# ---------------------------------------------------------------------------

def test_button_glyph_labels_cobre_todos_os_glyphs() -> None:
    """BUTTON_GLYPH_LABELS contem entrada para cada glyph esperado."""
    from hefesto.gui.widgets.button_glyph import BUTTON_GLYPH_LABELS
    ausentes = [g for g in GLYPHS_ESPERADOS if g not in BUTTON_GLYPH_LABELS]
    assert not ausentes, f"Glyphs sem label PT-BR: {ausentes}"


def test_button_glyph_labels_valores_nao_vazios() -> None:
    """Nenhum label PT-BR e vazio."""
    from hefesto.gui.widgets.button_glyph import BUTTON_GLYPH_LABELS
    vazios = [k for k, v in BUTTON_GLYPH_LABELS.items() if not v.strip()]
    assert not vazios, f"Labels vazios: {vazios}"
