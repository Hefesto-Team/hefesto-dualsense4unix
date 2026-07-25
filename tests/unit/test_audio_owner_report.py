"""AUDIO-OWNER-01 — o hefesto para de mandar áudio que não é dele.

Herdado do upstream pydualsense, TODO output report saía com:

  - `valid_flag0 = 0xFF`, que autoriza common[4..7] (volumes de fone,
    alto-falante e microfone + o byte de roteamento) — e esses quatro bytes
    NUNCA eram escritos por ninguém, então saía "volume ZERO" a até 60 Hz;
  - `valid_flag1` com `POWER_SAVE_CONTROL_ENABLE` (0x02) e `common[9] = 0x00`,
    ou seja "DESMUTA o microfone", também em todo report — por cima do kernel,
    que é quem alterna o mudo na borda do botão físico do controle.

MEDIDO AO VIVO (2026-07-25, DualSense por BT `14:3a:9a:...`, daemon rodando,
lendo o byte 55 do report de input):

    ninguém escreve            MicMuted   0.0%   transições  0
    asserindo MUTE a 20 Hz     MicMuted  96.4%   transições  9
    parei de escrever          MicMuted   7.9%   transições  1

As 9 transições em 2 s enquanto EU mantinha o mute a 20 Hz são o segundo
escritor desfazendo o mudo ~4x por segundo-e-meio — a cadência do keepalive
`OUT_REPORT_KEEPALIVE_SEC = 0.5`. É a assinatura de flapping que o
BT-MIC-GATING-01 descreve em `integrations/dualsense_bt_audio.py`.

A regra que estes testes travam: bit de validação só sai LIGADO quando alguém
deste projeto escreveu o valor correspondente.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.core.backend_pydualsense import _PinnedPyDualSense


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
    h._mic_mute_desejado = None
    h._raw_trigger_left = None
    h._raw_trigger_right = None
    return h


def test_sem_dono_nao_autoriza_volume_nem_manda_zero(handle: Any) -> None:
    common = handle._build_common(rumble_asserted=False)
    assert common[0] & rep.VALID_FLAG0_AUDIO_MASK == 0
    assert list(common[4:8]) == [0, 0, 0, 0]


def test_sem_dono_nao_disputa_o_mudo_com_o_kernel(handle: Any) -> None:
    """O bit 0x02 do flag1 some — o kernel volta a ser o dono do common[9]."""
    common = handle._build_common(rumble_asserted=False)
    assert common[1] & rep.VALID_FLAG1_POWER_SAVE_CONTROL_ENABLE == 0
    assert common[9] == 0


def test_gatilhos_e_leds_seguem_autorizados(handle: Any) -> None:
    """A poda é CIRÚRGICA: só áudio. Gatilhos/LEDs são nossos e continuam."""
    common = handle._build_common(rumble_asserted=False)
    assert common[0] & rep.VALID_FLAG0_RIGHT_TRIGGER_FFB
    assert common[0] & rep.VALID_FLAG0_LEFT_TRIGGER_FFB
    assert common[1] & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE
    assert common[1] & rep.VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE
    assert common[1] & rep.VALID_FLAG1_PLAYER_INDICATOR_CONTROL_ENABLE


def test_posse_do_volume_e_por_byte(handle: Any) -> None:
    """Quem pede só o alto-falante autoriza SÓ o alto-falante.

    O byte de roteamento (common[7]) fica de fora de propósito: não sabemos
    ler o valor vigente nem qual é o neutro, e chutá-lo mudaria o caminho do
    áudio do controle.
    """
    handle.set_audio_volumes(speaker=0xC0)
    common = handle._build_common(rumble_asserted=False)
    assert common[0] & rep.VALID_FLAG0_SPEAKER_VOLUME
    assert common[0] & rep.VALID_FLAG0_HEADPHONE_VOLUME == 0
    assert common[0] & rep.VALID_FLAG0_AUDIO_PATH == 0
    assert common[rep.COMMON_SPEAKER_VOLUME] == 0xC0
    assert common[rep.COMMON_HEADPHONE_VOLUME] == 0


def test_posse_do_mudo_liga_o_bit_e_o_valor(handle: Any) -> None:
    handle.set_microphone_mute(True)
    common = handle._build_common(rumble_asserted=False)
    assert common[1] & rep.VALID_FLAG1_POWER_SAVE_CONTROL_ENABLE
    assert common[9] == rep.POWER_SAVE_MIC_MUTE

    handle.set_microphone_mute(False)
    common = handle._build_common(rumble_asserted=False)
    assert common[1] & rep.VALID_FLAG1_POWER_SAVE_CONTROL_ENABLE
    assert common[9] == 0


def test_none_devolve_a_posse(handle: Any) -> None:
    """`None` ≠ False: False é a ORDEM "desmuta", None é "não é comigo"."""
    handle.set_microphone_mute(True)
    handle.set_microphone_mute(None)
    handle.set_audio_volumes(speaker=200)
    handle.release_audio_volumes()
    common = handle._build_common(rumble_asserted=False)
    assert common[1] & rep.VALID_FLAG1_POWER_SAVE_CONTROL_ENABLE == 0
    assert common[0] & rep.VALID_FLAG0_AUDIO_MASK == 0


def test_captura_do_byte_de_status_usa_o_indice_54(handle: Any) -> None:
    """AUDIO-STATUS-01: índice 54 do `states` normalizado, USB e BT.

    Validado ao vivo no report cru BT (offset 55, um a mais por causa do byte
    de seq/flags que a pydualsense descarta) — 945 reports lidos do
    `/dev/hidraw` do DualSense, byte estável em 0x00 (sem headset plugado).
    """
    handle._audio_status = None
    handle.states = [0] * 60
    handle.states[54] = 0x05  # fone plugado + mic MUDO
    handle._captura_status_audio()
    assert handle._audio_status == 0x05


def test_report_bt_continua_bem_formado_sem_os_bits_de_audio(handle: Any) -> None:
    """A poda não pode quebrar o envelope 0x31 (tag + CRC) do BTREPORT-02."""
    common = handle._build_common(rumble_asserted=False)
    buf = rep.build_bt_report(common, seq=3)
    assert buf[0] == rep.BT_REPORT_ID
    assert buf[2] == rep.BT_TAG
    esperado = rep.bt_crc32(buf[: rep.BT_REPORT_LEN - 4])
    assert int.from_bytes(buf[-4:], "little") == esperado
