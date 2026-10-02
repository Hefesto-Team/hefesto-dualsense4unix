"""Detecção de janela ativa com seleção automática de backend.

`detect_window_backend()` escolhe o backend adequado conforme as variáveis
de ambiente do compositor:

  WAYLAND_DISPLAY + DISPLAY  → _XlibComCosmicBackend (XWayland + Wayland nativo)
  WAYLAND_DISPLAY sem DISPLAY → _WaylandCascadeBackend (cosmic → portal → wlrctl)
  DISPLAY sem WAYLAND_DISPLAY → XlibBackend
  Nenhum                      → NullBackend    (loga autoswitch_compositor_unsupported)

Função `get_active_window_info()` mantém compatibilidade com a API legada de
`xlib_window.py`: retorna `dict[str, Any]` com chaves `wm_class`, `wm_name`,
`pid`, `exe_basename`.

BUG-COSMIC-WLR-BACKEND-REGRESSION-01 (v3.1.0): re-introduz o cascade
portal → wlrctl perdido no rebrand Hefesto → Hefesto - DualSense4Unix.
O portal XDG é canônico onde existe (GNOME 46+); o `WlrctlBackend` cobre o
bloco wlroots (Sway, Hyprland, niri, river) via
`wlr-foreign-toplevel-management-unstable-v1`.

FATO SUBSTITUÍDO — 02/09/2026, e ele estava escrito aqui e no `wlr_toplevel.py`:
este cabeçalho dizia que o `wlrctl` *"funciona em COSMIC"*, e mais abaixo que a
cascata Wayland *"funciona no COSMIC via wlrctl"*. **É falso, e a medição é
direta:** dos 58 globais que o cosmic-comp 0.1 desta máquina publica, o
`zwlr_foreign_toplevel_manager_v1` **não está entre eles** — por isso o wlrctl
instalado responde *"Foreign Toplevel Management interface not found"*. O que
está entre eles é o `zcosmic_toplevel_info_v1` (versão 3), e é dele que fala o
`CosmicToplevelBackend`, primeiro da cascata.

JANELA-WAYLAND-CEGA-01 (02/09/2026): em XWayland, o backend deixa de ser só o
`xlib`. Ele continua PREFERIDO — é o único que resolve `exe_basename` —, mas
quando ele não enxerga (um app Wayland nativo em foco: `sem_foco_x`), a leitura
passa para o `cosmic`, em vez de virar `unknown`. Medido na sessão dela: com o
Chrome/Wayland em foco, o produto lia `wm_class="unknown"` e o
`zcosmic_toplevel_info_v1` lia `google-chrome`, no mesmo instante.
"""
from __future__ import annotations

import os
from typing import Any

from hefesto_dualsense4unix.integrations.window_backends.base import WindowBackend, WindowInfo
from hefesto_dualsense4unix.integrations.window_backends.null import NullBackend
from hefesto_dualsense4unix.integrations.window_backends.xlib import XlibBackend
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

_unsupported_warned: bool = False

MOTIVO_CASCATA_SEM_LEITURA = "cascata_wayland_sem_leitura"
MOTIVO_JANELA_SEM_CLASSE = "janela_sem_classe"
MOTIVO_BACKEND_SEM_MOTIVO = "backend_sem_motivo"

BACKENDS_QUE_VEEM_O_PROCESSO = frozenset({"xlib"})
BACKENDS_CEGOS_AO_PROCESSO = frozenset({"portal", "wlrctl", "cosmic", "null"})


def backend_ve_nome_do_processo(backend: str | None) -> bool | None:
    """O backend entrega ``exe_basename``? ``None`` = **não dá para saber**."""
    if not isinstance(backend, str) or not backend:
        return None
    if backend in BACKENDS_QUE_VEEM_O_PROCESSO:
        return True
    if backend in BACKENDS_CEGOS_AO_PROCESSO:
        return False
    return None


class _WaylandCascadeBackend:
    """Cascade: cosmic → portal XDG → wlrctl → None."""

    def __init__(self) -> None:
        from hefesto_dualsense4unix.integrations.window_backends.cosmic_toplevel import (
            CosmicToplevelBackend,
        )
        from hefesto_dualsense4unix.integrations.window_backends.wayland_portal import (
            WaylandPortalBackend,
        )
        from hefesto_dualsense4unix.integrations.window_backends.wlr_toplevel import (
            WlrctlBackend,
        )

        self._cosmic = CosmicToplevelBackend()
        self._portal = WaylandPortalBackend()
        self._wlrctl = WlrctlBackend()
        self._fallback_announced: bool = False
        self.last_failure_reason: str | None = None
        self._last_source: str | None = None

    @property
    def backend_name(self) -> str:
        """Backend ativo na cascata: "cosmic" | "portal" | "wlrctl" | "null"."""
        if self._last_source == "cosmic" and self._cosmic.available:
            return "cosmic"
        if self._last_source == "portal" and not self._portal.unsupported:
            return "portal"
        if self._last_source == "wlrctl" and self._wlrctl.available:
            return "wlrctl"
        if self._cosmic.available:
            return "cosmic"
        if not self._portal.unsupported:
            return "portal"
        if self._wlrctl.available:
            return "wlrctl"
        return "null"

    def get_active_window_info(self) -> WindowInfo | None:
        info = self._cosmic.get_active_window_info()
        if info is not None:
            self._last_source = "cosmic"
            self.last_failure_reason = None
            return info

        info = self._portal.get_active_window_info()
        if info is not None:
            self._last_source = "portal"
            self.last_failure_reason = None
            return info

        info = self._wlrctl.get_active_window_info()
        if info is not None:
            self._last_source = "wlrctl"
            self.last_failure_reason = None
            if not self._fallback_announced:
                logger.info(
                    "wayland_backend_fallback_wlrctl",
                    hint=(
                        "portal XDG não respondeu; wlrctl ativo "
                        "(wlr-foreign-toplevel-management)."
                    ),
                )
                self._fallback_announced = True
            return info

        self.last_failure_reason = MOTIVO_CASCATA_SEM_LEITURA
        return None


class _XlibComCosmicBackend:
    """XWayland: o `xlib` na frente, e o Wayland nativo atrás dele."""

    def __init__(self, xlib: WindowBackend, wayland: WindowBackend) -> None:
        self._xlib = xlib
        self._wayland = wayland
        self.last_failure_reason: str | None = None
        self._ultima_fonte: str | None = None
        self._anunciado: bool = False

    @property
    def backend_name(self) -> str:
        """De onde veio a última leitura ÚTIL — "xlib" ou o nome da cascata."""
        if self._ultima_fonte == "wayland":
            nome = getattr(self._wayland, "backend_name", None)
            if isinstance(nome, str) and nome:
                return nome
            return "null"
        return getattr(self._xlib, "backend_name", "xlib")

    @property
    def xlib(self) -> WindowBackend:
        """O backend X11 de dentro — o `WindowReaderDiag` pergunta a saúde a ele."""
        return self._xlib

    def conexao_provada(self) -> bool | None:
        """Delega ao `xlib`: é dele que a pergunta fala (T-01, ONDA0-Z7)."""
        fn = getattr(self._xlib, "conexao_provada", None)
        return fn() if callable(fn) else None

    def get_active_window_info(self) -> WindowInfo | None:
        info = self._xlib.get_active_window_info()
        if info is not None:
            self._ultima_fonte = "xlib"
            self.last_failure_reason = None
            return info

        motivo_do_x = getattr(self._xlib, "last_failure_reason", None)
        info = self._wayland.get_active_window_info()
        if info is not None:
            self._ultima_fonte = "wayland"
            self.last_failure_reason = None
            if not self._anunciado:
                logger.info(
                    "janela_lida_pelo_wayland_nativo",
                    motivo_do_x=motivo_do_x,
                    hint=(
                        "o X não enxergou a janela em foco (app Wayland "
                        "nativo) e a leitura veio do compositor; o nome do "
                        "processo não vem por este caminho."
                    ),
                )
                self._anunciado = True
            return info

        self._ultima_fonte = None
        self.last_failure_reason = (
            motivo_do_x
            or getattr(self._wayland, "last_failure_reason", None)
            or MOTIVO_CASCATA_SEM_LEITURA
        )
        return None


def detect_window_backend() -> WindowBackend:
    """Detecta e retorna o backend mais adequado para o ambiente atual."""
    has_wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    has_x11 = bool(os.environ.get("DISPLAY"))

    if has_x11 and has_wayland:
        logger.debug("window_backend_selected", backend="xlib+wayland", xwayland=True)
        return _XlibComCosmicBackend(XlibBackend(), _WaylandCascadeBackend())

    if has_x11:
        logger.debug("window_backend_selected", backend="xlib", xwayland=False)
        return XlibBackend()

    if has_wayland:
        logger.debug("window_backend_selected", backend="wayland_cascade")
        return _WaylandCascadeBackend()

    global _unsupported_warned
    if not _unsupported_warned:
        logger.warning("autoswitch_compositor_unsupported")
        _unsupported_warned = True
    else:
        logger.debug("autoswitch_compositor_unsupported")
    return NullBackend()


_UNKNOWN_WINDOW: dict[str, Any] = {
    "wm_class": "unknown",
    "wm_name": "",
    "pid": 0,
    "exe_basename": "",
}


def get_active_window_info() -> dict[str, Any]:
    """Retorna dict com informações da janela ativa."""
    backend = detect_window_backend()
    info: WindowInfo | None = backend.get_active_window_info()
    if info is None:
        return dict(_UNKNOWN_WINDOW)
    return info.as_dict()


class WindowReaderDiag:
    """Leitor de janela com diagnóstico de primeira classe."""

    def __init__(self, backend: WindowBackend) -> None:
        self._backend = backend
        self.last_read_useful: bool = False
        self.useful_reads: int = 0
        self.last_useful_class: str | None = None
        self.last_reason: str | None = None

    @property
    def backend_name(self) -> str:
        """Nome do backend ativo; cai no nome da classe se não declarado."""
        name = getattr(self._backend, "backend_name", None)
        if isinstance(name, str) and name:
            return name
        return type(self._backend).__name__.lower()

    def __call__(self) -> dict[str, Any]:
        info: WindowInfo | None = self._backend.get_active_window_info()
        result: dict[str, Any] = (
            dict(_UNKNOWN_WINDOW) if info is None else info.as_dict()
        )
        wm_class = str(result.get("wm_class") or "")
        self.last_read_useful = wm_class not in ("", "unknown")
        if self.last_read_useful:
            self.useful_reads += 1
            self.last_useful_class = wm_class
            self.last_reason = None
        else:
            self.last_reason = self._motivo_da_cegueira(info)
        return result

    def _motivo_da_cegueira(self, info: WindowInfo | None) -> str:
        """Motivo desta leitura não-útil (JANELA-CEGA-01)."""
        motivo = getattr(self._backend, "last_failure_reason", None)
        if isinstance(motivo, str) and motivo:
            return motivo
        if info is not None:
            return MOTIVO_JANELA_SEM_CLASSE
        return MOTIVO_BACKEND_SEM_MOTIVO

    def conexao_provada(self) -> bool | None:
        """Delega a `XlibBackend.conexao_provada` (T-01, ONDA0-Z7)."""
        fn = getattr(self._backend, "conexao_provada", None)
        return fn() if callable(fn) else None

    def _xwayland_morto_com_wayland_vivo(self) -> bool:
        """O backend é `xlib` PURO, a conexão está PROVADA morta, e há Wayland?"""
        if not isinstance(self._backend, XlibBackend):
            return False
        if not os.environ.get("WAYLAND_DISPLAY"):
            return False
        return self._backend.conexao_provada() is False

    def precisa_de_resgate(self) -> bool:
        """O backend atual está cego de um jeito que a re-detecção cura?"""
        if isinstance(self._backend, NullBackend):
            return True
        return self._xwayland_morto_com_wayland_vivo()

    def maybe_recover(self) -> bool:
        """Troca o backend em-place quando o atual está cego e há alternativa.

        AUTOSWITCH-HEAL-01 (22/07): no login o daemon pode nascer ANTES de o
        compositor exportar WAYLAND_DISPLAY/DISPLAY para o systemd --user —
        o backend era fixado em Null UMA vez e o perfil-por-jogo ficava morto
        a sessão inteira (medido: `window_detect_diag_seeded backend=null` no
        boot com o env presente minutos depois). O poll chama este método
        (rate-limitado no chamador) DEPOIS de re-importar o env; quando a
        re-detecção sai do Null, o backend é trocado em-place e o autoswitch
        volta à vida sem restart. Retorna True quando recuperou.

        D-TROCA-DE-PERFIL-CEGA (25/08/2026): o segundo caso é o XWayland
        MORTO numa sessão Wayland (ver `_xwayland_morto_com_wayland_vivo`).
        Aqui NÃO se chama `detect_window_backend()` — ela devolveria `xlib` de
        novo se o env ainda não tiver o `WAYLAND_DISPLAY` que este método
        acabou de ver; o resgate monta o composto direto.

        **A troca DEIXOU de ser de mão única — 02/09/2026.** Ela trocava o
        `xlib` pela cascata Wayland e pronto: quem casava perfil por
        `process_name` perdia o casamento até o próximo start do daemon, mesmo
        que o XWayland ressuscitasse no minuto seguinte. Agora o resgate
        monta o `_XlibComCosmicBackend` com o MESMO `xlib` dentro — ele volta a
        ser o preferido no instante em que voltar a responder, e o
        `exe_basename` volta junto. O que se perde enquanto o X está morto é o
        mesmo de antes (a cascata é cega ao processo), e o
        `window_detect_backend` publicado no `state_full` continua dizendo por
        onde a leitura veio — é o que `backend_ve_nome_do_processo` lê para a
        tela.
        """
        if isinstance(self._backend, NullBackend):
            novo = detect_window_backend()
            if isinstance(novo, NullBackend):
                return False
            self._backend = novo
            return True
        if self._xwayland_morto_com_wayland_vivo():
            self._backend = _XlibComCosmicBackend(self._backend, _WaylandCascadeBackend())
            logger.warning(
                "window_backend_xwayland_morto_resgate_wayland",
                hint=(
                    "o servidor X recusou conexão e a sessão é Wayland; "
                    "a detecção de janela passa a cair para a cascata "
                    "cosmic/portal/wlrctl a cada leitura que o X perder. O "
                    "nome do processo não vem por esse caminho (perfis que "
                    "casam por process_name não entram enquanto durar); "
                    "wm_class e título continuam, e o xlib volta a ser o "
                    "preferido assim que voltar a responder."
                ),
            )
            return True
        return False


def build_window_reader() -> WindowReaderDiag:
    """Cria um leitor de janela com o backend instanciado UMA vez."""
    return WindowReaderDiag(detect_window_backend())


__all__ = [
    "BACKENDS_CEGOS_AO_PROCESSO",
    "BACKENDS_QUE_VEEM_O_PROCESSO",
    "MOTIVO_BACKEND_SEM_MOTIVO",
    "MOTIVO_CASCATA_SEM_LEITURA",
    "MOTIVO_JANELA_SEM_CLASSE",
    "WindowReaderDiag",
    "backend_ve_nome_do_processo",
    "build_window_reader",
    "detect_window_backend",
    "get_active_window_info",
]
