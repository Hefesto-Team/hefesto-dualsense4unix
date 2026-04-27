"""Subsystem UDP — wrapper do UdpServer para o orquestrador.

Expõe start_udp() / stop_udp() como funções utilitárias e implementa
o protocolo Subsystem para integração com o registry.
"""
from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.context import DaemonContext
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

logger = get_logger(__name__)


class UdpSubsystem:
    """Subsystem que gerencia o UdpServer do daemon."""

    name = "udp"
    _server: Any = None

    async def start(self, ctx: DaemonContext) -> None:
        """Inicia o UdpServer usando as dependências do DaemonContext."""
        from hefesto_dualsense4unix.daemon.udp_server import UdpServer

        cfg = ctx.config
        self._server = UdpServer(
            controller=ctx.controller,
            store=ctx.store,
            host=cfg.udp_host,
            port=cfg.udp_port,
        )
        try:
            await self._server.start()
            logger.info("udp_subsystem_started", host=cfg.udp_host, port=cfg.udp_port)
        except OSError as exc:
            logger.warning("udp_subsystem_bind_failed", err=str(exc))
            self._server = None

    async def stop(self) -> None:
        """Para o UdpServer de forma limpa. Idempotente."""
        if self._server is not None:
            with contextlib.suppress(Exception):
                await self._server.stop()
            self._server = None
            logger.info("udp_subsystem_stopped")

    def is_enabled(self, config: DaemonConfig) -> bool:
        return config.udp_enabled


async def start_udp(daemon: Any) -> None:
    """Função utilitária: inicia o UdpServer usando o Daemon diretamente."""
    from hefesto_dualsense4unix.daemon.udp_server import UdpServer

    daemon._udp_server = UdpServer(
        controller=daemon.controller,
        store=daemon.store,
        host=daemon.config.udp_host,
        port=daemon.config.udp_port,
    )
    try:
        await daemon._udp_server.start()
    except OSError as exc:
        logger.warning("udp_server_bind_failed", err=str(exc))
        daemon._udp_server = None


async def stop_udp(daemon: Any) -> None:
    """Função utilitária: para o UdpServer do Daemon."""
    if daemon._udp_server is not None:
        with contextlib.suppress(Exception):
            await daemon._udp_server.stop()
        daemon._udp_server = None


__all__ = ["UdpSubsystem", "start_udp", "stop_udp"]
