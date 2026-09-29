"""Testes de LED control.

O bloco do rumble com throttle (`RumbleEngine`) saiu em 28/09/2026 junto com a
classe, que o daemon nunca construiu: a vibração passa pelo funil vivo
(`core.rumble._effective_mult`, pelas três rotas que o chamam), e as réguas
dele estão em `test_rumble_policy.py` e `test_subsystem_rumble.py`.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.core.led_control import (
    LedSettings,
    apply_led_settings,
    hex_to_rgb,
    off,
    player_bitmask,
)
from hefesto_dualsense4unix.testing import FakeController


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

    def test_apply_led_settings_nao_toca_mic_led(self):
        """apply_led_settings NÃO chama set_mic_led — mic é estado runtime puro.

        Regressão original: `apply_led_settings` propagava `settings.mic_led`
        ao controller. Como `LedsConfig` não tem campo `mic_led`,
        `_to_led_settings` deixava `LedSettings.mic_led=False` (default);
        cada profile switch apagava o LED do mic mesmo quando o usuário o
        havia mutado via botão físico ou IPC
        (AUDIT-FINDING-PROFILE-MIC-LED-RESET-01; A-06).

        Fix opção (c): chamada `controller.set_mic_led(...)` removida de
        `apply_led_settings`. Mic LED só muda por caminho explícito.
        """
        fc = FakeController()
        fc.connect()
        # Simular usuário mutou o mic previamente (botão físico / IPC).
        fc.set_mic_led(True)
        assert fc.mic_led_history == [True]

        # Aplicar settings sem mic_led explícito — default False.
        apply_led_settings(fc, LedSettings(lightbar=(0, 0, 0)))

        # Histórico inalterado: o apply NÃO tocou o mic LED.
        assert fc.mic_led_history == [True]
        mic_cmds = [c for c in fc.commands if c.kind == "set_mic_led"]
        assert len(mic_cmds) == 1, (
            "apply_led_settings emitiu set_mic_led — regrediu A-06"
        )

    def test_apply_led_settings_ignora_mic_led_do_settings(self):
        """Mesmo quando caller passa mic_led=True explícito, o apply ignora.

        Garante que `LedSettings.mic_led` virou campo no-op (documentado no
        módulo). Callers antigos que passavam `mic_led=...` não regridem o
        estado runtime.
        """
        fc = FakeController()
        fc.connect()
        fc.set_mic_led(True)

        # Caller antigo instancia com mic_led=False — comportamento anterior
        # apagaria o LED. Pós-fix: ignorado.
        apply_led_settings(fc, LedSettings(lightbar=(255, 0, 0), mic_led=False))

        # Nenhuma chamada adicional de set_mic_led.
        assert fc.mic_led_history == [True]

    def test_apply_led_settings_propaga_player_leds_todos_acesos(self):
        """apply_led_settings invoca set_player_leds com o bitmask 'todos acesos'
        (BUG-PLAYER-LEDS-APPLY-01 — fecha A-06 para player_leds).

        Sem esta propagação, perfis que definem player_leds=True* ficam inertes
        no hardware apesar de aparecerem marcados na GUI.
        """
        fc = FakeController()
        fc.connect()
        bits = (True, True, True, True, True)
        apply_led_settings(fc, LedSettings(lightbar=(0, 0, 0), player_leds=bits))
        assert fc.last_player_leds == bits
        pl_cmds = [c for c in fc.commands if c.kind == "set_player_leds"]
        assert len(pl_cmds) == 1
        assert pl_cmds[0].payload == bits

    def test_apply_led_settings_propaga_player_leds_todos_apagados(self):
        """Preset 'Nenhum' (bitmask 0b00000) chega ao controle."""
        fc = FakeController()
        fc.connect()
        bits = (False, False, False, False, False)
        apply_led_settings(fc, LedSettings(lightbar=(50, 60, 70), player_leds=bits))
        assert fc.last_player_leds == bits

    def test_apply_led_settings_propaga_player_leds_padrao_alternado(self):
        """Bitmask arbitrário 0b10101 (Player 3 canônico) propagado fielmente."""
        fc = FakeController()
        fc.connect()
        bits = (True, False, True, False, True)
        apply_led_settings(fc, LedSettings(lightbar=(10, 20, 30), player_leds=bits))
        assert fc.last_player_leds == bits

    def test_apply_led_settings_default_propaga_player_leds_zerado(self):
        """Default de LedSettings (sem passar player_leds) ainda chama set_player_leds
        com o zerado — mantém o hardware consistente com o perfil recém-carregado
        em vez de preservar a configuração do último toggle manual.
        """
        fc = FakeController()
        fc.connect()
        apply_led_settings(fc, LedSettings(lightbar=(255, 255, 255)))
        assert fc.last_player_leds == (False, False, False, False, False)


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

