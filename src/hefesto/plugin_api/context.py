"""PluginContext — interface estavel exposta aos plugins.

Plugins recebem um PluginContext em on_load() e usam seus atributos
para interagir com o daemon de forma controlada, sem acesso direto
ao objeto Daemon ou ao IController completo.

API disponivel:
  - ctx.controller  → ControllerProxy (subset de IController: set_led,
                       set_trigger, set_rumble, set_player_leds,
                       set_mic_led + estado read-only)
  - ctx.bus         → BusProxy (bus.subscribe(topic))
  - ctx.store       → StoreProxy (store.counter(key))
  - ctx.log         → structlog logger prefixado com "plugin.<name>"

Nota: não exponha o IController completo, DaemonConfig, StateStore
bruto ou EventBus bruto. Use somente os proxies deste modulo.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncio

    from hefesto.core.controller import ControllerState, IController, Side, TriggerEffect
    from hefesto.core.events import EventBus
    from hefesto.daemon.state_store import StateStore


# ---------------------------------------------------------------------------
# ControllerProxy
# ---------------------------------------------------------------------------


class ControllerProxy:
    """Fachada sobre IController exposta aos plugins.

    Expoe apenas os metodos de output necessarios e o estado read-only.
    """

    def __init__(self, controller: IController) -> None:
        self._ctrl = controller

    # -- output --------------------------------------------------------------

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

    def set_mic_led(self, muted: bool) -> None:
        """Acende/apaga LED do microfone. True = mudo (LED aceso)."""
        self._ctrl.set_mic_led(muted)

    # -- estado read-only ----------------------------------------------------

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


# ---------------------------------------------------------------------------
# BusProxy
# ---------------------------------------------------------------------------


class BusProxy:
    """Fachada sobre EventBus exposta aos plugins.

    Permite apenas subscribe (plugins não devem publicar eventos internos).
    """

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    def subscribe(self, topic: str) -> asyncio.Queue[Any]:
        """Cria uma fila dedicada para receber eventos do topico."""
        return self._bus.subscribe(topic)


# ---------------------------------------------------------------------------
# StoreProxy
# ---------------------------------------------------------------------------


class StoreProxy:
    """Fachada sobre StateStore exposta aos plugins.

    Permite leitura de contadores e snapshot, sem acesso de escrita.
    """

    def __init__(self, store: StateStore) -> None:
        self._store = store

    def counter(self, key: str) -> int:
        """Retorna o valor atual do contador `key`. 0 se ainda não existe."""
        snap = self._store.snapshot()
        return snap.counters.get(key, 0)

    def snapshot(self) -> ControllerState | None:
        """Retorna o último ControllerState gravado no store (ou None)."""
        return self._store.snapshot().controller


# ---------------------------------------------------------------------------
# PluginContext
# ---------------------------------------------------------------------------


@dataclass
class PluginContext:
    """Container de dependencias injetado em Plugin.on_load().

    Atributos:
        controller: proxy sobre IController com subset de metodos.
        bus:        proxy sobre EventBus; use bus.subscribe(topic).
        store:      proxy sobre StateStore; use store.counter(key).
        log:        logger structlog prefixado "plugin.<plugin_name>".
    """

    controller: ControllerProxy
    bus: BusProxy
    store: StoreProxy
    log: Any  # structlog.BoundLogger ou logging.Logger


def make_plugin_context(
    plugin_name: str,
    controller: IController,
    bus: EventBus,
    store: StateStore,
) -> PluginContext:
    """Fabrica de PluginContext. Chamada pelo PluginsSubsystem em on_load."""
    try:
        from hefesto.utils.logging_config import get_logger as _get_logger
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
