"""Subsystem Autoswitch — gerencia troca automática de perfis por janela ativa.

Implementa o protocolo Subsystem e expõe start_autoswitch() / stop_autoswitch()
como funções utilitárias para uso direto pelo Daemon.
"""
from __future__ import annotations

import contextlib
import os
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.context import DaemonContext
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol

logger = get_logger(__name__)


def _ensure_display_env() -> None:
    """Importa WAYLAND_DISPLAY/DISPLAY de `systemctl --user show-environment`.

    AUTOSWITCH-FLOOD-FIX-01. O .service ancora em default.target (autostart
    resiliente em qualquer DE) e pode subir ANTES de o compositor exportar
    WAYLAND_DISPLAY/DISPLAY para o gerenciador de usuário — o processo nasce
    sem eles, o autoswitch cai em NullBackend e o perfil-por-app fica morto a
    sessão toda (além do flood). Aqui, se ambos faltam no os.environ, puxamos
    do systemd user (que os tem após o login do COSMIC). Best-effort: nunca
    propaga exceção. Complementa o `ExecStartPre=... import-environment` do
    .service (que cobre o próximo boot); este cobre a sessão atual / restart.
    """
    if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"):
        return
    import shutil
    import subprocess

    systemctl = shutil.which("systemctl")
    if systemctl is None:
        return
    try:
        result = subprocess.run(
            [systemctl, "--user", "show-environment"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort, nunca derruba o boot
        logger.debug("autoswitch_display_env_probe_failed", err=str(exc))
        return
    for line in result.stdout.splitlines():
        if line.startswith(("WAYLAND_DISPLAY=", "DISPLAY=")):
            key, _, value = line.partition("=")
            if value and not os.environ.get(key):
                os.environ[key] = value
                logger.info("autoswitch_display_env_imported", var=key)


class AutoswitchSubsystem:
    """Subsystem que gerencia o AutoSwitcher de perfis."""

    name = "autoswitch"
    _autoswitch: Any = None

    async def start(self, ctx: DaemonContext) -> None:
        """Inicia o AutoSwitcher com as dependências do DaemonContext."""
        from hefesto_dualsense4unix.integrations.window_detect import build_window_reader
        from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
        from hefesto_dualsense4unix.profiles.manager import ProfileManager

        _ensure_display_env()
        manager = ProfileManager(controller=ctx.controller, store=ctx.store)
        self._autoswitch = AutoSwitcher(
            manager=manager,
            window_reader=build_window_reader(),
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


async def start_autoswitch(daemon: DaemonProtocol) -> None:
    """Função utilitária: inicia o AutoSwitcher usando o Daemon diretamente."""
    from hefesto_dualsense4unix.integrations.window_detect import build_window_reader
    from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
    from hefesto_dualsense4unix.profiles.manager import ProfileManager

    _ensure_display_env()
    manager = ProfileManager(
        controller=daemon.controller,
        store=daemon.store,
        keyboard_device=getattr(daemon, "_keyboard_device", None),
    )
    daemon._autoswitch = AutoSwitcher(
        manager=manager,
        window_reader=build_window_reader(),
        store=daemon.store,
    )
    if not daemon._autoswitch.disabled():
        daemon._autoswitch.start()


async def stop_autoswitch(daemon: DaemonProtocol) -> None:
    """Função utilitária: para o AutoSwitcher do Daemon."""
    if daemon._autoswitch is not None:
        with contextlib.suppress(Exception):
            daemon._autoswitch.stop()
        daemon._autoswitch = None


__all__ = ["AutoswitchSubsystem", "start_autoswitch", "stop_autoswitch"]
