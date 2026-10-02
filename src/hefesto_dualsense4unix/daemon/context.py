"""DaemonContext — dataclass compartilhado entre subsystems."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from hefesto_dualsense4unix.core.controller import IController
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.state_store import StateStore


@dataclass
class DaemonContext:
    """Container de dependências injetado nos subsystems."""

    controller: IController
    bus: EventBus
    store: StateStore
    config: Any
    executor: ThreadPoolExecutor | None = field(default=None)


__all__ = ["DaemonContext"]
