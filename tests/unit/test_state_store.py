"""Testes do StateStore thread-safe."""
from __future__ import annotations

import threading

from hefesto.core.controller import ControllerState
from hefesto.daemon.state_store import StateStore


def _state(battery: int = 75) -> ControllerState:
    return ControllerState(
        battery_pct=battery,
        l2_raw=0,
        r2_raw=0,
        connected=True,
        transport="usb",
    )


def test_inicial_vazio():
    s = StateStore()
    assert s.controller_state is None
    assert s.active_profile is None
    assert s.last_battery_pct is None
    assert s.counter("irrelevante") == 0


def test_update_controller_state():
    s = StateStore()
    st = _state(80)
    s.update_controller_state(st)
    assert s.controller_state == st
    assert s.last_battery_pct == 80


def test_last_battery_tracking_atualiza_apenas_no_delta():
    s = StateStore()
    s.update_controller_state(_state(80))
    s.update_controller_state(_state(80))
    s.update_controller_state(_state(79))
    assert s.last_battery_pct == 79


def test_active_profile():
    s = StateStore()
    s.set_active_profile("shooter")
    assert s.active_profile == "shooter"
    s.set_active_profile(None)
    assert s.active_profile is None


def test_counters_bump_e_reset():
    s = StateStore()
    assert s.bump("udp.received") == 1
    assert s.bump("udp.received") == 2
    assert s.bump("udp.received", delta=5) == 7
    assert s.counter("udp.received") == 7
    s.reset_counters()
    assert s.counter("udp.received") == 0


def test_snapshot_e_imutavel_no_lado_consumidor():
    s = StateStore()
    s.update_controller_state(_state(60))
    s.set_active_profile("driving")
    s.bump("trigger.set", delta=3)

    snap = s.snapshot()
    assert snap.controller == _state(60)
    assert snap.active_profile == "driving"
    assert snap.counters == {"trigger.set": 3}

    # Mutações posteriores não afetam snapshot já emitido
    s.bump("trigger.set")
    s.set_active_profile("bow")
    assert snap.counters == {"trigger.set": 3}
    assert snap.active_profile == "driving"


def test_concorrencia_bump_sob_lock():
    s = StateStore()
    n_threads = 8
    n_bumps = 500

    def worker():
        for _ in range(n_bumps):
            s.bump("k")

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert s.counter("k") == n_threads * n_bumps


def test_concorrencia_escrita_leitura():
    s = StateStore()
    writer_done = threading.Event()
    erros: list[Exception] = []

    def writer():
        try:
            for pct in range(100, -1, -1):
                s.update_controller_state(_state(pct))
        except Exception as exc:
            erros.append(exc)
        finally:
            writer_done.set()

    def reader():
        try:
            for _ in range(500):
                snap = s.snapshot()
                _ = snap.controller
                _ = snap.counters
        except Exception as exc:
            erros.append(exc)

    tw = threading.Thread(target=writer)
    trs = [threading.Thread(target=reader) for _ in range(3)]

    tw.start()
    for t in trs:
        t.start()
    tw.join()
    for t in trs:
        t.join()

    assert erros == []
    assert s.last_battery_pct == 0
