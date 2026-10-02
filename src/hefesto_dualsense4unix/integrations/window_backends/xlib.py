"""Backend X11 via `python-xlib`."""
from __future__ import annotations

import contextlib
import os
import time
from typing import Any

from hefesto_dualsense4unix.integrations.window_backends.base import WindowInfo
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

_MAX_QUERY_FAILURES = 3

_RECONNECT_BACKOFF_SEC = 30.0
_RECONNECT_BACKOFF_MAX_SEC = 300.0

MOTIVO_SEM_CONEXAO = "sem_conexao_x"
MOTIVO_FOCO_SEM_ID = "foco_sem_id"
MOTIVO_SEM_FOCO = "sem_foco_x"
MOTIVO_FOCO_SEM_TOP_LEVEL = "foco_sem_top_level"
MOTIVO_FOCO_DISCORDA = "foco_discorda_do_net_active"
MOTIVO_ERRO_DE_CONSULTA = "erro_de_consulta"

_MAX_TREE_DEPTH = 8


def _exe_basename_from_pid(pid: int) -> str:
    """Resolve basename do executável via /proc/<pid>/exe."""
    try:
        target = os.readlink(f"/proc/{pid}/exe")
        return os.path.basename(target)
    except (OSError, FileNotFoundError):
        return ""


class XlibBackend:
    """Backend de detecção de janela ativa usando X11 + python-xlib."""

    backend_name: str = "xlib"

    def __init__(self) -> None:
        self._display: Any = None
        self._connected: bool = False
        self._init_attempted: bool = False
        self._focus_gate_active: bool = False
        self._query_failures: int = 0
        self._last_connect_fail: float = float("-inf")
        self._reconnect_pending: bool = False
        self._connect_backoff_sec: float = _RECONNECT_BACKOFF_SEC
        self._connect_fail_warned: bool = False
        self._desacordo_ativo: str | None = None
        # `WindowReaderDiag` e daí para o `StateStore`/`state_full`.
        self.last_failure_reason: str | None = None

    def _sem_leitura(self, motivo: str) -> None:
        """Marca o motivo desta leitura cega (JANELA-CEGA-01)."""
        self.last_failure_reason = motivo

    def conexao_provada(self) -> bool | None:
        """Estado JÁ CONHECIDO da conexão — não tenta conectar (T-01, ONDA0-Z7)."""
        if self._connected:
            return True
        if self._init_attempted:
            return False
        return None

    def _ensure_connected(self) -> bool:
        """Conecta (ou RECONECTA, com backoff) ao display X11."""
        if self._connected:
            return True
        if self._init_attempted and (
            time.monotonic() - self._last_connect_fail < self._connect_backoff_sec
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
            self._connect_backoff_sec = _RECONNECT_BACKOFF_SEC
            self._connect_fail_warned = False
            if self._reconnect_pending:
                self._reconnect_pending = False
                logger.info("x11_reconnected")
            else:
                logger.debug("x11_connected")
        except Exception as exc:
            if not self._connect_fail_warned:
                logger.warning("x11_connect_failed", err=str(exc))
                self._connect_fail_warned = True
            else:
                logger.debug("x11_connect_failed", err=str(exc))
            self._connected = False
            self._last_connect_fail = time.monotonic()
            self._connect_backoff_sec = min(
                self._connect_backoff_sec * 2, _RECONNECT_BACKOFF_MAX_SEC
            )

        return self._connected

    @staticmethod
    def _is_connection_error(exc: Exception) -> bool:
        """Erro de CONEXÃO (display morto) — nunca um BadWindow pontual."""
        try:
            from Xlib.error import ConnectionClosedError
        except Exception:  # pragma: no cover - python-xlib sempre presente
            return isinstance(exc, OSError)
        return isinstance(exc, (ConnectionClosedError, OSError))

    def _drop_connection(self) -> None:
        """Descarta a conexão morta; `_ensure_connected` tenta outra depois."""
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
        self._connect_backoff_sec = _RECONNECT_BACKOFF_SEC
        self._connect_fail_warned = False

    def _logar_desacordo_uma_vez(self, evento: str, **campos: Any) -> None:
        """FOCO-01: 1 log por episódio de desacordo (o poll é de 2 Hz)."""
        if self._desacordo_ativo == evento:
            return
        self._desacordo_ativo = evento
        logger.info(evento, **campos)

    def _janela_do_foco(self, focus_id: int) -> tuple[int, Any, Any] | None:
        """Sobe a árvore X do foco REAL até o primeiro top-level com WM_CLASS."""
        root_id = 0
        with contextlib.suppress(Exception):
            root_id = int(self._display.screen().root.id)

        wid = int(focus_id)
        win = self._display.create_resource_object("window", wid)
        for _ in range(_MAX_TREE_DEPTH):
            if root_id and wid == root_id:
                return None
            wm_class_tuple = None
            with contextlib.suppress(Exception):
                wm_class_tuple = win.get_wm_class()
            if wm_class_tuple:
                return wid, win, wm_class_tuple
            parent = None
            with contextlib.suppress(Exception):
                parent = win.query_tree().parent
            parent_id = getattr(parent, "id", None)
            if parent is None or not parent_id:
                return None
            wid = int(parent_id)
            win = parent
        return None

    def get_active_window_info(self) -> WindowInfo | None:
        """Retorna WindowInfo da janela ativa, ou None se indisponível."""
        if not self._ensure_connected():
            self._sem_leitura(MOTIVO_SEM_CONEXAO)
            return None

        try:
            from Xlib import X

            focus_reply = self._display.get_input_focus()
            self._query_failures = 0
            focus = getattr(focus_reply, "focus", None)
            focus_id = getattr(focus, "id", focus)
            if not isinstance(focus_id, int):
                if not self._focus_gate_active:
                    self._focus_gate_active = True
                    logger.info("x11_focus_gate_sem_id", focus=repr(focus))
                self._sem_leitura(MOTIVO_FOCO_SEM_ID)
                return None
            if focus_id in (X.NONE, X.PointerRoot):
                if not self._focus_gate_active:
                    self._focus_gate_active = True
                    logger.info("x11_focus_gate_no_x_focus", focus=focus_id)
                self._sem_leitura(MOTIVO_SEM_FOCO)
                return None
            self._focus_gate_active = False

            resolvido = self._janela_do_foco(focus_id)
            if resolvido is None:
                self._logar_desacordo_uma_vez(
                    "x11_foco_sem_top_level", focus=focus_id
                )
                self._sem_leitura(MOTIVO_FOCO_SEM_TOP_LEVEL)
                return None
            foco_wid, win, wm_class_tuple = resolvido

            root = self._display.screen().root
            net_active_window = self._display.intern_atom("_NET_ACTIVE_WINDOW")
            net_wm_pid = self._display.intern_atom("_NET_WM_PID")

            prop = root.get_full_property(net_active_window, X.AnyPropertyType)
            net_id = int(prop.value[0]) if (prop is not None and prop.value) else 0
            if net_id != foco_wid:
                self._logar_desacordo_uma_vez(
                    "x11_foco_discorda_do_net_active",
                    focus=foco_wid,
                    net_active=net_id,
                )
                self._sem_leitura(MOTIVO_FOCO_DISCORDA)
                return None
            self._desacordo_ativo = None

            wm_class = wm_class_tuple[1] if len(wm_class_tuple) > 1 else ""

            title = ""
            with contextlib.suppress(Exception):
                title = win.get_wm_name() or ""

            pid = 0
            with contextlib.suppress(Exception):
                pid_prop = win.get_full_property(net_wm_pid, X.AnyPropertyType)
                if pid_prop is not None and pid_prop.value:
                    pid = int(pid_prop.value[0])

            exe_basename = _exe_basename_from_pid(pid) if pid else ""

            self.last_failure_reason = None
            return WindowInfo(
                wm_class=wm_class or "unknown",
                pid=pid,
                app_id="",
                title=title,
                exe_basename=exe_basename,
            )
        except Exception as exc:
            logger.warning("x11_query_failed", err=str(exc))
            self._sem_leitura(MOTIVO_ERRO_DE_CONSULTA)
            self._query_failures += 1
            if (
                self._is_connection_error(exc)
                or self._query_failures >= _MAX_QUERY_FAILURES
            ):
                self._drop_connection()
            return None


__all__ = [
    "MOTIVO_ERRO_DE_CONSULTA",
    "MOTIVO_FOCO_DISCORDA",
    "MOTIVO_FOCO_SEM_ID",
    "MOTIVO_FOCO_SEM_TOP_LEVEL",
    "MOTIVO_SEM_CONEXAO",
    "MOTIVO_SEM_FOCO",
    "XlibBackend",
]
