"""Event bus async baseado em asyncio.Queue por subscriber.

Modelo pubsub simples:
  - `publish(topic, payload)` entrega para todas as filas registradas no tópico.
  - `subscribe(topic)` devolve uma `asyncio.Queue` dedicada e não-bloqueante.
  - Publisher nunca bloqueia: se a fila está cheia, o evento mais antigo
    é descartado (política `drop_oldest`) e emite log.warning uma vez por
    subscriber congestionado no ciclo.

Tópicos canônicos do domínio Hefesto - Dualsense4Unix (constantes em `EventTopic`):
  - `state.update`       — novo `ControllerState` completo.
  - `button.down` / `button.up` — mudanças de botão.
  - `battery.change`     — bateria mudou segundo debounce (ver ADR-008).
  - `controller.connected` / `controller.disconnected`.
  - `trigger.set`        — trigger efetivamente aplicado.
  - `led.set`            — led efetivamente aplicado.

Thread-safety: `publish` pode ser chamado de dentro de um executor
(thread diferente do loop). A entrega usa `loop.call_soon_threadsafe`
para enfileirar sem races. `subscribe` deve ser chamado do loop.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_MAXSIZE = 256


class EventTopic:
    STATE_UPDATE = "state.update"
    BUTTON_DOWN = "button.down"
    BUTTON_UP = "button.up"
    BATTERY_CHANGE = "battery.change"
    CONTROLLER_CONNECTED = "controller.connected"
    CONTROLLER_DISCONNECTED = "controller.disconnected"
    TRIGGER_SET = "trigger.set"
    LED_SET = "led.set"


@dataclass
class _Subscriber:
    queue: asyncio.Queue[Any]
    overflow_logged: bool = False


@dataclass
class EventBus:
    """Barramento pubsub assíncrono e thread-safe no lado do publisher."""

    queue_maxsize: int = DEFAULT_QUEUE_MAXSIZE
    _subs: dict[str, list[_Subscriber]] = field(default_factory=dict)
    _loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Marca qual loop o bus serve. Chamado uma vez no start do daemon."""
        self._loop = loop

    def subscribe(self, topic: str) -> asyncio.Queue[Any]:
        """Cria uma fila dedicada para o subscriber. Sempre chamada do loop."""
        queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=self.queue_maxsize)
        sub = _Subscriber(queue=queue)
        self._subs.setdefault(topic, []).append(sub)
        return queue

    def unsubscribe(self, topic: str, queue: asyncio.Queue[Any]) -> None:
        subs = self._subs.get(topic, [])
        self._subs[topic] = [s for s in subs if s.queue is not queue]

    def publish(self, topic: str, payload: Any) -> None:
        """Publica um evento. Seguro para chamar de threads não-loop.

        Se chamado do loop do daemon, entrega direto. Se chamado de outra
        thread, usa `call_soon_threadsafe` para marshal. Filas cheias
        descartam o evento mais antigo e logam warning uma vez.
        """
        subs = list(self._subs.get(topic, ()))
        if not subs:
            return

        loop = self._loop
        if loop is None:
            for sub in subs:
                self._deliver(sub, topic, payload)
            return

        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None

        if running is loop:
            for sub in subs:
                self._deliver(sub, topic, payload)
        else:
            for sub in subs:
                loop.call_soon_threadsafe(self._deliver, sub, topic, payload)

    def _deliver(self, sub: _Subscriber, topic: str, payload: Any) -> None:
        try:
            sub.queue.put_nowait(payload)
            sub.overflow_logged = False
            return
        except asyncio.QueueFull:
            pass

        with contextlib.suppress(asyncio.QueueEmpty):
            sub.queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                sub.queue.put_nowait(payload)

        if not sub.overflow_logged:
            logger.warning(
                "fila de subscriber cheia em %s — evento antigo descartado",
                topic,
            )
            sub.overflow_logged = True

    def topics(self) -> Iterable[str]:
        return tuple(self._subs.keys())

    def subscriber_count(self, topic: str) -> int:
        return len(self._subs.get(topic, []))


__all__ = ["DEFAULT_QUEUE_MAXSIZE", "EventBus", "EventTopic"]
