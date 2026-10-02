"""PluginContext — interface estavel exposta aos plugins."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncio

    from hefesto_dualsense4unix.core.controller import (
        ControllerState,
        IController,
        Side,
        TriggerEffect,
    )
    from hefesto_dualsense4unix.core.events import EventBus
    from hefesto_dualsense4unix.daemon.state_store import StateStore


class ControllerProxy:
    """Fachada sobre IController exposta aos plugins."""

    def __init__(self, controller: IController) -> None:
        self._ctrl = controller


    def set_led(self, color: tuple[int, int, int]) -> None:
        """Define a cor da lightbar. color = (R, G, B), valores 0-255."""
        self._ctrl.set_led(color)

    def set_trigger(self, side: Side, effect: TriggerEffect) -> None:
        """Aplica efeito de gatilho. side = "left" | "right"."""
        self._ctrl.set_trigger(side, effect)

    def set_rumble(self, weak: int, strong: int) -> None:
        """Vibra o controle. weak e strong em 0-255."""
        self._ctrl.set_rumble(weak, strong)

    def set_player_leds(self, bits: tuple[bool, bool, bool, bool, bool]) -> None:
        """Define os 5 LEDs de player. bits[0] = LED 1 (esquerda)."""
        self._ctrl.set_player_leds(bits)

    def set_mic_led(self, aceso: bool) -> None:
        """Acende/apaga o LED do microfone. `True` = ACESO = mic VIVO."""
        self._ctrl.set_mic_led(aceso)


    @property
    def is_connected(self) -> bool:
        """True se o controle esta conectado."""
        return self._ctrl.is_connected()

    @property
    def battery_pct(self) -> int:
        """Percentual de bateria atual."""
        return self._ctrl.get_battery()

    @property
    def transport(self) -> str:
        """Transporte ativo: "usb" ou "bt"."""
        return self._ctrl.get_transport()


class BusProxy:
    """Fachada sobre EventBus exposta aos plugins."""

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    def subscribe(self, topic: str) -> asyncio.Queue[Any]:
        """Cria uma fila dedicada para receber eventos do topico."""
        return self._bus.subscribe(topic)


class StoreProxy:
    """Fachada sobre StateStore exposta aos plugins."""

    def __init__(self, store: StateStore) -> None:
        self._store = store

    def counter(self, key: str) -> int:
        """Retorna o valor atual do contador `key`. 0 se ainda não existe."""
        snap = self._store.snapshot()
        return snap.counters.get(key, 0)

    def snapshot(self) -> ControllerState | None:
        """Retorna o último ControllerState gravado no store (ou None)."""
        return self._store.snapshot().controller


@dataclass
class PluginContext:
    """Container de dependências injetado em Plugin.on_load()."""

    controller: ControllerProxy
    bus: BusProxy
    store: StoreProxy
    log: Any


def make_plugin_context(
    plugin_name: str,
    controller: IController,
    bus: EventBus,
    store: StateStore,
) -> PluginContext:
    """Fabrica de PluginContext. Chamada pelo PluginsSubsystem em on_load."""
    try:
        from hefesto_dualsense4unix.utils.logging_config import get_logger as _get_logger
        _log = _get_logger(f"plugin.{plugin_name}")
    except Exception:
        _log = logging.getLogger(f"hefesto.plugin.{plugin_name}")

    return PluginContext(
        controller=ControllerProxy(controller),
        bus=BusProxy(bus),
        store=StoreProxy(store),
        log=_log,
    )


__all__ = [
    "BusProxy",
    "ControllerProxy",
    "PluginContext",
    "StoreProxy",
    "make_plugin_context",
]
