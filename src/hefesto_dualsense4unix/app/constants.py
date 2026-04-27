"""Paths e constantes da app GTK."""
from __future__ import annotations

from pathlib import Path

# Layout do source repo: parents[3] = root (~/Desenvolvimento/hefesto-dualsense4unix).
# Layout instalado (deb/flatpak/AppImage/wheel): parents[3] aponta para fora do
# pacote (site-packages/), e src/ não existe. GUI_DIR canônico pega o glade
# relativo ao próprio módulo (hefesto_dualsense4unix/gui/) — caminho coberto
# pelo pyproject.toml [tool.hatch.build.targets.wheel] include.
PACKAGE_DIR = Path(__file__).resolve().parent.parent
GUI_DIR = PACKAGE_DIR / "gui"
MAIN_GLADE = GUI_DIR / "main.glade"

# Mantidos por compatibilidade. ROOT_DIR/SRC_DIR/ICON_PATH resolvem só no
# source repo; caller deve checar .exists() antes de usar (ex.: GUI tenta
# ICON_PATH como header, mas faz fallback se não existir).
ROOT_DIR = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT_DIR / "src" / "hefesto_dualsense4unix"
ICON_PATH = ROOT_DIR / "assets" / "appimage" / "Hefesto-Dualsense4Unix.png"

# Polling da GUI contra o daemon (IPC).
LIVE_POLL_INTERVAL_MS = 100  # 10 Hz
STATE_POLL_INTERVAL_MS = 500  # 2 Hz, info pouco mutável (perfil ativo)

# Máquina de estado de reconnect do header (UX-RECONNECT-01).
RECONNECT_POLL_INTERVAL_S = 2   # 0.5 Hz — custo mínimo, latência aceitável
RECONNECT_FAIL_THRESHOLD = 3    # 3 falhas x 2s = 6s antes de declarar offline
