"""Partida do IpcServer do daemon (a parada mora na lista de `subsystems/__init__.py`)."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol

logger = get_logger(__name__)


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
    _o_hub_vigia_desde_o_arranque(daemon._ipc_server)


def _o_hub_vigia_desde_o_arranque(servidor: Any) -> None:
    """O hub de sensores vigia desde o arranque, com a interface fechada.

    Sem ele, o touchpad Desligado do perfil e o grab do jogo com máscara DualSense esperariam
    alguém abrir a tela ou rotear o giro: ninguém chamaria o ``reconciliar`` que vê o jogo.
    O modo FAKE (testes, CI) não abre os nós de verdade.
    """
    if os.environ.get("HEFESTO_DUALSENSE4UNIX_FAKE") == "1":
        return
    garantir = getattr(servidor, "_garantir_sensor_hub", None)
    vigiar = getattr(garantir(), "vigiar", None) if callable(garantir) else None
    if not callable(vigiar):
        return
    try:
        vigiar()
    except Exception as exc:
        logger.warning("sensor_hub_vigia_falhou", erro=str(exc))


__all__ = ["start_ipc"]
