"""Backend wlr-foreign-toplevel-management via `wlrctl` CLI.

Cobre compositors wlroots-like e compatíveis:
  - COSMIC (cosmic-comp, smithay).
  - Sway, Hyprland, niri, river.

O protocolo `wlr-foreign-toplevel-management-unstable-v1` é suportado pelos
compositors acima mesmo quando `org.freedesktop.portal.Window::GetActiveWindow`
não está implementado ainda (caso do COSMIC alpha histórico e ainda parcial
no COSMIC 1.0). `wlrctl` é um CLI pequeno que conversa com o compositor
via esse protocolo e emite JSON — mais simples que embutir `pywayland` e
resolve o problema hoje.

Disponibilidade do `wlrctl`:
  - Arch:          `pacman -S wlrctl`.
  - Fedora:        `dnf install wlrctl` (COPR em versões antigas).
  - Ubuntu/Debian: Ubuntu 24.04+ tem no universe; versões antigas precisam
                   AUR-like via `cargo install wlrctl` ou PPA.

Se o binário não está no PATH ou não responde, `get_active_window_info`
retorna `None` e o caller (autoswitch via cascade) degrada silenciosamente.

BUG-COSMIC-WLR-BACKEND-REGRESSION-01 (v3.1.0) — re-portado do v2.4.1 após o
rebrand Hefesto → Hefesto - Dualsense4Unix ter removido o arquivo no commit
de massa-rename. Sem este backend o autoswitch fica inoperante em COSMIC
puro (sem XWayland).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from hefesto_dualsense4unix.integrations.window_backends.base import WindowInfo
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

_WLRCTL_BIN = "wlrctl"
_WLRCTL_TIMEOUT_SECONDS = 1.0

# FEAT-WINDOW-DETECT-DIAG-01: mensagem que o wlrctl emite quando o compositor
# NÃO expõe `wlr-foreign-toplevel-management` (caso do cosmic-comp, que usa o
# protocolo próprio `zcosmic_toplevel_info_v1`). Validado ao vivo em COSMIC:
# a mensagem sai no stderr; o código de saída varia por versão (0 OU 1), por
# isso o marcador é checado ANTES do returncode. Comparação em minúsculas.
_PROTOCOL_UNSUPPORTED_MARKER = "foreign toplevel management interface not found"


class WlrctlBackend:
    """Backend de detecção de janela ativa via `wlrctl toplevel list --json`.

    Cacheia o resultado de `shutil.which("wlrctl")` na primeira chamada para
    evitar rescanning a cada consulta (AutoSwitcher chama a 2 Hz). Se o
    binário não está presente, todas as chamadas retornam `None`
    imediatamente — custo desprezível.

    FEAT-WINDOW-DETECT-DIAG-01: se o compositor declara que não implementa o
    protocolo (`_PROTOCOL_UNSUPPORTED_MARKER`), o backend se marca
    indisponível DE VEZ — antes isso era tratado como falha transiente e o
    diagnóstico mentiria ("wlrctl ativo" num compositor que nunca responderá).
    """

    # FEAT-WINDOW-DETECT-DIAG-01: nome estável para diagnóstico (store/doctor).
    backend_name: str = "wlrctl"

    def __init__(self) -> None:
        self._available: bool = shutil.which(_WLRCTL_BIN) is not None
        self._missing_warned: bool = False
        # FEAT-WINDOW-DETECT-DIAG-01: True quando o compositor respondeu que
        # não suporta o protocolo wlr (distinto de "binário ausente").
        self._protocol_unsupported: bool = False
        if not self._available:
            logger.debug("wlrctl_bin_missing")

    @property
    def available(self) -> bool:
        """True se o backend ainda pode produzir leituras.

        FEAT-WINDOW-DETECT-DIAG-01: False quando o binário está ausente OU o
        compositor declarou não suportar o protocolo. Consumido pela cascata
        Wayland para reportar o backend efetivamente ativo.
        """
        return self._available

    @property
    def protocol_unsupported(self) -> bool:
        """True se o compositor declarou não expor o protocolo wlr.

        FEAT-WINDOW-DETECT-DIAG-01: distingue, no diagnóstico, "wlrctl não
        instalado" de "instalado mas o compositor (ex.: cosmic-comp) não
        implementa wlr-foreign-toplevel-management".
        """
        return self._protocol_unsupported

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

        # FEAT-WINDOW-DETECT-DIAG-01: compositor sem o protocolo wlr (COSMIC).
        # Checado ANTES do returncode porque o wlrctl emite a mensagem com
        # exit 0 ou 1 dependendo da versão. Marca indisponível permanente:
        # retry a 2 Hz nunca vai funcionar e o diagnóstico deixaria de mentir.
        combined = f"{result.stdout or ''}\n{result.stderr or ''}".lower()
        if _PROTOCOL_UNSUPPORTED_MARKER in combined:
            self._available = False
            self._protocol_unsupported = True
            logger.warning(
                "wlrctl_protocol_unsupported",
                rc=result.returncode,
                hint=(
                    "Compositor sem wlr-foreign-toplevel-management (ex.: "
                    "cosmic-comp, que usa zcosmic_toplevel_info_v1). Jogos "
                    "XWayland/Proton seguem detectáveis via backend xlib."
                ),
            )
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
            pid=0,
            app_id=app_id,
            title=title,
            exe_basename="",
        )


__all__ = ["WlrctlBackend"]
