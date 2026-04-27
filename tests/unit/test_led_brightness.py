"""Testes para ``LedSettings.apply_brightness`` (FEAT-LED-BRIGHTNESS-01).

Cobertura:
- default 1.0 não altera RGB;
- 0.5 divide cada canal pela metade;
- 0.0 zera todos os canais;
- valores > 1.0 sofrem clamp por canal (0-255).
"""
from __future__ import annotations

from hefesto_dualsense4unix.core.led_control import LedSettings


class TestApplyBrightness:
    def test_default_um_preserva_rgb(self) -> None:
        original = LedSettings(lightbar=(200, 100, 50))
        escalado = original.apply_brightness(1.0)
        assert escalado.lightbar == (200, 100, 50)

    def test_metade_divide_canais(self) -> None:
        original = LedSettings(lightbar=(200, 100, 50))
        escalado = original.apply_brightness(0.5)
        assert escalado.lightbar == (100, 50, 25)

    def test_zero_apaga(self) -> None:
        original = LedSettings(lightbar=(255, 128, 64))
        escalado = original.apply_brightness(0.0)
        assert escalado.lightbar == (0, 0, 0)

    def test_acima_de_um_clampa_em_255(self) -> None:
        original = LedSettings(lightbar=(200, 100, 50))
        escalado = original.apply_brightness(2.0)
        # 200*2=400 -> 255, 100*2=200, 50*2=100
        assert escalado.lightbar == (255, 200, 100)

    def test_imutabilidade_da_origem(self) -> None:
        """Garante que apply_brightness devolve cópia e não muta original."""
        original = LedSettings(lightbar=(200, 100, 50), mic_led=True)
        _ = original.apply_brightness(0.25)
        assert original.lightbar == (200, 100, 50)
        assert original.mic_led is True

    def test_preserva_player_leds_e_mic(self) -> None:
        original = LedSettings(
            lightbar=(100, 100, 100),
            player_leds=(True, False, True, False, True),
            mic_led=True,
        )
        escalado = original.apply_brightness(0.5)
        assert escalado.player_leds == (True, False, True, False, True)
        assert escalado.mic_led is True
