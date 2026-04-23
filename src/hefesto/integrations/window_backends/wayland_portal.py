"""Backend Wayland via portal XDG D-Bus `org.freedesktop.portal.Window`.

Tenta usar (em ordem de preferência):
  1. `jeepney` — puro Python, sem dep nativa.
  2. `dbus-fast` — assíncrono, mais completo.

Se nenhuma biblioteca estiver disponível, `get_active_window_info()` retorna
`None` imediatamente (degradação silenciosa).

A interface `GetActiveWindow` foi introduzida no portal v1 (COSMIC 1.0+,
GNOME 46+). Compositors mais antigos podem não expor o método.
"""
from __future__ import annotations

import os
from typing import Any

from hefesto.integrations.window_backends.base import WindowInfo
from hefesto.utils.logging_config import get_logger

logger = get_logger(__name__)

# Constantes do portal D-Bus.
_PORTAL_BUS = "org.freedesktop.portal.Desktop"
_PORTAL_PATH = "/org/freedesktop/portal/desktop"
_PORTAL_IFACE = "org.freedesktop.portal.Window"


def _try_jeepney(handle_token: str) -> WindowInfo | None:
    """Tenta obter janela ativa via jeepney (síncrono, puro Python)."""
    try:
        from jeepney import DBusAddress, new_method_call  # type: ignore[import]
        from jeepney.io.blocking import open_dbus_connection  # type: ignore[import]
    except ImportError:
        return None

    try:
        conn = open_dbus_connection(bus="SESSION")
        addr = DBusAddress(_PORTAL_PATH, bus_name=_PORTAL_BUS, interface=_PORTAL_IFACE)
        msg = new_method_call(addr, "GetActiveWindow", "sa{sv}", (handle_token, {}))
        reply = conn.send_and_get_reply(msg)
        conn.close()

        # reply.body[0] é o handle; info real chega via sinal, mas alguns
        # compositors retornam diretamente no reply.body[1].
        result: dict[str, Any] = {}
        if len(reply.body) >= 2 and isinstance(reply.body[1], dict):
            result = reply.body[1]

        return _parse_portal_result(result)
    except Exception as exc:
        logger.debug("wayland_portal_jeepney_failed", err=str(exc))
        return None


def _try_dbus_fast(handle_token: str) -> WindowInfo | None:
    """Tenta obter janela ativa via dbus-fast (síncrono wrapper)."""
    try:
        from dbus_fast.aio.message_bus import MessageBus  # type: ignore[import]
    except ImportError:
        return None

    # dbus-fast é assíncrono; em contexto síncrono usamos thread-isolado.
    import asyncio
    import concurrent.futures

    def _run() -> WindowInfo | None:
        async def _async() -> WindowInfo | None:
            try:
                bus = await MessageBus().connect()
                introspection = await bus.introspect(_PORTAL_BUS, _PORTAL_PATH)
                proxy = bus.get_proxy_object(_PORTAL_BUS, _PORTAL_PATH, introspection)
                iface = proxy.get_interface(_PORTAL_IFACE)
                result = await iface.call_get_active_window(handle_token, {})
                bus.disconnect()
                return _parse_portal_result(result if isinstance(result, dict) else {})
            except Exception as exc:
                logger.debug("wayland_portal_dbus_fast_failed", err=str(exc))
                return None

        return asyncio.run(_async())

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_run)
        try:
            return future.result(timeout=2.0)
        except Exception as exc:
            logger.debug("wayland_portal_dbus_fast_timeout", err=str(exc))
            return None


def _parse_portal_result(result: dict[str, Any]) -> WindowInfo | None:
    """Converte dicionário de resultado do portal para WindowInfo."""
    if not result:
        return None

    app_id = str(result.get("app-id") or result.get("app_id") or "")
    title = str(result.get("title") or "")
    pid_raw = result.get("pid")
    pid = int(pid_raw) if pid_raw is not None else 0

    # wm_class usa app_id para compatibilidade com ProfileManager.select_for_window
    wm_class = app_id or "unknown"

    return WindowInfo(
        wm_class=wm_class,
        pid=pid,
        app_id=app_id,
        title=title,
        exe_basename="",
    )


class WaylandPortalBackend:
    """Backend de detecção de janela ativa via portal XDG D-Bus.

    Usado em ambientes Wayland puro (sem XWayland). Requer COSMIC 1.0+ ou
    GNOME 46+ para suporte à interface `org.freedesktop.portal.Window`.

    Se `jeepney` ou `dbus-fast` não estiver disponível no ambiente, ou se o
    portal não responder, `get_active_window_info()` retorna `None`.
    """

    def __init__(self) -> None:
        self._handle_counter: int = 0

    def _next_handle(self) -> str:
        self._handle_counter += 1
        pid = os.getpid()
        return f"hefesto_{pid}_{self._handle_counter}"

    def get_active_window_info(self) -> WindowInfo | None:
        """Retorna WindowInfo via portal D-Bus, ou None se indisponível."""
        handle = self._next_handle()

        # Tenta jeepney primeiro (sem deps nativas).
        result = _try_jeepney(handle)
        if result is not None:
            logger.debug("wayland_portal_ok", via="jeepney", app_id=result.app_id)
            return result

        # Fallback para dbus-fast.
        result = _try_dbus_fast(handle)
        if result is not None:
            logger.debug("wayland_portal_ok", via="dbus-fast", app_id=result.app_id)
            return result

        logger.debug("wayland_portal_unavailable")
        return None


__all__ = ["WaylandPortalBackend"]
