"""hefesto_dualsense4unix.app.widgets — widgets GTK3 leves da camada de app.

Pacote propositalmente enxuto: importa só o ``SegmentedSelector`` (import-seguro
sem display, via fallback em ``segmented_selector``). NÃO puxa os widgets de
``gui.widgets`` (ButtonGlyph/StickPreviewGtk), que dependem de ``Gtk.DrawingArea``
e exigem um stub de GTK mais completo nos testes.
"""
from __future__ import annotations

from hefesto_dualsense4unix.app.widgets.segmented_selector import SegmentedSelector

__all__ = ["SegmentedSelector"]
