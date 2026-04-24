"""Backend wlr-foreign-toplevel-management via `wlrctl` CLI.

Cobre compositors wlroots-like e compatíveis:
  - COSMIC (cosmic-comp, smithay — alpha de 2026).
  - Sway, Hyprland, niri, river.

O protocolo `wlr-foreign-toplevel-management-unstable-v1` é suportado pelos
compositors acima mesmo quando `org.freedesktop.portal.Window::GetActiveWindow`
não está implementado ainda (caso do COSMIC alpha). `wlrctl` é um CLI pequeno
que conversa com o compositor via esse protocolo e emite JSON — mais simples
que embutir `pywayland` e resolve o problema hoje.

Disponibilidade do `wlrctl`:
  - Arch:          `pacman -S wlrctl`.
  - Fedora:        `dnf install wlrctl` (COPR em versões antigas).
  - Ubuntu/Debian: Ubuntu 24.04+ tem no universe; versões antigas precisam
                   AUR-like via `cargo install wlrctl` ou PPA.

Se o binário não está no PATH ou não responde, `get_active_window_info`
retorna `None` e o caller (autoswitch) degrada silenciosamente.

BUG-COSMIC-WLR-BACKEND-01 — adicionado em v2.4.1 como resposta ao
compositor COSMIC alpha não implementar `GetActiveWindow`.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from hefesto.integrations.window_backends.base import WindowInfo
from hefesto.utils.logging_config import get_logger

logger = get_logger(__name__)

_WLRCTL_BIN = "wlrctl"
_WLRCTL_TIMEOUT_SECONDS = 1.0


class WlrctlBackend:
    """Backend de detecção de janela ativa via `wlrctl toplevel list --json`.

    Cacheia o resultado de `shutil.which("wlrctl")` na primeira chamada para
    evitar rescanning a cada consulta (AutoSwitcher chama a 2 Hz). Se o
    binário não está presente, todas as chamadas retornam `None`
    imediatamente — custo desprezível.
    """

    def __init__(self) -> None:
        self._available: bool = shutil.which(_WLRCTL_BIN) is not None
        self._missing_warned: bool = False
        if not self._available:
            logger.debug("wlrctl_bin_missing")

    def get_active_window_info(self) -> WindowInfo | None:
        """Retorna WindowInfo do toplevel ativo, ou None se indisponível."""
        if not self._available:
            return None

        try:
            result = subprocess.run(
                [
                    _WLRCTL_BIN,
                    "toplevel",
                    "list",
                    "--json",
                    "--state",
                    "activated",
                ],
                capture_output=True,
                text=True,
                timeout=_WLRCTL_TIMEOUT_SECONDS,
                check=False,
            )
        except FileNotFoundError:
            self._available = False
            return None
        except subprocess.TimeoutExpired:
            logger.debug("wlrctl_timeout")
            return None
        except OSError as exc:
            logger.debug("wlrctl_oserror", err=str(exc))
            return None

        if result.returncode != 0:
            logger.debug(
                "wlrctl_nonzero",
                rc=result.returncode,
                stderr=(result.stderr or "").strip()[:200],
            )
            return None

        stdout = (result.stdout or "").strip()
        if not stdout:
            return None

        try:
            data: Any = json.loads(stdout)
        except json.JSONDecodeError as exc:
            logger.debug("wlrctl_json_decode_failed", err=str(exc))
            return None

        if not isinstance(data, list) or not data:
            return None

        top = data[0]
        if not isinstance(top, dict):
            return None

        app_id = str(top.get("app_id") or top.get("appId") or "")
        title = str(top.get("title") or "")
        wm_class = app_id or "unknown"

        return WindowInfo(
            wm_class=wm_class,
            pid=0,  # wlr-foreign-toplevel não expõe pid
            app_id=app_id,
            title=title,
            exe_basename="",
        )


__all__ = ["WlrctlBackend"]
