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

USB_REPORT_ID = 0x02
BT_REPORT_ID = 0x31

COMMON_LEN = 47

USB_REPORT_LEN = 64
BT_REPORT_LEN = 78

BT_TAG = 0x10

BT_CRC_SEED = 0xA2

BT_INPUT_CRC_SEED = 0xA1
BT_FEATURE_CRC_SEED = 0xA3

VALID_FLAG0_COMPATIBLE_VIBRATION = 0x01
VALID_FLAG0_HAPTICS_SELECT = 0x02
VALID_FLAG0_RIGHT_TRIGGER_FFB = 0x04
VALID_FLAG0_LEFT_TRIGGER_FFB = 0x08
VALID_FLAG0_HEADPHONE_VOLUME = 0x10
VALID_FLAG0_SPEAKER_VOLUME = 0x20
VALID_FLAG0_MIC_VOLUME = 0x40
VALID_FLAG0_AUDIO_PATH = 0x80

VALID_FLAG0_AUDIO_MASK = (
    VALID_FLAG0_HEADPHONE_VOLUME
    | VALID_FLAG0_SPEAKER_VOLUME
    | VALID_FLAG0_MIC_VOLUME
    | VALID_FLAG0_AUDIO_PATH
)

COMMON_HEADPHONE_VOLUME = 4
COMMON_SPEAKER_VOLUME = 5
COMMON_MIC_VOLUME = 6
COMMON_AUDIO_PATH = 7
COMMON_AUDIO_CONTROL2 = 37

SAIDA_ESTEREO_NO_FONE = 0
SAIDA_MONO_NO_FONE = 1
SAIDA_L_FONE_R_ALTO_FALANTE = 2
SAIDA_SO_NO_ALTO_FALANTE = 3

OUTPUT_PATH_SEL_SHIFT = 4
OUTPUT_PATH_SEL_MASK = 0x30

AUDIO_CONTROL_FORCE_INTERNAL_MIC = 0x01
AUDIO_CONTROL_ECHO_CANCEL = 0x04
AUDIO_CONTROL_NOISE_CANCEL = 0x08
AUDIO_CONTROL_BASE_SEGURA = (
    AUDIO_CONTROL_FORCE_INTERNAL_MIC
    | AUDIO_CONTROL_ECHO_CANCEL
    | AUDIO_CONTROL_NOISE_CANCEL
)

SP_PREAMP_GAIN_MASK = 0x07
SP_PREAMP_GAIN_PADRAO = 0x02

TETO_HEADPHONE_VOLUME = 0x7F
TETO_MIC_VOLUME = 0x40
TETO_SPEAKER_VOLUME = 0xFF

POWER_SAVE_MIC_MUTE = 0x10

VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE = 0x01
VALID_FLAG1_POWER_SAVE_CONTROL_ENABLE = 0x02
VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE = 0x04
VALID_FLAG1_RELEASE_LEDS = 0x08
VALID_FLAG1_PLAYER_INDICATOR_CONTROL_ENABLE = 0x10
VALID_FLAG1_MOTOR_POWER = 0x40
VALID_FLAG1_AUDIO_CONTROL2_ENABLE = 0x80

VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE = 0x01
VALID_FLAG2_LIGHTBAR_SETUP_CONTROL_ENABLE = 0x02
VALID_FLAG2_COMPATIBLE_VIBRATION2 = 0x04

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
    """Regrava IN-PLACE o nibble de sequência (e o CRC) de um report 0x31."""
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
    "COMMON_AUDIO_PATH",
    "COMMON_HEADPHONE_VOLUME",
    "COMMON_LEN",
    "COMMON_MIC_VOLUME",
    "COMMON_SPEAKER_VOLUME",
    "COMMON_VALID_FLAG2",
    "POWER_SAVE_MIC_MUTE",
    "USB_REPORT_ID",
    "USB_REPORT_LEN",
    "VALID_FLAG0_AUDIO_MASK",
    "VALID_FLAG0_AUDIO_PATH",
    "VALID_FLAG0_COMPATIBLE_VIBRATION",
    "VALID_FLAG0_HAPTICS_SELECT",
    "VALID_FLAG0_HEADPHONE_VOLUME",
    "VALID_FLAG0_LEFT_TRIGGER_FFB",
    "VALID_FLAG0_MIC_VOLUME",
    "VALID_FLAG0_RIGHT_TRIGGER_FFB",
    "VALID_FLAG0_SPEAKER_VOLUME",
    "VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE",
    "VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE",
    "VALID_FLAG1_MOTOR_POWER",
    "VALID_FLAG1_PLAYER_INDICATOR_CONTROL_ENABLE",
    "VALID_FLAG1_POWER_SAVE_CONTROL_ENABLE",
    "VALID_FLAG1_RELEASE_LEDS",
    "VALID_FLAG2_COMPATIBLE_VIBRATION2",
    "VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE",
    "VALID_FLAG2_LIGHTBAR_SETUP_CONTROL_ENABLE",
    "bt_crc32",
    "build_bt_report",
    "build_usb_report",
    "stamp_bt_seq",
]


COMMON_REDUCE_MOTOR_POWER = 36
REDUCAO_DA_VIBRACAO_MASK = 0x07
REDUCAO_DO_GATILHO_SHIFT = 4
REDUCAO_DO_GATILHO_MASK = 0x70
PASSOS_DO_FIRMWARE = 8
REDUCAO_MAXIMA = 7

_MODO_FEEDBACK = 0x21
_MODO_ARCO = 0x22
_MODO_ARMA = 0x25
_MODO_VIBRACAO = 0x26
_MODO_METRALHADORA = 0x27
_MODO_DESLIGADO = 0x05
_ZONAS = 10
_FORCA_MAXIMA = 8


def _escala_limpa(escala: float) -> float:
    """A escala como número que se usa: negativa vira zero, e o que não é número vira 1."""
    try:
        valor = float(escala)
    except (TypeError, ValueError):
        return 1.0
    if valor != valor or valor in (float("inf"), float("-inf")):
        return 1.0
    return max(0.0, valor)


def passos_de_reducao(escala: float) -> int:
    """Quantos passos de 12,5% o firmware tira para a ``escala`` (1,0 = 100% do trilho).

    O passo é o de BAIXO (``floor``): a fração que o firmware deixa nunca fica abaixo da escala, e o
    resto que o software põe (:func:`resto_do_software`) só abaixa, nunca satura. De 100% para
    cima não há passo: o reforço é do software.
    """
    valor = _escala_limpa(escala)
    if valor >= 1.0:
        return 0
    return max(0, min(REDUCAO_MAXIMA, int(round((1.0 - valor) * PASSOS_DO_FIRMWARE, 9))))


def fracao_do_firmware(passos: int) -> float:
    """A fração da força que o firmware deixa passar com ``passos`` de redução."""
    return 1.0 - max(0, min(REDUCAO_MAXIMA, int(passos))) / PASSOS_DO_FIRMWARE


def resto_do_software(escala: float) -> float:
    """O que o software multiplica por cima do firmware para a soma dar a ``escala``.

    Abaixo de 100% é a sobra entre a escala e o degrau de 12,5% (entre 0,875 e 1); de 100% para
    cima é a própria escala, com o teto de cada motor posto por quem a aplica.
    """
    valor = _escala_limpa(escala)
    return valor / fracao_do_firmware(passos_de_reducao(valor))


def byte_de_reducao(escala_da_vibracao: float, escala_do_gatilho: float) -> int:
    """O ``common[36]``: a vibração no nibble baixo e o gatilho no alto."""
    return (passos_de_reducao(escala_da_vibracao) & REDUCAO_DA_VIBRACAO_MASK) | (
        (passos_de_reducao(escala_do_gatilho) << REDUCAO_DO_GATILHO_SHIFT)
        & REDUCAO_DO_GATILHO_MASK
    )


def _escalar_forca(forca: int, fator: float) -> int:
    """Uma força de 1 a 8 multiplicada, com o teto do efeito; zero tira a zona."""
    return min(_FORCA_MAXIMA, int(forca * fator + 0.5))


def _desligado() -> bytes:
    bloco = bytearray(11)
    bloco[0] = _MODO_DESLIGADO
    return bytes(bloco)


def _zonas_com_forca(bloco: bytes, fator: float) -> bytes | None:
    """FEEDBACK e VIBRACAO: a máscara de zonas e a força menos um, 3 bits por zona, em [3..6]."""
    mascara = bloco[1] | (bloco[2] << 8)
    empacotado = int.from_bytes(bloco[3:7], "little")
    dentro = 0
    for zona in range(_ZONAS):
        if mascara & (1 << zona):
            dentro |= 0x07 << (3 * zona)
    if not mascara or mascara >> _ZONAS or empacotado & ~dentro:
        return None
    nova_mascara = 0
    novo = 0
    for zona in range(_ZONAS):
        if not mascara & (1 << zona):
            continue
        forca = _escalar_forca(((empacotado >> (3 * zona)) & 0x07) + 1, fator)
        if forca > 0:
            nova_mascara |= 1 << zona
            novo |= (forca - 1) << (3 * zona)
    if not nova_mascara:
        return _desligado()
    fora = bytearray(bloco)
    fora[1], fora[2] = nova_mascara & 0xFF, (nova_mascara >> 8) & 0xFF
    fora[3:7] = novo.to_bytes(4, "little")
    return bytes(fora)


def _duas_pontas(bloco: bytes) -> bool:
    """A máscara de início e fim dos modos de arma, arco e metralhadora: dois bits, dez zonas."""
    mascara = bloco[1] | (bloco[2] << 8)
    return not mascara >> _ZONAS and bin(mascara).count("1") == 2


def _forcas_de_tres_bits(bloco: bytes, fator: float, *, quantas: int, bits: int,
                        resto_zerado: bool) -> bytes | None:
    """ARMA (uma força em [3]), ARCO (a força; o estalo, nos 3 bits de cima, não é força) e
    METRALHADORA (as duas amplitudes em [3]; a frequência e o período seguem em [4] e [5])."""
    if not _duas_pontas(bloco) or bloco[3] >> bits or (resto_zerado and any(bloco[4:7])):
        return None
    novas = [_escalar_forca(((bloco[3] >> (3 * i)) & 0x07) + 1, fator) for i in range(quantas)]
    if all(f <= 0 for f in novas):
        return _desligado()
    fora = bytearray(bloco)
    for indice, forca in enumerate(novas):
        fora[3] = (fora[3] & ~(0x07 << (3 * indice)) & 0xFF) | ((max(1, forca) - 1) << (3 * indice))
    return bytes(fora)


def escalar_o_bloco_do_gatilho(bloco: bytes | bytearray, fator: float) -> bytes:
    """O bloco de 11 bytes de um gatilho com a força multiplicada por ``fator``.

    É o software da «Intensidade do gatilho»: a sobra abaixo de 100% e o reforço acima, com o teto
    na força máxima de cada efeito (8). Vale para o efeito do Hefesto e para o bloco cru do jogo.
    Modo que não tem força (galope, desligado) ou bloco que não passa na conferência da forma sai
    como veio.
    """
    cru = bytes(bloco)
    valor = _escala_limpa(fator)
    if len(cru) != 11 or abs(valor - 1.0) < 1e-9:
        return cru
    modo = cru[0]
    novo: bytes | None = None
    if modo in (_MODO_FEEDBACK, _MODO_VIBRACAO):
        novo = _zonas_com_forca(cru, valor)
    elif modo == _MODO_ARMA:
        novo = _forcas_de_tres_bits(cru, valor, quantas=1, bits=3, resto_zerado=True)
    elif modo == _MODO_ARCO:
        novo = _forcas_de_tres_bits(cru, valor, quantas=1, bits=6, resto_zerado=True)
    elif modo == _MODO_METRALHADORA:
        novo = _forcas_de_tres_bits(cru, valor, quantas=2, bits=6, resto_zerado=False)
    return cru if novo is None else novo


__all__ += [
    "COMMON_REDUCE_MOTOR_POWER",
    "PASSOS_DO_FIRMWARE",
    "REDUCAO_DA_VIBRACAO_MASK",
    "REDUCAO_DO_GATILHO_MASK",
    "REDUCAO_DO_GATILHO_SHIFT",
    "REDUCAO_MAXIMA",
    "byte_de_reducao",
    "escalar_o_bloco_do_gatilho",
    "fracao_do_firmware",
    "passos_de_reducao",
    "resto_do_software",
]
