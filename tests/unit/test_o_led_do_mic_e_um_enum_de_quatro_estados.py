"""O `common[8]` carrega os QUATRO estados — e a mordida é o esmagamento."""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import _PinnedPyDualSense
from hefesto_dualsense4unix.core.ds_output_report import (
    VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE,
)

QUATRO_ESTADOS: tuple[tuple[int, str], ...] = (
    (0, "apagada"),
    (1, "acesa"),
    (2, "piscando"),
    (3, "piscando mais lento"),
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


@pytest.mark.parametrize(("valor", "o_que_a_luz_faz"), QUATRO_ESTADOS)
def test_cada_um_dos_quatro_estados_sai_inteiro_no_byte(
    handle: Any, valor: int, o_que_a_luz_faz: str
) -> None:
    """ESTE É O TESTE QUE MORDE."""
    handle._mic_led_desejado = valor
    common = handle._build_common(rumble_asserted=False)
    assert common[8] == valor, (
        f"o estado {valor} ({o_que_a_luz_faz}) não chegou inteiro ao byte 8 — "
        f"saiu {common[8]}. Alguém esmagou o campo de volta em 0/1?"
    )
    assert common[1] & VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE, (
        "o byte saiu, mas sem o bit 0x01 do flag1 que o autoriza: o aparelho "
        "vai ignorar o valor e a luz não muda."
    )


def test_o_bool_continua_valendo_exatamente_como_antes(handle: Any) -> None:
    """`True`/`False`/`None` não podem ter mudado — é o contrato de sempre."""
    handle._mic_led_desejado = True
    assert handle._build_common(rumble_asserted=False)[8] == 1

    handle._mic_led_desejado = False
    common = handle._build_common(rumble_asserted=False)
    assert common[8] == 0
    assert common[1] & VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE, (
        "`False` é uma ORDEM ('apaga'), e ordem precisa do bit de autorização"
    )

    handle._mic_led_desejado = None
    common = handle._build_common(rumble_asserted=False)
    assert not common[1] & VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE, (
        "`None` DEVOLVE a posse: o bit 0x01 tem de cair para o kernel voltar "
        "a mandar na luz na borda do botão físico"
    )


def test_o_produto_nao_pode_inventar_um_quinto_estado(handle: Any) -> None:
    """Fora de `0..3` o aparelho APAGA — medido com 4, 64 e 255."""
    for fora in (4, 64, 255):
        handle._mic_led_desejado = fora
        assert handle._build_common(rumble_asserted=False)[8] == fora
