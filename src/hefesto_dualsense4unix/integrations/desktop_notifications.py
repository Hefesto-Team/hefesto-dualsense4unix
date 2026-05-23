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
import os
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
    actions: list[tuple[str, str]] | None = None,
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
        actions: Lista de `(key, label)` para botões clicáveis na
            notification (FEAT-NOTIFY-ACTION-OPEN-01, v3.3.0). O servidor
            emite `org.freedesktop.Notifications::ActionInvoked` com `key`
            quando o usuário clica. Use `("default", "Abrir")` para
            ação implícita ao clicar no corpo. Listener é responsabilidade
            do caller (ex.: `app/app.py` escuta e chama `window.present()`).

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

    # FEAT-NOTIFY-ACTION-OPEN-01: actions é list[str] alternando key, label,
    # key, label... (spec freedesktop). Lista vazia = sem botões.
    actions_flat: list[str] = []
    for key, label in actions or []:
        actions_flat.extend([str(key), str(label)])

    # Signature: susssasa{sv}i
    #   app_name (s), replaces_id (u=0), icon (s), summary (s), body (s),
    #   actions (as), hints (a{sv}={}), timeout (i)
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


# ---------------------------------------------------------------------------
# FEAT-COSMIC-NOTIFICATIONS-01 — helpers de evento canonico (opt-in)
#
# Notifications de eventos sao opt-in via env var
# `HEFESTO_DUALSENSE4UNIX_DESKTOP_NOTIFICATIONS=1`. Sem isso, as funções
# `notify_*` retornam False imediatamente (zero overhead, zero ruido).
#
# Eventos cobertos:
#   notify_controller_connected(transport)
#   notify_controller_disconnected(reason)
#   notify_battery_low(pct)
#   notify_profile_activated(name)
# ---------------------------------------------------------------------------

_ENV_NOTIFICATIONS_ENABLED = "HEFESTO_DUALSENSE4UNIX_DESKTOP_NOTIFICATIONS"


def _notifications_enabled() -> bool:
    """Lê env var no momento da chamada (re-avalia a cada notify).

    Permite ao usuário habilitar/desabilitar sem reiniciar o daemon — embora,
    na prática, a env e fixada antes do daemon subir.
    """
    return os.environ.get(_ENV_NOTIFICATIONS_ENABLED, "").strip() in ("1", "true", "yes")


def notify_controller_connected(transport: str) -> bool:
    if not _notifications_enabled():
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
    body = "DualSense desconectado." if not reason else f"DualSense desconectado ({reason})."
    return notify(
        summary="Controle desconectado",
        body=body,
        icon="input-gaming",
        timeout_ms=3000,
        # FEAT-NOTIFY-ACTION-OPEN-01: usuário sem tray clica para restaurar
        # janela principal. Listener em app/app.py.
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
    """Reseta o cache de battery_low quando bateria volta a subir acima do
    threshold de recuperacao — permite emitir notify de novo na próxima queda."""
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
    """Avisa, uma vez por boot, que há perfis com configuração inválida
    (FEAT-CONFIG-AUDIT-BOOT-01). `invalid` = [(nome, erro)]."""
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
    """Avisa uma vez por boot sobre problemas de infra detectados
    (FEAT-SYSTEM-AUTOREPAIR-BOOT-01). Nunca roda reparo — só sugere o comando."""
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
    """Avisa que o modo jogo foi ligado/desligado (emulação de mouse/teclado).

    FEAT-EMULATION-GAMEMODE-LONGPRESS-01. Diferente dos eventos automáticos,
    este é feedback de uma ação DELIBERADA do usuário (long-press do PS), então
    notifica SEMPRE — independente do opt-in
    `HEFESTO_DUALSENSE4UNIX_DESKTOP_NOTIFICATIONS`. Sem feedback visível, o
    usuário não saberia se o gesto pegou.
    """
    if suppressed:
        summary = "Modo jogo ligado"
        body = "Emulação de mouse/teclado desativada. Segure o PS de novo para reativar."
    else:
        summary = "Modo jogo desligado"
        body = "Emulação de mouse/teclado reativada."
    return notify(summary=summary, body=body, icon="input-gaming", timeout_ms=2500)


__all__ = [
    "notify",
    "notify_battery_low",
    "notify_battery_recovered",
    "notify_config_errors",
    "notify_controller_connected",
    "notify_controller_disconnected",
    "notify_emulation_suppressed",
    "notify_profile_activated",
    "notify_system_warnings",
    "reset_once_cache",
    "statusnotifierwatcher_available",
]
