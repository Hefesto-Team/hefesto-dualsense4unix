"""Notificações desktop via `org.freedesktop.Notifications` (jeepney).

Cobre eventos onde feedback ao usuário é desejável fora do tray ou da janela
GUI (ex: controle conectado/desconectado, bateria baixa, mudança de perfil
quando o tray icon não está renderizado).

Implementação síncrona com `jeepney` (puro Python, sem deps nativas). Se a
biblioteca não está disponível, `notify()` retorna `False` silenciosamente —
não causa traceback.

Em COSMIC 1.0+, o daemon `cosmic-notifications` implementa o spec normalmente.
Em GNOME, KDE, Sway/Mako, qualquer compositor com notification daemon funciona.

FEAT-COSMIC-TRAY-FALLBACK-01 (v3.1.0): notificações são o canal primário de
feedback ao usuário em sessões COSMIC onde o tray icon não renderiza
(bug cosmic-applets#1009 + StatusNotifierWatcher race conditions).
"""
from __future__ import annotations

import contextlib
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

_NOTIFICATIONS_BUS = "org.freedesktop.Notifications"
_NOTIFICATIONS_PATH = "/org/freedesktop/Notifications"
_NOTIFICATIONS_IFACE = "org.freedesktop.Notifications"

_DBUS_TIMEOUT_SECONDS = 2.0

# Cache do "já avisado uma vez" — algumas mensagens são logadas a cada
# transição de estado e não devem inundar o usuário.
_announced_once: set[str] = set()


def notify(
    summary: str,
    body: str = "",
    *,
    app_name: str = "Hefesto - Dualsense4Unix",
    icon: str = "input-gaming",
    timeout_ms: int = 4000,
    once_key: str | None = None,
) -> bool:
    """Emite uma notification D-Bus padrão freedesktop.

    Retorna `True` em sucesso, `False` em qualquer falha (jeepney ausente,
    daemon não responde, exceção D-Bus). Não levanta.

    Args:
        summary: Título da notificação (linha 1, negrito no GNOME/COSMIC).
        body: Corpo da notificação (linhas 2+).
        app_name: Nome do aplicativo emissor. Usado para agrupamento.
        icon: Nome icon-theme freedesktop ou path absoluto.
        timeout_ms: Duração antes de auto-fechar (ignorado se usuário
            configurou notificações persistentes).
        once_key: Se fornecido, só emite uma vez por execução do daemon
            (chave deduplicação). Útil para avisos como "tray indisponível".

    Returns:
        bool: True se a notification foi entregue ao bus.
    """
    if once_key is not None and once_key in _announced_once:
        return False

    try:
        from jeepney import DBusAddress, new_method_call
        from jeepney.io.blocking import open_dbus_connection
    except ImportError:
        logger.debug("notify_jeepney_missing")
        return False

    addr = DBusAddress(
        _NOTIFICATIONS_PATH,
        bus_name=_NOTIFICATIONS_BUS,
        interface=_NOTIFICATIONS_IFACE,
    )

    # Signature: susssasa{sv}i
    #   app_name (s), replaces_id (u=0), icon (s), summary (s), body (s),
    #   actions (as=[]), hints (a{sv}={}), timeout (i)
    msg = new_method_call(
        addr,
        "Notify",
        "susssasa{sv}i",
        (app_name, 0, icon, summary, body, [], {}, int(timeout_ms)),
    )

    conn = None
    try:
        conn = open_dbus_connection(bus="SESSION")
        conn.send_and_get_reply(msg, timeout=_DBUS_TIMEOUT_SECONDS)
    except Exception as exc:
        logger.debug("notify_failed", err=str(exc))
        return False
    finally:
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()

    if once_key is not None:
        _announced_once.add(once_key)
    logger.debug("notify_sent", summary=summary, once_key=once_key)
    return True


def reset_once_cache() -> None:
    """Limpa o cache de chaves `once_key` — útil em testes."""
    _announced_once.clear()


def statusnotifierwatcher_available() -> bool:
    """Verifica via D-Bus se algum watcher de StatusNotifier está registrado.

    Em COSMIC 1.0.6+, é o próprio `cosmic-applet-status-area` que reivindica
    `org.kde.StatusNotifierWatcher`. Em GNOME com `appindicator` extension,
    é o `gnome-shell`. Em KDE/Sway, varia.

    Se o watcher não está presente, criar um Indicator vai não-fazer-nada
    (sem janela de erro, mas ícone também não aparece).

    Retorna `True` se o nome bem-conhecido `org.kde.StatusNotifierWatcher`
    está disponível na sessão D-Bus.
    """
    try:
        from jeepney import DBusAddress, new_method_call
        from jeepney.io.blocking import open_dbus_connection
    except ImportError:
        return False

    addr = DBusAddress(
        "/org/freedesktop/DBus",
        bus_name="org.freedesktop.DBus",
        interface="org.freedesktop.DBus",
    )
    msg = new_method_call(addr, "NameHasOwner", "s", ("org.kde.StatusNotifierWatcher",))

    conn = None
    try:
        conn = open_dbus_connection(bus="SESSION")
        reply = conn.send_and_get_reply(msg, timeout=_DBUS_TIMEOUT_SECONDS)
        result: Any = reply.body[0] if reply.body else False
        return bool(result)
    except Exception as exc:
        logger.debug("statusnotifierwatcher_probe_failed", err=str(exc))
        return False
    finally:
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()


__all__ = [
    "notify",
    "reset_once_cache",
    "statusnotifierwatcher_available",
]
