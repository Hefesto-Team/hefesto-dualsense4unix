"""Testes dos 19 trigger effect factories."""
from __future__ import annotations

import pytest
import structlog

from hefesto_dualsense4unix.core import trigger_effects as tfx
from hefesto_dualsense4unix.core.trigger_effects import (
    AMPLITUDE_SCALE,
    PRESET_FACTORIES,
    TriggerMode,
    build_from_name,
)


class TestBasicos:
    def test_off(self):
        eff = tfx.off()
        assert eff.mode == TriggerMode.OFF
        assert eff.forces == (0, 0, 0, 0, 0, 0, 0)

    def test_rigid_valores_canonicos(self):
        eff = tfx.rigid(5, 200)
        assert eff.mode == TriggerMode.RIGID_B
        assert eff.forces == (5, 200, 0, 0, 0, 0, 0)

    def test_rigid_position_fora_de_range(self):
        with pytest.raises(ValueError, match="position"):
            tfx.rigid(10, 0)

    def test_rigid_force_fora_de_byte(self):
        with pytest.raises(ValueError, match="force"):
            tfx.rigid(0, 300)

    def test_simple_rigid_usa_amp_scale(self):
        eff = tfx.simple_rigid(7)  # 7*32 = 224, sem clamp
        assert eff.forces[1] == 7 * AMPLITUDE_SCALE

    def test_simple_rigid_8_satura_no_byte(self):
        eff = tfx.simple_rigid(8)
        assert eff.forces[1] == 255  # clamp em byte

    def test_pulse(self):
        eff = tfx.pulse()
        assert eff.mode == TriggerMode.PULSE
        assert eff.forces == (0, 0, 0, 0, 0, 0, 0)


class TestPulseAB:
    def test_pulse_a(self):
        eff = tfx.pulse_a(2, 7, 180)
        assert eff.mode == TriggerMode.PULSE_A
        assert eff.forces == (2, 7, 180, 0, 0, 0, 0)

    def test_pulse_b(self):
        eff = tfx.pulse_b(2, 7, 180)
        assert eff.mode == TriggerMode.PULSE_B
        assert eff.forces == (2, 7, 180, 0, 0, 0, 0)

    def test_end_menor_ou_igual_start_rejeita(self):
        with pytest.raises(ValueError, match="end"):
            tfx.pulse_a(5, 5, 100)
        with pytest.raises(ValueError, match="end"):
            tfx.pulse_b(5, 3, 100)


class TestResistance:
    def test_mapeamento(self):
        eff = tfx.resistance(3, 5)
        assert eff.mode == TriggerMode.RIGID_AB
        assert eff.forces == (3, 5 * AMPLITUDE_SCALE, 0, 0, 0, 0, 0)


class TestBow:
    def test_canonico(self):
        eff = tfx.bow(1, 7, 7, 7)
        assert eff.mode == TriggerMode.PULSE_AB
        assert eff.forces == (1, 7, 7 * AMPLITUDE_SCALE, 7 * AMPLITUDE_SCALE, 0, 0, 0)

    def test_force_8_satura(self):
        eff = tfx.bow(1, 7, 8, 8)
        assert eff.forces[2] == 255
        assert eff.forces[3] == 255

    def test_end_menor_rejeita(self):
        with pytest.raises(ValueError, match="end"):
            tfx.bow(5, 5, 4, 4)


class TestGalloping:
    def test_canonico(self):
        eff = tfx.galloping(0, 9, 7, 7, 10)
        assert eff.mode == TriggerMode.PULSE_AB
        assert eff.forces == (0, 9, 7, 7, 10, 0, 0)

    def test_frequency_aceita_0_a_255(self):
        eff = tfx.galloping(0, 9, 0, 0, 255)
        assert eff.forces[4] == 255

    def test_foot_fora_de_0_7(self):
        with pytest.raises(ValueError, match="first_foot"):
            tfx.galloping(0, 9, 8, 0, 10)
        with pytest.raises(ValueError, match="second_foot"):
            tfx.galloping(0, 9, 0, 8, 10)


class TestGuns:
    def test_semi_auto_gun(self):
        eff = tfx.semi_auto_gun(3, 6, 5)
        assert eff.mode == TriggerMode.PULSE_AB
        assert eff.forces == (3, 6, 5 * AMPLITUDE_SCALE, 0, 0, 0, 0)

    def test_semi_auto_gun_start_fora(self):
        with pytest.raises(ValueError, match="start"):
            tfx.semi_auto_gun(1, 5, 3)

    def test_semi_auto_gun_end_invalido(self):
        with pytest.raises(ValueError, match="end"):
            tfx.semi_auto_gun(3, 3, 3)

    def test_auto_gun(self):
        eff = tfx.auto_gun(2, 6, 100)
        assert eff.mode == TriggerMode.PULSE_AB
        assert eff.forces == (2, 6 * AMPLITUDE_SCALE, 100, 0, 0, 0, 0)

    def test_weapon(self):
        eff = tfx.weapon(2, 5, 200)
        assert eff.mode == TriggerMode.PULSE_B
        assert eff.forces == (2, 5, 200, 0, 0, 0, 0)


class TestMachine:
    def test_canonico_6_params_produz_7_forces(self):
        eff = tfx.machine(0, 9, 3, 3, 50, 8)
        assert eff.mode == TriggerMode.PULSE_AB
        assert eff.forces == (0, 9, 3, 3, 50, 8, 0)  # última sempre 0

    def test_end_menor_rejeita(self):
        with pytest.raises(ValueError, match="end"):
            tfx.machine(5, 5, 0, 0, 0, 0)


class TestFeedbackEVibration:
    def test_feedback(self):
        eff = tfx.feedback(5, 4)
        assert eff.mode == TriggerMode.RIGID_B
        assert eff.forces == (5, 4 * AMPLITUDE_SCALE, 0, 0, 0, 0, 0)

    def test_vibration(self):
        eff = tfx.vibration(3, 4, 40)
        assert eff.mode == TriggerMode.PULSE_A
        assert eff.forces == (3, 4 * AMPLITUDE_SCALE, 40, 0, 0, 0, 0)

    def test_slope_feedback(self):
        eff = tfx.slope_feedback(1, 8, 2, 7)
        assert eff.mode == TriggerMode.RIGID_AB
        assert eff.forces == (1, 8, 2 * AMPLITUDE_SCALE, 7 * AMPLITUDE_SCALE, 0, 0, 0)

    def test_slope_feedback_strength_0_rejeita(self):
        with pytest.raises(ValueError, match="start_strength"):
            tfx.slope_feedback(1, 8, 0, 7)


class TestMultiPosition:
    """Empacotamento de 10 posições em campos de 3 bits.

    Os valores esperados destes testes são LITERAIS escritos à mão — nunca
    recalculados com a expressão do código de produção. O teste antigo
    reproduzia o `(s & 0x7) << (i * 3)` da própria factory e por isso
    passava mesmo com o bug BUG-TRIGGER-MULTIPOS-FORCA8-01 (força 8 virando
    força 0) dentro dela: era tautológico.
    """

    def test_feedback_packing_bytes_literais(self):
        # strengths = [0, 1, 2, 3, 4, 5, 6, 7, 0, 1]
        # Campos de 3 bits, posição 0 nos bits menos significativos:
        #   pos0=000 pos1=001 pos2=010 pos3=011 pos4=100
        #   pos5=101 pos6=110 pos7=111 pos8=000 pos9=001
        # Fita de 30 bits (pos9 -> pos0):
        #   001 000 111 110 101 100 011 010 001 000
        # Fatiada em bytes, do menos significativo para o mais:
        #   byte0 = 0b10001000 = 136
        #   byte1 = 0b11000110 = 198
        #   byte2 = 0b11111010 = 250
        #   byte3 = 0b00001000 = 8
        eff = tfx.multi_position_feedback([0, 1, 2, 3, 4, 5, 6, 7, 0, 1])
        assert eff.mode == TriggerMode.RIGID_AB
        assert eff.forces == (136, 198, 250, 8, 0, 0, 0)

    def test_forca_8_nao_vira_zero_satura_em_7(self):
        """Força 8 na posição 0 tem que sair 7 (máximo real), nunca 0.

        O campo tem 3 bits: `8 & 0x7 == 0`. Sem a saturação, a força MÁXIMA
        pedida pela usuária chegava ao controle como NENHUMA força.
        """
        eff = tfx.multi_position_feedback([8, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        assert eff.forces[0] == 7
        assert eff.forces == (7, 0, 0, 0, 0, 0, 0)

    def test_forca_8_satura_em_todas_as_posicoes(self):
        """Preset `stop_hard` da GUI: [0]*6 + [8]*4 — nenhum byte pode ser 0.

        pos6..pos9 saturam em 7 (111) e ocupam os bits 18 a 29; pos0..pos5
        ficam em 0 (bits 0 a 17):
          byte0 = 0, byte1 = 0,
          byte2 = bits 23..16 = 0b11111100 = 252,
          byte3 = bits 29..24 = 0b00111111 = 63.
        """
        eff = tfx.multi_position_feedback([0, 0, 0, 0, 0, 0, 8, 8, 8, 8])
        assert eff.forces == (0, 0, 252, 63, 0, 0, 0)

    def test_rampa_crescente_com_dois_oitos_literal(self):
        """Preset `rampa_crescente`: [0,1,2,3,4,5,6,7,8,8].

        pos8 e pos9 saturam em 7 (111):
          111 111 111 110 101 100 011 010 001 000
        byte0 = 136, byte1 = 198, byte2 = 250, byte3 = 0b00111111 = 63.
        """
        eff = tfx.multi_position_feedback([0, 1, 2, 3, 4, 5, 6, 7, 8, 8])
        assert eff.forces == (136, 198, 250, 63, 0, 0, 0)

    def test_saturacao_registra_warning_explicito(self):
        with structlog.testing.capture_logs() as captured:
            tfx.multi_position_feedback([0, 0, 0, 0, 0, 0, 0, 0, 0, 8])
        avisos = [
            e for e in captured
            if e.get("event") == "multi_position_strength_saturada"
        ]
        assert len(avisos) == 1, captured
        assert avisos[0]["log_level"] == "warning"
        assert avisos[0]["posicao"] == 9
        assert avisos[0]["pedido"] == 8
        assert avisos[0]["aplicado"] == 7

    def test_forca_7_nao_gera_warning(self):
        with structlog.testing.capture_logs() as captured:
            tfx.multi_position_feedback([7] * 10)
        assert [
            e for e in captured
            if e.get("event") == "multi_position_strength_saturada"
        ] == []

    def test_feedback_strengths_9_rejeita(self):
        with pytest.raises(ValueError, match="10 strengths"):
            tfx.multi_position_feedback([0] * 9)

    def test_feedback_valor_acima_8_rejeita(self):
        bad = [0, 0, 9, 0, 0, 0, 0, 0, 0, 0]
        with pytest.raises(ValueError, match="strengths\\[2\\]"):
            tfx.multi_position_feedback(bad)

    def test_vibration(self):
        eff = tfx.multi_position_vibration(100, [0] * 10)
        assert eff.mode == TriggerMode.PULSE_A
        assert eff.forces[0] == 100

    def test_vibration_com_oitos_bytes_literais(self):
        """`[frequency] + 6 primeiros bytes` — mesmos literais do feedback."""
        eff = tfx.multi_position_vibration(100, [0, 1, 2, 3, 4, 5, 6, 7, 8, 8])
        assert eff.mode == TriggerMode.PULSE_A
        assert eff.forces == (100, 136, 198, 250, 63, 0, 0)


class TestCustomEBuild:
    def test_custom_passa_forces_cru(self):
        eff = tfx.custom(TriggerMode.PULSE_AB, (0, 9, 7, 7, 10, 0, 0))
        assert eff.mode == TriggerMode.PULSE_AB
        assert eff.forces == (0, 9, 7, 7, 10, 0, 0)

    def test_custom_arity_errada_rejeita(self):
        with pytest.raises(ValueError, match="forces precisa"):
            tfx.custom(0, (0, 0, 0))

    def test_build_from_name_posicional(self):
        eff = build_from_name("Galloping", [0, 9, 7, 7, 10])
        assert eff.mode == TriggerMode.PULSE_AB
        assert eff.forces == (0, 9, 7, 7, 10, 0, 0)

    def test_build_from_name_nomeado(self):
        eff = build_from_name("Rigid", {"position": 5, "force": 200})
        assert eff.forces == (5, 200, 0, 0, 0, 0, 0)

    def test_build_from_name_desconhecido(self):
        with pytest.raises(ValueError, match="preset desconhecido"):
            build_from_name("Inexistente", [])


def test_registry_tem_19_presets():
    assert len(PRESET_FACTORIES) == 19


def test_todos_os_presets_chave_retornam_callable():
    for name, factory in PRESET_FACTORIES.items():
        assert callable(factory), f"{name} não eh callable"
