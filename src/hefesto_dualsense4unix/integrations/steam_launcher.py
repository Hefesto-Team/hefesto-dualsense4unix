"""Abrir ou focar a Steam a partir de botao PS solo (FEAT-HOTKEY-STEAM-01).

Contrato:
  - `open_or_focus_steam()` e idempotente e nunca levanta: loga falha e segue.
  - Se o binário `steam` não existir no PATH, loga warning uma vez e retorna
    imediatamente nas chamadas subsequentes ate que o processo do daemon
    seja reiniciado. Evita poluir log com tentativas repetidas.
  - Se `pgrep -x steam` localiza PID, usa `wmctrl -lx` para achar a janela
    com WM_CLASS casando `steam.Steam` e chama `wmctrl -ia <id>`.
  - Se o processo não esta rodando, abre `steam` por `fora_do_servico.abrir`
    (STEAM-FORA-DO-SERVICO-01): de dentro do serviço do daemon, numa unidade
    própria do gerenciador de usuário (nice 0, oom do gerenciador, e viva
    depois de um restart do serviço); de fora dele, ou sem systemd de
    usuário, o `Popen(start_new_session=True, stdin/out/err=DEVNULL)` de
    sempre. Nos dois, com o ambiente de `ambiente_do_jogo.ambiente_limpo`
    (AMBIENTE-DO-JOGO-01).
  - NUNCA usa `shell=True`.
  - Execução em thread worker e responsabilidade do chamador; a função em si
    faz chamadas subprocess sincronas de curta duracao (pgrep/wmctrl, e o
    `systemd-run`, medido em 6 a 12 ms) e não espera a Steam.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
from collections.abc import Callable
from typing import Any

from hefesto_dualsense4unix.integrations import fora_do_servico
from hefesto_dualsense4unix.integrations.ambiente_do_jogo import ambiente_limpo
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

STEAM_BINARY = "steam"
WMCTRL_BINARY = "wmctrl"
PGREP_BINARY = "pgrep"
STEAM_WM_CLASS = "steam.Steam"

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
    *,
    contexto: fora_do_servico.Contexto | None = None,
    executar: fora_do_servico.Executar | None = None,
) -> bool:
    """Dispara a Steam FORA do serviço do Hefesto, desprendida de quem chama.

    STEAM-FORA-DO-SERVICO-01 (26/09/2026): o botão PS abria a Steam por
    `Popen` de dentro do daemon, e a Steam e o jogo nasciam no cgroup
    `hefesto-dualsense4unix.service`, com o nice 5 e o oom 200 dele — e
    morriam no restart do serviço. Quem decide a forma é
    `fora_do_servico.abrir`: de dentro de um serviço, uma unidade própria do
    gerenciador de usuário; de um lugar que já é da pessoa, ou sem systemd de
    usuário, o `Popen` de sempre (`start_new_session=True`).

    AMBIENTE-DO-JOGO-01 (18/09/2026): o `ambiente_limpo` entra porque o
    daemon também sobe fora da unit — pelo terminal de quem desenvolve, ou
    pelo `Popen` da janela quando o `systemctl` falta —, e a Steam que nasce
    daqui é a que todo jogo da sessão herda. Pela unidade ele vai por
    `--setenv`.
    """
    runner = popen_runner or _default_popen
    try:
        abertura = fora_do_servico.abrir(
            [STEAM_BINARY],
            env=ambiente_limpo(os.environ),
            aplicativo=STEAM_BINARY,
            contexto=contexto,
            executar=executar,
            popen=runner,
        )
    except FileNotFoundError:
        _warn_steam_missing_once()
        return False
    except Exception as exc:
        logger.warning("steam_spawn_failed", err=str(exc))
        return False
    logger.info(
        "steam_spawn_requested",
        caminho=abertura.caminho,
        unidade=abertura.unidade,
        motivo=abertura.motivo,
        tentativas=list(abertura.tentativas),
    )
    return True


def _default_popen(cmd: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
    # kwargs aceita stdin/stdout/stderr/start_new_session/env — tipagem livre para
    # permitir injecao de fakes nos testes sem duplicar a assinatura.
    return subprocess.Popen(cmd, **kwargs)


def open_or_focus_steam(
    *,
    which: Callable[[str], str | None] | None = None,
    pgrep_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    wmctrl_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    popen_runner: Callable[..., object] | None = None,
    contexto: fora_do_servico.Contexto | None = None,
    executar: fora_do_servico.Executar | None = None,
) -> bool:
    """Ponto de entrada publico. Nunca levanta.

    Retorna True se a tentativa foi bem-sucedida (focus ou spawn). False
    caso contrario. Parametros opcionais permitem injetar fakes em testes;
    `contexto` e `executar` vão a `fora_do_servico.abrir`.
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
            return _spawn_steam(
                popen_runner=popen_runner, contexto=contexto, executar=executar
            )
        spawned = _spawn_steam(
            popen_runner=popen_runner, contexto=contexto, executar=executar
        )
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
