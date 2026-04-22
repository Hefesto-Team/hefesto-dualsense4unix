"""hefesto.gui.widgets — widgets GTK3 reutilizaveis do Hefesto.

Exportacoes disponiveis:
  BUTTON_GLYPH_LABELS — mapa PT-BR de nomes canonicos de botoes.
  ButtonGlyph         — glyph SVG de botao DualSense com estado pressionado.
  StickPreviewGtk     — preview circular de stick analógico 120x120.
"""
from __future__ import annotations

from hefesto.gui.widgets.button_glyph import (
    BUTTON_GLYPH_LABELS,
    ButtonGlyph,
)
from hefesto.gui.widgets.stick_preview_gtk import StickPreviewGtk

__all__ = [
    "BUTTON_GLYPH_LABELS",
    "ButtonGlyph",
    "StickPreviewGtk",
]
