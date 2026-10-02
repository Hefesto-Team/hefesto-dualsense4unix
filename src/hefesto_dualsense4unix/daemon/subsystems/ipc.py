"""Subsystem IPC — wrapper do IpcServer para o orquestrador."""
from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.context import DaemonContext
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol

logger = get_logger(__name__)


class IpcSubsystem:
    """Subsystem que gerencia o IpcServer do daemon."""

    name = "ipc"
    _server: Any = None

    async def start(self, ctx: DaemonContext) -> None:
        """Inicia o IpcServer usando as dependências do DaemonContext."""
        from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
        from hefesto_dualsense4unix.profiles.manager import gerente_do_daemon

        daemon = getattr(ctx, "daemon", None)
        manager = gerente_do_daemon(daemon, controller=ctx.controller, store=ctx.store)
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


async def start_ipc(daemon: DaemonProtocol) -> None:
    """Função utilitária: inicia o IpcServer usando o Daemon diretamente."""
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
    from hefesto_dualsense4unix.profiles.manager import gerente_do_daemon

    manager = gerente_do_daemon(daemon, store=daemon.store)
    daemon._ipc_server = IpcServer(
        controller=daemon.controller,
        store=daemon.store,
        profile_manager=manager,
        daemon=daemon,
    )
    await daemon._ipc_server.start()


__all__ = ["IpcSubsystem", "start_ipc"]
