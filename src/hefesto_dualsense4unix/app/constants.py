"""Paths e constantes da app GTK."""
from __future__ import annotations

from pathlib import Path

# Layout do source repo: parents[3] = root (~/Desenvolvimento/hefesto-dualsense4unix).
# Layout instalado (deb/flatpak/AppImage/wheel): parents[3] aponta para fora do
# pacote (site-packages/), e src/ não existe. Os paths canônicos pegam recursos
# relativos ao próprio módulo — cobertos pelo pyproject.toml include.
PACKAGE_DIR = Path(__file__).resolve().parent.parent
GUI_DIR = PACKAGE_DIR / "gui"
MAIN_GLADE = GUI_DIR / "main.glade"


def _resolve_icon_path() -> Path:
    """Logo do header. Tenta package/gui/assets primeiro (cenário .deb/flatpak/
    wheel), depois fallback ao source repo (assets/appimage/...png) durante
    desenvolvimento. Retorna o primeiro caminho que existe ou o do package
    como sentinela (caller faz set_from_pixbuf que dá warning se ausente).
    """
    candidates = [
        GUI_DIR / "assets" / "logo.png",
        Path(__file__).resolve().parents[3] / "assets" / "appimage"
            / "Hefesto-Dualsense4Unix.png",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


ICON_PATH = _resolve_icon_path()

# Compat com código que pode importar ROOT_DIR/SRC_DIR (ex.: testes do source
# repo). Em instalação real esses paths podem não existir — sempre verifique
# .exists() antes de usar.
ROOT_DIR = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT_DIR / "src" / "hefesto_dualsense4unix"

# Polling da GUI contra o daemon (IPC).
LIVE_POLL_INTERVAL_MS = 100  # 10 Hz
STATE_POLL_INTERVAL_MS = 500  # 2 Hz, info pouco mutável (perfil ativo)

# Máquina de estado de reconnect do header (UX-RECONNECT-01).
RECONNECT_POLL_INTERVAL_S = 2   # 0.5 Hz — custo mínimo, latência aceitável
RECONNECT_FAIL_THRESHOLD = 3    # 3 falhas x 2s = 6s antes de declarar offline
