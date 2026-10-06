"""Protocols estruturais para o Daemon e seus handlers/subsystems."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Literal, Protocol, TypeVar

if TYPE_CHECKING:
    from hefesto_dualsense4unix.core.controller import ControllerState, IController
    from hefesto_dualsense4unix.core.events import EventBus
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
    from hefesto_dualsense4unix.daemon.state_store import StateStore

_T = TypeVar("_T")

PortaQueGrava = Literal["ipc", "controle"]

GravaOModo = Literal[False, "ipc", "controle"]


class DaemonProtocol(Protocol):
    """Superfície pública/privada do Daemon usada por handlers e subsystems."""

    controller: IController
    bus: EventBus
    store: StateStore
    config: DaemonConfig

    _stop_event: asyncio.Event | None
    _executor: ThreadPoolExecutor | None
    _external_executor: ThreadPoolExecutor | None
    _tasks: list[asyncio.Task[Any]]
    _reconnect_task: asyncio.Task[Any] | None

    _ipc_server: Any
    _udp_server: Any
    _autoswitch: Any
    _mouse_device: Any
    _keyboard_device: Any
    _gamepad_device: Any
    _motion_reader: Any
    _hidraw_broker_client: Any
    _hidraw_broker_executor: Any
    _coop_manager: Any
    _hotkey_manager: Any
    _audio: Any
    _plugins_subsystem: Any

    _last_state: ControllerState | None
    _last_auto_mult: float
    _last_auto_change_at: float
    _input_ready_at: float
    _last_rebackend_ts: float
    _paused: bool
    _emulation_suppressed: bool
    _suppress_manual_ts: float
    _suppress_from_profile: bool
    _failed_subsystems: dict[str, str]
    _bt_mic_subsystem: Any
    _registro_de_gatilhos: Any
    _sentinela_de_escritor_cru: Any
    _cartorio_do_nascimento: Any
    _vigia_do_sequestro: Any

    _osk_controller: Any
    _touchpad_reader: Any
    _cursor_do_toque: Any

    async def _run_blocking(self, fn: Callable[..., _T], *args: Any) -> _T:
        """Executa `fn` no executor compartilhado, mantendo a loop GTK livre."""
        ...

    def _is_stopping(self) -> bool:
        """True se `stop()` já foi chamado e a shutdown está em andamento."""
        ...

    def _arm_input_grace(self) -> None:
        """Rearma o settling/grace pós-conexão (BUG-DAEMON-CONNECT-GHOST-INPUT-01)."""
        ...

    def stop(self) -> None:
        """Sinaliza o stop_event para encerrar `run()` graciosamente."""
        ...

    def pause(self) -> None:
        """Pausa o despacho de input em runtime (FEAT-DAEMON-PAUSE-RESUME-01)."""
        ...

    def resume(self) -> None:
        """Retoma o despacho de input em runtime."""
        ...

    def is_paused(self) -> bool:
        """True se o despacho de input está pausado."""
        ...

    def reload_config(self, new_config: DaemonConfig) -> None:
        """Substitui a config em runtime (usado pelo IPC `daemon.set_config`)."""
        ...

    def set_mouse_emulation(
        self,
        enabled: bool,
        speed: int | None = None,
        scroll_speed: int | None = None,
        *,
        origin: Literal["manual", "profile"],
    ) -> bool:
        """Liga/desliga emulação de mouse e ajusta velocidades."""
        ...

    def set_mouse_speed(
        self,
        speed: int | None = None,
        scroll_speed: int | None = None,
    ) -> bool:
        """Ajusta velocidades SEM ligar/desligar a emulação (BUG-MOUSE-GUI-SYNC-01)."""
        ...

    def set_keyboard_emulation(self, enabled: bool, *, persist: bool = True) -> bool:
        """Liga/desliga a emulação de TECLADO (EMULACAO-NO-JOGO-01).

        Desligar destrói o device virtual (o gate do poll loop fecha por
        consequência) e persiste a escolha em `keyboard_emulation.flag`, salvo
        `persist=False` (restore de boot / testes). Retorna o estado efetivo.
        """
        ...

    def set_gamepad_emulation(
        self,
        enabled: bool,
        flavor: str | None = None,
        *,
        origin: Literal["manual", "profile"],
        caminho: str | None = None,
        caminho_e_escolha: bool = True,
        grava_o_modo: GravaOModo = False,
    ) -> bool:
        """Liga/desliga o gamepad virtual e define a máscara (FEAT-DSX-GAMEPAD-FLAVOR-01)."""
        ...

    def set_coop_enabled(
        self, enabled: bool, *, origin: Literal["manual", "profile"]
    ) -> bool:
        """Liga/desliga o co-op local (FEAT-DSX-COOP-LOCAL-01)."""
        ...

    def set_emulation_suppressed(self, value: bool | None = None) -> bool:
        """Alterna/define a supressão da emulação mouse/teclado (modo jogo)."""
        ...

    def apply_profile_suppression(
        self, desired: bool, *, profile: Any | None = None, origin: str = "autoswitch"
    ) -> str:
        """Aplica `suppress_desktop_emulation` de um perfil (FEAT-POINT-AND-CLICK-01)."""
        ...

    def aplicar_o_arranjo_do_desktop(
        self,
        *,
        origin: str = "manual",
        grava_o_modo: GravaOModo = False,
    ) -> dict[str, str]:
        """O modo Navegação carregando o PERFIL ATIVO (POINT-AND-CLICK-01).

        Mouse, `key_bindings`, `button_actions`, `teclado_emulado` e a queda da
        supressão — as cinco coisas que a aba Navegação grava e que o
        `mouse.emulation.restore` descartava, porque ele lê a flag de sessão da
        máquina e não abre perfil nenhum.

        Entrar na Navegação LIGA o mouse, pelas duas portas (o chip e o PS +
        R3), com as velocidades do perfil (D-2909-A-NAVEGACAO-LIGA-O-MOUSE,
        O-MOUSE-SEGUE-A-NAVEGACAO-01); o socorro `forcar_mouse` saiu com ela.

        `grava_o_modo`: a porta da escolha do usuário; o modo `desktop` vai ao
        perfil ativo depois do arranjo, e o `mouse.enabled` que a entrada
        ligou vai na mesma gravação (O-MODO-SE-GRAVA-ONDE-ELE-MUDA-01).

        Devolve `seção → estado` no vocabulário de `apply_profile_suppression`.
        Declarado aqui porque o GESTO o chama — o `hotkey.py` fala com o daemon
        por este Protocol, e sem a linha o mypy reprovaria a chamada.
        """
        ...

    def definir_o_status_da_navegacao(
        self,
        ligado: bool,
        *,
        origin: Literal["manual", "profile"],
        grava: GravaOModo = False,
    ) -> dict[str, Any]:
        """O «Status do Modo» da aba Navegação: o mouse, depois o teclado.

        Com `grava`, ``mouse.enabled`` e ``teclado_emulado`` vão ao perfil
        ativo numa gravação só, depois do aparelho
        (O-MOUSE-SEGUE-A-NAVEGACAO-01). O `desktop.status.set` o chama.
        """
        ...

    def is_native_mode(self) -> bool:
        """True se o Modo Nativo está ativo (FEAT-NATIVE-MODE-01)."""
        ...

    def set_native_mode(
        self,
        enabled: bool,
        *,
        reapply: bool = True,
        origin: Literal["manual", "profile", "exclusão"],
        grava_o_modo: GravaOModo = False,
    ) -> bool:
        """Liga/desliga o Modo Nativo — solta o controle para o jogo nativo."""
        ...

    def apply_profile_mouse(
        self,
        enabled: bool,
        speed: int | None,
        scroll_speed: int | None,
        *,
        origin: str = "autoswitch",
        profile: Any | None = None,
    ) -> str:
        """Aplica a seção `mouse` de um perfil (BUG-PROFILE-MOUSE-KILLS-GAMEPAD-01)."""
        ...

    def apply_profile_mode(
        self, mode: Any | None, *, profile: Any | None = None, origin: str = "autoswitch"
    ) -> str:
        """Aplica a seção `mode` de um perfil (FEAT-PROFILE-MODE-01)."""
        ...

    def apply_profile_speaker(
        self,
        volume: int,
        muted: bool = False,
        *,
        uniq: str | None = None,
        origin: str = "autoswitch",
        rota: int | None = None,
    ) -> str:
        """Aplica a seção `speaker` de um perfil (SOM-02/E4)."""
        ...


__all__ = ["DaemonProtocol", "GravaOModo", "PortaQueGrava"]
