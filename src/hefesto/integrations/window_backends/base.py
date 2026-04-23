"""Tipos base para backends de detecção de janela ativa.

Define `WindowInfo` (dataclass) e `WindowBackend` (Protocol).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class WindowInfo:
    """Informações sobre a janela ativa.

    Campos:
        wm_class:  Classe WM da janela (X11) ou app_id (Wayland).
        pid:       PID do processo dono da janela (0 se indisponível).
        app_id:    Identificador de aplicação Wayland (vazio em X11).
        title:     Título da janela.
        exe_basename: Basename do executável via /proc/PID/exe (X11).
    """

    wm_class: str = "unknown"
    pid: int = 0
    app_id: str = ""
    title: str = ""
    exe_basename: str = ""

    def as_dict(self) -> dict[str, object]:
        """Converte para dicionário compatível com a API legada de `xlib_window`."""
        return {
            "wm_class": self.wm_class,
            "wm_name": self.title,
            "pid": self.pid,
            "exe_basename": self.exe_basename,
        }


@runtime_checkable
class WindowBackend(Protocol):
    """Protocol para backends de detecção de janela ativa."""

    def get_active_window_info(self) -> WindowInfo | None:
        """Retorna informações sobre a janela ativa, ou None se indisponível."""
        ...


__all__ = ["WindowBackend", "WindowInfo"]
