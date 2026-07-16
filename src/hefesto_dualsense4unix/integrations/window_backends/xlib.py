"""Backend X11 via `python-xlib`.

Encapsula a lógica de `xlib_window.py` na classe `XlibBackend`.
Retorna `WindowInfo` com `wm_class`, `pid`, `title` e `exe_basename`.
"""
from __future__ import annotations

import contextlib
import os
import time
from typing import Any

from hefesto_dualsense4unix.integrations.window_backends.base import WindowInfo
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Falhas CONSECUTIVAS de consulta antes de descartar a conexão mesmo sem
#: reconhecer a classe do erro (3 ticks ≈ 1,5 s no poll de 2 Hz do autoswitch).
#: Erro de conexão RECONHECIDO (ConnectionClosedError/OSError) descarta na 1ª.
_MAX_QUERY_FAILURES = 3

#: Backoff entre tentativas de reconectar ao servidor X que FALHARAM — o
#: connect é bloqueante e roda no tick do autoswitch; marretar um XWayland que
#: ainda não voltou seria I/O inútil a 2 Hz.
_RECONNECT_BACKOFF_SEC = 30.0


def _exe_basename_from_pid(pid: int) -> str:
    """Resolve basename do executável via /proc/<pid>/exe."""
    try:
        target = os.readlink(f"/proc/{pid}/exe")
        return os.path.basename(target)
    except (OSError, FileNotFoundError):
        return ""


class XlibBackend:
    """Backend de detecção de janela ativa usando X11 + python-xlib.

    Lazy-conecta ao servidor X na primeira chamada a `get_active_window_info`.
    """

    # FEAT-WINDOW-DETECT-DIAG-01: nome estável para diagnóstico (store/doctor).
    backend_name: str = "xlib"

    def __init__(self) -> None:
        self._display: Any = None
        self._connected: bool = False
        self._init_attempted: bool = False
        # UX-02 (SPRINT-UX-AUTOSWITCH-01): episódio do gate de foco em curso —
        # loga 1x por episódio (o poll do autoswitch chama a 2 Hz).
        self._focus_gate_active: bool = False
        # Reconexão (achado MED da revisão adversarial da Fase 2): falhas
        # consecutivas de consulta + carimbo da última tentativa de conexão
        # FALHADA + episódio de reconexão em curso (log 1x por episódio).
        self._query_failures: int = 0
        self._last_connect_fail: float = float("-inf")
        self._reconnect_pending: bool = False

    def _ensure_connected(self) -> bool:
        """Conecta (ou RECONECTA, com backoff) ao display X11.

        Antes, `_init_attempted` congelava o resultado da primeira tentativa
        para sempre: se o XWayland morresse/reiniciasse (crash de jogo +
        NVIDIA; o cosmic-comp o respawna), o Display do python-xlib ficava
        morto, todo tick virava 'unknown' e a histerese UX-01 retinha o
        perfil de jogo INDEFINIDAMENTE — inclusive as rampas de saída
        documentadas (Steam e GUI são XWayland) dependem desta conexão.
        Agora `_drop_connection` zera o estado e este método tenta um Display
        novo, com backoff entre tentativas falhadas.
        """
        if self._connected:
            return True
        if self._init_attempted and (
            time.monotonic() - self._last_connect_fail < _RECONNECT_BACKOFF_SEC
        ):
            return False
        self._init_attempted = True

        if not os.environ.get("DISPLAY"):
            logger.debug("x11_no_display")
            self._connected = False
            self._last_connect_fail = time.monotonic()
            return False

        try:
            from Xlib import display as xdisplay

            self._display = xdisplay.Display()
            self._connected = True
            self._query_failures = 0
            if self._reconnect_pending:
                self._reconnect_pending = False
                logger.info("x11_reconnected")
            else:
                logger.debug("x11_connected")
        except Exception as exc:
            logger.warning("x11_connect_failed", err=str(exc))
            self._connected = False
            self._last_connect_fail = time.monotonic()

        return self._connected

    @staticmethod
    def _is_connection_error(exc: Exception) -> bool:
        """Erro de CONEXÃO (display morto) — nunca um BadWindow pontual.

        `ConnectionClosedError` é o que o python-xlib levanta quando o socket
        do X morre; OSError cobre o socket quebrando por baixo. Erros de
        protocolo (BadWindow etc.) NÃO derrubam a conexão — janela morta é
        transitório normal e o caminho pontual já degrada para None.
        """
        try:
            from Xlib.error import ConnectionClosedError
        except Exception:  # pragma: no cover - python-xlib sempre presente
            return isinstance(exc, OSError)
        return isinstance(exc, (ConnectionClosedError, OSError))

    def _drop_connection(self) -> None:
        """Descarta a conexão morta; `_ensure_connected` tenta outra depois.

        Log `x11_reconnect_attempt` 1x por episódio (o poll é de 2 Hz); o
        carimbo de falha é zerado para a reconexão ser tentada JÁ no próximo
        tick — o backoff só vale entre tentativas de conexão que falharam.
        """
        if not self._reconnect_pending:
            self._reconnect_pending = True
            logger.info("x11_reconnect_attempt", falhas=self._query_failures)
        with contextlib.suppress(Exception):
            if self._display is not None:
                self._display.close()
        self._display = None
        self._connected = False
        self._init_attempted = False
        self._query_failures = 0
        self._last_connect_fail = float("-inf")

    def get_active_window_info(self) -> WindowInfo | None:
        """Retorna WindowInfo da janela ativa, ou None se indisponível."""
        if not self._ensure_connected():
            return None

        try:
            from Xlib import X

            # UX-02 (SPRINT-UX-AUTOSWITCH-01): gate de foco X. O
            # `_NET_ACTIVE_WINDOW` fica RANÇOSO no cosmic-comp — aponta até
            # janela X morta (BadWindow ao consultar WM_CLASS) enquanto o foco
            # real está numa janela Wayland nativa; provado ao vivo 2x, de
            # forma independente, na sessão COSMIC (get_input_focus() == 0).
            # Se o servidor X diz que NENHUMA janela X tem o foco (None=0) ou
            # que ele é PointerRoot (1), a propriedade não é confiável →
            # retorna None (o reader vira 'unknown' e a histerese UX-01 retém
            # o perfil corrente). Tradeoff declarado: tratar PointerRoot como
            # sem-foco cega sessões X11 legadas focus-follows-mouse — aceito,
            # o alvo é COSMIC; comportamento intencional e coberto por teste.
            focus_reply = self._display.get_input_focus()
            # A conexão respondeu — zera o contador de falhas consecutivas.
            self._query_failures = 0
            focus = getattr(focus_reply, "focus", None)
            # python-xlib devolve `focus` como int (0/1) OU objeto Window —
            # normaliza antes de comparar (comparar o objeto direto com
            # {0, 1} quebraria o caminho feliz).
            focus_id = getattr(focus, "id", focus)
            if focus_id in (X.NONE, X.PointerRoot):
                if not self._focus_gate_active:
                    self._focus_gate_active = True
                    logger.info("x11_focus_gate_no_x_focus", focus=focus_id)
                return None
            self._focus_gate_active = False

            root = self._display.screen().root
            net_active_window = self._display.intern_atom("_NET_ACTIVE_WINDOW")
            net_wm_pid = self._display.intern_atom("_NET_WM_PID")

            prop = root.get_full_property(net_active_window, X.AnyPropertyType)
            if prop is None or not prop.value:
                return None
            win_id = int(prop.value[0])
            if win_id == 0:
                return None

            win = self._display.create_resource_object("window", win_id)

            wm_class_tuple: tuple[str, str] | None = None
            with contextlib.suppress(Exception):
                wm_class_tuple = win.get_wm_class()
            wm_class = wm_class_tuple[1] if wm_class_tuple else ""

            title = ""
            with contextlib.suppress(Exception):
                title = win.get_wm_name() or ""

            pid = 0
            with contextlib.suppress(Exception):
                pid_prop = win.get_full_property(net_wm_pid, X.AnyPropertyType)
                if pid_prop is not None and pid_prop.value:
                    pid = int(pid_prop.value[0])

            exe_basename = _exe_basename_from_pid(pid) if pid else ""

            return WindowInfo(
                wm_class=wm_class or "unknown",
                pid=pid,
                app_id="",
                title=title,
                exe_basename=exe_basename,
            )
        except Exception as exc:
            logger.warning("x11_query_failed", err=str(exc))
            # Reconexão: erro de CONEXÃO derruba o Display morto na hora;
            # erro não-reconhecido só depois de N falhas consecutivas (um
            # BadWindow pontual não pode custar a conexão viva).
            self._query_failures += 1
            if (
                self._is_connection_error(exc)
                or self._query_failures >= _MAX_QUERY_FAILURES
            ):
                self._drop_connection()
            return None


__all__ = ["XlibBackend"]
