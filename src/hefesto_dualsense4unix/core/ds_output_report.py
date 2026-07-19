"""Builder comum do output report do DualSense (USB 0x02 e BT 0x31) — BTREPORT-02.

Layout validado contra o `hid-playstation` do kernel (structs
`dualsense_output_report_usb`/`_bt`/`_common`), NUNCA contra a pydualsense —
o 0x31 que ela monta é MALFORMADO (off-by-one: `[1]=0x02` fixo em vez de
`seq<<4`, `0xFF` onde o firmware espera o tag obrigatório `0x10`), e o
firmware o descarta (era o "cor nunca funcionou por BT" e o rumble BT no-op).

O payload "common" tem 47 bytes e é IDÊNTICO nos dois transportes; muda só o
envelope:

  USB (64 bytes, sem CRC):    ``[0]=0x02, [1..47]=common, resto zero``
  BT  (78 bytes, com CRC):    ``[0]=0x31, [1]=seq<<4 (nibble alto),
                              [2]=0x10 (tag mágico obrigatório),
                              [3..49]=common, [50..73]=reservado,
                              [74..77]=CRC-32 little-endian sobre o byte de
                              seed 0xA2 (header HIDP DATA|OUTPUT) + [0..73]``

Offsets DENTRO do common (espelho do `dualsense_output_report_common`):
  [0]  valid_flag0 (vibração 0x01|0x02, gatilhos 0x04|0x08, áudio 0x10..0x40)
  [1]  valid_flag1 (mic-LED 0x01, mute 0x02, lightbar 0x04, RELEASE_LEDS 0x08,
       player-LEDs 0x10, atenuação de motor 0x40)
  [2]  motor direito (weak)   [3]  motor esquerdo (strong)
  [8]  LED do mic             [9]  power_save (0x10 = mute do mic)
  [10..19] gatilho R (modo + forças)   [21..30] gatilho L
  [38] valid_flag2 (vibração v2 0x04)  [41..46] lightbar/player/cor

Consumidores: `core/lightbar_reset.py` (report de Reset LED state) e o
override `_PinnedPyDualSense.prepareReport` do backend (report normal).
"""
from __future__ import annotations

import zlib

#: Report IDs de output do DualSense.
USB_REPORT_ID = 0x02
BT_REPORT_ID = 0x31

#: Tamanho do payload comum (struct `dualsense_output_report_common`).
COMMON_LEN = 47

#: Tamanho dos reports por transporte (o USB é o que a pydualsense/hidapi
#: escrevem historicamente: 64; o kernel usa 63 + padding — inócuo).
USB_REPORT_LEN = 64
BT_REPORT_LEN = 78

#: Tag mágico obrigatório do report BT ("Magic value required in tag field").
BT_TAG = 0x10

#: Seed do CRC-32 dos reports de output BT (header HIDP DATA|OUTPUT).
BT_CRC_SEED = 0xA2

#: Seeds dos DEMAIS sentidos do mesmo CRC (hid-playstation.c): input 0xA1
#: (header HIDP DATA|INPUT — valida o report 0x31 que o FÍSICO emite, usado
#: pelo espelho de motion do GYRO-01) e feature 0xA3 (GET_REPORT por BT — os
#: 4 últimos bytes do feature 0x05 lido de um físico BT são CRC, não dado).
BT_INPUT_CRC_SEED = 0xA1
BT_FEATURE_CRC_SEED = 0xA3

# --- bits de valid_flag0 (common[0]) ---------------------------------------
VALID_FLAG0_COMPATIBLE_VIBRATION = 0x01
VALID_FLAG0_HAPTICS_SELECT = 0x02

# --- bits de valid_flag1 (common[1]) ---------------------------------------
VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE = 0x01
VALID_FLAG1_POWER_SAVE_CONTROL_ENABLE = 0x02
VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE = 0x04
VALID_FLAG1_RELEASE_LEDS = 0x08
VALID_FLAG1_PLAYER_INDICATOR_CONTROL_ENABLE = 0x10
VALID_FLAG1_MOTOR_POWER = 0x40

# --- bits de valid_flag2 (common[38]) --------------------------------------
VALID_FLAG2_COMPATIBLE_VIBRATION2 = 0x04

#: Offset do valid_flag2 dentro do common.
COMMON_VALID_FLAG2 = 38


def bt_crc32(data: bytes | bytearray, *, seed: int = BT_CRC_SEED) -> int:
    """CRC-32 dos reports BT: byte de seed (header HIDP) + os bytes do report.

    O default é o de OUTPUT (0xA2, comportamento histórico). Quem valida
    INPUT/FEATURE passa `BT_INPUT_CRC_SEED`/`BT_FEATURE_CRC_SEED` — é o
    `ps_check_crc32` do kernel: ``~crc32_le(crc32_le(-1, &seed, 1), data, n)``.
    """
    return zlib.crc32(bytes([seed & 0xFF]) + bytes(data)) & 0xFFFFFFFF


def _check_common(common: bytes | bytearray) -> bytes:
    out = bytes(common)
    if len(out) != COMMON_LEN:
        raise ValueError(f"common deve ter {COMMON_LEN} bytes, veio {len(out)}")
    return out


def build_usb_report(common: bytes | bytearray) -> bytearray:
    """Report de output USB (0x02): ``[0]=0x02, [1..47]=common``, sem CRC."""
    buf = bytearray(USB_REPORT_LEN)
    buf[0] = USB_REPORT_ID
    buf[1 : 1 + COMMON_LEN] = _check_common(common)
    return buf


def build_bt_report(common: bytes | bytearray, *, seq: int = 0) -> bytearray:
    """Report de output BT (0x31) BEM-FORMADO, com tag 0x10 e CRC válido.

    ``seq`` é o nibble de sequência (0..15, mascarado) no nibble ALTO de
    ``[1]`` — o firmware aceita 0 fixo (comportamento do SDL), mas quem envia
    em fluxo deve rotacionar por handle (ver ``stamp_bt_seq``).
    """
    buf = bytearray(BT_REPORT_LEN)
    buf[0] = BT_REPORT_ID
    buf[1] = (int(seq) & 0x0F) << 4
    buf[2] = BT_TAG
    buf[3 : 3 + COMMON_LEN] = _check_common(common)
    crc = bt_crc32(buf[: BT_REPORT_LEN - 4])
    buf[BT_REPORT_LEN - 4 :] = crc.to_bytes(4, "little")
    return buf


def stamp_bt_seq(report: bytearray | list[int], seq: int) -> None:
    """Regrava IN-PLACE o nibble de sequência (e o CRC) de um report 0x31.

    Permite montar o report uma vez (seq 0 — comparável para dedup) e carimbar
    o contador por handle só no momento do WRITE, sem reconstruir o buffer.
    """
    if len(report) != BT_REPORT_LEN or report[0] != BT_REPORT_ID:
        raise ValueError("stamp_bt_seq espera um report 0x31 completo (78 bytes)")
    report[1] = (int(seq) & 0x0F) << 4
    crc = bt_crc32(bytes(report[: BT_REPORT_LEN - 4]))
    crc_bytes = crc.to_bytes(4, "little")
    for i in range(4):
        report[BT_REPORT_LEN - 4 + i] = crc_bytes[i]


__all__ = [
    "BT_CRC_SEED",
    "BT_FEATURE_CRC_SEED",
    "BT_INPUT_CRC_SEED",
    "BT_REPORT_ID",
    "BT_REPORT_LEN",
    "BT_TAG",
    "COMMON_LEN",
    "COMMON_VALID_FLAG2",
    "USB_REPORT_ID",
    "USB_REPORT_LEN",
    "VALID_FLAG0_COMPATIBLE_VIBRATION",
    "VALID_FLAG0_HAPTICS_SELECT",
    "VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE",
    "VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE",
    "VALID_FLAG1_MOTOR_POWER",
    "VALID_FLAG1_PLAYER_INDICATOR_CONTROL_ENABLE",
    "VALID_FLAG1_POWER_SAVE_CONTROL_ENABLE",
    "VALID_FLAG1_RELEASE_LEDS",
    "VALID_FLAG2_COMPATIBLE_VIBRATION2",
    "bt_crc32",
    "build_bt_report",
    "build_usb_report",
    "stamp_bt_seq",
]
