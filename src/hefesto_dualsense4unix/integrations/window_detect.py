"""Detecção de janela ativa com seleção automática de backend.

`detect_window_backend()` escolhe o backend adequado conforme as variáveis
de ambiente do compositor:

  WAYLAND_DISPLAY + DISPLAY  → XlibBackend     (XWayland, preferido)
  WAYLAND_DISPLAY sem DISPLAY → _WaylandCascadeBackend (portal XDG → wlrctl → None)
  DISPLAY sem WAYLAND_DISPLAY → XlibBackend
  Nenhum                      → NullBackend    (loga autoswitch_compositor_unsupported)

Função `get_active_window_info()` mantém compatibilidade com a API legada de
`xlib_window.py`: retorna `dict[str, Any]` com chaves `wm_class`, `wm_name`,
`pid`, `exe_basename`.

BUG-COSMIC-WLR-BACKEND-REGRESSION-01 (v3.1.0): re-introduz o cascade
portal → wlrctl perdido no rebrand Hefesto → Hefesto - Dualsense4Unix.
O portal XDG é tentado primeiro (canônico, GNOME 46+); se falhar acima
do threshold do `WaylandPortalBackend._UNSUPPORTED_THRESHOLD`, o cascade
passa a tentar `WlrctlBackend` (funciona em COSMIC, Sway, Hyprland,
niri, river via `wlr-foreign-toplevel-management-unstable-v1`). Se nem
`wlrctl` responde, degrada para None e o caller usa o `fallback.json`.
"""
from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from hefesto_dualsense4unix.integrations.window_backends.base import WindowBackend, WindowInfo
from hefesto_dualsense4unix.integrations.window_backends.null import NullBackend
from hefesto_dualsense4unix.integrations.window_backends.xlib import XlibBackend
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

# AUTOSWITCH-FLOOD-FIX-01: once-guard p/ não floodar o journal com
# 'autoswitch_compositor_unsupported' quando não há display (ver detect_window_backend).
_unsupported_warned: bool = False


class _WaylandCascadeBackend:
    """Cascade: portal XDG → wlrctl → None.

    Mantém o portal como backend primário porque em compositors onde ele
    funciona (GNOME 46+, COSMIC com `xdg-desktop-portal-cosmic` atualizado),
    o caminho é oficial, mais rápido e não depende de binário externo. Se o
    portal falha repetidamente (o próprio `WaylandPortalBackend` detecta e
    retorna None permanentemente após `_UNSUPPORTED_THRESHOLD` falhas),
    caímos para `wlrctl` que cobre o bloco wlroots-like.

    Esta classe vive em `window_detect.py` em vez de `window_backends/`
    porque é puramente composicional (escolhe entre backends existentes).
    """

    def __init__(self) -> None:
        from hefesto_dualsense4unix.integrations.window_backends.wayland_portal import (
            WaylandPortalBackend,
        )
        from hefesto_dualsense4unix.integrations.window_backends.wlr_toplevel import (
            WlrctlBackend,
        )

        self._portal = WaylandPortalBackend()
        self._wlrctl = WlrctlBackend()
        self._fallback_announced: bool = False

    def get_active_window_info(self) -> WindowInfo | None:
        info = self._portal.get_active_window_info()
        if info is not None:
            return info

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
        logger.debug("window_backend_selected", backend="xlib", xwayland=has_wayland)
        return XlibBackend()

    if has_wayland:
        logger.debug("window_backend_selected", backend="wayland_cascade")
        return _WaylandCascadeBackend()

    # AUTOSWITCH-FLOOD-FIX-01: once-guard. Sem display, esta função era chamada
    # a cada tick do AutoSwitcher (0,5s) via get_active_window_info legado e
    # logava WARNING toda vez — 1800+ linhas em 10min no journal. Agora o
    # subsystem usa build_window_reader() (backend instanciado 1x), mas o
    # guard protege qualquer caller repetido (CLI/doctor) de floodar: avisa
    # uma vez, depois rebaixa para debug.
    global _unsupported_warned
    if not _unsupported_warned:
        logger.warning("autoswitch_compositor_unsupported")
        _unsupported_warned = True
    else:
        logger.debug("autoswitch_compositor_unsupported")
    return NullBackend()


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


def build_window_reader() -> Callable[[], dict[str, Any]]:
    """Cria um leitor de janela com o backend instanciado UMA vez.

    AUTOSWITCH-FLOOD-FIX-01. Diferente de `get_active_window_info()` (stateless,
    recria o backend a cada chamada — adequado p/ CLI/doctor pontual), este
    mantém o backend vivo para o poll do AutoSwitcher (2Hz). Ganhos:
    - não loga `autoswitch_compositor_unsupported` por tick (flood no journal);
    - preserva o estado anti-flood/anti-D-Bus dos backends
      (`_consecutive_failures`, `_unsupported_warned`, cache do `which`,
      `_fallback_announced`) em vez de resetá-lo a cada 0,5s;
    - evita gastar o timeout de 2s do portal jeepney a cada tick numa sessão
      Wayland real onde o portal não tem GetActiveWindow.

    Retorna um callable dict→compatível com a API legada (wm_class/wm_name/
    pid/exe_basename), devolvendo `_UNKNOWN_WINDOW` quando o backend não acha
    janela. O backend é fixado no momento da chamada — chame após o ambiente
    gráfico estar disponível (o subsystem importa o env antes).
    """
    backend = detect_window_backend()

    def _read() -> dict[str, Any]:
        info: WindowInfo | None = backend.get_active_window_info()
        if info is None:
            return dict(_UNKNOWN_WINDOW)
        return info.as_dict()

    return _read


__all__ = [
    "build_window_reader",
    "detect_window_backend",
    "get_active_window_info",
]
