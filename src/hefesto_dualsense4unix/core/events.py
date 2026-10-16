"""Event bus async baseado em asyncio.Queue por subscriber.

Pubsub simples: `publish(topic, payload)` entrega a todas as filas do tópico; `subscribe(topic)`
devolve uma `asyncio.Queue` dedicada. O publisher nunca bloqueia: com a fila cheia, o evento mais
antigo é descartado (`drop_oldest`) e um log.warning sai uma vez por subscriber congestionado.
Os tópicos são as constantes de `EventTopic` (o que cada um leva está em
docs/research/o-porque-dos-modulos.md). `publish` pode vir de um executor: a entrega usa
`loop.call_soon_threadsafe`; `subscribe` é chamado do loop.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
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
    MIC_DA_MESA = "mic.da_mesa"
    MIC_DO_JOGO = "mic.do_jogo"
    SOM_DO_SISTEMA = "som.do_sistema"
    JOGO_VIBRACAO = "jogo.vibracao"
    JOGO_FECHOU = "jogo.fechou"
    JOGO_GATILHO = "jogo.gatilho"
    JOGO_HAPTICA = "jogo.haptica"
    PERFIL_TROCOU = "perfil.trocou"
    ACESSORIOS_GESTO = "acessorios.gesto"
    ACESSORIOS_ESTADO = "acessorios.estado"


#: Nomes reservados SEM fonte (momento do jogo, app que abre, hora): ninguém publica nem assina
#: até a fonte existir; o nome fica guardado para as extensões não inventarem outro.
TOPICOS_RESERVADOS: frozenset[str] = frozenset({
    "jogo.momento",
    "sistema.app_abriu",
    "sistema.hora",
})


#: Os tópicos de ESTADO: o último valor publicado fica guardado e vai a quem assina depois,
#: porque o estado vale até a próxima troca e quem conecta com o jogo já aberto não tem
#: de esperá-la. Evento (a vibração, o jogo que fechou) não entra aqui: repeti-lo seria mentir.
TOPICOS_DE_ESTADO: frozenset[str] = frozenset(
    {EventTopic.PERFIL_TROCOU, EventTopic.ACESSORIOS_ESTADO}
)


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
    _estado: dict[str, Any] = field(default_factory=dict)
    #: Quantos eventos cada tópico já publicou (com ou sem assinante): é o que o
    #: `hefesto_events_dispatched_total{topic}` das métricas lê.
    _publicados: dict[str, int] = field(default_factory=dict)
    _trava_da_contagem: threading.Lock = field(default_factory=threading.Lock)

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Marca qual loop o bus serve. Chamado uma vez no start do daemon."""
        self._loop = loop

    def subscribe(self, topic: str) -> asyncio.Queue[Any]:
        """Cria uma fila dedicada para o subscriber. Sempre chamada do loop."""
        queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=self.queue_maxsize)
        sub = _Subscriber(queue=queue)
        self._subs.setdefault(topic, []).append(sub)
        if topic in self._estado:
            queue.put_nowait(self._estado[topic])
        return queue

    def unsubscribe(self, topic: str, queue: asyncio.Queue[Any]) -> None:
        subs = self._subs.get(topic, [])
        self._subs[topic] = [s for s in subs if s.queue is not queue]

    def publish(self, topic: str, payload: Any) -> None:
        """Publica um evento. Seguro para chamar de threads não-loop."""
        with self._trava_da_contagem:
            self._publicados[topic] = self._publicados.get(topic, 0) + 1
        if topic in TOPICOS_DE_ESTADO:
            self._estado[topic] = payload
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

    def contagem_por_topico(self) -> dict[str, int]:
        """Cópia da contagem de eventos publicados, por tópico."""
        with self._trava_da_contagem:
            return dict(self._publicados)

    def topics(self) -> Iterable[str]:
        return tuple(self._subs.keys())

    def subscriber_count(self, topic: str) -> int:
        return len(self._subs.get(topic, []))

    def ultimo(self, topic: str) -> Any | None:
        """O último valor publicado de um tópico de ESTADO, ou None (síncrono, sem fila)."""
        return self._estado.get(topic)


__all__ = ["DEFAULT_QUEUE_MAXSIZE", "TOPICOS_DE_ESTADO", "EventBus", "EventTopic"]
