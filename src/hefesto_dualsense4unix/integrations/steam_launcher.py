"""Abrir ou mostrar a Steam: a porta do botão PS, do gesto e do «repor o lançador».

A porta é fina, sem pergunta própria. Quem sabe se a Steam está de pé, e de que lar,
é o ``steam_launch_options`` (``processos_da_steam``, ``steam_running``); quem sabe
reabri-la, pelo ``steam`` ou pela ``steam://open/main`` que a Flatpak e a Snap
registram, e conferir que ela subiu, é o ``reopen_steam``. Com a Steam de pé, o pedido
é repassado à instância viva, que se mostra: é o «focar» que vale em X11 e em Wayland.
"""
from __future__ import annotations

import threading

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

_steam_missing_warned = False
_steam_missing_lock = threading.Lock()


def _reset_missing_warning_for_tests() -> None:
    """Reinicia o flag de warning única. Uso: testes unitarios."""
    global _steam_missing_warned
    with _steam_missing_lock:
        _steam_missing_warned = False


def _warn_steam_missing_once() -> None:
    global _steam_missing_warned
    with _steam_missing_lock:
        if _steam_missing_warned:
            return
        _steam_missing_warned = True
    logger.warning("steam_binary_not_found", hint="instalar steam ou configurar PATH")


def _steam_de_outro_lar() -> bool:
    """A Steam de pé é toda de outro `HOME`? Quem responde é o dono da pergunta"""
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    todas = slo.processos_da_steam()
    return bool(todas) and all(x.lar and not slo.do_meu_lar(x.lar) for x in todas)


def open_or_focus_steam() -> bool:
    """Abre a Steam, ou mostra a que está de pé. ``True`` = a Steam deste lar está de pé.

    Nunca levanta. A Steam de outro lar não ganha outra: a recusa é a de sempre.
    """
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    try:
        if _steam_de_outro_lar():
            logger.info("ps_button_action_steam", outcome="steam_de_outro_lar")
            return False
        if not slo.ha_porta_de_reabrir():
            _warn_steam_missing_once()
            return False
        de_pe = slo.reopen_steam()
    except Exception as exc:
        logger.warning("open_or_focus_steam_unexpected", err=str(exc))
        return False
    logger.info("ps_button_action_steam", outcome="de_pe" if de_pe else "nao_subiu")
    return de_pe


__all__ = ["open_or_focus_steam"]
