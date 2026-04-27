"""Detecção de janela ativa com seleção automática de backend.

`detect_window_backend()` escolhe o backend adequado conforme as variáveis
de ambiente do compositor:

  WAYLAND_DISPLAY + DISPLAY  → XlibBackend   (XWayland, preferido)
  WAYLAND_DISPLAY sem DISPLAY → WaylandPortalBackend
  DISPLAY sem WAYLAND_DISPLAY → XlibBackend
  Nenhum                      → NullBackend  (loga autoswitch_compositor_unsupported)

Função `get_active_window_info()` mantém compatibilidade com a API legada de
`xlib_window.py`: retorna `dict[str, Any]` com chaves `wm_class`, `wm_name`,
`pid`, `exe_basename`.
"""
from __future__ import annotations

import os
from typing import Any

from hefesto_dualsense4unix.integrations.window_backends.base import WindowBackend, WindowInfo
from hefesto_dualsense4unix.integrations.window_backends.null import NullBackend
from hefesto_dualsense4unix.integrations.window_backends.xlib import XlibBackend
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


def detect_window_backend() -> WindowBackend:
    """Detecta e retorna o backend mais adequado para o ambiente atual.

    Lógica de seleção:
    - XWayland (ambas variáveis presentes): XlibBackend.
    - Wayland puro (apenas WAYLAND_DISPLAY): WaylandPortalBackend.
    - X11 puro (apenas DISPLAY): XlibBackend.
    - Sem display: NullBackend (com log de advertência).
    """
    has_wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    has_x11 = bool(os.environ.get("DISPLAY"))

    if has_x11:
        # XWayland ou X11 puro — XlibBackend funciona em ambos.
        logger.debug("window_backend_selected", backend="xlib", xwayland=has_wayland)
        return XlibBackend()

    if has_wayland:
        # Wayland puro — tenta portal XDG D-Bus.
        from hefesto_dualsense4unix.integrations.window_backends.wayland_portal import (
            WaylandPortalBackend,
        )

        logger.debug("window_backend_selected", backend="wayland_portal")
        return WaylandPortalBackend()

    # Nenhum display disponível.
    logger.warning("autoswitch_compositor_unsupported")
    return NullBackend()


# ---------------------------------------------------------------------------
# API de compatibilidade com xlib_window.py (legado)
# ---------------------------------------------------------------------------

_UNKNOWN_WINDOW: dict[str, Any] = {
    "wm_class": "unknown",
    "wm_name": "",
    "pid": 0,
    "exe_basename": "",
}


def get_active_window_info() -> dict[str, Any]:
    """Retorna dict com informações da janela ativa.

    Mantém compatibilidade com a assinatura original de
    `hefesto_dualsense4unix.integrations.xlib_window.get_active_window_info`.
    """
    backend = detect_window_backend()
    info: WindowInfo | None = backend.get_active_window_info()
    if info is None:
        return dict(_UNKNOWN_WINDOW)
    return info.as_dict()


__all__ = [
    "detect_window_backend",
    "get_active_window_info",
]
