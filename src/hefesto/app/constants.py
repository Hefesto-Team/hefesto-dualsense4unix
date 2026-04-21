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

# Máquina de estado de reconnect do header (UX-RECONNECT-01).
RECONNECT_POLL_INTERVAL_S = 2   # 0.5 Hz — custo mínimo, latência aceitável
RECONNECT_FAIL_THRESHOLD = 3    # 3 falhas x 2s = 6s antes de declarar offline
