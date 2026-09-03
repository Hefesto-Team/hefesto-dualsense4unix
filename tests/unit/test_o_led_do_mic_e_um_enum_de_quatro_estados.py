"""O `common[8]` carrega os QUATRO estados — e a mordida é o esmagamento.

MEDIDO NO APARELHO em 02/09/2026, no cabo, com o olho dela
(`docs/data/ensaios.csv`: `led-mic-nivel-cabo-1`, `led-mic-faixa-cabo-2`;
instrumento: `scripts/ensaios/nivel_do_led_do_mic.py`):

    0 = apagada · 1 = acesa · 2 = PISCANDO · 3 = PISCANDO MAIS LENTO
    4, 64 e 255 = apagadas — o firmware VALIDA A FAIXA 0..3

Até esse dia o `_build_common` fazia `common[8] = 1 if mic_led else 0`, e o
byte só sabia dizer duas coisas. Este teste existe para que ninguém devolva o
esmagamento sem que a suíte reprove: **arrancar a cura é reescrever aquela
linha, e os testes de nível abaixo caem na hora.**

Por que isso vira teste e não só nota: o mapa declara
`luz.led_microfone` com `cabo_de_onde_sei = medido`, e nesta casa afirmação
forte sem teste que morda é o defeito que o `check_paridade_transporte.py`
existe para pegar — `sem-mordida`.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import _PinnedPyDualSense
from hefesto_dualsense4unix.core.ds_output_report import (
    VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE,
)

#: Os quatro estados medidos, e o que cada um faz na luz. O `apagado` aparece
#: duas vezes de propósito: `0` é o estado, e `4`/`64`/`255` são a FAIXA
#: recusada — o firmware apaga o que não entende.
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
    """ESTE É O TESTE QUE MORDE.

    Devolva `common[8] = 1 if mic_led else 0` ao `_build_common` e os casos do
    `2` e do `3` reprovam na hora — que é exatamente o que se quer, porque
    esmagar em 0/1 apaga dois dos quatro estados que o aparelho tem.
    """
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
    """`True`/`False`/`None` não podem ter mudado — é o contrato de sempre.

    `bool` é subclasse de `int`, então o alargamento de 02/09/2026 é
    byte-idêntico para todo chamador que já existia. Se este teste cair junto
    com os de cima, o alargamento quebrou o que funcionava.
    """
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
    """Fora de `0..3` o aparelho APAGA — medido com 4, 64 e 255.

    O byte continua saindo como foi pedido (é o `& 0xFF` do builder), e é isso
    que este teste fixa: o produto não FILTRA a faixa. Quem filtra é o
    firmware, e registrar isso aqui evita que alguém acrescente um `clamp`
    achando que conserta algo — o `clamp` esconderia um pedido errado em vez
    de deixá-lo aparecer.
    """
    for fora in (4, 64, 255):
        handle._mic_led_desejado = fora
        assert handle._build_common(rumble_asserted=False)[8] == fora
