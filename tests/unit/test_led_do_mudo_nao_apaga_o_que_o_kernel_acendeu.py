"""AUDIO-OWNER-01, o TERCEIRO campo — o LED do mudo que o produto apagava.

O DEFEITO, lido no código dos dois lados (12/08/2026)
=====================================================
`common[8]` é o `mute_button_led` do `dualsense_output_report_common`, e o bit
que o autoriza é o `VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE` (0x01).

O kernel desta máquina escreve os dois — UMA vez, na BORDA do botão de mudo:

    assets/dkms/hid-playstation/hid-playstation.c:1538-1540
        common->valid_flag1 |= DS_OUTPUT_VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE;
        common->mute_button_led = ds->mic_muted;

e, junto, muta o microfone de verdade no firmware (`POWER_SAVE_CONTROL` com o
bit `MIC_MUTE`, `:1542-1553`).

Nós autorizávamos o MESMO byte em TODO report — o `0x01` estava fixo no `flag1`
do `_build_common` — escrevendo `audio.microphone_led`, que a pydualsense
inicializa em 0. A consequência é a que ela vê na mão: ela aperta o mudo, o
kernel acende o LED e muta o mic, e o próximo report nosso (≤ 0,5 s, o
keepalive) **apaga o LED sem desmutar**. O microfone segue mudo com a luz
apagada — o produto mente sobre o estado do microfone dela.

É a mesma classe de defeito que o AUDIO-OWNER-01 já tinha curado nos volumes e
no mudo em 25/07, e este campo passou batido: autorizar um byte que ninguém
escreveu é mandar uma ORDEM com cara de keepalive.

A CURA, e o que ela NÃO pode reintroduzir
=========================================
Posse por byte: sem dono, o bit `0x01` sai apagado e `common[8]` fica inerte —
**não escrever é o único write não-destrutivo**, porque este registrador não
tem caminho de leitura. Com dono (`set_microphone_led`), o bit volta e o byte
sai: o defeito que a posse por byte existe para curar é "autorizar sem
escrever", nunca "parar de funcionar quando alguém pede". Os dois lados estão
travados aqui.
"""
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
    """O bit 0x01 some do flag1 — o kernel volta a ser o dono do common[8].

    Este é o teste que morde: com o `0x01` fixo de volta no `_build_common`,
    ele reprova, e o que ele descreve é o report que apagava a luz dela.
    """
    common = handle._build_common(rumble_asserted=False)

    assert common[1] & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE == 0
    assert common[8] == 0, "byte inerte, mas nunca autorizado"


def test_o_keepalive_nao_desfaz_o_mudo_que_ela_apertou(handle: Any) -> None:
    """A cena inteira, no report: o kernel acendeu, e o nosso não apaga.

    Nenhum report nosso pode autorizar `common[8]` enquanto ninguém deste
    projeto tiver pedido o LED — é isso que faz o LED aceso pelo kernel
    sobreviver ao keepalive de ≤ 0,5 s.
    """
    for _ in range(5):
        common = handle._build_common(rumble_asserted=False)
        assert common[1] & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE == 0


def test_com_dono_o_led_acende_de_verdade(handle: Any) -> None:
    """A metade que prova que a cura não é "parar de funcionar".

    `set_microphone_led(True)` assume a posse: o bit volta E o byte sai. Sem
    isto, a posse por byte teria matado o `set_mic_led` do produto (o hotkey de
    mudo, o comando UDP do DSX e o `mic_led` do perfil).
    """
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
    """`_escrever_led_do_mic` é o que `set_mic_led` e o perfil chamam.

    Se ele chamasse só `audio.setMicrophoneLED`, o byte seria escrito e o bit
    nunca ligaria — o LED não acenderia, e o defeito trocaria de lado.
    """
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
