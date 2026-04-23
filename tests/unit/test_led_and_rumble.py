"""Testes de LED control e rumble com throttle."""
from __future__ import annotations

import pytest

from hefesto.core.led_control import (
    LedSettings,
    apply_led_settings,
    hex_to_rgb,
    off,
    player_bitmask,
)
from hefesto.core.rumble import (
    DEFAULT_MIN_INTERVAL_SEC,
    RumbleCommand,
    RumbleEngine,
)
from hefesto.testing import FakeController


class TestLedSettings:
    def test_defaults(self):
        s = LedSettings(lightbar=(255, 0, 128))
        assert s.lightbar == (255, 0, 128)
        assert s.player_leds == (False, False, False, False, False)
        assert s.mic_led is False

    def test_componente_fora_de_byte_rejeita(self):
        with pytest.raises(ValueError, match="lightbar"):
            LedSettings(lightbar=(300, 0, 0))

    def test_tamanho_errado_rejeita(self):
        with pytest.raises(ValueError, match="3 componentes"):
            LedSettings(lightbar=(10, 20))  # type: ignore[arg-type]

    def test_off_helper(self):
        assert off().lightbar == (0, 0, 0)


class TestApplyLedSettings:
    def test_chama_set_led_no_controller(self):
        fc = FakeController()
        fc.connect()
        apply_led_settings(fc, LedSettings(lightbar=(100, 200, 50)))
        leds = [c for c in fc.commands if c.kind == "set_led"]
        assert len(leds) == 1
        assert leds[0].payload == (100, 200, 50)

    def test_apply_led_settings_propagates_mic_led(self):
        """apply_led_settings invoca set_mic_led com o valor de mic_led (INFRA-SET-MIC-LED-01)."""
        fc = FakeController()
        fc.connect()
        apply_led_settings(fc, LedSettings(lightbar=(0, 0, 0), mic_led=True))
        assert fc.mic_led_history == [True]

    def test_apply_led_settings_mic_led_false(self):
        """apply_led_settings propaga mic_led=False corretamente."""
        fc = FakeController()
        fc.connect()
        apply_led_settings(fc, LedSettings(lightbar=(255, 0, 0), mic_led=False))
        assert fc.mic_led_history == [False]


class TestPlayerBitmask:
    def test_todos_apagados(self):
        assert player_bitmask((False, False, False, False, False)) == 0

    def test_todos_acesos(self):
        assert player_bitmask((True, True, True, True, True)) == 31

    def test_alternados(self):
        assert player_bitmask((True, False, True, False, True)) == 0b10101


class TestHexToRgb:
    def test_com_hash(self):
        assert hex_to_rgb("#FF8000") == (255, 128, 0)

    def test_sem_hash(self):
        assert hex_to_rgb("ff8000") == (255, 128, 0)

    def test_invalido(self):
        with pytest.raises(ValueError, match="RRGGBB"):
            hex_to_rgb("#F80")
        with pytest.raises(ValueError, match="não numérico"):
            hex_to_rgb("#ZZZZZZ")


class TestRumbleEngine:
    def _mk_engine(self, interval: float = DEFAULT_MIN_INTERVAL_SEC):
        fc = FakeController()
        fc.connect()
        clock = {"t": 0.0}

        def now() -> float:
            return clock["t"]

        engine = RumbleEngine(fc, min_interval_sec=interval, time_fn=now)
        return fc, engine, clock

    def test_primeiro_tick_aplica(self):
        fc, engine, _clock = self._mk_engine(interval=0.02)
        engine.set(100, 200)
        applied = engine.tick()
        assert applied == RumbleCommand(weak=100, strong=200)
        rumbles = [c for c in fc.commands if c.kind == "set_rumble"]
        assert rumbles[-1].payload == (100, 200)

    def test_segundo_tick_respeita_throttle(self):
        _fc, engine, clock = self._mk_engine(interval=0.02)
        engine.set(100, 200)
        engine.tick()
        clock["t"] += 0.005
        engine.set(150, 50)
        applied = engine.tick()
        assert applied is None  # dentro da janela — suprime

    def test_depois_do_intervalo_aplica_valor_mais_recente(self):
        _fc, engine, clock = self._mk_engine(interval=0.02)
        engine.set(100, 200)
        engine.tick()
        clock["t"] += 0.03  # passa janela
        engine.set(150, 50)
        applied = engine.tick()
        assert applied == RumbleCommand(weak=150, strong=50)

    def test_stop_ignora_throttle_e_aplica_imediato(self):
        _fc, engine, clock = self._mk_engine(interval=0.5)
        engine.set(100, 200)
        engine.tick()  # aplicou
        clock["t"] += 0.01  # dentro da janela
        engine.set(0, 0)
        applied = engine.tick()
        assert applied is not None
        assert applied.is_stop()

    def test_tick_sem_pending_retorna_none(self):
        _fc, engine, _clock = self._mk_engine()
        assert engine.tick() is None

    def test_clamp_de_valores(self):
        fc, engine, _clock = self._mk_engine(interval=0.02)
        engine.set(-50, 500)
        engine.tick()
        rumbles = [c for c in fc.commands if c.kind == "set_rumble"]
        assert rumbles[-1].payload == (0, 255)

    def test_flood_suprimido_mas_ultimo_valor_pendente_aplicado(self):
        # Janela grande (0.5s) > soma dos deltas do loop (100 * 0.001 = 0.1s)
        # garante que só o tick inicial aplica durante o flood.
        fc, engine, clock = self._mk_engine(interval=0.5)
        engine.set(10, 20)
        engine.tick()
        for i in range(100):
            engine.set(50 + i % 10, 100 + i % 10)
            clock["t"] += 0.001
            engine.tick()
        rumbles = [c for c in fc.commands if c.kind == "set_rumble"]
        assert len(rumbles) == 1
        clock["t"] += 0.5
        applied = engine.tick()
        assert applied is not None
        rumbles = [c for c in fc.commands if c.kind == "set_rumble"]
        assert len(rumbles) == 2

    def test_stop_via_metodo_explicito(self):
        _fc, engine, clock = self._mk_engine(interval=0.5)
        engine.set(200, 200)
        engine.tick()
        clock["t"] += 0.01
        engine.stop()
        assert engine.last_applied is not None
        assert engine.last_applied.is_stop()
