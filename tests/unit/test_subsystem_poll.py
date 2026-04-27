"""Testes unitários do subsystem poll (isolamento de BatteryDebouncer e evdev).

Prova que:
  - BatteryDebouncer.should_emit retorna True na primeira leitura.
  - BatteryDebouncer.should_emit respeita min-interval.
  - BatteryDebouncer.should_emit dispara em delta >= 1%.
  - evdev_buttons_once retorna frozenset vazio se evdev indisponível.
  - evdev_buttons_once retorna frozenset vazio em exceção.
  - PollSubsystem.is_enabled é sempre True.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon.subsystems.poll import (
    BATTERY_DEBOUNCE_SEC,
    BatteryDebouncer,
    PollSubsystem,
    evdev_buttons_once,
)


class TestBatteryDebouncer:
    def test_primeiro_valor_sempre_emite(self) -> None:
        db = BatteryDebouncer()
        assert db.should_emit(80, 0.0) is True

    def test_min_interval_bloqueia(self) -> None:
        db = BatteryDebouncer()
        db.mark_emitted(80, 100.0)
        # now = 100.05 → interval < 0.1s
        assert db.should_emit(80, 100.05) is False

    def test_delta_dispara(self) -> None:
        db = BatteryDebouncer()
        db.mark_emitted(80, 0.0)
        # delta = 1 (>= BATTERY_DELTA_THRESHOLD_PCT), interval >= min
        assert db.should_emit(79, 1.0) is True

    def test_sem_delta_sem_disparo(self) -> None:
        db = BatteryDebouncer()
        db.mark_emitted(80, 0.0)
        # delta = 0, elapsed = 1s < BATTERY_DEBOUNCE_SEC
        assert db.should_emit(80, 1.0) is False

    def test_debounce_sec_dispara_mesmo_sem_delta(self) -> None:
        db = BatteryDebouncer()
        db.mark_emitted(80, 0.0)
        # elapsed >= BATTERY_DEBOUNCE_SEC → dispara
        assert db.should_emit(80, BATTERY_DEBOUNCE_SEC + 0.1) is True

    def test_mark_emitted_atualiza_estado(self) -> None:
        db = BatteryDebouncer()
        db.mark_emitted(75, 10.0)
        assert db.last_emitted_value == 75
        assert db.last_emit_at == 10.0


class TestEvdevButtonsOnce:
    def _make_daemon_sem_evdev(self) -> MagicMock:
        d = MagicMock()
        d.controller = MagicMock(spec=[])  # sem _evdev
        return d

    def _make_daemon_com_evdev(self, available: bool, snapshot_result: object) -> MagicMock:
        d = MagicMock()
        evdev = MagicMock()
        evdev.is_available.return_value = available
        evdev.snapshot.return_value = snapshot_result
        d.controller._evdev = evdev
        return d

    def test_sem_evdev_retorna_frozenset_vazio(self) -> None:
        d = self._make_daemon_sem_evdev()
        result = evdev_buttons_once(d)
        assert result == frozenset()

    def test_evdev_indisponivel_retorna_frozenset_vazio(self) -> None:
        d = self._make_daemon_com_evdev(available=False, snapshot_result=None)
        result = evdev_buttons_once(d)
        assert result == frozenset()

    def test_evdev_disponivel_retorna_botoes(self) -> None:
        snap = MagicMock()
        snap.buttons_pressed = ["cross", "circle"]
        d = self._make_daemon_com_evdev(available=True, snapshot_result=snap)
        result = evdev_buttons_once(d)
        assert result == frozenset({"cross", "circle"})

    def test_excecao_retorna_frozenset_vazio(self) -> None:
        d = MagicMock()
        evdev = MagicMock()
        evdev.is_available.return_value = True
        evdev.snapshot.side_effect = RuntimeError("explodiu")
        d.controller._evdev = evdev
        result = evdev_buttons_once(d)
        assert result == frozenset()


class TestPollSubsystem:
    def test_is_enabled_sempre_true(self) -> None:
        subsystem = PollSubsystem()
        cfg = MagicMock()
        assert subsystem.is_enabled(cfg) is True

    @pytest.mark.asyncio
    async def test_start_noop(self) -> None:
        subsystem = PollSubsystem()
        ctx = MagicMock()
        await subsystem.start(ctx)  # não lança

    @pytest.mark.asyncio
    async def test_stop_noop(self) -> None:
        subsystem = PollSubsystem()
        await subsystem.stop()  # não lança
