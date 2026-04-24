"""Subsystem IPC — wrapper do IpcServer para o orquestrador.

Expõe start_ipc() / stop_ipc() como funções utilitárias e implementa
o protocolo Subsystem para integração com o registry.
"""
from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from hefesto.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto.daemon.context import DaemonContext
    from hefesto.daemon.lifecycle import DaemonConfig

logger = get_logger(__name__)


class IpcSubsystem:
    """Subsystem que gerencia o IpcServer do daemon."""

    name = "ipc"
    _server: Any = None

    async def start(self, ctx: DaemonContext) -> None:
        """Inicia o IpcServer usando as dependências do DaemonContext."""
        from hefesto.daemon.ipc_server import IpcServer
        from hefesto.profiles.manager import ProfileManager

        # Daemon é o próprio ctx se tiver atributo daemon; fallback é None.
        daemon = getattr(ctx, "daemon", None)
        manager = ProfileManager(
            controller=ctx.controller,
            store=ctx.store,
            keyboard_device=getattr(daemon, "_keyboard_device", None),
        )
        self._server = IpcServer(
            controller=ctx.controller,
            store=ctx.store,
            profile_manager=manager,
            daemon=daemon,
        )
        await self._server.start()
        logger.info("ipc_subsystem_started")

    async def stop(self) -> None:
        """Para o IpcServer de forma limpa. Idempotente."""
        if self._server is not None:
            with contextlib.suppress(Exception):
                await self._server.stop()
            self._server = None
            logger.info("ipc_subsystem_stopped")

    def is_enabled(self, config: DaemonConfig) -> bool:
        return config.ipc_enabled


async def start_ipc(daemon: Any) -> None:
    """Função utilitária: inicia o IpcServer usando o Daemon diretamente.

    Mantida para compatibilidade com código que chame start_ipc(daemon)
    em vez de usar o subsystem registry.
    """
    from hefesto.daemon.ipc_server import IpcServer
    from hefesto.profiles.manager import ProfileManager

    manager = ProfileManager(controller=daemon.controller, store=daemon.store)
    daemon._ipc_server = IpcServer(
        controller=daemon.controller,
        store=daemon.store,
        profile_manager=manager,
        daemon=daemon,
    )
    await daemon._ipc_server.start()


async def stop_ipc(daemon: Any) -> None:
    """Função utilitária: para o IpcServer do Daemon."""
    if daemon._ipc_server is not None:
        with contextlib.suppress(Exception):
            await daemon._ipc_server.stop()
        daemon._ipc_server = None


__all__ = ["IpcSubsystem", "start_ipc", "stop_ipc"]
