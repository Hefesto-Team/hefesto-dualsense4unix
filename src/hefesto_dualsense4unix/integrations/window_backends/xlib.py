"""Backend X11 via `python-xlib`.

Encapsula a lógica de `xlib_window.py` na classe `XlibBackend`.
Retorna `WindowInfo` com `wm_class`, `pid`, `title` e `exe_basename`.
"""
from __future__ import annotations

import contextlib
import os
from typing import Any

from hefesto_dualsense4unix.integrations.window_backends.base import WindowInfo
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


def _exe_basename_from_pid(pid: int) -> str:
    """Resolve basename do executável via /proc/<pid>/exe."""
    try:
        target = os.readlink(f"/proc/{pid}/exe")
        return os.path.basename(target)
    except (OSError, FileNotFoundError):
        return ""


class XlibBackend:
    """Backend de detecção de janela ativa usando X11 + python-xlib.

    Lazy-conecta ao servidor X na primeira chamada a `get_active_window_info`.
    """

    def __init__(self) -> None:
        self._display: Any = None
        self._connected: bool = False
        self._init_attempted: bool = False

    def _ensure_connected(self) -> bool:
        """Tenta conectar ao display X11. Retorna True se conectado."""
        if self._init_attempted:
            return self._connected
        self._init_attempted = True

        if not os.environ.get("DISPLAY"):
            logger.debug("x11_no_display")
            self._connected = False
            return False

        try:
            from Xlib import display as xdisplay

            self._display = xdisplay.Display()
            self._connected = True
            logger.debug("x11_connected")
        except Exception as exc:
            logger.warning("x11_connect_failed", err=str(exc))
            self._connected = False

        return self._connected

    def get_active_window_info(self) -> WindowInfo | None:
        """Retorna WindowInfo da janela ativa, ou None se indisponível."""
        if not self._ensure_connected():
            return None

        try:
            from Xlib import X

            root = self._display.screen().root
            net_active_window = self._display.intern_atom("_NET_ACTIVE_WINDOW")
            net_wm_pid = self._display.intern_atom("_NET_WM_PID")

            prop = root.get_full_property(net_active_window, X.AnyPropertyType)
            if prop is None or not prop.value:
                return None
            win_id = int(prop.value[0])
            if win_id == 0:
                return None

            win = self._display.create_resource_object("window", win_id)

            wm_class_tuple: tuple[str, str] | None = None
            with contextlib.suppress(Exception):
                wm_class_tuple = win.get_wm_class()
            wm_class = wm_class_tuple[1] if wm_class_tuple else ""

            title = ""
            with contextlib.suppress(Exception):
                title = win.get_wm_name() or ""

            pid = 0
            with contextlib.suppress(Exception):
                pid_prop = win.get_full_property(net_wm_pid, X.AnyPropertyType)
                if pid_prop is not None and pid_prop.value:
                    pid = int(pid_prop.value[0])

            exe_basename = _exe_basename_from_pid(pid) if pid else ""

            return WindowInfo(
                wm_class=wm_class or "unknown",
                pid=pid,
                app_id="",
                title=title,
                exe_basename=exe_basename,
            )
        except Exception as exc:
            logger.warning("x11_query_failed", err=str(exc))
            return None


__all__ = ["XlibBackend"]
