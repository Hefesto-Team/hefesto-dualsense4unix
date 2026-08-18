"""Backend nulo para ambientes sem suporte de detecção de janela ativa.

Retorna sempre `None`. Usado quando nem X11 nem Wayland portal estão
disponíveis. `AutoSwitcher` continua funcionando em modo silencioso com
`fallback.json`.
"""
from __future__ import annotations

from hefesto_dualsense4unix.integrations.window_backends.base import WindowInfo

#: JANELA-CEGA-01: motivo único deste backend — não há detecção nenhuma para
#: falhar. Distingue "nem tento" de "tentei e o X não respondeu".
MOTIVO_SEM_BACKEND = "sem_backend"


class NullBackend:
    """Backend de janela ativa que sempre retorna None (modo silencioso)."""

    # FEAT-WINDOW-DETECT-DIAG-01: nome estável para diagnóstico (store/doctor).
    backend_name: str = "null"

    # JANELA-CEGA-01: motivo constante — este backend é cego por construção.
    last_failure_reason: str | None = MOTIVO_SEM_BACKEND

    def get_active_window_info(self) -> WindowInfo | None:
        """Retorna sempre None — ambiente sem suporte de detecção."""
        return None


__all__ = ["MOTIVO_SEM_BACKEND", "NullBackend"]
