"""Paths e constantes da app GTK."""
from __future__ import annotations

from pathlib import Path

# `MAIN_GLADE = GUI_DIR / "main.glade"` MORREU em 06/09/2026 (`GTK-3`), com o


ROOT_DIR = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT_DIR / "src" / "hefesto_dualsense4unix"


