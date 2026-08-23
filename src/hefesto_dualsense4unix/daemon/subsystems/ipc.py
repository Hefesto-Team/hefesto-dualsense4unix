"""Subsystem IPC — wrapper do IpcServer para o orquestrador.

Expõe start_ipc() / stop_ipc() como funções utilitárias e implementa
o protocolo Subsystem para integração com o registry.
"""
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

        # Daemon é o próprio ctx se tiver atributo daemon; fallback é None.
        daemon = getattr(ctx, "daemon", None)
        # A-FÁBRICA-COM-UM-CLIENTE-01 (22/08/2026): a lista de appliers vem da
        # FÁBRICA, não de sete linhas repetidas aqui. Applier ausente não
        # levanta — a seção é ignorada em silêncio, e foi assim que a rota da
        # saída do Modo Nativo passou semanas sem o `rumble.passthrough`. O
        # `controller`/`store` vêm por fora porque esta rota sobe pelo
        # `DaemonContext`, e o `daemon` pode ser `None`.
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
    """Função utilitária: inicia o IpcServer usando o Daemon diretamente.

    Mantida para compatibilidade com código que chame start_ipc(daemon)
    em vez de usar o subsystem registry.
    """
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
    from hefesto_dualsense4unix.profiles.manager import gerente_do_daemon

    # A-FÁBRICA-COM-UM-CLIENTE-01: idem `IpcSubsystem.start` — as DUAS rotas de
    # subida do IPC tiram a lista de appliers da mesma fábrica, e é isso que
    # impede uma delas de derivar da outra em silêncio.
    manager = gerente_do_daemon(daemon, store=daemon.store)
    daemon._ipc_server = IpcServer(
        controller=daemon.controller,
        store=daemon.store,
        profile_manager=manager,
        daemon=daemon,
    )
    await daemon._ipc_server.start()


async def stop_ipc(daemon: DaemonProtocol) -> None:
    """Função utilitária: para o IpcServer do Daemon."""
    if daemon._ipc_server is not None:
        with contextlib.suppress(Exception):
            await daemon._ipc_server.stop()
        daemon._ipc_server = None


__all__ = ["IpcSubsystem", "start_ipc", "stop_ipc"]
