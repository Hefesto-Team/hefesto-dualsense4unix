"""Testes do EventBus async."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

from hefesto_dualsense4unix.core.events import EventBus, EventTopic


@pytest.mark.asyncio
async def test_subscribe_entrega_publicacao():
    bus = EventBus()
    queue = bus.subscribe(EventTopic.STATE_UPDATE)
    bus.publish(EventTopic.STATE_UPDATE, {"battery": 80})
    payload = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert payload == {"battery": 80}


@pytest.mark.asyncio
async def test_multiplos_subscribers_recebem_copia_logica():
    bus = EventBus()
    q1 = bus.subscribe("t")
    q2 = bus.subscribe("t")
    bus.publish("t", "hello")
    assert await asyncio.wait_for(q1.get(), timeout=1.0) == "hello"
    assert await asyncio.wait_for(q2.get(), timeout=1.0) == "hello"


@pytest.mark.asyncio
async def test_unsubscribe_para_de_receber():
    bus = EventBus()
    queue = bus.subscribe("t")
    bus.unsubscribe("t", queue)
    bus.publish("t", "perdido")
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(queue.get(), timeout=0.05)


@pytest.mark.asyncio
async def test_topico_sem_subscriber_e_noop():
    bus = EventBus()
    bus.publish("inexistente", "x")


@pytest.mark.asyncio
async def test_fila_cheia_drop_oldest():
    bus = EventBus(queue_maxsize=3)
    queue = bus.subscribe("t")
    for i in range(5):
        bus.publish("t", i)
    # Esperado: fila com os 3 mais recentes — 2, 3, 4
    received = []
    while not queue.empty():
        received.append(await queue.get())
    assert received == [2, 3, 4]


@pytest.mark.asyncio
async def test_publish_cross_thread_via_loop():
    bus = EventBus()
    loop = asyncio.get_running_loop()
    bus.bind_loop(loop)
    queue = bus.subscribe(EventTopic.BATTERY_CHANGE)

    def produtor():
        bus.publish(EventTopic.BATTERY_CHANGE, 42)

    with ThreadPoolExecutor(max_workers=1) as ex:
        await loop.run_in_executor(ex, produtor)

    payload = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert payload == 42


@pytest.mark.asyncio
async def test_subscriber_count():
    bus = EventBus()
    assert bus.subscriber_count("t") == 0
    q1 = bus.subscribe("t")
    q2 = bus.subscribe("t")
    assert bus.subscriber_count("t") == 2
    bus.unsubscribe("t", q1)
    assert bus.subscriber_count("t") == 1
    bus.unsubscribe("t", q2)
    assert bus.subscriber_count("t") == 0


@pytest.mark.asyncio
async def test_concorrencia_publishers_multiplas_threads():
    bus = EventBus(queue_maxsize=10000)
    loop = asyncio.get_running_loop()
    bus.bind_loop(loop)
    queue = bus.subscribe("x")

    n_threads = 4
    n_msgs = 50

    def produtor(offset: int):
        for i in range(n_msgs):
            bus.publish("x", offset * 1000 + i)

    with ThreadPoolExecutor(max_workers=n_threads) as ex:
        await asyncio.gather(
            *(loop.run_in_executor(ex, produtor, k) for k in range(n_threads))
        )

    # Drena tudo
    received = []
    while True:
        try:
            received.append(await asyncio.wait_for(queue.get(), timeout=0.1))
        except asyncio.TimeoutError:
            break
    assert len(received) == n_threads * n_msgs
