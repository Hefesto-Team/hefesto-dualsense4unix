"""Backend nulo para ambientes sem suporte de detecção de janela ativa."""
from __future__ import annotations

from hefesto_dualsense4unix.integrations.window_backends.base import WindowInfo

MOTIVO_SEM_BACKEND = "sem_backend"


class NullBackend:
    """Backend de janela ativa que sempre retorna None (modo silencioso)."""

    backend_name: str = "null"

    last_failure_reason: str | None = MOTIVO_SEM_BACKEND

    def get_active_window_info(self) -> WindowInfo | None:
        """Retorna sempre None — ambiente sem suporte de detecção."""
        return None


__all__ = ["MOTIVO_SEM_BACKEND", "NullBackend"]
