"""Funções de conexão, reconexão e shutdown do daemon.

Extrai lógica de ciclo de vida de conexão do IController para funções
puras que recebem o daemon como argumento, mantendo Daemon.run() slim.
"""
from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from hefesto.core.events import EventTopic
from hefesto.utils.logging_config import get_logger

logger = get_logger(__name__)


async def connect_with_retry(daemon: Any) -> None:
    """Tenta conectar o controller com backoff. Publica CONTROLLER_CONNECTED."""
    backoff = daemon.config.reconnect_backoff_sec
    while True:
        try:
            await daemon._run_blocking(daemon.controller.connect)
            transport = daemon.controller.get_transport()
            daemon.bus.publish(EventTopic.CONTROLLER_CONNECTED, {"transport": transport})
            logger.info("controller_connected", transport=transport)
            return
        except Exception as exc:
            logger.warning("controller_connect_failed", err=str(exc))
            if not daemon.config.auto_reconnect:
                raise
            await asyncio.sleep(backoff)


async def restore_last_profile(daemon: Any) -> None:
    """Reativa o último perfil salvo pelo usuário (FEAT-PERSIST-SESSION-01)."""
    from hefesto.profiles.manager import ProfileManager
    from hefesto.utils.session import load_last_profile

    name = load_last_profile()
    if not name:
        return
    try:
        manager = ProfileManager(controller=daemon.controller, store=daemon.store)
        await daemon._run_blocking(manager.activate, name)
        logger.info("last_profile_restored", name=name)
    except Exception as exc:
        logger.warning("last_profile_restore_failed", name=name, err=str(exc))


async def reconnect(daemon: Any) -> None:
    """Desconecta e tenta reconectar com backoff."""
    with contextlib.suppress(Exception):
        await daemon._run_blocking(daemon.controller.disconnect)
    await asyncio.sleep(daemon.config.reconnect_backoff_sec)
    await connect_with_retry(daemon)


async def shutdown(daemon: Any) -> None:
    """Encerra todos os recursos do daemon de forma limpa."""
    logger.info("daemon_shutting_down")
    # Plugins: stop antes dos outros subsystems (on_unload pode usar controller).
    if daemon._plugins_subsystem is not None:
        with contextlib.suppress(Exception):
            await daemon._plugins_subsystem.stop()
        daemon._plugins_subsystem = None
    daemon._hotkey_manager = None
    daemon._audio = None
    if daemon._mouse_device is not None:
        with contextlib.suppress(Exception):
            daemon._mouse_device.stop()
        daemon._mouse_device = None
    if getattr(daemon, "_keyboard_device", None) is not None:
        with contextlib.suppress(Exception):
            daemon._keyboard_device.stop()
        daemon._keyboard_device = None
    if daemon._ipc_server is not None:
        with contextlib.suppress(Exception):
            await daemon._ipc_server.stop()
        daemon._ipc_server = None
    if daemon._udp_server is not None:
        with contextlib.suppress(Exception):
            await daemon._udp_server.stop()
        daemon._udp_server = None
    if daemon._autoswitch is not None:
        with contextlib.suppress(Exception):
            daemon._autoswitch.stop()
        daemon._autoswitch = None
    for task in daemon._tasks:
        task.cancel()
    for task in daemon._tasks:
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
    try:
        await daemon._run_blocking(daemon.controller.disconnect)
    except Exception as exc:
        logger.warning("controller_disconnect_failed", err=str(exc))
    if daemon._executor is not None:
        daemon._executor.shutdown(wait=False, cancel_futures=True)
        daemon._executor = None
    daemon._tasks.clear()
    logger.info("daemon_stopped")


__all__ = ["connect_with_retry", "reconnect", "restore_last_profile", "shutdown"]
