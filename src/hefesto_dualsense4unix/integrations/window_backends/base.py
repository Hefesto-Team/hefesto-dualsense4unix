"""Tipos base para backends de detecção de janela ativa."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class WindowInfo:
    """Informações sobre a janela ativa."""

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
