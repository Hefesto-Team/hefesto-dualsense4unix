"""Testes de `hefesto_dualsense4unix.daemon.connection` — AUDIT-FINDING-LOG-EXC-INFO-01."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventTopic
from hefesto_dualsense4unix.daemon.connection import BACKOFF_MAX_SEC, connect_with_retry


@dataclass
class _FakeConfig:
    reconnect_backoff_sec: float = 1.0
    auto_reconnect: bool = True


class _FakeBus:
    def __init__(self) -> None:
        self.published: list[tuple[Any, dict[str, Any]]] = []

    def publish(self, topic: Any, payload: dict[str, Any]) -> None:
        self.published.append((topic, payload))


class _FakeController:
    def __init__(self, fail_until: int = 0, transport: str = "usb") -> None:
        self._calls = 0
        self._fail_until = fail_until
        self._transport = transport

    def connect(self) -> None:
        self._calls += 1
        if self._calls <= self._fail_until:
            raise ConnectionError(f"tentativa {self._calls} falhou")

    def get_transport(self) -> str:
        return self._transport


@dataclass
class _FakeDaemon:
    config: _FakeConfig
    controller: _FakeController
    bus: _FakeBus = field(default_factory=_FakeBus)
    _stop_event: asyncio.Event | None = None

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        return fn(*args)


class _SleepRecorder:
    """Patches `asyncio.wait_for` e `asyncio.sleep` para registrar timeouts sem esperar."""

    def __init__(self) -> None:
        self.calls: list[float] = []

    async def wait_for(self, coro: Any, timeout: float) -> None:
        self.calls.append(timeout)
        if asyncio.iscoroutine(coro):
            coro.close()
        raise asyncio.TimeoutError()

    async def sleep(self, delay: float) -> None:
        self.calls.append(delay)


@pytest.mark.asyncio
@pytest.mark.parametrize("transporte", ["usb", "bt"])
async def test_connect_with_retry_sucesso_primeira_tentativa(transporte: str) -> None:
    daemon = _FakeDaemon(
        config=_FakeConfig(reconnect_backoff_sec=1.0),
        controller=_FakeController(fail_until=0, transport=transporte),
        _stop_event=asyncio.Event(),
    )
    await connect_with_retry(daemon)
    assert daemon.controller._calls == 1
    assert any(topic for topic, _ in daemon.bus.published)
    topic, payload = daemon.bus.published[-1]
    assert topic == EventTopic.CONTROLLER_CONNECTED
    assert payload["transport"] == transporte


@pytest.mark.asyncio
@pytest.mark.parametrize("transporte", ["usb", "bt"])
async def test_connect_with_retry_backoff_exponencial(
    monkeypatch: pytest.MonkeyPatch, transporte: str
) -> None:
    """3 falhas consecutivas → backoff vai 1s, 2s, 4s (dobra a cada falha)."""
    daemon = _FakeDaemon(
        config=_FakeConfig(reconnect_backoff_sec=1.0),
        controller=_FakeController(fail_until=3, transport=transporte),
        _stop_event=asyncio.Event(),
    )
    recorder = _SleepRecorder()
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.connection.asyncio.wait_for", recorder.wait_for)  # noqa: E501

    await connect_with_retry(daemon)

    assert recorder.calls == [1.0, 2.0, 4.0], f"esperado [1,2,4], obtido {recorder.calls}"
    assert daemon.controller._calls == 4
    _, payload = daemon.bus.published[-1]
    assert payload["transport"] == transporte


@pytest.mark.asyncio
@pytest.mark.parametrize("transporte", ["usb", "bt"])
async def test_connect_with_retry_backoff_com_teto(
    monkeypatch: pytest.MonkeyPatch, transporte: str
) -> None:
    """Após suficientes falhas, backoff cresce mas não passa de BACKOFF_MAX_SEC."""
    daemon = _FakeDaemon(
        config=_FakeConfig(reconnect_backoff_sec=10.0),
        controller=_FakeController(fail_until=5, transport=transporte),
        _stop_event=asyncio.Event(),
    )
    recorder = _SleepRecorder()
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.connection.asyncio.wait_for", recorder.wait_for)  # noqa: E501

    await connect_with_retry(daemon)

    assert recorder.calls == [10.0, 20.0, BACKOFF_MAX_SEC, BACKOFF_MAX_SEC, BACKOFF_MAX_SEC]
    _, payload = daemon.bus.published[-1]
    assert payload["transport"] == transporte


@pytest.mark.asyncio
@pytest.mark.parametrize("transporte", ["usb", "bt"])
async def test_connect_with_retry_aborta_no_shutdown(
    monkeypatch: pytest.MonkeyPatch, transporte: str
) -> None:
    """Se stop_event setar durante o backoff, connect_with_retry retorna sem conectar."""
    daemon = _FakeDaemon(
        config=_FakeConfig(reconnect_backoff_sec=1.0),
        controller=_FakeController(fail_until=99, transport=transporte),
        _stop_event=asyncio.Event(),
    )

    async def stop_triggered_wait_for(coro: Any, timeout: float) -> None:
        if asyncio.iscoroutine(coro):
            coro.close()
        return None

    monkeypatch.setattr("hefesto_dualsense4unix.daemon.connection.asyncio.wait_for", stop_triggered_wait_for)  # noqa: E501

    await connect_with_retry(daemon)

    assert daemon.controller._calls == 1
    assert daemon.bus.published == []


@pytest.mark.asyncio
@pytest.mark.parametrize("transporte", ["usb", "bt"])
async def test_connect_with_retry_sem_auto_reconnect_propaga_erro(transporte: str) -> None:
    daemon = _FakeDaemon(
        config=_FakeConfig(reconnect_backoff_sec=1.0, auto_reconnect=False),
        controller=_FakeController(fail_until=1, transport=transporte),
        _stop_event=asyncio.Event(),
    )
    with pytest.raises(ConnectionError):
        await connect_with_retry(daemon)
    assert daemon.controller._calls == 1
    assert daemon.bus.published == []


def test_is_connected_default_false_quando_attr_ausente() -> None:
    """`PyDualSenseController.is_connected()` retorna False quando `connected` ausente."""
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

    ctrl = PyDualSenseController()

    class _FakeDS:
        pass

    ctrl._ds = _FakeDS()  # type: ignore[assignment]
    assert ctrl.is_connected() is False, "deve retornar False quando attr ausente (conservador)"


def test_is_connected_true_quando_attr_true() -> None:
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

    ctrl = PyDualSenseController()

    class _FakeDS:
        connected = True

    ctrl._ds = _FakeDS()  # type: ignore[assignment]
    assert ctrl.is_connected() is True


def test_is_connected_false_quando_attr_false() -> None:
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

    ctrl = PyDualSenseController()

    class _FakeDS:
        connected = False

    ctrl._ds = _FakeDS()  # type: ignore[assignment]
    assert ctrl.is_connected() is False


def test_is_connected_false_sem_ds() -> None:
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

    ctrl = PyDualSenseController()
    assert ctrl.is_connected() is False
