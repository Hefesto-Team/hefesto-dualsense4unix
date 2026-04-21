"""Paths e constantes da app GTK."""
from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT_DIR / "src" / "hefesto"
GUI_DIR = SRC_DIR / "gui"
MAIN_GLADE = GUI_DIR / "main.glade"
ICON_PATH = ROOT_DIR / "assets" / "appimage" / "Hefesto.png"

# Polling da GUI contra o daemon (IPC).
LIVE_POLL_INTERVAL_MS = 50   # 20 Hz
STATE_POLL_INTERVAL_MS = 500  # 2 Hz, info pouco mutável (perfil ativo)
