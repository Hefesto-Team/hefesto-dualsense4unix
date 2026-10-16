"""Partida do UdpServer do daemon (a parada mora na lista de `subsystems/__init__.py`)."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol

logger = get_logger(__name__)


def _numeros_do_daemon(daemon: Any) -> Callable[[], Mapping[str, int]] | None:
    """Quem é cada jogador da mesa, pela fonte única do co-op (`numeros_de_jogador`)."""
    if daemon is None:
        return None
    from hefesto_dualsense4unix.daemon.subsystems.coop import get_coop_manager

    return lambda: get_coop_manager(daemon).numeros_de_jogador()


async def start_udp(daemon: DaemonProtocol) -> None:
    """Função utilitária: inicia o UdpServer usando o Daemon diretamente."""
    from hefesto_dualsense4unix.daemon.udp_server import UdpServer

    daemon._udp_server = UdpServer(
        controller=daemon.controller,
        store=daemon.store,
        host=daemon.config.udp_host,
        port=daemon.config.udp_port,
        jogadores=_numeros_do_daemon(daemon),
    )
    try:
        await daemon._udp_server.start()
    except OSError as exc:
        logger.warning("udp_server_bind_failed", err=str(exc))
        daemon._udp_server = None


__all__ = ["start_udp"]
