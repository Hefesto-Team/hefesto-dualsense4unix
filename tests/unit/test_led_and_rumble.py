"""Testes de LED control."""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.core.led_control import (
    LedSettings,
    hex_to_rgb,
    off,
    player_bitmask,
)


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

