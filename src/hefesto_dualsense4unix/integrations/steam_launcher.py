"""Abrir ou focar a Steam a partir de botao PS solo (FEAT-HOTKEY-STEAM-01).

Contrato:
  - `open_or_focus_steam()` e idempotente e nunca levanta: loga falha e segue.
  - Se o binário `steam` não existir no PATH, loga warning uma vez e retorna
    imediatamente nas chamadas subsequentes ate que o processo do daemon
    seja reiniciado. Evita poluir log com tentativas repetidas.
  - Se `pgrep -x steam` localiza PID, usa `wmctrl -lx` para achar a janela
    com WM_CLASS casando `steam.Steam` e chama `wmctrl -ia <id>`.
  - Se o processo não esta rodando, faz `Popen(["steam"], start_new_session=True,
    stdin/out/err=DEVNULL)` e desprende do daemon.
  - NUNCA usa `shell=True`.
  - Execução em thread worker e responsabilidade do chamador; a função em si
    faz chamadas subprocess sincronas de curta duracao (pgrep/wmctrl) e um
    Popen não-bloqueante para o launcher.
"""
from __future__ import annotations

import shutil
import subprocess
import threading
from collections.abc import Callable
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

STEAM_BINARY = "steam"
WMCTRL_BINARY = "wmctrl"
PGREP_BINARY = "pgrep"
STEAM_WM_CLASS = "steam.Steam"

_steam_missing_warned = False
_steam_missing_lock = threading.Lock()


def _reset_missing_warning_for_tests() -> None:
    """Reinicia o flag de warning unica. Uso: testes unitarios."""
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


def _steam_running(
    pgrep_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> bool:
    """Retorna True se `pgrep -x steam` achar processo. Nunca levanta."""
    runner = pgrep_runner or _default_pgrep
    try:
        proc = runner([PGREP_BINARY, "-x", STEAM_BINARY])
    except FileNotFoundError:
        logger.warning("pgrep_binary_not_found")
        return False
    except Exception as exc:
        logger.warning("pgrep_call_failed", err=str(exc))
        return False
    return proc.returncode == 0 and bool((proc.stdout or "").strip())


def _default_pgrep(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=2.0)


def _focus_steam_window(
    wmctrl_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> bool:
    """Traz a janela Steam para foreground via `wmctrl -lx`.

    Retorna True se alguma janela foi focada, False caso contrario.
    """
    runner = wmctrl_runner or _default_wmctrl
    if shutil.which(WMCTRL_BINARY) is None:
        logger.warning("wmctrl_binary_not_found")
        return False
    try:
        listing = runner([WMCTRL_BINARY, "-lx"])
    except Exception as exc:
        logger.warning("wmctrl_list_failed", err=str(exc))
        return False
    if listing.returncode != 0:
        logger.warning("wmctrl_list_nonzero", rc=listing.returncode)
        return False

    target_wid: str | None = None
    for raw_line in (listing.stdout or "").splitlines():
        # Formato: <wid> <desktop> <wm_class> <host> <title...>
        parts = raw_line.split(None, 4)
        if len(parts) < 3:
            continue
        wid, _, wm_class = parts[0], parts[1], parts[2]
        if wm_class == STEAM_WM_CLASS:
            target_wid = wid
            break

    if target_wid is None:
        logger.info("steam_window_not_found")
        return False

    try:
        activate = runner([WMCTRL_BINARY, "-ia", target_wid])
    except Exception as exc:
        logger.warning("wmctrl_activate_failed", err=str(exc))
        return False
    if activate.returncode != 0:
        logger.warning("wmctrl_activate_nonzero", rc=activate.returncode)
        return False
    logger.info("steam_window_focused", wid=target_wid)
    return True


def _default_wmctrl(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=2.0)


def _spawn_steam(
    popen_runner: Callable[..., object] | None = None,
) -> bool:
    """Dispara Steam em sessão nova, desprendida do daemon."""
    runner = popen_runner or _default_popen
    try:
        runner(
            [STEAM_BINARY],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except FileNotFoundError:
        _warn_steam_missing_once()
        return False
    except Exception as exc:
        logger.warning("steam_spawn_failed", err=str(exc))
        return False
    logger.info("steam_spawn_requested")
    return True


def _default_popen(cmd: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
    # kwargs aceita stdin/stdout/stderr/start_new_session — tipagem livre para
    # permitir injecao de fakes nos testes sem duplicar a assinatura.
    return subprocess.Popen(cmd, **kwargs)


def open_or_focus_steam(
    *,
    which: Callable[[str], str | None] | None = None,
    pgrep_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    wmctrl_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    popen_runner: Callable[..., object] | None = None,
) -> bool:
    """Ponto de entrada publico. Nunca levanta.

    Retorna True se a tentativa foi bem-sucedida (focus ou spawn). False
    caso contrario. Parametros opcionais permitem injetar fakes em testes.
    """
    which_fn = which or shutil.which
    if which_fn(STEAM_BINARY) is None:
        _warn_steam_missing_once()
        return False

    try:
        if _steam_running(pgrep_runner=pgrep_runner):
            focused = _focus_steam_window(wmctrl_runner=wmctrl_runner)
            if focused:
                logger.info("ps_button_action_steam", outcome="focused")
                return True
            # Processo existe mas janela não achada: fallback para spawn.
            logger.info("ps_button_action_steam", outcome="refocus_fallback_spawn")
            return _spawn_steam(popen_runner=popen_runner)
        spawned = _spawn_steam(popen_runner=popen_runner)
        if spawned:
            logger.info("ps_button_action_steam", outcome="spawned")
        return spawned
    except Exception as exc:  # salvaguarda: nunca propagar
        logger.warning("open_or_focus_steam_unexpected", err=str(exc))
        return False


__all__ = [
    "PGREP_BINARY",
    "STEAM_BINARY",
    "STEAM_WM_CLASS",
    "WMCTRL_BINARY",
    "open_or_focus_steam",
]
