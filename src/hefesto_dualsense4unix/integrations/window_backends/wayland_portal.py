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

    BUG-COSMIC-PORTAL-UNSUPPORTED-01 (v2.4.0, re-portado em v3.1.0): após
    `_UNSUPPORTED_THRESHOLD` falhas consecutivas, o backend loga um
    warning único com instrução para o usuário (ex: Pop!_OS COSMIC ainda
    não implementa o método `GetActiveWindow` no `xdg-desktop-portal-cosmic`)
    e passa a retornar None sem consultar o portal — economiza D-Bus
    traffic e ruído no log. Reset do estado ao menos uma resposta OK
    volta o backend a probar normalmente. Essencial para o cascade
    portal → wlrctl não ficar pendurado 2s por chamada quando o portal
    é definitivamente inacessível.
    """

    _UNSUPPORTED_THRESHOLD: int = 3

    def __init__(self) -> None:
        self._handle_counter: int = 0
        self._consecutive_failures: int = 0
        self._unsupported_warned: bool = False

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
        """Retorna WindowInfo via portal D-Bus, ou None se indisponível.

        Quando o portal falha `_UNSUPPORTED_THRESHOLD` vezes seguidas, para
        de chamar o D-Bus e retorna None diretamente — poupa o event loop
        de 2s de timeout a cada 500ms em compositors que não implementam o
        método (ex: Pop!_OS COSMIC sem `xdg-desktop-portal-cosmic` com
        suporte a `GetActiveWindow`).
        """
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
