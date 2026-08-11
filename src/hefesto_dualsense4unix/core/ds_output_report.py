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
#: 0x04/0x08 habilitam o bloco de efeito de gatilho DIREITO/ESQUERDO
#: (common[10..20] / common[21..31]) — esses NÓS controlamos (perfis).
VALID_FLAG0_RIGHT_TRIGGER_FFB = 0x04
VALID_FLAG0_LEFT_TRIGGER_FFB = 0x08
#: 0x10..0x80 habilitam os QUATRO bytes de áudio common[4..7] — volume do
#: fone (4), volume do alto-falante interno (5), volume do microfone (6) e o
#: byte de roteamento/caminho de áudio (7).
#:
#: TEXTO DE 01/08/2026, preservado porque proveniência não se apaga: *"O
#: kernel (`hid-playstation`) declara common[4..7] como `reserved[4]` e NUNCA
#: os escreve; a nomenclatura por bit vem da documentação de comunidade do
#: report 0x02 (Nielk1 / DS5 wiki), que é a única fonte que os descreve — por
#: isso o mapeamento bitbyte está documentado como PROVÁVEL, não como
#: medido."*
#:
#: NOTA DATADA DE 11/08/2026 — o parágrafo acima CADUCOU, e caducou contra
#: este mesmo arquivo: os TETOS logo abaixo (`TETO_HEADPHONE_VOLUME`,
#: `TETO_MIC_VOLUME`) são atribuídos ali ao kernel 6.18, enquanto este
#: comentário dizia que o kernel não conhecia os campos. Um dos dois estava
#: errado, e é este. O Linux 6.18 (patches do jack de áudio, Collabora)
#: NOMEIA os campos. Grau novo: **ALTA** para o alto-falante (5), o microfone
#: (6) e o caminho de áudio (7).
#:
#: O fone (4) fica em DUAS partes, e a distinção é o que importa aqui: o
#: CAMPO é nomeado pelo kernel, mas o BIT DE AUTORIZAÇÃO `0x10` logo abaixo
#: **não** — o kernel define enable para alto-falante, microfone e
#: audio_control, e nenhum para o fone. O `0x10` segue sendo de fonte de
#: COMUNIDADE, grau MÉDIA, e ninguém mediu o que ele faz neste firmware.
#:
#: Limite honesto desta nota: o fonte do `hid-playstation` NÃO foi relido
#: nesta passagem. Ela se apoia no comentário dos tetos, na seção 2 de
#: `docs/protocol/dualsense-referencia-canonica.md` e no registro do mapa de
#: canais (`docs/data/mapa-controles.csv`, linha `audio.jack.volume`), que
#: leu o kernel desta máquina.
VALID_FLAG0_HEADPHONE_VOLUME = 0x10
VALID_FLAG0_SPEAKER_VOLUME = 0x20
VALID_FLAG0_MIC_VOLUME = 0x40
VALID_FLAG0_AUDIO_PATH = 0x80

#: AUDIO-OWNER-01: máscara dos bits de flag0 que autorizam o firmware a
#: adotar common[4..7]. Enquanto o hefesto não tiver um valor de volume para
#: mandar, esta máscara sai ZERADA — asserir autoridade sobre um campo que
#: escrevemos como 0x00 a 60 Hz é mandar "volume zero" com cara de keepalive
#: (é a MESMA classe de defeito do keepalive de vibração do GUERRA-01, que já
#: zerava o rumble de terceiros neste projeto).
VALID_FLAG0_AUDIO_MASK = (
    VALID_FLAG0_HEADPHONE_VOLUME
    | VALID_FLAG0_SPEAKER_VOLUME
    | VALID_FLAG0_MIC_VOLUME
    | VALID_FLAG0_AUDIO_PATH
)

#: Offsets dos bytes de áudio dentro do common (os que a máscara acima valida).
COMMON_HEADPHONE_VOLUME = 4
COMMON_SPEAKER_VOLUME = 5
COMMON_MIC_VOLUME = 6
COMMON_AUDIO_PATH = 7
#: SOM-ROTA-01: o `audio_control2`, longe dos outros quatro no report.
COMMON_AUDIO_CONTROL2 = 37

#: Os valores do campo `OUTPUT_PATH_SEL` (bits 4-5 de `common[7]`), nomeados
#: pela CONSEQUÊNCIA e não pelo número — é assim que eles aparecem na tela.
#:
#: O caso que ela descreveu com o Zelda (*"o speaker do controle faz os
#: barulhos da espada do Link enquanto na tela tem o som normal do jogo"*) é o
#: valor **2**: canal esquerdo para o fone/TV, canal direito para o
#: alto-falante do controle. Um byte.
SAIDA_ESTEREO_NO_FONE = 0
SAIDA_MONO_NO_FONE = 1
SAIDA_L_FONE_R_ALTO_FALANTE = 2
SAIDA_SO_NO_ALTO_FALANTE = 3

#: O deslocamento do `OUTPUT_PATH_SEL` dentro de `common[7]`.
#:
#: Ele existe porque o byte 7 carrega DUAS coisas — a rota de saída (bits 4-5)
#: e o caminho do microfone (bits 0-3 e 6-7). Escrever o byte inteiro com o
#: número da rota apagaria o caminho do mic em silêncio, e é por isso que a
#: sprint proíbe "mexer no common[7] sem o OUTPUT_PATH_SEL inteiro".
OUTPUT_PATH_SEL_SHIFT = 4
OUTPUT_PATH_SEL_MASK = 0x30

#: Os bits do MICROFONE dentro do `common[7]`, e o valor que preserva o
#: microfone interno funcionando quando assumimos a posse do byte.
#:
#: SOM-CANAL-01, REGRESSÃO MEDIDA em 02/08/2026 e curada no mesmo dia: ao pedir
#: uma rota de saída, o `common[7]` era escrito com base ZERO — porque ninguém
#: tinha posse dele antes e não há como LER o valor que o firmware usava. O
#: microfone do controle parou de captar: o `parec` passou de 131072 bytes para
#: **zero**, e voltou assim que a posse foi devolvida.
#:
#: É exatamente a armadilha 2 da sprint dela — *"o common[7] carrega a rota E o
#: caminho do microfone; escrever meio byte muda o outro meio"* — e o
#: `_byte_da_rota` só preservava o outro meio quando JÁ havia posse.
#:
#: `FORCE_INTERNAL_MIC` (bit0) é a base segura: ele diz ao firmware para usar o
#: microfone interno, que é o que o DualSense tem quando não há headset. Os
#: demais bits (cancelamento de eco e de ruído, `INPUT_PATH`) ficam em zero, que
#: é o neutro deles.
AUDIO_CONTROL_FORCE_INTERNAL_MIC = 0x01
AUDIO_CONTROL_BASE_SEGURA = AUDIO_CONTROL_FORCE_INTERNAL_MIC

#: O ganho do pré-amplificador do alto-falante, nos bits 0-2 de `common[37]`.
#: `0x2` é o valor que o kernel 6.18 escolhe, e é o que a E1 da SOM-ROTA-01
#: passou a escrever.
#:
#: NOTA DATADA DE 11/08/2026 — estas três linhas estavam ÓRFÃS: elas abriam o
#: bloco de comentário das constantes do MICROFONE (`common[7]`), quatro
#: constantes acima, e documentavam um par que ficava aqui embaixo sem
#: comentário nenhum. Nada de lógica mudou; o comentário voltou para o que
#: ele descreve.
#:
#: E o que ele descreve JÁ ESTÁ VIVO: `core/backend_pydualsense.py:786-790`
#: escreve `common[37]` e liga o `VALID_FLAG1_AUDIO_CONTROL2_ENABLE` sempre
#: que há um pré-amp pedido, e a linha `:2695` manda o
#: `SP_PREAMP_GAIN_PADRAO`. A seção 3 da referência canônica dizia até hoje
#: que *"este projeto escreve só o volume"* — ela recebeu nota datada.
SP_PREAMP_GAIN_MASK = 0x07
SP_PREAMP_GAIN_PADRAO = 0x02

#: Os TETOS reais de cada volume, que não são 255.
#:
#: SOM-ROTA-01: a árvore tratava os quatro bytes como 0-255. O fone vai até
#: `0x7F` e o microfone até `0x40` — mandar mais é mandar lixo num campo que o
#: firmware interpreta. Fonte: kernel 6.18 (patches do jack de áudio,
#: Collabora) e `dualsensectl`, que concordam.
TETO_HEADPHONE_VOLUME = 0x7F
TETO_MIC_VOLUME = 0x40
TETO_SPEAKER_VOLUME = 0xFF

#: Bit de MUDO do microfone dentro de `common[9]` (power_save_control) —
#: `DS_OUTPUT_POWER_SAVE_CONTROL_MIC_MUTE` do `hid-playstation`.
POWER_SAVE_MIC_MUTE = 0x10

# --- bits de valid_flag1 (common[1]) ---------------------------------------
VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE = 0x01
VALID_FLAG1_POWER_SAVE_CONTROL_ENABLE = 0x02
VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE = 0x04
VALID_FLAG1_RELEASE_LEDS = 0x08
VALID_FLAG1_PLAYER_INDICATOR_CONTROL_ENABLE = 0x10
VALID_FLAG1_MOTOR_POWER = 0x40
#: SOM-ROTA-01 — bit7 do flag1: autoriza o firmware a adotar `common[37]`
#: (`audio_control2`), que carrega o GANHO DO PRÉ-AMPLIFICADOR do alto-falante
#: nos bits 0-2 e o beam forming do microfone no bit4.
#:
#: **Ele é a peça que faltava para o controle deslizante de volume valer o
#: curso inteiro.** Ela mediu em 01/08: mudo até 38, satura em 102 — 60% do
#: curso inerte. O kernel 6.18, para fazer o alto-falante soar quando o fone
#: sai, escreve TRÊS campos (a rota em `common[7]`, o volume em `common[5]` e
#: o pré-amp aqui); esta árvore escrevia só o volume, e os 64 passos úteis são
#: a assinatura de mexer em um de três botões.
VALID_FLAG1_AUDIO_CONTROL2_ENABLE = 0x80

# --- bits de valid_flag2 (common[38]) --------------------------------------
#: bit0 (pydualsense `LedOptions.PlayerLedBrightness`): habilita o controle de
#: BRILHO da lightbar (common[42]).
VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE = 0x01
#: bit1 (pydualsense `LedOptions.UninterrumpableLed`; kernel
#: `DS_OUTPUT_VALID_FLAG2_LIGHTBAR_SETUP_CONTROL_ENABLE`): habilita o SETUP da
#: lightbar (common[41] = fade-in/fade-out). O kernel o usa UMA vez por
#: conexão (opcode 2 = LIGHT_OUT) para tomar a barra; mantê-lo engatado em
#: regime (keepalive) trava a exibição no firmware — ver LIGHTBAR-BT-KEEPALIVE-01.
VALID_FLAG2_LIGHTBAR_SETUP_CONTROL_ENABLE = 0x02
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
