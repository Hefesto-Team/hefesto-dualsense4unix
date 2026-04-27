"""Protocol Subsystem — interface mínima para subsystems do daemon.

Cada subsystem deve implementar start(), stop() e is_enabled().
O atributo `name` identifica o subsystem nos logs.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.context import DaemonContext
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig


@runtime_checkable
class Subsystem(Protocol):
    """Interface mínima que todo subsystem do daemon deve satisfazer."""

    name: str

    async def start(self, ctx: DaemonContext) -> None:
        """Inicia o subsystem com o contexto fornecido."""
        ...

    async def stop(self) -> None:
        """Para o subsystem de forma limpa e idempotente."""
        ...

    def is_enabled(self, config: DaemonConfig) -> bool:
        """Retorna True se o subsystem deve ser ativado com a config atual."""
        ...


__all__ = ["Subsystem"]
