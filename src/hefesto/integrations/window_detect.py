"""Detecção de janela ativa com seleção automática de backend.

`detect_window_backend()` escolhe o backend adequado conforme as variáveis
de ambiente do compositor:

  WAYLAND_DISPLAY + DISPLAY  → XlibBackend   (XWayland, preferido)
  WAYLAND_DISPLAY sem DISPLAY → CascadeBackend (portal XDG → wlrctl → null)
  DISPLAY sem WAYLAND_DISPLAY → XlibBackend
  Nenhum                      → NullBackend  (loga autoswitch_compositor_unsupported)

Função `get_active_window_info()` mantém compatibilidade com a API legada de
`xlib_window.py`: retorna `dict[str, Any]` com chaves `wm_class`, `wm_name`,
`pid`, `exe_basename`.

BUG-COSMIC-WLR-BACKEND-01 (v2.4.1): Wayland puro ganhou cascade de
backends. O portal XDG é tentado primeiro (canônico, GNOME 46+); se
falhar N vezes (ver `WaylandPortalBackend._UNSUPPORTED_THRESHOLD`),
o cascade passa a tentar `WlrctlBackend` (funciona em COSMIC alpha,
Sway, Hyprland, niri, river). Se nem `wlrctl` responde, degrada para
NullBackend.
"""
from __future__ import annotations

import os
from typing import Any

from hefesto.integrations.window_backends.base import WindowBackend, WindowInfo
from hefesto.integrations.window_backends.null import NullBackend
from hefesto.integrations.window_backends.xlib import XlibBackend
from hefesto.utils.logging_config import get_logger

logger = get_logger(__name__)


class _WaylandCascadeBackend:
    """Cascade: portal XDG → wlrctl → None.

    Mantém o portal como backend primário porque em compositors onde ele
    funciona (GNOME 46+, futuro COSMIC estável), o caminho é oficial,
    mais rápido e não depende de binário externo. Se o portal falha
    repetidamente (o próprio `WaylandPortalBackend` detecta e retorna
    None permanentemente após `_UNSUPPORTED_THRESHOLD` falhas), caímos
    para `wlrctl` que cobre o bloco wlroots-like.

    Esta classe vive em `window_detect.py` em vez de `window_backends/`
    porque é puramente composicional (escolhe entre backends existentes).
    """

    def __init__(self) -> None:
        from hefesto.integrations.window_backends.wayland_portal import (
            WaylandPortalBackend,
        )
        from hefesto.integrations.window_backends.wlr_toplevel import (
            WlrctlBackend,
        )

        self._portal = WaylandPortalBackend()
        self._wlrctl = WlrctlBackend()
        self._fallback_announced: bool = False

    def get_active_window_info(self) -> WindowInfo | None:
        info = self._portal.get_active_window_info()
        if info is not None:
            return info

        # Portal deu None — pode ser falha transiente, mas se o próprio
        # `WaylandPortalBackend` já decidiu que o portal não é suportado,
        # ele retorna None direto. Tentamos wlrctl em seguida.
        info = self._wlrctl.get_active_window_info()
        if info is not None:
            if not self._fallback_announced:
                logger.info(
                    "wayland_backend_fallback_wlrctl",
                    hint=(
                        "portal XDG não respondeu; wlrctl ativo "
                        "(wlr-foreign-toplevel-management)."
                    ),
                )
                self._fallback_announced = True
            return info

        return None


def detect_window_backend() -> WindowBackend:
    """Detecta e retorna o backend mais adequado para o ambiente atual.

    Lógica de seleção:
    - XWayland (ambas variáveis presentes): XlibBackend.
    - Wayland puro (apenas WAYLAND_DISPLAY): cascade portal → wlrctl → null.
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
        logger.debug("window_backend_selected", backend="wayland_cascade")
        return _WaylandCascadeBackend()

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
    `hefesto.integrations.xlib_window.get_active_window_info`.
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
