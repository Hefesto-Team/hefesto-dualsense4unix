"""Backend nulo para ambientes sem suporte de detecção de janela ativa.

Retorna sempre `None`. Usado quando nem X11 nem Wayland portal estão
disponíveis. `AutoSwitcher` continua funcionando em modo silencioso com
`fallback.json`.
"""
from __future__ import annotations

from hefesto_dualsense4unix.integrations.window_backends.base import WindowInfo


class NullBackend:
    """Backend de janela ativa que sempre retorna None (modo silencioso)."""

    def get_active_window_info(self) -> WindowInfo | None:
        """Retorna sempre None — ambiente sem suporte de detecção."""
        return None


__all__ = ["NullBackend"]
