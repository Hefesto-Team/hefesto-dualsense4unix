"""Notificações desktop via `org.freedesktop.Notifications` (jeepney)."""
from __future__ import annotations

import contextlib
import os
import time
from typing import Any

from hefesto_dualsense4unix.utils import identidade
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

_NOTIFICATIONS_BUS = "org.freedesktop.Notifications"
_NOTIFICATIONS_PATH = "/org/freedesktop/Notifications"
_NOTIFICATIONS_IFACE = "org.freedesktop.Notifications"

_DBUS_TIMEOUT_SECONDS = 2.0

_announced_once: set[str] = set()

_THROTTLE_MIN_INTERVAL_SEC: float = float(
    os.environ.get("HEFESTO_DUALSENSE4UNIX_NOTIFY_THROTTLE_SEC", "30")
)

_last_emit_at: dict[str, float] = {}


def _throttle_passes(throttle_key: str) -> bool:
    """True se a chave NÃO foi emitida nos últimos `_THROTTLE_MIN_INTERVAL_SEC`."""
    now = time.monotonic()
    last = _last_emit_at.get(throttle_key, 0.0)
    if now - last < _THROTTLE_MIN_INTERVAL_SEC:
        return False
    _last_emit_at[throttle_key] = now
    return True


def reset_throttle_cache() -> None:
    """Limpa o cache de throttling — útil em testes."""
    _last_emit_at.clear()


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


_ENV_NOTIFICATIONS_ENABLED = "HEFESTO_DUALSENSE4UNIX_DESKTOP_NOTIFICATIONS"


def _notifications_enabled() -> bool:
    """Lê env var no momento da chamada (re-avalia a cada notify)."""
    return os.environ.get(_ENV_NOTIFICATIONS_ENABLED, "").strip() in ("1", "true", "yes")


def notify_controller_connected(transport: str) -> bool:
    if not _notifications_enabled():
        return False
    if not _throttle_passes("controller_connected"):
        return False
    tr_label = {"usb": "USB", "bt": "Bluetooth"}.get(transport.lower(), transport)
    return notify(
        summary="Controle conectado",
        body=f"DualSense detectado via {tr_label}.",
        icon="input-gaming",
        timeout_ms=3000,
    )


def notify_controller_disconnected(reason: str = "") -> bool:
    if not _notifications_enabled():
        return False
    if not _throttle_passes("controller_disconnected"):
        return False
    body = "DualSense desconectado." if not reason else f"DualSense desconectado ({reason})."
    return notify(
        summary="Controle desconectado",
        body=body,
        icon="input-gaming",
        timeout_ms=3000,
        actions=[("open", "Abrir Hefesto")],
    )


def notify_battery_low(pct: int, threshold: int = 15) -> bool:
    """Emite uma vez por queda abaixo do threshold (dedup via once_key dinâmica)."""
    if not _notifications_enabled():
        return False
    if pct > threshold:
        return False
    return notify(
        summary="Bateria baixa do DualSense",
        body=f"Bateria em {pct}%. Conecte via USB para carregar.",
        icon="battery-caution",
        timeout_ms=8000,
        once_key=f"battery_low_below_{threshold}",
        actions=[("open", "Abrir Hefesto")],
    )


def notify_battery_recovered(pct: int, threshold: int = 30) -> None:
    """Reseta o cache de battery_low quando bateria volta a subir acima do"""
    if pct >= threshold:
        _announced_once.discard(f"battery_low_below_{threshold - 15}")
        _announced_once.discard("battery_low_below_15")


def notify_profile_activated(name: str) -> bool:
    if not _notifications_enabled():
        return False
    return notify(
        summary="Perfil ativado",
        body=f"Hefesto trocou para o perfil: {name}.",
        icon="input-gaming",
        timeout_ms=2000,
    )


def notify_config_errors(invalid: list[tuple[str, str]]) -> bool:
    """Avisa, uma vez por boot, que há perfis com configuração inválida"""
    if not _notifications_enabled() or not invalid:
        return False
    names = ", ".join(name for name, _err in invalid[:3])
    extra = "…" if len(invalid) > 3 else ""
    return notify(
        summary="Perfis com configuração inválida",
        body=(
            f"{len(invalid)} perfil(is) ignorado(s): {names}{extra}. "
            "Rode 'hefesto-dualsense4unix doctor' ou corrija/exclua o arquivo."
        ),
        icon="dialog-warning",
        timeout_ms=8000,
        once_key="config_errors",
    )


def notify_system_warnings(warnings: list[str]) -> bool:
    """Avisa uma vez por boot sobre problemas de infra detectados"""
    if not _notifications_enabled() or not warnings:
        return False
    body = "; ".join(warnings[:2]) + ("…" if len(warnings) > 2 else "")
    return notify(
        summary="Hefesto: reparo recomendado",
        body=body,
        icon="dialog-warning",
        timeout_ms=10000,
        once_key="system_warnings",
    )


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
    "notify_battery_low",
    "notify_battery_recovered",
    "notify_config_errors",
    "notify_controller_connected",
    "notify_controller_disconnected",
    "notify_emulation_suppressed",
    "notify_profile_activated",
    "notify_system_warnings",
    "notify_teclado_na_tela_aberto",
    "notify_teclado_na_tela_ausente",
    "reset_once_cache",
    "reset_throttle_cache",
    "statusnotifierwatcher_available",
]


AVISO_DE_VERDADE_NA_SUITE = "HEFESTO_AVISO_DE_VERDADE"


def _a_suite_esta_rodando() -> bool:
    """A suíte está no ar? Então nenhum aviso sai para a área de trabalho."""
    import sys

    if os.environ.get(AVISO_DE_VERDADE_NA_SUITE) == "1":
        return False
    return bool(os.environ.get("PYTEST_CURRENT_TEST")) or "pytest" in sys.modules
