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
        """TRIGGER-CANON-01: `RIGID_B` é `0x05`, que é o OFF do bloco."""
        eff = tfx.rigid(5, 200)
        assert eff.mode == TriggerMode.FEEDBACK
        assert eff.mode != TriggerMode.RIGID_B, "0x05 é OFF, não rígido"
        zonas = eff.forces[0] | (eff.forces[1] << 8)
        assert zonas == 0b1111100000

    def test_rigid_position_fora_de_range(self):
        with pytest.raises(ValueError, match="position"):
            tfx.rigid(10, 0)

    def test_rigid_force_fora_de_byte(self):
        with pytest.raises(ValueError, match="force"):
            tfx.rigid(0, 300)

    def test_simple_rigid_ativa_todas_as_zonas(self):
        """TRIGGER-CANON-01: o `AMPLITUDE_SCALE` não se aplica aos oficiais."""
        eff = tfx.simple_rigid(7)
        assert eff.mode == TriggerMode.FEEDBACK
        zonas = eff.forces[0] | (eff.forces[1] << 8)
        assert zonas == 0b1111111111

    def test_simple_rigid_forca_8_e_expressavel(self):
        """A força máxima cabe: 8 vira 7 nos três bits (8 - 1), não satura."""
        eff = tfx.simple_rigid(8)
        forcas = (
            eff.forces[2] | (eff.forces[3] << 8)
            | (eff.forces[4] << 16) | (eff.forces[5] << 24)
        )
        assert forcas & 0x07 == 7

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
        """TRIGGER-CANON-01: `0x25` é o Weapon OFICIAL, e não fazia nada."""
        eff = tfx.resistance(3, 5)
        assert eff.mode == TriggerMode.FEEDBACK
        zonas = eff.forces[0] | (eff.forces[1] << 8)
        assert zonas == 0b1111111000, "zonas 3..9 ativas"


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
        assert eff.forces == (0, 9, 3, 3, 50, 8, 0)

    def test_end_menor_rejeita(self):
        with pytest.raises(ValueError, match="end"):
            tfx.machine(5, 5, 0, 0, 0, 0)


class TestFeedbackEVibration:
    def test_feedback(self):
        """O preset cujo NOME sempre foi certo e cujo MODO sempre foi errado."""
        eff = tfx.feedback(5, 4)
        assert eff.mode == TriggerMode.FEEDBACK
        assert int(eff.mode) == 0x21
        zonas = eff.forces[0] | (eff.forces[1] << 8)
        assert zonas == 0b1111100000

    def test_vibration(self):
        eff = tfx.vibration(3, 4, 40)
        assert eff.mode == TriggerMode.PULSE_A
        assert eff.forces == (3, 4 * AMPLITUDE_SCALE, 40, 0, 0, 0, 0)

    def test_slope_feedback(self):
        """`SlopeFeedback` não tem byte de modo próprio — é o Feedback com rampa.

        Foi esta descoberta que fechou a conta dos SETE modos da enum da Sony
        contra os bytes do fio: `MultiPositionFeedback` e `SlopeFeedback` são
        `0x21` com o array de zonas preenchido de jeitos diferentes.

        Mordida: devolver `RIGID_AB` com as duas posições cruas.
        """
        eff = tfx.slope_feedback(1, 8, 2, 7)
        assert eff.mode == TriggerMode.FEEDBACK
        zonas = eff.forces[0] | (eff.forces[1] << 8)
        assert zonas == 0b0111111110, "zonas 1..8, e nenhuma fora da rampa"
        forcas = (
            eff.forces[2] | (eff.forces[3] << 8)
            | (eff.forces[4] << 16) | (eff.forces[5] << 24)
        )
        assert (forcas >> 3) & 0x07 == 1, "zona 1 com força 2"
        assert (forcas >> 24) & 0x07 == 6, "zona 8 com força 7"

    def test_slope_feedback_strength_0_rejeita(self):
        with pytest.raises(ValueError, match="start_strength"):
            tfx.slope_feedback(1, 8, 0, 7)


class TestMultiPosition:
    """Empacotamento de 10 posições no formato dos modos OFICIAIS."""

    def test_feedback_packing_bytes_literais(self):
        """strengths = [0, 1, 2, 3, 4, 5, 6, 7, 0, 1]."""
        eff = tfx.multi_position_feedback([0, 1, 2, 3, 4, 5, 6, 7, 0, 1])
        assert eff.mode == TriggerMode.FEEDBACK
        assert eff.forces == (254, 2, 64, 52, 214, 0, 0)

    def test_forca_8_e_expressavel_e_nao_satura(self):
        """A REFUTAÇÃO do `BUG-TRIGGER-MULTIPOS-FORCA8-01`, medida aqui."""
        eff = tfx.multi_position_feedback([8, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        assert eff.forces == (1, 0, 7, 0, 0, 0, 0)

    def test_forca_8_nas_quatro_ultimas_posicoes(self):
        """Preset `stop_hard` da GUI: [0]*6 + [8]*4."""
        eff = tfx.multi_position_feedback([0, 0, 0, 0, 0, 0, 8, 8, 8, 8])
        assert eff.forces == (192, 3, 0, 0, 252, 63, 0)

    def test_rampa_crescente_com_dois_oitos_literal(self):
        """Preset `rampa_crescente`: [0,1,2,3,4,5,6,7,8,8]."""
        eff = tfx.multi_position_feedback([0, 1, 2, 3, 4, 5, 6, 7, 8, 8])
        assert eff.forces == (254, 3, 64, 52, 214, 63, 0)

    def test_forca_8_nao_avisa_mais_saturacao(self):
        """O aviso de saturação DEIXOU de fazer sentido, e por isso saiu."""
        with structlog.testing.capture_logs() as captured:
            tfx.multi_position_feedback([0, 0, 0, 0, 0, 0, 0, 0, 0, 8])
        assert [
            e for e in captured
            if e.get("event") == "multi_position_strength_saturada"
        ] == []

    def test_forca_7_nao_gera_warning(self):
        with structlog.testing.capture_logs() as captured:
            tfx.multi_position_feedback([7] * 10)
        assert [
            e for e in captured
            if e.get("event") == "multi_position_strength_saturada"
        ] == []

    def test_vibration(self):
        """TRIGGER-CANON-01: mandava `0x22` (Bow) e a frequência no slot errado."""
        eff = tfx.multi_position_vibration(100, [4] * 10)
        assert eff.mode == TriggerMode.VIBRATION
        assert int(eff.mode) == 0x26
        assert eff.forces[6] == 100

    def test_vibration_com_oitos_bytes_literais(self):
        """Mesmos literais de zona/força do feedback, mais a frequência."""
        eff = tfx.multi_position_vibration(100, [0, 1, 2, 3, 4, 5, 6, 7, 8, 8])
        assert eff.mode == TriggerMode.VIBRATION
        assert eff.forces == (254, 3, 64, 52, 214, 63, 100)


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
        """O caminho nomeado continua valendo — o que mudou é o que ele produz."""
        eff = build_from_name("Rigid", {"position": 5, "force": 200})
        assert eff.mode == TriggerMode.FEEDBACK
        zonas = eff.forces[0] | (eff.forces[1] << 8)
        assert zonas == 0b1111100000, "zonas 5..9, como o posicional"
        assert eff.forces == tfx.rigid(5, 200).forces

    def test_build_from_name_desconhecido(self):
        with pytest.raises(ValueError, match="preset desconhecido"):
            build_from_name("Inexistente", [])


def test_registry_tem_19_presets():
    assert len(PRESET_FACTORIES) == 19


def test_todos_os_presets_chave_retornam_callable():
    for name, factory in PRESET_FACTORIES.items():
        assert callable(factory), f"{name} não eh callable"
