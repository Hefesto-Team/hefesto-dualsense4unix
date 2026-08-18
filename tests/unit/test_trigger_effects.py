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
        """TRIGGER-CANON-01: `RIGID_B` é `0x05`, que é o OFF do bloco.

        Este teste travava o mecanismo antigo com todas as letras — e o
        mecanismo antigo mandava o controle DESLIGAR o gatilho. Ela mediu pelo
        tato em 01/08: *"rígido e desligado sem diferença"*.

        A regra que ele passa a travar é a que sempre quis: "rígido" põe
        resistência. Modo `FEEDBACK` oficial (0x21) e as zonas de `position`
        até o fim marcadas no bitmask.

        Mordida: devolver `TriggerMode.RIGID_B` à factory.
        """
        eff = tfx.rigid(5, 200)
        assert eff.mode == TriggerMode.FEEDBACK
        assert eff.mode != TriggerMode.RIGID_B, "0x05 é OFF, não rígido"
        # position=5 -> zonas 5..9 ativas = 0b1111100000 = 0x3E0 = 992
        zonas = eff.forces[0] | (eff.forces[1] << 8)
        assert zonas == 0b1111100000

    def test_rigid_position_fora_de_range(self):
        with pytest.raises(ValueError, match="position"):
            tfx.rigid(10, 0)

    def test_rigid_force_fora_de_byte(self):
        with pytest.raises(ValueError, match="force"):
            tfx.rigid(0, 300)

    def test_simple_rigid_ativa_todas_as_zonas(self):
        """TRIGGER-CANON-01: o `AMPLITUDE_SCALE` não se aplica aos oficiais.

        Os dois testes que este substitui travavam a multiplicação por 32
        (0-8 -> 0-255). Ela nunca valeu para os modos oficiais: eles recebem
        forças de TRÊS BITS com valor `força - 1`, e a escala de 255 caía num
        byte que o firmware lê como parte do bitmask de zonas.

        Mordida: voltar a escrever `_amp(strength)` em `forces[1]`.
        """
        eff = tfx.simple_rigid(7)
        assert eff.mode == TriggerMode.FEEDBACK
        # "Rígido simples" = firmeza uniforme no curso inteiro: as dez zonas.
        zonas = eff.forces[0] | (eff.forces[1] << 8)
        assert zonas == 0b1111111111

    def test_simple_rigid_forca_8_e_expressavel(self):
        """A força máxima cabe: 8 vira 7 nos três bits (8 - 1), não satura.

        Mordida: saturar 8 em 7 ANTES de subtrair 1 (o que dá 6).
        """
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
        """TRIGGER-CANON-01: `0x25` é o Weapon OFICIAL, e não fazia nada.

        Ela mediu: *"resistência nada também"*. O número do modo estava certo
        para "arma", mas os modos oficiais VALIDAM os parâmetros — e sem
        bitmask de zonas o firmware vê nenhuma zona ativa. Foi essa medição
        que provou que o defeito do empacotamento é independente do defeito
        do modo.

        Semanticamente isto é feedback: resistência constante de `start` até
        o fim do curso.

        Mordida: devolver `RIGID_AB` com posições cruas.
        """
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
        assert eff.forces == (0, 9, 3, 3, 50, 8, 0)  # última sempre 0

    def test_end_menor_rejeita(self):
        with pytest.raises(ValueError, match="end"):
            tfx.machine(5, 5, 0, 0, 0, 0)


class TestFeedbackEVibration:
    def test_feedback(self):
        """O preset cujo NOME sempre foi certo e cujo MODO sempre foi errado.

        `Feedback` é o nome que a enum da Sony dá ao `0x21`. Esta factory
        mandava `0x05` — OFF.

        Mordida: devolver `RIGID_B`.
        """
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
        # A rampa vai de 2 (zona 1) a 7 (zona 8), e o campo guarda força-1.
        assert (forcas >> 3) & 0x07 == 1, "zona 1 com força 2"
        assert (forcas >> 24) & 0x07 == 6, "zona 8 com força 7"

    def test_slope_feedback_strength_0_rejeita(self):
        with pytest.raises(ValueError, match="start_strength"):
            tfx.slope_feedback(1, 8, 0, 7)


class TestMultiPosition:
    """Empacotamento de 10 posições no formato dos modos OFICIAIS.

    Os valores esperados destes testes são LITERAIS escritos à mão — nunca
    recalculados com a expressão do código de produção. O teste original
    reproduzia o `(s & 0x7) << (i * 3)` da própria factory e por isso passava
    mesmo com o `BUG-TRIGGER-MULTIPOS-FORCA8-01` dentro dela: era tautológico.
    A regra vale inteira aqui, e os números abaixo foram derivados da
    ESPECIFICAÇÃO, não do código.

    TRIGGER-CANON-01 mudou o que se empacota, e são DUAS mudanças:

    1. o modo era `0x25`/`0x22` e passa a ser o `FEEDBACK`/`VIBRATION` oficial;
    2. **entrou o bitmask de zonas ativas** (bytes 1-2), que não existia. Sem
       ele o firmware vê "nenhuma zona ativa" e não faz nada — é a causa
       medida de `resistance` e `slope_feedback` não fazerem efeito nenhum
       nas mãos dela.

    E o campo de força passou a guardar `força - 1`, que é a codificação real:
    força 1..8 ocupa 0..7 nos três bits, e o ZERO não é força — é zona
    inativa, dita no bitmask.
    """

    def test_feedback_packing_bytes_literais(self):
        """strengths = [0, 1, 2, 3, 4, 5, 6, 7, 0, 1].

        As posições 0 e 8 têm força ZERO — elas não entram no bitmask, porque
        força zero é zona INATIVA:

            zonas ativas: 1,2,3,4,5,6,7,9
            bitmask  = 0b1011111110 = 766  -> bytes 254, 2

        E as forças, `força - 1` em 3 bits, na posição da zona:

            zona1:0  zona2:1  zona3:2  zona4:3
            zona5:4  zona6:5  zona7:6  zona9:0
            u32 = 0x00D63440              -> bytes 64, 52, 214, 0
        """
        eff = tfx.multi_position_feedback([0, 1, 2, 3, 4, 5, 6, 7, 0, 1])
        assert eff.mode == TriggerMode.FEEDBACK
        assert eff.forces == (254, 2, 64, 52, 214, 0, 0)

    def test_forca_8_e_expressavel_e_nao_satura(self):
        """A REFUTAÇÃO do `BUG-TRIGGER-MULTIPOS-FORCA8-01`, medida aqui.

        O bug foi registrado como medido e concluiu *"o campo tem 3 bits, logo
        o máximo real é 7 e a força 8 satura"*. A conclusão está errada na
        causa: a codificação é `(força - 1) & 0x07` com força em 1..8, então
        **8 cabe** (vira 7) e **1 cabe** (vira 0). O que não cabe é o zero — e
        zero não é um nível de força, é zona inativa.

        Mordida: saturar 8 em 7 antes de subtrair 1.
        """
        eff = tfx.multi_position_feedback([8, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        assert eff.forces == (1, 0, 7, 0, 0, 0, 0)

    def test_forca_8_nas_quatro_ultimas_posicoes(self):
        """Preset `stop_hard` da GUI: [0]*6 + [8]*4.

            zonas 6,7,8,9  -> bitmask 0b1111000000 = 960 -> bytes 192, 3
            forças (8-1=7) nas zonas 6..9, u32 = 0x3FFC0000 -> 0, 0, 252, 63
        """
        eff = tfx.multi_position_feedback([0, 0, 0, 0, 0, 0, 8, 8, 8, 8])
        assert eff.forces == (192, 3, 0, 0, 252, 63, 0)

    def test_rampa_crescente_com_dois_oitos_literal(self):
        """Preset `rampa_crescente`: [0,1,2,3,4,5,6,7,8,8].

            zona 0 fica de fora (força 0): bitmask 0b1111111110 = 1022
            forças u32 = 0x3FD63440
        """
        eff = tfx.multi_position_feedback([0, 1, 2, 3, 4, 5, 6, 7, 8, 8])
        assert eff.forces == (254, 3, 64, 52, 214, 63, 0)

    def test_forca_8_nao_avisa_mais_saturacao(self):
        """O aviso de saturação DEIXOU de fazer sentido, e por isso saiu.

        Ele existia para tornar visível um clamp real (8 -> 7) que a
        codificação errada exigia. Com `força - 1`, os oito níveis são
        expressáveis e não há clamp nenhum a anunciar — manter o aviso seria
        a tela alertando sobre uma perda que não acontece.

        Mordida: voltar a emitir `multi_position_strength_saturada`.
        """
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
        """TRIGGER-CANON-01: mandava `0x22` (Bow) e a frequência no slot errado.

        Mordida: devolver `PULSE_A` ou pôr a frequência em `forces[0]`.
        """
        eff = tfx.multi_position_vibration(100, [4] * 10)
        assert eff.mode == TriggerMode.VIBRATION
        assert int(eff.mode) == 0x26
        # `forces[6]` é o byte 9 do bloco, que é onde a frequência mora.
        assert eff.forces[6] == 100

    def test_vibration_com_oitos_bytes_literais(self):
        """Mesmos literais de zona/força do feedback, mais a frequência.

            zonas 0b1111111110 = 1022, forças u32 = 0x3FD63440, freq = 100
        """
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
        """O caminho nomeado continua valendo — o que mudou é o que ele produz.

        Mordida: fazer o `build_from_name` ignorar o dict.
        """
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
