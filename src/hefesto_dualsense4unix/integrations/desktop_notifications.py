"""Notificações desktop via `org.freedesktop.Notifications` (jeepney)."""
from __future__ import annotations

import contextlib
import os
from typing import Any

from hefesto_dualsense4unix.utils import identidade
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

_NOTIFICATIONS_BUS = "org.freedesktop.Notifications"
_NOTIFICATIONS_PATH = "/org/freedesktop/Notifications"
_NOTIFICATIONS_IFACE = "org.freedesktop.Notifications"

_DBUS_TIMEOUT_SECONDS = 2.0

_announced_once: set[str] = set()

def notify(
    summary: str,
    body: str = "",
    *,
    app_name: str = identidade.atual().nome_longo,
    icon: str = "input-gaming",
    timeout_ms: int = 4000,
    once_key: str | None = None,
    actions: list[tuple[str, str]] | None = None,
) -> bool:
    """Emite uma notification D-Bus padrão freedesktop."""
    if _a_suite_esta_rodando() or (once_key is not None and once_key in _announced_once):
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

    actions_flat: list[str] = []
    for key, label in actions or []:
        actions_flat.extend([str(key), str(label)])

    msg = new_method_call(
        addr,
        "Notify",
        "susssasa{sv}i",
        (app_name, 0, icon, summary, body, actions_flat, {}, int(timeout_ms)),
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
    logger.debug(
        "notify_sent",
        summary=summary,
        once_key=once_key,
        actions=len(actions or []),
    )
    return True


def reset_once_cache() -> None:
    """Limpa o cache de chaves `once_key` — útil em testes."""
    _announced_once.clear()


def statusnotifierwatcher_available() -> bool:
    """Verifica via D-Bus se algum watcher de StatusNotifier está registrado."""
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


def notify_emulation_suppressed(suppressed: bool) -> bool:
    """Avisa que o modo jogo foi ligado/desligado (emulação de mouse/teclado)."""
    if suppressed:
        summary = "Modo jogo ligado"
        body = "Emulação de mouse/teclado desativada. Segure o PS de novo para reativar."
    else:
        summary = "Modo jogo desligado"
        body = "Emulação de mouse/teclado reativada."
    return notify(summary=summary, body=body, icon="input-gaming", timeout_ms=2500)


def notify_teclado_na_tela_ausente(candidatos: list[str]) -> bool:
    """Avisa que o "teclado na tela" (L3/R3) não tem programa para abrir."""
    lista = " ou ".join(candidatos) if candidatos else "onboard"
    return notify(
        summary="Teclado na tela não instalado",
        body=(
            "L3 abriria o teclado na tela, mas nenhum programa de teclado na "
            f"tela foi encontrado no computador. Instale {lista} e aperte L3 "
            "de novo."
        ),
        icon="dialog-warning",
        timeout_ms=10000,
        once_key="osk_binary_missing",
    )


_OSK_ABERTO_TITULO = "Teclado na tela aberto pelo L3."
_OSK_ABERTO_CORPO = "Para fechar, aperte R3."


def notify_teclado_na_tela_aberto() -> bool:
    """Avisa que o teclado na tela ACABOU de abrir, e ensina como fechá-lo."""
    return notify(
        summary=_OSK_ABERTO_TITULO,
        body=_OSK_ABERTO_CORPO,
        icon="input-keyboard",
        timeout_ms=10000,
    )


__all__ = [
    "AVISO_DE_VERDADE_NA_SUITE",
    "notify",
    "notify_emulation_suppressed",
    "notify_teclado_na_tela_aberto",
    "notify_teclado_na_tela_ausente",
    "reset_once_cache",
    "statusnotifierwatcher_available",
]


AVISO_DE_VERDADE_NA_SUITE = "HEFESTO_AVISO_DE_VERDADE"


def _a_suite_esta_rodando() -> bool:
    """A suíte está no ar? Então nenhum aviso sai para a área de trabalho."""
    import sys

    if os.environ.get(AVISO_DE_VERDADE_NA_SUITE) == "1":
        return False
    return bool(os.environ.get("PYTEST_CURRENT_TEST")) or "pytest" in sys.modules
