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
    def test_pulse_a_manda_o_arco_do_firmware_entre_duas_posicoes(self):
        """`22 84 00 2D`: bits 2 e 7 na máscara, força 6 e estalo 6 (menos um)."""
        eff = tfx.pulse_a(2, 7, 180)
        assert eff.mode == TriggerMode.BOW
        assert eff.forces == (0x84, 0x00, 0x2D, 0, 0, 0, 0)

    def test_pulse_b_manda_a_arma_oficial_entre_duas_posicoes(self):
        """`25 84 00 05`: bits 2 e 7 na máscara e a força 6 menos um."""
        eff = tfx.pulse_b(2, 7, 180)
        assert eff.mode == TriggerMode.WEAPON
        assert eff.forces == (0x84, 0x00, 0x05, 0, 0, 0, 0)

    def test_pulse_b_e_o_mesmo_bloco_do_disparo(self):
        assert tfx.pulse_b(3, 6, 90) == tfx.weapon(3, 6, 90)

    def test_pulse_a_sem_forca_e_o_gatilho_desligado(self):
        assert tfx.pulse_a(2, 7, 0) == tfx.off()
        assert tfx.pulse_b(2, 7, 0) == tfx.off()

    def test_pulse_a_encosta_o_fim_na_zona_8_do_arco(self):
        """O arco vai até a zona 8 (a 9 é do galope): a tela deixa 9, o bloco leva 8."""
        assert tfx.pulse_a(0, 9, 255).forces[:2] == (0x01, 0x01)
        assert tfx.pulse_a(8, 9, 255).forces[:2] == (0x80, 0x01)
        assert tfx.pulse_a(0, 8, 255).forces[:2] == (0x01, 0x01)

    def test_end_menor_ou_igual_start_rejeita(self):
        with pytest.raises(ValueError, match="end"):
            tfx.pulse_a(5, 5, 100)
        with pytest.raises(ValueError, match="end"):
            tfx.pulse_b(5, 3, 100)

    def test_force_fora_de_byte_rejeita(self):
        with pytest.raises(ValueError, match="force"):
            tfx.pulse_a(2, 7, 300)
        with pytest.raises(ValueError, match="force"):
            tfx.pulse_b(2, 7, -1)


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



class TestWeapon:
    """O Disparo é a arma oficial (`0x25`), de 08/10/2026: a máscara com o início
    e o fim nos bytes 1-2 e a força menos um no byte 3."""

    def test_os_padroes_mandam_o_bloco_da_arma(self):
        eff = tfx.weapon(2, 5, 200)
        assert eff.mode == TriggerMode.WEAPON
        assert eff.forces == (0x24, 0x00, 0x05, 0, 0, 0, 0)

    def test_a_forca_de_byte_vira_um_a_oito_e_o_bloco_guarda_menos_um(self):
        for byte, guardado in ((1, 0), (32, 0), (64, 1), (128, 3), (200, 5), (255, 7)):
            assert tfx.weapon(2, 5, byte).forces[2] == guardado, byte

    def test_a_mascara_tem_o_bit_do_inicio_e_o_do_fim(self):
        for inicio, fim in ((2, 3), (3, 8), (7, 8), (4, 6)):
            forces = tfx.weapon(inicio, fim, 200).forces
            assert forces[0] | forces[1] << 8 == (1 << inicio) | (1 << fim)

    def test_sem_forca_e_o_gatilho_desligado(self):
        assert tfx.weapon(2, 5, 0) == tfx.off()

    def test_o_que_a_tela_deixa_e_a_arma_nao_aceita_encosta_no_limite(self):
        """A tela vai de 0 a 9; o modo, de 2 a 7 no início e até 8 no fim."""
        assert tfx.weapon(0, 9, 200) == tfx.weapon(2, 8, 200)
        assert tfx.weapon(1, 2, 200) == tfx.weapon(2, 3, 200)
        assert tfx.weapon(8, 9, 200) == tfx.weapon(7, 8, 200)

    def test_end_menor_ou_igual_start_rejeita(self):
        with pytest.raises(ValueError, match="end"):
            tfx.weapon(5, 5, 200)

    def test_force_fora_de_byte_rejeita(self):
        with pytest.raises(ValueError, match="force"):
            tfx.weapon(2, 5, 256)


class TestMachine:
    """A Metralhadora é a vibração da lista oficial (`0x26`), de 08/10/2026."""

    def test_os_padroes_mandam_o_bloco_da_vibracao_oficial(self):
        eff = tfx.machine(2, 9, 4, 40)
        assert eff.mode == TriggerMode.VIBRATION
        assert eff.forces == (0xFC, 0x03, 0xC0, 0xB6, 0x6D, 0x1B, 40)

    def test_e_o_mesmo_bloco_da_vibracao_por_posicao_com_as_zonas_iguais(self):
        igual = tfx.multi_position_vibration(40, [0, 0, 4, 4, 4, 4, 4, 4, 4, 4])
        assert tfx.machine(2, 9, 4, 40) == igual

    def test_o_fim_e_incluido_e_o_resto_do_curso_fica_de_fora(self):
        eff = tfx.machine(1, 3, 8, 20)
        assert eff.forces[0] | eff.forces[1] << 8 == 0b1110
        assert eff.forces[6] == 20

    def test_valor_fora_da_faixa_encosta_no_limite_mais_perto(self):
        assert tfx.machine(0, 9, 255, 255) == tfx.machine(0, 9, 8, 255)
        assert tfx.machine(0, 9, 0, 0) == tfx.machine(0, 9, 1, 1)
        assert tfx.machine(9, 99, 4, 40) == tfx.machine(8, 9, 4, 40)
        assert tfx.machine(-3, 5, 4, 40) == tfx.machine(0, 5, 4, 40)

    def test_fim_que_nao_passa_do_inicio_vira_o_inicio_mais_um(self):
        assert tfx.machine(5, 5, 4, 40) == tfx.machine(5, 6, 4, 40)
        assert tfx.machine(7, 2, 4, 40) == tfx.machine(7, 8, 4, 40)

    def test_a_frequencia_nunca_chega_zero_ao_controle(self):
        assert tfx.machine(2, 9, 4, 0).forces[6] == 1

    def test_os_ajustes_que_o_efeito_le_sao_os_que_a_fabrica_manda(self):
        """A tela pergunta aqui o que mostrar; a resposta tem de ser o que vai
        ao fio. Mordida: devolver os seis valores crus de `ajustes_que_o_efeito_le`."""
        for velho, lido in (
            ([0, 9, 3, 3, 50, 8], [0, 9, 3, 50]),
            ([1, 8, 200, 150, 20, 10], [1, 8, 8, 20]),
            ([2, 9, 4, 40], [2, 9, 4, 40]),
            ([9, 99, 0, 0], [8, 9, 1, 1]),
        ):
            assert tfx.ajustes_que_o_efeito_le("Machine", velho) == lido
            assert tfx.build_from_name("Machine", lido) == tfx.build_from_name(
                "Machine", velho
            )
        assert tfx.ajustes_que_o_efeito_le("AutoGun", [2, 6, 60]) == [2, 6, 60]


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
        assert zonas == 0b1111111110, "zonas 1..9: a rampa chega ao fundo do curso"
        forcas = (
            eff.forces[2] | (eff.forces[3] << 8)
            | (eff.forces[4] << 16) | (eff.forces[5] << 24)
        )
        assert (forcas >> 3) & 0x07 == 1, "zona 1 com força 2"
        assert (forcas >> 24) & 0x07 == 6, "zona 8 com força 7"
        assert (forcas >> 27) & 0x07 == 6, "zona 9 com a força final, 7"

    @pytest.mark.parametrize(
        ("start", "end", "inicial", "final"),
        [(1, 8, 2, 7), (0, 3, 1, 8), (2, 5, 8, 1), (4, 9, 3, 6)],
    )
    def test_rampa_enche_do_fim_ate_o_fundo_com_a_forca_final(
        self, start: int, end: int, inicial: int, final: int
    ) -> None:
        """Depois de `end`, cada zona até a nona vale a força final; antes de
        `start`, nenhuma zona liga.

        Mordida: devolver só as zonas de `start` a `end`.
        """
        eff = tfx.slope_feedback(start, end, inicial, final)
        zonas = eff.forces[0] | (eff.forces[1] << 8)
        assert zonas == sum(1 << z for z in range(start, 10))
        forcas = int.from_bytes(bytes(eff.forces[2:6]), "little")
        por_zona = {z: (forcas >> (3 * z)) & 0x07 for z in range(10)}
        assert all(por_zona[z] == final - 1 for z in range(end, 10))
        assert por_zona[start] == inicial - 1
        assert all(por_zona[z] == 0 for z in range(start))

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

    def test_vibration_frequencia_zero_com_amplitude_recusa(self):
        """O controle lê frequência 0 como desligado: pedir vibração e mandar
        zero é calar sem avisar.

        Mordida: tirar a recusa de `multi_position_vibration`.
        """
        with pytest.raises(ValueError, match="frequency 0"):
            tfx.multi_position_vibration(0, [0, 0, 0, 0, 0, 0, 0, 0, 0, 1])

    def test_vibration_frequencia_zero_sem_amplitude_e_o_desligado(self):
        eff = tfx.multi_position_vibration(0, [0] * 10)
        assert eff.forces == (0, 0, 0, 0, 0, 0, 0)

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
