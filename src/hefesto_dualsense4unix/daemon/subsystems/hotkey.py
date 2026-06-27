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
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol

logger = get_logger(__name__)


def build_ps_solo_callback(daemon: DaemonProtocol) -> Any:
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


def build_ps_long_press_callback(daemon: DaemonProtocol) -> Any:
    """Cria o callback on_ps_long_press: alterna o modo jogo (supressao da
    emulacao de mouse/teclado). FEAT-EMULATION-GAMEMODE-LONGPRESS-01."""

    def _on_ps_long_press() -> None:
        daemon.set_emulation_suppressed()

    return _on_ps_long_press


def build_profile_cycle_callback(daemon: DaemonProtocol, direction: int) -> Any:
    """Cria o callback on_next (+1) / on_prev (-1): cicla para o perfil
    seguinte/anterior e o ativa — triggers + LEDs + key_bindings + marca ativo +
    notifica — reusando ProfileManager.activate, o MESMO caminho do profile.switch
    (IPC) e do restore_last_profile. FEAT-HOTKEY-PROFILE-CYCLE-01.

    Antes os combos PS+D-pad estavam disabled_until_wired: o observe() disparava
    com cb=None (no-op) mas ainda suprimia o D-pad e o PS-solo — gesto morto que
    comia o D-pad. Agora o cb troca de perfil de verdade.

    Feedback in-hand (você está com o controle na mão): flasha o lightbar em
    branco antes do activate() repintar a cor do perfil novo, então há sinal
    visível mesmo que dois perfis tenham a mesma cor. O sleep roda em task
    própria (não bloqueia o poll loop).
    """

    async def _cycle() -> None:
        import time as _time

        from hefesto_dualsense4unix.daemon.state_store import MANUAL_PROFILE_LOCK_SEC
        from hefesto_dualsense4unix.profiles.manager import ProfileManager
        from hefesto_dualsense4unix.utils.session import save_active_marker

        manager = ProfileManager(
            controller=daemon.controller,
            store=daemon.store,
            keyboard_device=getattr(daemon, "_keyboard_device", None),
        )
        profiles = await daemon._run_blocking(manager.list_profiles)
        if len(profiles) < 2:
            logger.info("profile_cycle_skip", n=len(profiles))
            return
        names = [p.name for p in profiles]
        active = daemon.store.active_profile
        idx = names.index(active) if active in names else 0
        target = names[(idx + direction) % len(names)]

        # Feedback visual imediato; activate() repinta a cor do perfil a seguir.
        with contextlib.suppress(Exception):
            await daemon._run_blocking(daemon.controller.set_led, (255, 255, 255))
            await asyncio.sleep(0.12)

        profile = await daemon._run_blocking(manager.activate, target)
        with contextlib.suppress(Exception):
            save_active_marker(profile.name)
        # Gesto explícito do usuário: libera o autoswitch e arma o lock manual
        # (paridade com _handle_profile_switch) — senão o autoswitch desfaz a
        # troca no próximo tick por causa da janela ativa.
        daemon.store.clear_manual_trigger_active()
        daemon.store.mark_manual_profile_lock(
            _time.monotonic() + MANUAL_PROFILE_LOCK_SEC
        )
        logger.info("profile_cycled", direction=direction, to=profile.name)

    return _cycle


def start_hotkey_manager(daemon: DaemonProtocol) -> None:
    """Instancia HotkeyManager e atribui a daemon._hotkey_manager.

    BUGFIX: o HotkeyManager era criado sem config, ignorando
    `daemon.config.ps_long_press_ms` (ficava preso no default 1000ms). Agora a
    config do daemon é propagada — inclusive 0 = desliga o long-press do PS.
    """
    from hefesto_dualsense4unix.integrations.hotkey_daemon import (
        DEFAULT_COMBO_NEXT,
        DEFAULT_COMBO_PREV,
        HotkeyConfig,
        HotkeyManager,
    )

    # FEAT-HOTKEY-PROFILE-CYCLE-01: os combos next/prev (PS+D-pad) agora estão
    # LIGADOS — on_next/on_prev ciclam o perfil via ProfileManager.activate (o
    # mesmo caminho do profile.switch). Antes ficavam disabled_until_wired: o
    # observe() disparava com cb=None (no-op) mas ainda comia o D-pad. Com o cb
    # de verdade, suprimir o D-pad durante o hold do PS é o comportamento certo
    # (você está trocando de perfil, não mirando). Modo-jogo segue no PS+Options.
    hotkey_config = HotkeyConfig(
        ps_long_press_ms=getattr(daemon.config, "ps_long_press_ms", 0),
        next_profile=DEFAULT_COMBO_NEXT,
        prev_profile=DEFAULT_COMBO_PREV,
    )
    daemon._hotkey_manager = HotkeyManager(
        on_ps_solo=build_ps_solo_callback(daemon),
        on_ps_long_press=build_ps_long_press_callback(daemon),
        on_next=build_profile_cycle_callback(daemon, +1),
        on_prev=build_profile_cycle_callback(daemon, -1),
        config=hotkey_config,
    )
    logger.info(
        "hotkey_manager_started",
        ps_button_action=daemon.config.ps_button_action,
        ps_long_press_ms=hotkey_config.ps_long_press_ms,
        next_prev_combos="ps+dpad_up / ps+dpad_down",
    )


def stop_hotkey_manager(daemon: DaemonProtocol) -> None:
    """Descarta o HotkeyManager. Idempotente."""
    daemon._hotkey_manager = None


def start_mic_hotkey(daemon: DaemonProtocol) -> None:
    """Cria AudioControl e inicia task de consumo de BUTTON_DOWN para mic_btn."""
    from hefesto_dualsense4unix.integrations.audio_control import AudioControl

    if daemon._audio is None:
        daemon._audio = AudioControl()
    task = asyncio.create_task(mic_button_loop(daemon), name="mic_button_loop")
    daemon._tasks.append(task)
    logger.info("mic_hotkey_iniciado")


async def mic_button_loop(daemon: DaemonProtocol) -> None:
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
    "build_ps_long_press_callback",
    "build_ps_solo_callback",
    "mic_button_loop",
    "start_hotkey_manager",
    "start_mic_hotkey",
    "stop_hotkey_manager",
]
