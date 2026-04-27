"""Backend Wayland via portal XDG D-Bus `org.freedesktop.portal.Window`.

Usa `jeepney` (puro Python, síncrono). Se a biblioteca não estiver
disponível no ambiente, `get_active_window_info()` retorna `None`
imediatamente (degradação silenciosa).

A interface `GetActiveWindow` foi introduzida no portal v1 (COSMIC 1.0+,
GNOME 46+). Compositors mais antigos podem não expor o método.

Nota de performance (AUDIT-FINDING-WAYLAND-PORTAL-PERF-01):
    Versões anteriores criavam `ThreadPoolExecutor(max_workers=1)` +
    `asyncio.run()` a cada chamada para envolver `dbus-fast`. Como o
    `AutoSwitcher` chama este backend a 2 Hz em Wayland puro, o overhead
    de spawn/tear-down de thread e loop asyncio era desnecessário.
    A implementação foi simplificada para usar apenas `jeepney` síncrono
    direto na thread do autoswitch (que já é bloqueante), com timeout
    nativo do próprio jeepney. Zero threads novas por chamada.
"""
from __future__ import annotations

import contextlib
import os
from typing import Any

from hefesto_dualsense4unix.integrations.window_backends.base import WindowInfo
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

# Constantes do portal D-Bus.
_PORTAL_BUS = "org.freedesktop.portal.Desktop"
_PORTAL_PATH = "/org/freedesktop/portal/desktop"
_PORTAL_IFACE = "org.freedesktop.portal.Window"

# Timeout máximo por chamada ao portal (segundos). Se o compositor não
# responder neste prazo, `_try_jeepney` retorna None e o caller degrada.
_PORTAL_TIMEOUT_SECONDS = 2.0


def _try_jeepney(handle_token: str) -> WindowInfo | None:
    """Tenta obter janela ativa via jeepney (síncrono, puro Python).

    Aplica timeout explícito de `_PORTAL_TIMEOUT_SECONDS` via kwarg nativo
    do `send_and_get_reply`. Retorna None em qualquer falha (ImportError,
    timeout, erro do portal, resposta inesperada).
    """
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

        # reply.body[0] é o handle; info real chega via sinal, mas alguns
        # compositors retornam diretamente no reply.body[1].
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

    Se `jeepney` não estiver disponível no ambiente, ou se o portal não
    responder, `get_active_window_info()` retorna `None`.

    Nenhuma thread ou loop asyncio é criada por chamada — `jeepney` roda
    sincronamente na thread do caller (o `AutoSwitcher` já bloqueia a
    500ms, então o acoplamento direto é seguro).
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

        result = _try_jeepney(handle)
        if result is not None:
            logger.debug("wayland_portal_ok", via="jeepney", app_id=result.app_id)
            return result

        logger.debug("wayland_portal_unavailable")
        return None


__all__ = ["WaylandPortalBackend"]
