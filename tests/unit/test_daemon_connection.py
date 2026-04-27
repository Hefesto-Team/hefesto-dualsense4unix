"""Testes de `hefesto_dualsense4unix.daemon.connection` — AUDIT-FINDING-LOG-EXC-INFO-01.

Cobre:
- `connect_with_retry` backoff exponencial (1s, 2s, 4s, ..., teto 30s).
- `connect_with_retry` aborta no shutdown via `stop_event`.
- Reset do backoff ao valor inicial após sucesso (não testado aqui, coberto indiretamente).

Usa fakes puros — sem pydualsense real.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest

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
    def __init__(self, fail_until: int = 0) -> None:
        self._calls = 0
        self._fail_until = fail_until

    def connect(self) -> None:
        self._calls += 1
        if self._calls <= self._fail_until:
            raise ConnectionError(f"tentativa {self._calls} falhou")

    def get_transport(self) -> str:
        return "usb"


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
        # Cancela o coro para não deixar pendente; levanta TimeoutError como a implementação real.
        if asyncio.iscoroutine(coro):
            coro.close()
        raise asyncio.TimeoutError()

    async def sleep(self, delay: float) -> None:
        self.calls.append(delay)


@pytest.mark.asyncio
async def test_connect_with_retry_sucesso_primeira_tentativa() -> None:
    daemon = _FakeDaemon(
        config=_FakeConfig(reconnect_backoff_sec=1.0),
        controller=_FakeController(fail_until=0),
        _stop_event=asyncio.Event(),
    )
    await connect_with_retry(daemon)
    assert daemon.controller._calls == 1
    assert any(topic for topic, _ in daemon.bus.published)


@pytest.mark.asyncio
async def test_connect_with_retry_backoff_exponencial(monkeypatch: pytest.MonkeyPatch) -> None:
    """3 falhas consecutivas → backoff vai 1s, 2s, 4s (dobra a cada falha)."""
    daemon = _FakeDaemon(
        config=_FakeConfig(reconnect_backoff_sec=1.0),
        controller=_FakeController(fail_until=3),
        _stop_event=asyncio.Event(),
    )
    recorder = _SleepRecorder()
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.connection.asyncio.wait_for", recorder.wait_for)  # noqa: E501

    await connect_with_retry(daemon)

    # 3 falhas geraram 3 esperas com backoff 1.0, 2.0, 4.0.
    assert recorder.calls == [1.0, 2.0, 4.0], f"esperado [1,2,4], obtido {recorder.calls}"
    assert daemon.controller._calls == 4  # 3 falhas + 1 sucesso


@pytest.mark.asyncio
async def test_connect_with_retry_backoff_com_teto(monkeypatch: pytest.MonkeyPatch) -> None:
    """Após suficientes falhas, backoff cresce mas não passa de BACKOFF_MAX_SEC."""
    # Com backoff inicial 10s: 10 → 20 → 30 (teto) → 30 → 30...
    daemon = _FakeDaemon(
        config=_FakeConfig(reconnect_backoff_sec=10.0),
        controller=_FakeController(fail_until=5),
        _stop_event=asyncio.Event(),
    )
    recorder = _SleepRecorder()
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.connection.asyncio.wait_for", recorder.wait_for)  # noqa: E501

    await connect_with_retry(daemon)

    assert recorder.calls == [10.0, 20.0, BACKOFF_MAX_SEC, BACKOFF_MAX_SEC, BACKOFF_MAX_SEC]


@pytest.mark.asyncio
async def test_connect_with_retry_aborta_no_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    """Se stop_event setar durante o backoff, connect_with_retry retorna sem conectar."""
    daemon = _FakeDaemon(
        config=_FakeConfig(reconnect_backoff_sec=1.0),
        controller=_FakeController(fail_until=99),  # sempre falha
        _stop_event=asyncio.Event(),
    )

    # wait_for que SINALIZA sucesso (stop_event.wait completou) no primeiro call.
    async def stop_triggered_wait_for(coro: Any, timeout: float) -> None:
        if asyncio.iscoroutine(coro):
            coro.close()
        return None  # stop_event.wait() retornou sem timeout — aborta.

    monkeypatch.setattr("hefesto_dualsense4unix.daemon.connection.asyncio.wait_for", stop_triggered_wait_for)  # noqa: E501

    await connect_with_retry(daemon)

    # Primeira tentativa falhou, stop_event "sinalizou" no sleep, função retornou.
    assert daemon.controller._calls == 1


@pytest.mark.asyncio
async def test_connect_with_retry_sem_auto_reconnect_propaga_erro() -> None:
    daemon = _FakeDaemon(
        config=_FakeConfig(reconnect_backoff_sec=1.0, auto_reconnect=False),
        controller=_FakeController(fail_until=1),
        _stop_event=asyncio.Event(),
    )
    with pytest.raises(ConnectionError):
        await connect_with_retry(daemon)
    assert daemon.controller._calls == 1


# -----------------------------------------------------------------------------
# is_connected — default conservador False (item 7 do must-do)
# -----------------------------------------------------------------------------


def test_is_connected_default_false_quando_attr_ausente() -> None:
    """`PyDualSenseController.is_connected()` retorna False quando `connected` ausente."""
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

    ctrl = PyDualSenseController()

    class _FakeDS:
        # Intencionalmente sem atributo `connected`.
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
