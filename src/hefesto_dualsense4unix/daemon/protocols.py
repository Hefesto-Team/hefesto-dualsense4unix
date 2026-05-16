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
    _hotkey_manager: Any
    _audio: Any
    _plugins_subsystem: Any

    # Estado interno
    _last_state: ControllerState | None
    _last_auto_mult: float
    _last_auto_change_at: float

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

    def stop(self) -> None:
        """Sinaliza o stop_event para encerrar `run()` graciosamente."""
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


__all__ = ["DaemonProtocol"]
