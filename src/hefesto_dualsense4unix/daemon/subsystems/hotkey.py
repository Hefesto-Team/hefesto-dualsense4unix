"""Subsystem Hotkey — gerencia HotkeyManager e hotkey de microfone.

Responsabilidades:
  - Instanciar HotkeyManager com callback on_ps_solo (leitura de config em runtime).
  - Iniciar e parar a task _mic_button_loop que ouve BUTTON_DOWN para mic_btn.
  - Expor funções utilitárias usadas pelo Daemon como thin wrappers.
"""
from __future__ import annotations

import asyncio
import contextlib
import subprocess as _sp
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.context import DaemonContext

logger = get_logger(__name__)


def build_ps_solo_callback(daemon: Any) -> Any:
    """Cria o callback on_ps_solo que lê self.config em runtime (REFACTOR-DAEMON-RELOAD-01).

    Leitura em runtime — não em closure — para que reload_config funcione sem
    recriar closures manualmente.
    """

    def _on_ps_solo() -> None:
        cfg = daemon.config
        if cfg.ps_button_action == "none":
            return
        if cfg.ps_button_action == "steam":
            from hefesto_dualsense4unix.integrations.steam_launcher import open_or_focus_steam

            open_or_focus_steam()
        elif cfg.ps_button_action == "custom":
            command = cfg.ps_button_command
            if not command:
                logger.warning("hotkey_ps_solo_custom_sem_comando")
                return
            with contextlib.suppress(Exception):
                _sp.Popen(
                    command,
                    stdin=_sp.DEVNULL,
                    stdout=_sp.DEVNULL,
                    stderr=_sp.DEVNULL,
                    start_new_session=True,
                )

    return _on_ps_solo


def start_hotkey_manager(daemon: Any) -> None:
    """Instancia HotkeyManager e atribui a daemon._hotkey_manager."""
    from hefesto_dualsense4unix.integrations.hotkey_daemon import HotkeyManager

    daemon._hotkey_manager = HotkeyManager(on_ps_solo=build_ps_solo_callback(daemon))
    logger.info("hotkey_manager_started", ps_button_action=daemon.config.ps_button_action)


def stop_hotkey_manager(daemon: Any) -> None:
    """Descarta o HotkeyManager. Idempotente."""
    daemon._hotkey_manager = None


def start_mic_hotkey(daemon: Any) -> None:
    """Cria AudioControl e inicia task de consumo de BUTTON_DOWN para mic_btn."""
    from hefesto_dualsense4unix.integrations.audio_control import AudioControl

    if daemon._audio is None:
        daemon._audio = AudioControl()
    task = asyncio.create_task(mic_button_loop(daemon), name="mic_button_loop")
    daemon._tasks.append(task)
    logger.info("mic_hotkey_iniciado")


async def mic_button_loop(daemon: Any) -> None:
    """Consome BUTTON_DOWN do bus e aciona mute/unmute do microfone do sistema.

    Filtra apenas eventos com button='mic_btn'. Chama AudioControl (que já
    tem debounce interno de 200ms) e atualiza set_mic_led no controle.
    Não relança exceções: falhas são logadas como warning.
    """
    from hefesto_dualsense4unix.core.events import EventTopic

    queue = daemon.bus.subscribe(EventTopic.BUTTON_DOWN)
    try:
        while not daemon._is_stopping():
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            if payload.get("button") != "mic_btn":
                continue
            audio = daemon._audio
            if audio is None:
                continue
            try:
                muted = audio.toggle_default_source_mute()
                daemon.controller.set_mic_led(muted)
                logger.info("mic_hotkey_toggle", muted=muted)
            except Exception as exc:
                logger.warning("mic_hotkey_falhou", err=str(exc))
    finally:
        daemon.bus.unsubscribe(EventTopic.BUTTON_DOWN, queue)


class HotkeySubsystem:
    """Subsystem sentinela para hotkey no registry.

    A lógica real está nas funções start_hotkey_manager / start_mic_hotkey
    porque o Daemon precisa de referências diretas para backcompat de testes
    que acessam daemon._hotkey_manager e daemon._audio.
    """

    name = "hotkey"

    async def start(self, ctx: DaemonContext) -> None:
        """Noop: hotkey é iniciado diretamente pelo Daemon.run()."""
        logger.debug("hotkey_subsystem_start")

    async def stop(self) -> None:
        """Noop: daemon._hotkey_manager é limpado em _shutdown."""
        logger.debug("hotkey_subsystem_stop")

    def is_enabled(self, config: Any) -> bool:
        return True


__all__ = [
    "HotkeySubsystem",
    "build_ps_solo_callback",
    "mic_button_loop",
    "start_hotkey_manager",
    "start_mic_hotkey",
    "stop_hotkey_manager",
]
