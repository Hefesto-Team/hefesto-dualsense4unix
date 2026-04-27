"""Módulo de compatibilidade — re-exporta de `window_detect`.

Este arquivo é um shim de transição. Código legado que importa de
`hefesto_dualsense4unix.integrations.xlib_window` continua funcionando sem alteração.

Novos módulos devem importar de `hefesto_dualsense4unix.integrations.window_detect`.
"""
from __future__ import annotations

# XlibClient e UNKNOWN_WINDOW: mantidos para testes que os referenciam
# diretamente (test_xlib_window.py). Importar do backend xlib.
import contextlib
import os
from dataclasses import dataclass
from typing import Any

# Re-exportações para compatibilidade com imports legados.
from hefesto_dualsense4unix.integrations.window_detect import get_active_window_info
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

UNKNOWN_WINDOW: dict[str, Any] = {
    "wm_class": "unknown",
    "wm_name": "",
    "pid": 0,
    "exe_basename": "",
}


@dataclass
class XlibClient:
    """Compatibilidade legada. Use `XlibBackend` (window_backends/xlib.py) em código novo."""

    display: Any = None

    def __post_init__(self) -> None:
        if self.display is not None:
            return
        if not os.environ.get("DISPLAY"):
            logger.debug("x11_no_display")
            return
        try:
            from Xlib import display as xdisplay

            self.display = xdisplay.Display()
        except Exception as exc:
            logger.warning("x11_connect_failed", err=str(exc))
            self.display = None

    def is_connected(self) -> bool:
        return self.display is not None

    def active_window_info(self) -> dict[str, Any]:
        if self.display is None:
            return dict(UNKNOWN_WINDOW)
        try:
            from Xlib import X

            root = self.display.screen().root
            net_active_window = self.display.intern_atom("_NET_ACTIVE_WINDOW")
            net_wm_pid = self.display.intern_atom("_NET_WM_PID")

            prop = root.get_full_property(net_active_window, X.AnyPropertyType)
            if prop is None or not prop.value:
                return dict(UNKNOWN_WINDOW)
            win_id = int(prop.value[0])
            if win_id == 0:
                return dict(UNKNOWN_WINDOW)

            win = self.display.create_resource_object("window", win_id)

            wm_class_tuple: tuple[str, str] | None = None
            try:
                wm_class_tuple = win.get_wm_class()
            except Exception:
                wm_class_tuple = None
            wm_class = wm_class_tuple[1] if wm_class_tuple else ""

            wm_name = ""
            with contextlib.suppress(Exception):
                wm_name = win.get_wm_name() or ""

            pid = 0
            with contextlib.suppress(Exception):
                pid_prop = win.get_full_property(net_wm_pid, X.AnyPropertyType)
                if pid_prop is not None and pid_prop.value:
                    pid = int(pid_prop.value[0])

            exe_basename = _exe_basename_from_pid(pid) if pid else ""

            return {
                "wm_class": wm_class or "unknown",
                "wm_name": wm_name,
                "pid": pid,
                "exe_basename": exe_basename,
            }
        except Exception as exc:
            logger.warning("x11_query_failed", err=str(exc))
            return dict(UNKNOWN_WINDOW)


def _exe_basename_from_pid(pid: int) -> str:
    try:
        target = os.readlink(f"/proc/{pid}/exe")
        return os.path.basename(target)
    except (OSError, FileNotFoundError):
        return ""


__all__ = ["UNKNOWN_WINDOW", "XlibClient", "get_active_window_info"]
