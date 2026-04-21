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
from typing import Any

from hefesto.core.controller import IController
from hefesto.core.events import EventBus, EventTopic
from hefesto.daemon.state_store import StateStore
from hefesto.profiles.manager import ProfileManager
from hefesto.utils.logging_config import get_logger

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
            self._tasks = [asyncio.create_task(self._poll_loop(), name="poll_loop")]
            if self.config.ipc_enabled:
                await self._start_ipc()
            if self.config.udp_enabled:
                await self._start_udp()
            if self.config.autoswitch_enabled:
                await self._start_autoswitch()
            if self.config.mouse_emulation_enabled:
                self._start_mouse_emulation()
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

    async def _poll_loop(self) -> None:
        period = 1.0 / max(1, self.config.poll_hz)
        battery = BatteryDebouncer()
        loop = asyncio.get_running_loop()

        while not self._is_stopping():
            tick_started = loop.time()
            try:
                state = await self._run_blocking(self.controller.read_state)
            except Exception as exc:
                logger.warning("poll_read_failed", err=str(exc))
                self.bus.publish(EventTopic.CONTROLLER_DISCONNECTED, {"reason": str(exc)})
                if self.config.auto_reconnect:
                    await self._reconnect()
                    continue
                break

            self.store.update_controller_state(state)
            self.bus.publish(EventTopic.STATE_UPDATE, state)
            self.store.bump("poll.tick")

            if self._mouse_device is not None:
                self._dispatch_mouse_emulation(state)

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

    def _dispatch_mouse_emulation(self, state: Any) -> None:
        """Traduz o estado do poll em eventos de mouse+teclado virtual."""
        if self._mouse_device is None:
            return
        buttons: frozenset[str] = frozenset()
        evdev_reader = getattr(self.controller, "_evdev", None)
        if evdev_reader is not None and evdev_reader.is_available():
            with contextlib.suppress(Exception):
                buttons = frozenset(evdev_reader.snapshot().buttons_pressed)
        try:
            self._mouse_device.dispatch(
                lx=state.raw_lx,
                ly=state.raw_ly,
                rx=state.raw_rx,
                ry=state.raw_ry,
                l2=state.l2_raw,
                r2=state.r2_raw,
                buttons=buttons,
            )
        except Exception as exc:
            logger.warning("mouse_dispatch_failed", err=str(exc))

    async def _shutdown(self) -> None:
        logger.info("daemon_shutting_down")
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
    "BATTERY_DEBOUNCE_SEC",
    "BATTERY_DELTA_THRESHOLD_PCT",
    "BATTERY_MIN_INTERVAL_SEC",
    "DEFAULT_POLL_HZ",
    "BatteryDebouncer",
    "Daemon",
    "DaemonConfig",
]
