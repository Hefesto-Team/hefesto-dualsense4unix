"""Ciclo de vida do daemon: conectar controle, rodar poll loop, desligar limpo.

O daemon é composto por:
  - 1 `IController` (real ou fake) conectado ao dispositivo.
  - 1 `EventBus` global.
  - 1 `StateStore` global.
  - Tasks async: poll_loop, e futuramente ipc_server, udp_server, autoswitch.

`Daemon.run()` orquestra start -> run_until_stopped -> shutdown. Captura SIGINT
e SIGTERM para desligar limpo. Poll roda em `ThreadPoolExecutor` dedicado
porque `IController` é síncrono (V2-7).
"""
from __future__ import annotations

import asyncio
import contextlib
import signal
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Literal

from hefesto.core.controller import IController
from hefesto.core.events import EventBus, EventTopic
from hefesto.daemon.state_store import StateStore
from hefesto.profiles.manager import ProfileManager
from hefesto.utils.logging_config import get_logger

# FEAT-RUMBLE-POLICY-01: políticas de intensidade global de rumble.
RUMBLE_POLICY_MULT: dict[str, float] = {
    "economia": 0.3,
    "balanceado": 0.7,
    "max": 1.0,
}
AUTO_DEBOUNCE_SEC = 5.0

logger = get_logger(__name__)

DEFAULT_POLL_HZ = 60
BATTERY_DEBOUNCE_SEC = 5.0
BATTERY_MIN_INTERVAL_SEC = 0.1
BATTERY_DELTA_THRESHOLD_PCT = 1


@dataclass
class DaemonConfig:
    poll_hz: int = DEFAULT_POLL_HZ
    auto_reconnect: bool = True
    reconnect_backoff_sec: float = 2.0
    ipc_enabled: bool = True
    udp_enabled: bool = True
    udp_host: str = "127.0.0.1"
    udp_port: int = 6969
    autoswitch_enabled: bool = True
    # FEAT-MOUSE-01: opt-in, default OFF. Device virtual só nasce se o
    # usuário ligar o toggle na aba Mouse da GUI (via IPC mouse.emulation.set).
    mouse_emulation_enabled: bool = False
    mouse_speed: int = 6
    mouse_scroll_speed: int = 1
    # FEAT-HOTKEY-STEAM-01: comportamento do PS solo (sem combo em 150ms).
    # "steam"  -> abre/foca a Steam via steam_launcher.open_or_focus_steam.
    # "none"   -> não faz nada (PS solo e ignorado pelo hotkey_manager).
    # "custom" -> dispara `ps_button_command` (ex.: ["xdg-open", "steam://open/bigpicture"]).
    ps_button_action: Literal["steam", "none", "custom"] = "steam"
    ps_button_command: list[str] = field(default_factory=list)
    # BUG-RUMBLE-APPLY-IGNORED-01: estado persistente de rumble ativo.
    # None = passthrough (jogo controla via UDP/emulação ou motores parados).
    # (weak, strong) = valor fixado pelo usuário via IPC rumble.set.
    # Poll loop re-afirma a cada 200ms para sobrepor writes HID que zeram motores.
    # Se emulation_enabled=True E rumble_active is None, re-asserção é pulada
    # para não conflitar com o jogo. Usuário pode forçar mesmo em modo emulação
    # fixando rumble_active != None — seu valor vence.
    rumble_active: tuple[int, int] | None = None
    # FEAT-RUMBLE-POLICY-01: política de intensidade global de rumble.
    # Multiplicador aplicado sobre todos os valores antes de enviar ao hardware.
    # "economia"  -> 0.3 (vibração sutil, 70% menos energia)
    # "balanceado"-> 0.7 (default)
    # "max"       -> 1.0 (sem limite)
    # "auto"      -> dinâmico por bateria (debounce 5s): >50%->1.0, 20-50%->0.7, <20%->0.3
    # "custom"    -> usar rumble_policy_custom_mult
    rumble_policy: Literal["economia", "balanceado", "max", "auto", "custom"] = "balanceado"
    rumble_policy_custom_mult: float = 0.7
    # FEAT-HOTKEY-MIC-01: botao Mic do DualSense controla microfone do sistema.
    # True  -> subscreve BUTTON_DOWN e chama AudioControl.toggle_default_source_mute().
    # False -> opt-out; botao Mic continua funcionando apenas no controle interno.
    mic_button_toggles_system: bool = True


class BatteryDebouncer:
    """Debounce de eventos de bateria (V2-17 + ADR-008).

    Dispara se:
      - nunca disparou (primeiro valor); ou
      - `abs(delta_pct) >= BATTERY_DELTA_THRESHOLD_PCT` (e respeita min interval); ou
      - `elapsed_since_last_emit >= BATTERY_DEBOUNCE_SEC`.

    Sempre respeita `BATTERY_MIN_INTERVAL_SEC` entre disparos consecutivos.
    """

    def __init__(self) -> None:
        self.last_emitted_value: int | None = None
        self.last_emit_at: float = 0.0

    def should_emit(self, value: int, now: float) -> bool:
        if self.last_emitted_value is None:
            return True
        interval = now - self.last_emit_at
        if interval < BATTERY_MIN_INTERVAL_SEC:
            return False
        delta = abs(value - self.last_emitted_value)
        return delta >= BATTERY_DELTA_THRESHOLD_PCT or interval >= BATTERY_DEBOUNCE_SEC

    def mark_emitted(self, value: int, now: float) -> None:
        self.last_emitted_value = value
        self.last_emit_at = now


def _effective_mult_inline(
    config: DaemonConfig,
    battery_pct: int,
    now: float,
    last_auto_mult: float,
    last_auto_change_at: float,
) -> tuple[float, float, float]:
    """Calcula multiplicador de política inline (sem importar rumble.py).

    Retorna (mult, novo_last_auto_mult, novo_last_auto_change_at).
    Chamado por _reassert_rumble no Daemon para aplicar política sem
    importação circular.
    """
    policy = config.rumble_policy

    if policy in RUMBLE_POLICY_MULT:
        return RUMBLE_POLICY_MULT[policy], last_auto_mult, last_auto_change_at

    if policy == "custom":
        mult = float(config.rumble_policy_custom_mult)
        return mult, last_auto_mult, last_auto_change_at

    if policy == "auto":
        if battery_pct > 50:
            target = 1.0
        elif battery_pct >= 20:
            target = 0.7
        else:
            target = 0.3

        if target != last_auto_mult:
            elapsed = now - last_auto_change_at
            if elapsed >= AUTO_DEBOUNCE_SEC or last_auto_change_at == 0.0:
                logger.info(
                    "rumble_auto_policy_change",
                    mult=target,
                    battery_pct=battery_pct,
                )
                return target, target, now
            return last_auto_mult, last_auto_mult, last_auto_change_at

        return last_auto_mult, last_auto_mult, last_auto_change_at

    # Fallback: balanceado.
    return 0.7, last_auto_mult, last_auto_change_at


@dataclass
class Daemon:
    controller: IController
    bus: EventBus = field(default_factory=EventBus)
    store: StateStore = field(default_factory=StateStore)
    config: DaemonConfig = field(default_factory=DaemonConfig)

    _stop_event: asyncio.Event | None = None
    _executor: ThreadPoolExecutor | None = None
    _tasks: list[asyncio.Task[Any]] = field(default_factory=list)
    _ipc_server: Any = None
    _udp_server: Any = None
    _autoswitch: Any = None
    _mouse_device: Any = None
    _hotkey_manager: Any = None
    # FEAT-HOTKEY-MIC-01: instancia de AudioControl criada se mic_button_toggles_system=True.
    _audio: Any = None
    # FEAT-RUMBLE-POLICY-01: debounce de modo "auto" de política de rumble.
    _last_auto_mult: float = field(default=0.7)
    _last_auto_change_at: float = field(default=0.0)

    async def run(self) -> None:
        """Entry point: start tasks, wait until stop, shutdown."""
        loop = asyncio.get_running_loop()
        self.bus.bind_loop(loop)
        self._stop_event = asyncio.Event()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="hefesto-hid")
        self._install_signal_handlers(loop)

        logger.info("daemon_starting", poll_hz=self.config.poll_hz)
        try:
            await self._connect_with_retry()
            await self._restore_last_profile()
            self._tasks = [asyncio.create_task(self._poll_loop(), name="poll_loop")]
            if self.config.ipc_enabled:
                await self._start_ipc()
            if self.config.udp_enabled:
                await self._start_udp()
            if self.config.autoswitch_enabled:
                await self._start_autoswitch()
            if self.config.mouse_emulation_enabled:
                self._start_mouse_emulation()
            self._start_hotkey_manager()
            if self.config.mic_button_toggles_system:
                self._start_mic_hotkey()
            await self._stop_event.wait()
        finally:
            await self._shutdown()

    def stop(self) -> None:
        """Sinaliza parada; idempotente."""
        if self._stop_event is not None and not self._stop_event.is_set():
            logger.info("daemon_stop_requested")
            self._stop_event.set()

    async def _connect_with_retry(self) -> None:
        backoff = self.config.reconnect_backoff_sec
        while True:
            try:
                await self._run_blocking(self.controller.connect)
                transport = self.controller.get_transport()
                self.bus.publish(EventTopic.CONTROLLER_CONNECTED, {"transport": transport})
                logger.info("controller_connected", transport=transport)
                return
            except Exception as exc:
                logger.warning("controller_connect_failed", err=str(exc))
                if not self.config.auto_reconnect:
                    raise
                await asyncio.sleep(backoff)

    async def _restore_last_profile(self) -> None:
        """Reativa o último perfil salvo pelo usuário (FEAT-PERSIST-SESSION-01)."""
        from hefesto.profiles.manager import ProfileManager
        from hefesto.utils.session import load_last_profile

        name = load_last_profile()
        if not name:
            return
        try:
            manager = ProfileManager(controller=self.controller, store=self.store)
            await self._run_blocking(manager.activate, name)
            logger.info("last_profile_restored", name=name)
        except Exception as exc:
            logger.warning("last_profile_restore_failed", name=name, err=str(exc))

    def _reassert_rumble(self, now: float) -> None:
        """Re-aplica rumble_active no hardware a cada ~200ms com política (FEAT-RUMBLE-POLICY-01).

        Idempotente. Necessário porque writes HID de LED/trigger podem zerar os
        motores de vibração involuntariamente. A re-asserção a 5Hz (200ms) garante
        que o valor fixado pelo usuário persista mesmo com outras escritas HID.

        Aplica multiplicador de política (economia/balanceado/max/auto/custom) sobre
        os valores brutos guardados em rumble_active antes de enviar ao hardware.

        Pula silenciosamente se:
        - rumble_active is None (passthrough — jogo/UDP controla).
        - Controle não está conectado.
        """
        cfg = self.config
        active = cfg.rumble_active
        if active is None:
            return
        weak_raw, strong_raw = active

        # Aplica política de intensidade (FEAT-RUMBLE-POLICY-01).
        battery_pct = 50  # fallback neutro
        try:
            snap = self.store.snapshot()
            ctrl = snap.controller
            if ctrl is not None and ctrl.battery_pct is not None:
                battery_pct = int(ctrl.battery_pct)
        except Exception:
            pass

        mult, self._last_auto_mult, self._last_auto_change_at = _effective_mult_inline(
            config=cfg,
            battery_pct=battery_pct,
            now=now,
            last_auto_mult=self._last_auto_mult,
            last_auto_change_at=self._last_auto_change_at,
        )
        weak = max(0, min(255, round(weak_raw * mult)))
        strong = max(0, min(255, round(strong_raw * mult)))

        try:
            self.controller.set_rumble(weak=weak, strong=strong)
        except Exception as exc:
            logger.warning("rumble_reassert_failed", err=str(exc))

    async def _poll_loop(self) -> None:
        period = 1.0 / max(1, self.config.poll_hz)
        battery = BatteryDebouncer()
        loop = asyncio.get_running_loop()
        next_rumble_assert_at: float = 0.0  # deadline para próxima re-asserção de rumble
        # Diff de botões entre ticks consecutivos (INFRA-BUTTON-EVENTS-01).
        # Resetar em _reconnect() para evitar BUTTON_UP fantasma pós-reconexão.
        previous_buttons: frozenset[str] = frozenset()

        while not self._is_stopping():
            tick_started = loop.time()
            try:
                state = await self._run_blocking(self.controller.read_state)
            except Exception as exc:
                logger.warning("poll_read_failed", err=str(exc))
                self.bus.publish(EventTopic.CONTROLLER_DISCONNECTED, {"reason": str(exc)})
                if self.config.auto_reconnect:
                    previous_buttons = frozenset()  # reseta para evitar BUTTON_UP fantasma
                    await self._reconnect()
                    continue
                break

            self.store.update_controller_state(state)
            self.bus.publish(EventTopic.STATE_UPDATE, state)
            self.store.bump("poll.tick")

            # Re-afirmar rumble a cada 200ms (BUG-RUMBLE-APPLY-IGNORED-01).
            if tick_started >= next_rumble_assert_at:
                self._reassert_rumble(tick_started)
                next_rumble_assert_at = tick_started + 0.200

            # Snapshot evdev único por tick — reusado por todos os consumidores.
            # Extraído antes dos consumidores para evitar snapshots duplicados
            # (armadilha A-09). Skew de até 1 frame entre read_state e o snapshot
            # evdev é aceitável — os dois canais são independentes por design.
            buttons_pressed = self._evdev_buttons_once()

            if self._mouse_device is not None:
                self._dispatch_mouse_emulation(state, buttons_pressed)

            if self._hotkey_manager is not None:
                self._hotkey_manager.observe(buttons_pressed, now=tick_started)

            # Diff de botões: publica BUTTON_DOWN/UP por mudança de estado
            # (INFRA-BUTTON-EVENTS-01). Usa state.buttons_pressed (populado pelo
            # backend via evdev + HID-raw), não o snapshot evdev separado — mantém
            # fonte única de verdade e cobre o botão Mic que não tem evdev estável.
            current_buttons = state.buttons_pressed
            pressed_now = current_buttons - previous_buttons
            released_now = previous_buttons - current_buttons
            for name in sorted(pressed_now):
                self.bus.publish(EventTopic.BUTTON_DOWN, {"button": name, "pressed": True})
                self.store.bump("button.down.emitted")
            for name in sorted(released_now):
                self.bus.publish(EventTopic.BUTTON_UP, {"button": name, "pressed": False})
                self.store.bump("button.up.emitted")
            previous_buttons = current_buttons

            if battery.should_emit(state.battery_pct, tick_started):
                self.bus.publish(EventTopic.BATTERY_CHANGE, state.battery_pct)
                battery.mark_emitted(state.battery_pct, tick_started)
                self.store.bump("battery.change.emitted")

            elapsed = loop.time() - tick_started
            sleep_for = period - elapsed
            if sleep_for > 0:
                stop_event = self._stop_event
                assert stop_event is not None
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(stop_event.wait(), timeout=sleep_for)
                    break

    async def _reconnect(self) -> None:
        with contextlib.suppress(Exception):
            await self._run_blocking(self.controller.disconnect)
        await asyncio.sleep(self.config.reconnect_backoff_sec)
        await self._connect_with_retry()

    async def _start_ipc(self) -> None:
        from hefesto.daemon.ipc_server import IpcServer

        manager = ProfileManager(controller=self.controller, store=self.store)
        self._ipc_server = IpcServer(
            controller=self.controller,
            store=self.store,
            profile_manager=manager,
            daemon=self,
        )
        await self._ipc_server.start()

    async def _start_autoswitch(self) -> None:
        from hefesto.integrations.xlib_window import get_active_window_info
        from hefesto.profiles.autoswitch import AutoSwitcher

        manager = ProfileManager(controller=self.controller, store=self.store)
        # BUG-MOUSE-TRIGGERS-01: store compartilhado permite ao autoswitch
        # respeitar override de trigger manual (aba Gatilhos).
        self._autoswitch = AutoSwitcher(
            manager=manager,
            window_reader=get_active_window_info,
            store=self.store,
        )
        if not self._autoswitch.disabled():
            self._autoswitch.start()

    async def _start_udp(self) -> None:
        from hefesto.daemon.udp_server import UdpServer

        self._udp_server = UdpServer(
            controller=self.controller,
            store=self.store,
            host=self.config.udp_host,
            port=self.config.udp_port,
        )
        try:
            await self._udp_server.start()
        except OSError as exc:
            logger.warning("udp_server_bind_failed", err=str(exc))
            self._udp_server = None

    def _start_mouse_emulation(self) -> bool:
        """Cria device virtual de mouse+teclado (FEAT-MOUSE-01). Idempotente."""
        if self._mouse_device is not None:
            return True
        try:
            from hefesto.integrations.uinput_mouse import UinputMouseDevice

            device = UinputMouseDevice(
                mouse_speed=self.config.mouse_speed,
                scroll_speed=self.config.mouse_scroll_speed,
            )
        except Exception as exc:
            logger.warning("mouse_emulation_import_failed", err=str(exc))
            return False
        if not device.start():
            logger.warning("mouse_emulation_start_failed")
            return False
        self._mouse_device = device
        self.config.mouse_emulation_enabled = True
        logger.info("mouse_emulation_started",
                    speed=self.config.mouse_speed,
                    scroll_speed=self.config.mouse_scroll_speed)
        return True

    def _start_hotkey_manager(self) -> None:
        """Instancia HotkeyManager com on_ps_solo conforme config (FEAT-HOTKEY-STEAM-01).

        REFACTOR-DAEMON-RELOAD-01: `_on_ps_solo` le `self.config` em runtime para
        que `reload_config` possa substituir `self.config` sem recriar closures.
        """
        from hefesto.integrations.hotkey_daemon import HotkeyManager

        def _on_ps_solo() -> None:
            # Leitura em runtime — não em closure — para que reload_config funcione.
            cfg = self.config
            if cfg.ps_button_action == "none":
                return
            if cfg.ps_button_action == "steam":
                from hefesto.integrations.steam_launcher import open_or_focus_steam
                open_or_focus_steam()
            elif cfg.ps_button_action == "custom":
                command = cfg.ps_button_command
                if not command:
                    logger.warning("hotkey_ps_solo_custom_sem_comando")
                    return
                import subprocess as _sp
                with contextlib.suppress(Exception):
                    _sp.Popen(
                        command,
                        stdin=_sp.DEVNULL,
                        stdout=_sp.DEVNULL,
                        stderr=_sp.DEVNULL,
                        start_new_session=True,
                    )

        self._hotkey_manager = HotkeyManager(on_ps_solo=_on_ps_solo)
        logger.info("hotkey_manager_started", ps_button_action=self.config.ps_button_action)

    def _start_mic_hotkey(self) -> None:
        """Cria AudioControl e inicia task de consumo de BUTTON_DOWN para mic_btn.

        Chamado em run() quando mic_button_toggles_system=True. Idempotente:
        se _audio ja existe, não recria.
        """
        from hefesto.integrations.audio_control import AudioControl

        if self._audio is None:
            self._audio = AudioControl()
        task = asyncio.create_task(self._mic_button_loop(), name="mic_button_loop")
        self._tasks.append(task)
        logger.info("mic_hotkey_iniciado")

    async def _mic_button_loop(self) -> None:
        """Consome BUTTON_DOWN do bus e aciona mute/unmute do microfone do sistema.

        Filtra apenas eventos com button='mic_btn'. Chama AudioControl (que ja
        tem debounce interno de 200ms) e atualiza set_mic_led no controle.
        Não relanca excecoes: falhas sao logadas como warning.
        """
        queue = self.bus.subscribe(EventTopic.BUTTON_DOWN)
        try:
            while not self._is_stopping():
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                if payload.get("button") != "mic_btn":
                    continue
                audio = self._audio
                if audio is None:
                    continue
                try:
                    muted = audio.toggle_default_source_mute()
                    self.controller.set_mic_led(muted)
                    logger.info("mic_hotkey_toggle", muted=muted)
                except Exception as exc:
                    logger.warning("mic_hotkey_falhou", err=str(exc))
        finally:
            self.bus.unsubscribe(EventTopic.BUTTON_DOWN, queue)

    def _stop_hotkey_manager(self) -> None:
        """Para e descarta o HotkeyManager atual. Idempotente."""
        self._hotkey_manager = None

    def reload_config(self, new_config: DaemonConfig) -> None:
        """Aplica nova configuração em runtime sem reiniciar o daemon.

        Substitui `self.config`, rebuilda o HotkeyManager (closures frescas via
        runtime-read de `self.config`) e reage a mudanças de mouse_emulation_enabled.

        Nota: se o usuário estiver com PS+combo pressionado no momento do reload,
        o novo HotkeyManager perde o estado de hold — soltar e pressionar novamente
        é necessário para retomar a detecção de combo.
        """
        old = self.config
        self.config = new_config

        # Rebuild do HotkeyManager garante closures apontando para self.config novo.
        self._stop_hotkey_manager()
        self._start_hotkey_manager()

        # Mouse: reage só se o estado mudou.
        if old.mouse_emulation_enabled != new_config.mouse_emulation_enabled:
            self.set_mouse_emulation(
                new_config.mouse_emulation_enabled,
                speed=new_config.mouse_speed,
                scroll_speed=new_config.mouse_scroll_speed,
            )

        keys_changed = [
            k for k in new_config.__dataclass_fields__
            if getattr(old, k, None) != getattr(new_config, k)
        ]
        logger.info("daemon_config_reloaded", keys_changed=keys_changed)

    def _stop_mouse_emulation(self) -> None:
        if self._mouse_device is None:
            return
        with contextlib.suppress(Exception):
            self._mouse_device.stop()
        self._mouse_device = None
        self.config.mouse_emulation_enabled = False
        logger.info("mouse_emulation_stopped")

    def set_mouse_emulation(
        self,
        enabled: bool,
        speed: int | None = None,
        scroll_speed: int | None = None,
    ) -> bool:
        """Liga/desliga emulação e atualiza velocidades. Usado pelo IPC."""
        if speed is not None:
            self.config.mouse_speed = max(1, min(12, int(speed)))
        if scroll_speed is not None:
            self.config.mouse_scroll_speed = max(1, min(5, int(scroll_speed)))

        if enabled:
            ok = self._start_mouse_emulation()
            if ok and self._mouse_device is not None:
                self._mouse_device.set_speed(
                    mouse_speed=self.config.mouse_speed,
                    scroll_speed=self.config.mouse_scroll_speed,
                )
            return ok
        self._stop_mouse_emulation()
        return True

    def _evdev_buttons_once(self) -> frozenset[str]:
        """Snapshot dos botões físicos via evdev — chamado 1x por tick em _poll_loop.

        Retorna frozenset vazio se evdev não está disponível ou falha.
        Exceções são logadas em debug para não poluir logs de produção.
        """
        evdev = getattr(self.controller, "_evdev", None)
        if evdev is None or not evdev.is_available():
            return frozenset()
        try:
            return frozenset(evdev.snapshot().buttons_pressed)
        except Exception as exc:
            logger.debug("evdev_snapshot_falhou", err=str(exc))
            return frozenset()

    def _dispatch_mouse_emulation(self, state: Any, buttons_pressed: frozenset[str]) -> None:
        """Traduz o estado do poll em eventos de mouse+teclado virtual.

        Recebe `buttons_pressed` do _poll_loop (snapshot único por tick,
        obtido via _evdev_buttons_once). Não relê o evdev internamente.
        """
        if self._mouse_device is None:
            return
        try:
            self._mouse_device.dispatch(
                lx=state.raw_lx,
                ly=state.raw_ly,
                rx=state.raw_rx,
                ry=state.raw_ry,
                l2=state.l2_raw,
                r2=state.r2_raw,
                buttons=buttons_pressed,
            )
        except Exception as exc:
            logger.warning("mouse_dispatch_failed", err=str(exc))

    async def _shutdown(self) -> None:
        logger.info("daemon_shutting_down")
        self._hotkey_manager = None
        self._audio = None
        if self._mouse_device is not None:
            with contextlib.suppress(Exception):
                self._mouse_device.stop()
            self._mouse_device = None
        if self._ipc_server is not None:
            with contextlib.suppress(Exception):
                await self._ipc_server.stop()
            self._ipc_server = None
        if self._udp_server is not None:
            with contextlib.suppress(Exception):
                await self._udp_server.stop()
            self._udp_server = None
        if self._autoswitch is not None:
            with contextlib.suppress(Exception):
                self._autoswitch.stop()
            self._autoswitch = None
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        try:
            await self._run_blocking(self.controller.disconnect)
        except Exception as exc:
            logger.warning("controller_disconnect_failed", err=str(exc))
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
        self._tasks.clear()
        logger.info("daemon_stopped")

    def _install_signal_handlers(self, loop: asyncio.AbstractEventLoop) -> None:
        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sig, self.stop)

    async def _run_blocking(self, fn: Callable[..., Any], *args: Any) -> Any:
        assert self._executor is not None, "executor não inicializado"
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, fn, *args)

    def _is_stopping(self) -> bool:
        return self._stop_event is not None and self._stop_event.is_set()


__all__ = [
    "AUTO_DEBOUNCE_SEC",
    "BATTERY_DEBOUNCE_SEC",
    "BATTERY_DELTA_THRESHOLD_PCT",
    "BATTERY_MIN_INTERVAL_SEC",
    "DEFAULT_POLL_HZ",
    "RUMBLE_POLICY_MULT",
    "BatteryDebouncer",
    "Daemon",
    "DaemonConfig",
]
