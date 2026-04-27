"""DaemonContext — dataclass compartilhado entre subsystems.

Expõe os recursos centrais do daemon (controller, bus, store, config,
executor) para que cada subsystem possa operar sem acesso direto ao
objeto Daemon completo, preservando isolamento de módulos.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from hefesto_dualsense4unix.core.controller import IController
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.state_store import StateStore


@dataclass
class DaemonContext:
    """Container de dependências injetado nos subsystems.

    Atributos:
        controller: IController conectado ao hardware.
        bus: EventBus global de eventos.
        store: StateStore global.
        config: DaemonConfig atual (substituído in-place em reload_config).
        executor: ThreadPoolExecutor dedicado para chamadas síncronas de HID.
    """

    controller: IController
    bus: EventBus
    store: StateStore
    config: Any  # DaemonConfig — importação lazy para evitar circular
    executor: ThreadPoolExecutor | None = field(default=None)


__all__ = ["DaemonContext"]
