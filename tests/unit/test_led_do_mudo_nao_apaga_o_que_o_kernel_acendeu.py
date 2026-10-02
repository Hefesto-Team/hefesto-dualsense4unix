"""AUDIO-OWNER-01, o TERCEIRO campo — o LED do mudo que o produto apagava."""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.core.backend_pydualsense import (
    _PinnedPyDualSense,
    _escrever_led_do_mic,
)


@pytest.fixture()
def handle() -> Any:
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


def test_sem_dono_o_led_do_mudo_nao_e_autorizado(handle: Any) -> None:
    """O bit 0x01 some do flag1 — o kernel volta a ser o dono do common[8]."""
    common = handle._build_common(rumble_asserted=False)

    assert common[1] & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE == 0
    assert common[8] == 0, "byte inerte, mas nunca autorizado"


def test_o_keepalive_nao_desfaz_o_mudo_que_ela_apertou(handle: Any) -> None:
    """A cena inteira, no report: o kernel acendeu, e o nosso não apaga."""
    for _ in range(5):
        common = handle._build_common(rumble_asserted=False)
        assert common[1] & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE == 0


def test_com_dono_o_led_acende_de_verdade(handle: Any) -> None:
    """A metade que prova que a cura não é "parar de funcionar"."""
    handle.set_microphone_led(True)
    common = handle._build_common(rumble_asserted=False)

    assert common[1] & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE
    assert common[8] == 1
    assert bool(handle.audio.microphone_led), "o espelho lido pela suíte/GUI"


def test_com_dono_apagar_tambem_e_uma_ordem_valida(handle: Any) -> None:
    """`False` é ORDEM ("apaga"), e continua valendo — o que não vale é o default."""
    handle.set_microphone_led(False)
    common = handle._build_common(rumble_asserted=False)

    assert common[1] & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE
    assert common[8] == 0


def test_devolver_a_posse_com_none_devolve_o_byte_ao_kernel(handle: Any) -> None:
    """Simetria com `set_microphone_mute`: `None` não é "apaga", é "não sou dono"."""
    handle.set_microphone_led(True)
    handle.set_microphone_led(None)
    common = handle._build_common(rumble_asserted=False)

    assert common[1] & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE == 0


def test_o_caminho_do_produto_toma_a_posse(handle: Any) -> None:
    """`_escrever_led_do_mic` é o que `set_mic_led` e o perfil chamam."""
    _escrever_led_do_mic(handle, True)
    common = handle._build_common(rumble_asserted=False)

    assert common[1] & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE
    assert common[8] == 1


def test_dublê_sem_posse_ainda_recebe_a_escrita_historica() -> None:
    """Handle que não é `_PinnedPyDualSense` (dublês da suíte) não pode quebrar."""

    class _Dublê:
        def __init__(self) -> None:
            self.audio = type("A", (), {"microphone_led": False})()
            self.audio.setMicrophoneLED = self._set  # type: ignore[attr-defined]

        def _set(self, valor: bool) -> None:
            self.audio.microphone_led = bool(valor)

    d = _Dublê()
    _escrever_led_do_mic(d, True)  # type: ignore[arg-type]

    assert d.audio.microphone_led is True
