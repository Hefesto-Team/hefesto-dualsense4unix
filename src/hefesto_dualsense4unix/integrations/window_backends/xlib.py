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

#: JANELA-CEGA-01 (28/07): os SEIS motivos distintos pelos quais este backend
#: devolve `None`. Antes colapsavam todos no mesmo `None` — e "sem foco X"
#: (normal: app Wayland nativo em foco) ficava indistinguível de "backend
#: morto" (grave: XWayland caiu). Publicados em `last_failure_reason`.
MOTIVO_SEM_CONEXAO = "sem_conexao_x"
MOTIVO_FOCO_SEM_ID = "foco_sem_id"
MOTIVO_SEM_FOCO = "sem_foco_x"
MOTIVO_FOCO_SEM_TOP_LEVEL = "foco_sem_top_level"
MOTIVO_FOCO_DISCORDA = "foco_discorda_do_net_active"
MOTIVO_ERRO_DE_CONSULTA = "erro_de_consulta"

#: FOCO-01 (auditoria 24/07): profundidade máxima da subida na árvore X, do
#: `focus` de `get_input_focus()` até o primeiro top-level com `WM_CLASS`. O
#: foco quase nunca está NO top-level: ele fica numa janela-filha (a área de
#: cliente do toolkit) e/ou dentro do frame que o WM reparenta por cima. Dois
#: níveis bastam no caso normal; 8 dá folga para toolkits que empilham mais e
#: ainda limita o custo do passeio no tick de 2 Hz (e barra ciclo patológico).
_MAX_TREE_DEPTH = 8


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
        # FOCO-01: episódio de DESACORDO entre o foco real e o
        # `_NET_ACTIVE_WINDOW` (ou de foco sem top-level identificável) em
        # curso — guarda o nome do evento para logar 1x por episódio, no mesmo
        # padrão do gate UX-02 (o poll do autoswitch chama a 2 Hz).
        self._desacordo_ativo: str | None = None
        # JANELA-CEGA-01: motivo da ÚLTIMA chamada que devolveu None (um dos
        # MOTIVO_* acima); None depois de uma leitura bem-sucedida. Lido pelo
        # `WindowReaderDiag` e daí para o `StateStore`/`state_full`.
        self.last_failure_reason: str | None = None

    def _sem_leitura(self, motivo: str) -> None:
        """Marca o motivo desta leitura cega (JANELA-CEGA-01)."""
        self.last_failure_reason = motivo

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

    def _logar_desacordo_uma_vez(self, evento: str, **campos: Any) -> None:
        """FOCO-01: 1 log por episódio de desacordo (o poll é de 2 Hz).

        Mesmo padrão do `_focus_gate_active` do UX-02: o episódio é a
        SEQUÊNCIA de ticks com o mesmo motivo; motivo diferente (ou uma leitura
        boa, que zera o estado) reabre o log.
        """
        if self._desacordo_ativo == evento:
            return
        self._desacordo_ativo = evento
        logger.info(evento, **campos)

    def _janela_do_foco(self, focus_id: int) -> tuple[int, Any, Any] | None:
        """Sobe a árvore X do foco REAL até o primeiro top-level com WM_CLASS.

        FOCO-01 (auditoria 24/07). O gate UX-02 já perguntava ao servidor X
        QUEM tem o foco — mas o DADO (wm_class/título/pid) continuava vindo do
        `_NET_ACTIVE_WINDOW`, a propriedade que o próprio UX-02 documentou como
        rançosa no cosmic-comp. A correção parou no gate e não chegou ao dado, e
        o resultado foi medido ao vivo: com a GUI do Hefesto em foco e nenhuma
        janela Steam à frente, `get_input_focus()` devolvia 35651599 (sem
        WM_CLASS) enquanto o `_NET_ACTIVE_WINDOW` dizia 44040223 (`steam`) — as
        duas fontes DISCORDAM, e era a rançosa que o autoswitch obedecia (o
        ping-pong `vitoria``Navegação` a cada 18-28 s do journal de 22-23/07).

        O foco quase nunca está NO top-level: o servidor X entrega o foco à
        janela-filha do toolkit, dentro do frame que o WM reparenta. Por isso
        sobe-se a árvore (`query_tree().parent`) até achar quem tem `WM_CLASS` —
        essa é a janela de CLIENTE, a mesma entidade que o `_NET_ACTIVE_WINDOW`
        aponta quando não está rançoso, o que torna os dois ids comparáveis.

        Devolve `(id, janela, wm_class_tuple)` ou None quando a subida esgota a
        árvore (chegou à raiz / sem pai / profundidade máxima) sem achar
        WM_CLASS nenhum — "não sei qual janela é" é resposta honesta, e a
        histerese UX-01 do autoswitch retém o perfil corrente nesse caso.
        """
        root_id = 0
        with contextlib.suppress(Exception):
            root_id = int(self._display.screen().root.id)

        wid = int(focus_id)
        win = self._display.create_resource_object("window", wid)
        for _ in range(_MAX_TREE_DEPTH):
            if root_id and wid == root_id:
                # A raiz não é janela de aplicação nenhuma.
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
        """Retorna WindowInfo da janela ativa, ou None se indisponível.

        JANELA-CEGA-01: todo caminho que devolve None carimba antes o
        `last_failure_reason` correspondente; o caminho feliz o limpa.
        """
        if not self._ensure_connected():
            self._sem_leitura(MOTIVO_SEM_CONEXAO)
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
            # `None` NÃO é pego pelo teste abaixo (`None not in (0, 1)`), então
            # vazaria inteiro para o `_janela_do_foco`, que espera um id. Sem
            # foco é sem foco, venha como X.NONE ou como ausência do atributo.
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

            # FOCO-01: o DADO passa a vir da janela do foco REAL, não da
            # propriedade rançosa. Sem isto o gate acima só evitava o pior caso
            # (nenhum foco X); com foco X válido numa janela QUALQUER, o
            # autoswitch ainda lia a wm_class de outra — foi assim que o foco na
            # nossa própria GUI virou "steam em foco" e o ping-pong de perfis
            # trocou lightbar/gatilhos/rumble a cada 18-28 s.
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
            # Discordância entre as duas fontes = NÃO SEI (None), nunca "confia
            # na rançosa". `net_id == 0` (propriedade ausente/zerada) cai aqui
            # pelo mesmo caminho, preservando o comportamento histórico de
            # degradar para None sem corroboração. O reader vira 'unknown' e a
            # histerese UX-01 retém o perfil corrente — a lição de sempre: o
            # certo é reter, não adivinhar no meio da partida.
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


__all__ = [
    "MOTIVO_ERRO_DE_CONSULTA",
    "MOTIVO_FOCO_DISCORDA",
    "MOTIVO_FOCO_SEM_ID",
    "MOTIVO_FOCO_SEM_TOP_LEVEL",
    "MOTIVO_SEM_CONEXAO",
    "MOTIVO_SEM_FOCO",
    "XlibBackend",
]
