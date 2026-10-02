"""MIC-DA-MESA-ELEICAO-01 — o LED do microfone, POR CONTROLE."""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.core.backend_pydualsense import (
    _PinnedPyDualSense,
    PyDualSenseController,
)

_A = "aabbcc000001"
_B = "aabbcc000002"
_C = "aabbcc000003"
_D = "aabbcc000004"


class _LockFalso:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *_: Any) -> None:
        return None


def _handle() -> Any:
    """Handle da pydualsense sem device — só o estado que o builder lê."""
    from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

    h = _PinnedPyDualSense.__new__(_PinnedPyDualSense)
    h.audio = DSAudio()
    h.light = DSLight()
    h.triggerL = DSTrigger()
    h.triggerR = DSTrigger()
    h.leftMotor = 0
    h.rightMotor = 0
    h._suppress_leds = False
    h._volumes_audio = [None, None, None, None]
    h._preamp_audio = None
    h._mic_mute_desejado = None
    h._mic_led_desejado = None
    h._raw_trigger_left = None
    h._raw_trigger_right = None
    return h


@pytest.fixture()
def mesa_de_quatro() -> Any:
    """Backend com quatro handles endereçáveis e overrides por-uniq vivos."""
    from hefesto_dualsense4unix.core.backend_pydualsense import _DesiredOutput

    ctrl = PyDualSenseController.__new__(PyDualSenseController)
    ctrl._handles = {mac: _handle() for mac in (_A, _B, _C, _D)}
    ctrl._io_lock = _LockFalso()
    ctrl._primary_key = _A
    ctrl._output_target_key = None
    ctrl._desired_default = _DesiredOutput()
    ctrl._desired_by_uniq = {mac: _DesiredOutput(mic_led=False) for mac in (_A, _B, _C, _D)}
    ctrl._desired_owner_by_uniq = {}
    return ctrl


def test_o_led_com_uniq_escreve_so_no_handle_daquele_controle(mesa_de_quatro: Any) -> None:
    """`set_mic_led(True, uniq=B)`: o byte sai no B e em mais ninguém."""
    mesa_de_quatro.set_mic_led(True, uniq=_B)

    for mac, handle in mesa_de_quatro._handles.items():
        comum = handle._build_common(rumble_asserted=False)
        se_esperava = mac == _B
        assert bool(
            comum[1] & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE
        ) is se_esperava, f"o controle {mac} não devia ter mudado"
        assert comum[8] == (1 if se_esperava else 0)


def test_o_led_com_uniq_nao_apaga_o_estado_dos_outros_tres(mesa_de_quatro: Any) -> None:
    """A segunda metade, e ela é a que mais dói."""
    mesa_de_quatro.set_mic_led(True, uniq=_B)

    assert mesa_de_quatro._desired_by_uniq[_B].mic_led is True
    for mac in (_A, _C, _D):
        override = mesa_de_quatro._desired_by_uniq.get(mac)
        assert override is not None, f"o override de {mac} sumiu inteiro"
        assert (
            override.mic_led is False
        ), f"o override de {mac} foi zerado por uma escrita que não era dele"


def test_o_led_sem_uniq_continua_valendo_para_o_alvo(mesa_de_quatro: Any) -> None:
    """A metade que prova que a cura não é "parar de funcionar"."""
    mesa_de_quatro.set_mic_led(True)
    for handle in mesa_de_quatro._handles.values():
        comum = handle._build_common(rumble_asserted=False)
        assert comum[1] & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE
        assert comum[8] == 1


def test_apply_output_defaults_com_mic_led_acende_o_byte(mesa_de_quatro: Any) -> None:
    """O LED do perfil em broadcast tem de acender `common[8]`, não só o espelho."""
    from hefesto_dualsense4unix.core.controller import OutputSpec

    mesa_de_quatro._reassert_task = None
    mesa_de_quatro.apply_output_defaults(OutputSpec(mic_led=True))

    for handle in mesa_de_quatro._handles.values():
        comum = handle._build_common(rumble_asserted=False)
        assert comum[1] & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE, (
            "o bit de autorização tem de sair LIGADO"
        )
        assert comum[8] == 1, "e o byte tem de sair com o valor"


def test_devolver_a_posse_limpa_o_bit_e_o_byte(mesa_de_quatro: Any) -> None:
    """`set_microphone_led(None)` devolve `common[8]` ao kernel."""
    mesa_de_quatro.set_microphone_led(True, uniq=_A)
    comum = mesa_de_quatro._handles[_A]._build_common(rumble_asserted=False)
    assert comum[1] & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE

    mesa_de_quatro.set_microphone_led(None, uniq=_A)
    comum = mesa_de_quatro._handles[_A]._build_common(rumble_asserted=False)
    assert comum[1] & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE == 0
    assert comum[8] == 0

    outras = mesa_de_quatro._handles[_A]._build_common(rumble_asserted=False)
    assert outras[1] & rep.VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE, (
        "a lightbar continua nossa — a devolução é do byte do LED do mic, só"
    )


def test_a_borda_muda_o_report_montado(mesa_de_quatro: Any) -> None:
    """Reafirmar o mesmo valor NÃO chega ao aparelho — o report tem de MUDAR."""
    handle = mesa_de_quatro._handles[_A]

    mesa_de_quatro.set_mic_led(True, uniq=_A)
    primeiro = bytes(handle._build_common(rumble_asserted=False))

    mesa_de_quatro.set_mic_led(False, uniq=_A)
    segundo = bytes(handle._build_common(rumble_asserted=False))

    assert segundo != primeiro, (
        "report idêntico não é escrito — o LED ficaria com o que o kernel pôs"
    )
    assert primeiro[8] == 1
    assert segundo[8] == 0
