"""Backend Wayland via portal XDG D-Bus `org.freedesktop.portal.Window`."""
from __future__ import annotations

import contextlib
import os
from typing import Any

from hefesto_dualsense4unix.integrations.window_backends.base import WindowInfo
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

_PORTAL_BUS = "org.freedesktop.portal.Desktop"
_PORTAL_PATH = "/org/freedesktop/portal/desktop"
_PORTAL_IFACE = "org.freedesktop.portal.Window"

_PORTAL_TIMEOUT_SECONDS = 2.0


def _try_jeepney(handle_token: str) -> WindowInfo | None:
    """Tenta obter janela ativa via jeepney (síncrono, puro Python)."""
    try:
        from jeepney import DBusAddress, new_method_call
        from jeepney.io.blocking import open_dbus_connection
    except ImportError:
        return None

    conn = None
    try:
        conn = open_dbus_connection(bus="SESSION")
        addr = DBusAddress(_PORTAL_PATH, bus_name=_PORTAL_BUS, interface=_PORTAL_IFACE)
        msg = new_method_call(addr, "GetActiveWindow", "sa{sv}", (handle_token, {}))
        reply = conn.send_and_get_reply(msg, timeout=_PORTAL_TIMEOUT_SECONDS)

        result: dict[str, Any] = {}
        if len(reply.body) >= 2 and isinstance(reply.body[1], dict):
            result = reply.body[1]

        return _parse_portal_result(result)
    except Exception as exc:
        logger.debug("wayland_portal_jeepney_failed", err=str(exc))
        return None
    finally:
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()


def _parse_portal_result(result: dict[str, Any]) -> WindowInfo | None:
    """Converte dicionário de resultado do portal para WindowInfo."""
    if not result:
        return None

    app_id = str(result.get("app-id") or result.get("app_id") or "")
    title = str(result.get("title") or "")
    pid_raw = result.get("pid")
    pid = int(pid_raw) if pid_raw is not None else 0

    wm_class = app_id or "unknown"

    return WindowInfo(
        wm_class=wm_class,
        pid=pid,
        app_id=app_id,
        title=title,
        exe_basename="",
    )


class WaylandPortalBackend:
    """Backend de detecção de janela ativa via portal XDG D-Bus."""

    _UNSUPPORTED_THRESHOLD: int = 3

    backend_name: str = "portal"

    def __init__(self) -> None:
        self._handle_counter: int = 0
        self._consecutive_failures: int = 0
        self._unsupported_warned: bool = False

    @property
    def unsupported(self) -> bool:
        """True quando o portal desistiu (falhas seguidas >= threshold)."""
        return self._consecutive_failures >= self._UNSUPPORTED_THRESHOLD

    def _next_handle(self) -> str:
        self._handle_counter += 1
        pid = os.getpid()
        return f"hefesto_{pid}_{self._handle_counter}"

    def _compositor_hint(self) -> str:
        """Retorna uma string de pista sobre o compositor para o log."""
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
        session = os.environ.get("XDG_SESSION_DESKTOP", "")
        return desktop or session or "unknown"

    def get_active_window_info(self) -> WindowInfo | None:
        """Retorna WindowInfo via portal D-Bus, ou None se indisponível."""
        if self._consecutive_failures >= self._UNSUPPORTED_THRESHOLD:
            return None

        handle = self._next_handle()
        result = _try_jeepney(handle)
        if result is not None:
            if self._consecutive_failures > 0:
                logger.info(
                    "wayland_portal_recovered",
                    after_failures=self._consecutive_failures,
                )
            self._consecutive_failures = 0
            self._unsupported_warned = False
            logger.debug("wayland_portal_ok", via="jeepney", app_id=result.app_id)
            return result

        self._consecutive_failures += 1
        if (
            self._consecutive_failures >= self._UNSUPPORTED_THRESHOLD
            and not self._unsupported_warned
        ):
            self._unsupported_warned = True
            logger.warning(
                "wayland_portal_unsupported",
                compositor=self._compositor_hint(),
                failures=self._consecutive_failures,
                hint=(
                    "Compositor Wayland não implementa "
                    "'org.freedesktop.portal.Window::GetActiveWindow' "
                    "(COSMIC 1.0+ com xdg-desktop-portal-cosmic atualizado "
                    "ou GNOME 46+ necessário). Cascade tentara wlrctl em "
                    "seguida; se ausente, autoswitch fica inativo."
                ),
            )
        else:
            logger.debug("wayland_portal_unavailable")
        return None


__all__ = ["WaylandPortalBackend"]
