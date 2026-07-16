"""Protocols estruturais para o Daemon e seus handlers/subsystems.

PYDANTIC-PROTOCOL-DAEMON-01: até v3.1.1 todas as funções top-level em
`daemon/connection.py`, `daemon/subsystems/*.py` e os handlers de IPC
declaravam o argumento `daemon` como `Any` para evitar import cycle
(eles são importados *de dentro* de `daemon/lifecycle.py`).

Esse Protocol descreve a superfície da classe `Daemon` que esses módulos
realmente tocam. Substituindo `daemon: Any` por `daemon: DaemonProtocol`
recuperamos validação estática (mypy --strict + IDE autocomplete) sem
forçar import circular.

A classe concreta `Daemon` (dataclass em `daemon/lifecycle.py`) satisfaz
o Protocol estruturalmente — Python valida em tempo de checagem, não em
runtime. Se algum atributo desaparecer da `Daemon`, mypy aponta no
primeiro arquivo que tentar lê-lo.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Protocol, TypeVar

if TYPE_CHECKING:
    from hefesto_dualsense4unix.core.controller import ControllerState, IController
    from hefesto_dualsense4unix.core.events import EventBus
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
    from hefesto_dualsense4unix.daemon.state_store import StateStore

_T = TypeVar("_T")


class DaemonProtocol(Protocol):
    """Superfície pública/privada do Daemon usada por handlers e subsystems.

    Os atributos com sufixo `_` continuam acessíveis: o Protocol descreve
    contrato estrutural, não enforce de encapsulamento. Refactors futuros
    podem migrar tudo para getters/setters sem mudar quem consome.
    """

    # Componentes injetados
    controller: IController
    bus: EventBus
    store: StateStore
    config: DaemonConfig

    # Ciclo de vida
    _stop_event: asyncio.Event | None
    _executor: ThreadPoolExecutor | None
    _tasks: list[asyncio.Task[Any]]
    _reconnect_task: asyncio.Task[Any] | None

    # Subsystems opt-in
    _ipc_server: Any
    _udp_server: Any
    _autoswitch: Any
    _mouse_device: Any
    _keyboard_device: Any
    # FEAT-DSX-GAMEPAD-FLAVOR-01: gamepad virtual (`integrations.virtual_pad.
    # VirtualPad` — uhid ou uinput, ver `make_virtual_pad`) ou None.
    _gamepad_device: Any
    # FEAT-DSX-COOP-LOCAL-01: CoopManager (jogadores secundários) ou None.
    _coop_manager: Any
    _hotkey_manager: Any
    _audio: Any
    _plugins_subsystem: Any

    # Estado interno
    _last_state: ControllerState | None
    _last_auto_mult: float
    _last_auto_change_at: float
    # BUG-DAEMON-CONNECT-GHOST-INPUT-01: instante a partir do qual o input
    # emulado volta a ser despachado após (re)conexão (settling/grace).
    _input_ready_at: float
    # VPAD-01/VPAD-02: instante (time.monotonic) da última tentativa de
    # rebackend do vpad do P1 (uinput→uhid); -inf = nunca. Cooldown único
    # compartilhado entre a promoção do hotplug e a re-seleção pela GUI.
    _last_rebackend_ts: float
    # FEAT-DAEMON-PAUSE-RESUME-01: despacho de input pausado (daemon vivo).
    _paused: bool
    # FEAT-EMULATION-GAMEMODE-LONGPRESS-01: modo jogo — emulacao mouse/teclado
    # suprimida (devices vivos, hotkeys ativos).
    _emulation_suppressed: bool
    # FEAT-POINT-AND-CLICK-01: instante do último toggle MANUAL do modo-jogo
    # (-inf = nunca) e origem da supressão atual (True = veio de perfil).
    _suppress_manual_ts: float
    _suppress_from_profile: bool
    # FEAT-DAEMON-RESILIENT-SUBSYSTEMS-01: subsystems que falharam ao iniciar.
    _failed_subsystems: dict[str, str]

    # FEAT-KEYBOARD-EMULATOR-01: attrs adicionados em runtime pelo subsystem
    # keyboard (OSK + touchpad reader). Declarados aqui para mypy strict.
    _osk_controller: Any
    _touchpad_reader: Any

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

    def set_gamepad_emulation(self, enabled: bool, flavor: str | None = None) -> bool:
        """Liga/desliga o gamepad virtual e define a máscara (FEAT-DSX-GAMEPAD-FLAVOR-01)."""
        ...

    def set_coop_enabled(self, enabled: bool) -> bool:
        """Liga/desliga o co-op local (FEAT-DSX-COOP-LOCAL-01)."""
        ...

    def set_emulation_suppressed(self, value: bool | None = None) -> bool:
        """Alterna/define a supressão da emulação mouse/teclado (modo jogo).

        FEAT-EMULATION-GAMEMODE-LONGPRESS-01. `value=None` faz toggle. Retorna o
        novo estado (True = suprimida).
        """
        ...

    def apply_profile_suppression(self, desired: bool) -> None:
        """Aplica `suppress_desktop_emulation` de um perfil (FEAT-POINT-AND-CLICK-01).

        Respeita o toggle manual recente (janela de MANUAL_PROFILE_LOCK_SEC) e
        só libera supressão que veio de perfil. Injetado como
        `suppression_applier` do ProfileManager pelos callsites.
        """
        ...

    def is_native_mode(self) -> bool:
        """True se o Modo Nativo está ativo (FEAT-NATIVE-MODE-01)."""
        ...

    def set_native_mode(self, enabled: bool, *, reapply: bool = True) -> bool:
        """Liga/desliga o Modo Nativo — solta o controle para o jogo nativo."""
        ...

    def apply_profile_mouse(
        self, enabled: bool, speed: int, scroll_speed: int
    ) -> None:
        """Aplica a seção `mouse` de um perfil (BUG-PROFILE-MOUSE-KILLS-GAMEPAD-01).

        Respeita o lock manual recente da emulação (não sequestra um gamepad
        ligado na mão) e é idempotente. Injetado como `mouse_applier` do
        ProfileManager nas rotas de ativação (IPC switch, autoswitch, hotkey).
        """
        ...

    def apply_profile_mode(self, mode: Any | None) -> None:
        """Aplica a seção `mode` de um perfil (FEAT-PROFILE-MODE-01).

        Nativo/gamepad/desktop + co-op por perfil, com lock manual de 30s e
        origem rastreada. Injetado como `mode_applier` do ProfileManager nas
        rotas de ativação (IPC switch, autoswitch, hotkey).
        """
        ...


__all__ = ["DaemonProtocol"]
