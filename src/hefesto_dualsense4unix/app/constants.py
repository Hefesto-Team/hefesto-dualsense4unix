"""Paths e constantes da app GTK."""
from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent
GUI_DIR = PACKAGE_DIR / "gui"
# `MAIN_GLADE = GUI_DIR / "main.glade"` MORREU em 06/09/2026 (`GTK-3`), com o


def _resolve_icon_path() -> Path:
    """Logo do header. Tenta package/gui/assets primeiro (cenário .deb/flatpak/"""
    raiz = Path(__file__).resolve().parents[3]
    candidates = [
        GUI_DIR / "assets" / "logo.png",
        raiz / "assets" / "appimage" / "Hefesto-Dualsense4Unix.png",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


ICON_PATH = _resolve_icon_path()

ROOT_DIR = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT_DIR / "src" / "hefesto_dualsense4unix"

LIVE_POLL_INTERVAL_MS = 100
STATE_POLL_INTERVAL_MS = 500

RECONNECT_POLL_INTERVAL_S = 2
RECONNECT_FAIL_THRESHOLD = 3
