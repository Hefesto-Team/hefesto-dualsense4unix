"""Subsystem Autoswitch — gerencia troca automática de perfis por janela ativa.

Implementa o protocolo Subsystem e expõe start_autoswitch() / stop_autoswitch()
como funções utilitárias para uso direto pelo Daemon.
"""
from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.context import DaemonContext
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

logger = get_logger(__name__)


class AutoswitchSubsystem:
    """Subsystem que gerencia o AutoSwitcher de perfis."""

    name = "autoswitch"
    _autoswitch: Any = None

    async def start(self, ctx: DaemonContext) -> None:
        """Inicia o AutoSwitcher com as dependências do DaemonContext."""
        from hefesto_dualsense4unix.integrations.xlib_window import get_active_window_info
        from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
        from hefesto_dualsense4unix.profiles.manager import ProfileManager

        manager = ProfileManager(controller=ctx.controller, store=ctx.store)
        self._autoswitch = AutoSwitcher(
            manager=manager,
            window_reader=get_active_window_info,
            store=ctx.store,
        )
        if not self._autoswitch.disabled():
            self._autoswitch.start()
            logger.info("autoswitch_subsystem_started")
        else:
            logger.info("autoswitch_subsystem_disabled_by_config")

    async def stop(self) -> None:
        """Para o AutoSwitcher de forma limpa. Idempotente."""
        if self._autoswitch is not None:
            with contextlib.suppress(Exception):
                self._autoswitch.stop()
            self._autoswitch = None
            logger.info("autoswitch_subsystem_stopped")

    def is_enabled(self, config: DaemonConfig) -> bool:
        return config.autoswitch_enabled


async def start_autoswitch(daemon: Any) -> None:
    """Função utilitária: inicia o AutoSwitcher usando o Daemon diretamente."""
    from hefesto_dualsense4unix.integrations.xlib_window import get_active_window_info
    from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
    from hefesto_dualsense4unix.profiles.manager import ProfileManager

    manager = ProfileManager(
        controller=daemon.controller,
        store=daemon.store,
        keyboard_device=getattr(daemon, "_keyboard_device", None),
    )
    daemon._autoswitch = AutoSwitcher(
        manager=manager,
        window_reader=get_active_window_info,
        store=daemon.store,
    )
    if not daemon._autoswitch.disabled():
        daemon._autoswitch.start()


async def stop_autoswitch(daemon: Any) -> None:
    """Função utilitária: para o AutoSwitcher do Daemon."""
    if daemon._autoswitch is not None:
        with contextlib.suppress(Exception):
            daemon._autoswitch.stop()
        daemon._autoswitch = None


__all__ = ["AutoswitchSubsystem", "start_autoswitch", "stop_autoswitch"]
