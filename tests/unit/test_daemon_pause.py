"""Pausar/retomar em runtime (FEAT-DAEMON-PAUSE-RESUME-01).

Pausado, o daemon segue lendo estado/bateria e publicando STATE_UPDATE, mas
NÃO despacha input (BUTTON_DOWN/UP, teclado/mouse/hotkey) — daemon vivo sem
afetar o sistema. Reusa o gate do grace-period no _poll_loop.
"""
from __future__ import annotations

import asyncio

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.testing import FakeController


def _state(buttons: frozenset[str] | None = None) -> ControllerState:
    return ControllerState(
        battery_pct=80,
        l2_raw=0,
        r2_raw=0,
        connected=True,
        transport="usb",
        buttons_pressed=buttons or frozenset(),
    )


def _config(**over: object) -> DaemonConfig:
    base: dict[str, object] = dict(
        poll_hz=200,
        auto_reconnect=False,
        ipc_enabled=False,
        udp_enabled=False,
        autoswitch_enabled=False,
        mouse_emulation_enabled=False,
        keyboard_emulation_enabled=False,
        ps_button_action="none",
        mic_button_toggles_system=False,
    )
    base.update(over)
    return DaemonConfig(**base)  # type: ignore[arg-type]


def _no_persist(monkeypatch: pytest.MonkeyPatch, *, loaded: bool = False) -> None:
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.save_paused_state", lambda _p: None
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.load_paused_state", lambda: loaded
    )


def test_pause_resume_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """pause()/resume() são idempotentes; persistem só nas transições."""
    saved: list[bool] = []
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.save_paused_state", saved.append
    )
    daemon = Daemon(controller=FakeController(transport="usb"), config=_config())
    assert daemon.is_paused() is False
    daemon.pause()
    daemon.pause()
    assert daemon.is_paused() is True
    daemon.resume()
    daemon.resume()
    assert daemon.is_paused() is False
    assert saved == [True, False]


def test_session_paused_persistence(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """save/load_paused_state via arquivo-flag em config_dir."""
    from hefesto_dualsense4unix.utils import session

    monkeypatch.setattr(session, "config_dir", lambda ensure=False: tmp_path)
    assert session.load_paused_state() is False
    session.save_paused_state(True)
    assert session.load_paused_state() is True
    session.save_paused_state(False)
    assert session.load_paused_state() is False


@pytest.mark.asyncio
async def test_paused_suppresses_button_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pausado (fora do grace), pressionar um botão NÃO publica BUTTON_DOWN,
    mas o estado segue sendo lido (telemetria preservada)."""
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.05)
    _no_persist(monkeypatch)
    fc = FakeController(transport="usb", states=[_state()])
    bus = EventBus()
    store = StateStore()
    down_queue = bus.subscribe(EventTopic.BUTTON_DOWN)

    daemon = Daemon(controller=fc, bus=bus, store=store, config=_config())
    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.12)  # passa o grace
    daemon.pause()
    fc.set_buttons(["cross"])  # pressiona DEPOIS de pausar
    await asyncio.sleep(0.10)
    daemon.stop()
    await run_task

    assert down_queue.qsize() == 0
    assert store.counter("button.down.emitted") == 0
    assert store.counter("poll.tick") >= 1


@pytest.mark.asyncio
async def test_resume_restores_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Após resume(), pressionar volta a publicar BUTTON_DOWN."""
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.05)
    _no_persist(monkeypatch)
    fc = FakeController(transport="usb", states=[_state()])
    bus = EventBus()
    store = StateStore()
    down_queue = bus.subscribe(EventTopic.BUTTON_DOWN)

    daemon = Daemon(controller=fc, bus=bus, store=store, config=_config())
    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.12)
    daemon.pause()
    fc.set_buttons(["cross"])
    await asyncio.sleep(0.08)
    assert down_queue.qsize() == 0  # pausado: nada
    fc.set_buttons([])
    daemon.resume()
    await asyncio.sleep(0.06)
    fc.set_buttons(["circle"])  # pressiona após retomar
    await asyncio.sleep(0.08)
    daemon.stop()
    await run_task

    downs = []
    while not down_queue.empty():
        downs.append(down_queue.get_nowait())
    assert any(e["button"] == "circle" for e in downs)


@pytest.mark.asyncio
async def test_run_restores_paused_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """run() nasce pausado se a sessão anterior terminou pausada."""
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.02)
    _no_persist(monkeypatch, loaded=True)
    fc = FakeController(transport="usb", states=[_state()])
    daemon = Daemon(controller=fc, config=_config())
    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.06)
    assert daemon.is_paused() is True
    daemon.stop()
    await run_task
