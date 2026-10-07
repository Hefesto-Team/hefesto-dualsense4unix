"""Gamepad virtual via /dev/uhid — um DualSense DE VERDADE (SPRINT-UHID-VPAD-01).

Por que este módulo existe
--------------------------
O vpad de `uinput_gamepad.py` é um device de **evdev**: ele não tem hidraw. O SDL,
ao ver a máscara DualSense (VID/PID 054c:0ce6), usa o driver PS5 e procura o
**hidraw** para vibrar — não acha, e a vibração morre. Foi por isso que a máscara
Xbox 360 virou obrigatória para o rumble funcionar, e por isso a matriz de
paridade (`2026-07-13-sprint-paridade-de-features.md`) marcou como MORTO no vpad:
gatilhos adaptativos, lightbar, giroscópio, touchpad e bateria.

O uhid registra um device **HID** no kernel. O driver `hid_playstation` faz bind
nele e constrói o DualSense inteiro — de graça, com o código que já está no
kernel::

    playstation 0003:054C:0CE6.000C: hidraw6: USB HID v1.00 Gamepad [...]
    input: ... P1  /  ... P1 Motion Sensors  /  ... P1 Touchpad  /  ... Headset Jack
    playstation 0003:054C:0CE6.000C: Registered DualSense controller
    leds/: input86:rgb:indicator + input86:white:player-1..5

E o rumble que o jogo pede chega a nós como `UHID_OUTPUT` — de onde o
`rumble_sink` o entrega ao controle físico, igual ao caminho FF do uinput.

Como o device é forjado
-----------------------
O report descriptor e os feature reports (0x05 calibração, 0x09 MAC, 0x20
firmware) são os que o `hid_playstation` pede no probe
(`dualsense_get_mac_address`, `dualsense_get_calibration_data`,
`dualsense_get_firmware_info`). Desde VPAD-03/BT-01 eles vêm do **blueprint
canônico embutido** (`uhid_blueprint.py`) — nenhuma leitura do controle físico
no caminho de criação, então o vpad sobe até sem controle conectado e o EIO do
BT ocioso deixou de existir como modo de falha. A captura do físico
(`capture_dualsense_blueprint`) sobrevive como ferramenta de diagnóstico.

Três detalhes custaram um PoC e não podem se perder:

1. **MAC duplicado faz o probe falhar** com ``Duplicate device found for MAC
   address ... / Failed to create dualsense / probe failed -17``. Cada vpad
   precisa do seu MAC, na faixa localmente administrada (ver `vpad_mac`, e
   `player_mac` para o piso). Desde COOP-QUE-NÃO-DESMONTA-01/E3 esse MAC segue
   o CONTROLE FÍSICO, não o número do jogador: o número é reciclado quando
   alguém sai da mesa, e o MAC não pode ser reciclado junto.
2. **Responder UHID_GET_REPORT é obrigatório** durante o probe — sem isso o
   driver não registra o controle.
3. **UHID_SET_REPORT também precisa de reply**, senão o probe trava.

Degradação: sem `/dev/uhid` (ou sem permissão, ou kernel sem `hid_playstation`),
`start()` devolve False e o chamador cai no `UinputGamepad` — sem crash, mas
avisando que a vibração da máscara DualSense não vai funcionar.
"""
from __future__ import annotations

import collections
import contextlib
import errno
import fcntl
import os
import re
import struct
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.core import system_check
from hefesto_dualsense4unix.core.rumble import pedido_mais_forte
from hefesto_dualsense4unix.integrations import pad_usb
from hefesto_dualsense4unix.utils.espera import prontos_para_ler
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

UHID_NODE = "/dev/uhid"

UHID_DESTROY = 1
UHID_START = 2
UHID_STOP = 3
UHID_OPEN = 4
UHID_CLOSE = 5
UHID_OUTPUT = 6
UHID_GET_REPORT = 9
UHID_GET_REPORT_REPLY = 10
UHID_CREATE2 = 11
UHID_INPUT2 = 12
UHID_SET_REPORT = 13
UHID_SET_REPORT_REPLY = 14

HID_MAX_DESCRIPTOR_SIZE = 4096

_CREATE2_HEAD = 128 + 64 + 64 + 2 + 2 + 4 + 4 + 4 + 4
UHID_EVENT_SIZE = 4 + _CREATE2_HEAD + HID_MAX_DESCRIPTOR_SIZE

BUS_USB = 0x03

#: VID/PID do DualSense FÍSICO. É o que o `_is_dualsense` exige do controle de
DUALSENSE_VENDOR = 0x054C
DUALSENSE_PRODUCT = 0x0CE6

#: forjado, ele vira um DualSense **Edge** (0x0DF2): o `hid_playstation` o
#: registra como DualSense COMPLETO (validado ao vivo — hidraw+lightbar+motion+
#: touchpad+rumble; dmesg "Registered DualSense controller") e o SDL o reconhece
#: trata 0x0DF2 como PID de FÍSICO (o Edge real existe) — quem impede o daemon de
#: VID/PID com o vpad — só a dedup por ancestralidade na regra udev (Fase B do
VPAD_PRODUCT = 0x0DF2

#: Feature reports que o probe do hid_playstation lê, com os tamanhos que o
_FEATURE_SIZES: tuple[tuple[int, int], ...] = ((0x05, 41), (0x09, 20), (0x20, 64))

#: Report de output do DualSense em USB (rumble/lightbar/gatilhos do jogo).
_OUTPUT_REPORT_USB = 0x02

_VALID_FLAG0_OFFSET = 0
_RUMBLE_WEAK_OFFSET = 2
_RUMBLE_STRONG_OFFSET = 3

#: 0x02 SOZINHO. Os dois DualSense da máquina de teste são 0x0630 — testar só o
#: SDL, winebus, a implementação DualSense do próprio título). Nada obriga
_VIBRATION_FLAGS = 0x03

#: tremendo sem parar, em todo jogo, em qualquer DualSense".
_RUMBLE_STALE_SEC = 3.0

_TRIGGER_FLAGS = 0x0C

_LUZ_FLAGS = 0x14

_MAX_EVENTS_PER_PUMP = 64

_UHID_FIO_ACORDA_S = 1.0

_ANEL_DE_VIBRACAO_MAX = 8

RAMO_V1 = "v1"
RAMO_V2 = "v2"
RAMO_PARADA_SDL = "parada_sdl"
RAMO_DESCARTADO = "descartado"

ATIVIDADE_TRIGGER = "trigger"
ATIVIDADE_LIGHTBAR = "lightbar"
ATIVIDADE_PLAYER_LEDS = "player_leds"
ATIVIDADE_RUMBLE = "rumble"
ATIVIDADE_TOUCHPAD_CLICK = "touchpad_click"
ATIVIDADE_OUTPUT = "output"
ATIVIDADE_JACK = "jack"
ATIVIDADE_AUDIO_DO_JOGO = "audio_do_jogo"

_AUDIO_FLAGS_DO_JOGO = 0xF0

_ATIVIDADE_POR_CATEGORIA: dict[str, str] = {
    "trigger_left": ATIVIDADE_TRIGGER,
    "trigger_right": ATIVIDADE_TRIGGER,
    "lightbar": ATIVIDADE_LIGHTBAR,
    "player_leds": ATIVIDADE_PLAYER_LEDS,
}

_VALID_FLAG1_OFFSET = 1
_TRIGGER_R_BLOCK_OFFSET = 10
_TRIGGER_L_BLOCK_OFFSET = 21
_TRIGGER_BLOCK_LEN = 11
_PLAYER_LEDS_OFFSET = 43
_LIGHTBAR_RGB_OFFSET = 44

_TRIGGER_R_EFFECT_ENABLE = 0x04
_TRIGGER_L_EFFECT_ENABLE = 0x08

_LIGHTBAR_CONTROL_ENABLE = 0x04
_PLAYER_INDICATOR_CONTROL_ENABLE = 0x10

_PLAYER_LEDS_MASK = 0x1F

_REPLICA_MIN_INTERVAL_S = 1.0 / 250.0

_GAME_REPLICA_GRACE_S = 0.5

#: Report de input do DualSense em USB (sticks/gatilhos/botões → jogo).
_INPUT_REPORT_USB = 0x01

_INPUT_PAYLOAD_SIZE = 63

_SEQ_OFFSET = 6
_BUTTONS0_OFFSET = 7
_BUTTONS1_OFFSET = 8
_BUTTONS2_OFFSET = 9

_STICK_CENTER = 0x80
_AXES_NEUTRAL = (_STICK_CENTER, _STICK_CENTER, _STICK_CENTER, _STICK_CENTER, 0, 0)

_BUTTONS0_BITS: dict[str, int] = {
    "square": 0x10,
    "cross": 0x20,
    "circle": 0x40,
    "triangle": 0x80,
}
_BUTTONS1_BITS: dict[str, int] = {
    "l1": 0x01,
    "r1": 0x02,
    "l2_btn": 0x04,
    "r2_btn": 0x08,
    "create": 0x10,
    "options": 0x20,
    "l3": 0x40,
    "r3": 0x80,
}
_BUTTONS2_BITS: dict[str, int] = {
    "ps": 0x01,
    "mic_btn": 0x04,
}

#: (esquerda/meio/direita) é invenção nossa para o modo mouse, o DualSense real
_TOUCHPAD_BUTTONS = frozenset({
    "touchpad", "touchpad_press",
    "touchpad_left_press", "touchpad_middle_press", "touchpad_right_press",
})
_TOUCHPAD_BIT = 0x02

#: Pontos de toque do touchpad (4 B cada) dentro do payload do report 0x01.
#:
#: O byte de contato é INVERTIDO: o `dualsense_parse_report` lê
#: ``active = !(point->contact & 0x80)`` — ou seja, payload zerado significa
#: **dedo encostado em (0,0)**, não "sem toque". Sem carimbar o 0x80 o vpad nasce
#: com dois toques fantasma presos no canto do touchpad.
#:
#: 32/36, não 31/35: o `reserved2` do `struct dualsense_input_report` fica no 31 e
#: empurra os pontos. Medido num report cru do controle com o dedo FORA do
#: touchpad — o 0x80 aparece exatamente em ``payload[32]`` e ``payload[36]``
#: (o 31 vale 0x15, lixo do sensor_timestamp).
_TOUCH_POINT_OFFSETS = (32, 36)
_TOUCH_INACTIVE = 0x80

#: GYRO-01 — janela de MOTION do payload do report 0x01: bytes 15..39 do
#: `struct dualsense_input_report` (hid-playstation.c): gyro[3] __le16 em
#: 15-20, accel[3] __le16 em 21-26, sensor_timestamp __le32 em 27-30 (unidade
#: de 0,33 µs — o dt que o SDL usa para integrar o gyro), reserved2 em 31 e os
#: dois pontos de toque (4 B cada) em 32-35/36-39. É a fatia que o
#: `PhysicalReportReader` copia VERBATIM do report cru do físico (0x01 USB /
#: 0x31 BT) e entrega em `forward_motion` — zero matemática no caminho.
_MOTION_WINDOW_START = 15
_MOTION_WINDOW_LEN = 25
_MOTION_WINDOW = slice(_MOTION_WINDOW_START, _MOTION_WINDOW_START + _MOTION_WINDOW_LEN)

#: Janela NEUTRA — byte a byte idêntica ao que o encoder sempre emitiu: IMU
_MOTION_NEUTRAL = bytes(
    _TOUCH_INACTIVE if offset in _TOUCH_POINT_OFFSETS else 0
    for offset in range(_MOTION_WINDOW_START, _MOTION_WINDOW_START + _MOTION_WINDOW_LEN)
)

_CALIBRATION_FEATURE_ID = 0x05
_CALIBRATION_FEATURE_SIZE = 41

#: Zerado, o vpad anuncia **5% descarregando para sempre** — o jogo mostra alerta
#: de bateria fraca num controle carregado. Medido: o físico manda 0x29 (= 95%).
#: Espelhamos a bateria do controle físico daquele jogador; sem dado, "cheio e
#: carregando" (0x1F) é a mentira menos daninha — não dispara alerta.
_STATUS_OFFSET = 52
_STATUS_DESCONHECIDO = 0x1F

#: BT-E-VPAD-01, furo 2 — o byte 53 do report de entrada (`status[1]`), que o
#: vpad NUNCA escrevia.
#:
#: Ele carrega três bits, documentados no kernel 6.18 (patches do jack de
#: áudio, Collabora):
#:
#:   bit0 HP_DETECT   — há fone plugado
#:   bit1 MIC_DETECT  — há microfone plugado
#:   bit2 MIC_MUTE    — o microfone está mudo
#:
#: Saindo sempre `0x00`, o vpad anunciava... exatamente o contrário do que
#: parece: com os bits em zero, **nenhum** dispositivo é declarado. O problema
#: é que o campo nunca acompanhava o físico — um jogo que decida rotear som
#: para o alto-falante do controle SÓ quando não há fone estava lendo um valor
#: fixo que não corresponde a nada.
#:
#: A cura é espelhar o byte do controle físico daquele jogador. O dado está
#: FORA da janela de motion (15..39), então precisa de caminho próprio — o
#: mesmo desenho que o clique do touchpad já usa.
_STATUS1_OFFSET = 53

#: O valor neutro do byte 53: nada plugado, nada mudo. É o que o vpad manda
#: enquanto o físico não disser o contrário — e é honesto, porque "não sei" e
_STATUS1_NEUTRO = 0x00

_STATUS1_BITS_CONHECIDOS = 0x07

_STATUS1_HP_DETECT = 0x01
_STATUS1_MIC_DETECT = 0x02
_STATUS1_MIC_MUTE = 0x04
_CHARGING_SHIFT = 4
_BATTERY_MAX_NIBBLE = 0x0A

_DPAD_NEUTRAL = 0x08
_HAT_BY_VECTOR: dict[tuple[int, int], int] = {
    (0, -1): 0, (1, -1): 1, (1, 0): 2, (1, 1): 3,
    (0, 1): 4, (-1, 1): 5, (-1, 0): 6, (-1, -1): 7,
    (0, 0): _DPAD_NEUTRAL,
}

_BIND_POLL_INTERVAL_S = 0.01

#: Medido ao vivo: o probe que recusa manda CLOSE+STOP em ~2 ms → 50 ms são 25x de
#: folga, pagos uma vez por promoção de jogador. (Começou em 150 ms, que davam 75x
_BIND_SETTLE_S = 0.05

#: escreve (num DualSense de verdade este campo é o MAC do adaptador, no rádio,
VPAD_HID_PHYS = "hefesto-vpad"


VPAD_MAC_PREFIXO = "02:fe"

_VPAD_MAC_BIT_DERIVADO = 0x80


def player_mac(player: int) -> str:
    """MAC do vpad DERIVADO DO NÚMERO do jogador (1-based) — o **fallback**."""
    return f"{VPAD_MAC_PREFIXO}:00:00:00:{player:02x}"


def vpad_mac(identity: str | None, player: int) -> str:
    """MAC do vpad deste jogador, ancorado no APARELHO e não no número."""
    digitos = _somente_hex(identity)
    if len(digitos) != 12:
        return player_mac(player)
    import hashlib

    bruto = bytearray(hashlib.blake2b(digitos.encode("ascii"), digest_size=4).digest())
    bruto[0] |= _VPAD_MAC_BIT_DERIVADO
    return f"{VPAD_MAC_PREFIXO}:" + ":".join(f"{b:02x}" for b in bruto)


def _somente_hex(valor: str | None) -> str:
    """Os dígitos hexadecimais de `valor`, minúsculos. `None` → string vazia."""
    if not valor:
        return ""
    baixo = valor.lower()
    if any(ch not in "0123456789abcdef:" for ch in baixo):
        return ""
    return baixo.replace(":", "")


def _bitmask(pressed: frozenset[str], bits: dict[str, int]) -> int:
    """OR dos bits dos botões pressionados que existem no mapa dado."""
    mask = 0
    for name, bit in bits.items():
        if name in pressed:
            mask |= bit
    return mask


def _mac_to_report_bytes(mac: str) -> bytes:
    """MAC textual → os 6 bytes do report 0x09, em little-endian."""
    return bytes(reversed(bytes.fromhex(mac.replace(":", ""))))


def _percent_para_nibble(percent: int) -> int:
    """Bateria em % → o nibble do byte de status, no nível REPRESENTÁVEL mais perto.

    O kernel faz o caminho inverso: ``capacity = min(nibble * 10 + 5, 100)``. Só
    existem 11 níveis (5, 15, …, 95 e 100), então arredondar para o mais próximo
    erra no máximo 5% — truncar erraria 9% e "100%" nunca chegaria a aparecer
    (viraria 95%, com o controle na base carregado).
    """
    if percent >= 100:
        return _BATTERY_MAX_NIBBLE
    nibble = int((percent - 5 + 5) // 10)  # == round-half-up de (percent-5)/10
    return min(max(nibble, 0), _BATTERY_MAX_NIBBLE - 1)


def _hidiocgfeature(fd: int, report_id: int, size: int) -> bytes:
    """HIDIOCGFEATURE(len) = _IOC(READ|WRITE, 'H', 0x07, len)."""
    buf = bytearray(size)
    buf[0] = report_id
    request = (3 << 30) | (size << 16) | (ord("H") << 8) | 0x07
    ret = fcntl.ioctl(fd, request, buf, True)
    return bytes(buf[:ret]) if ret > 0 else b""


def _is_dualsense(node: str) -> bool:
    """Confere VID/PID no sysfs — nem todo hidraw é um DualSense.

    Sem isto, apontar para o hidraw errado (teclado, mouse, headset) produzia um
    "blueprint" que o hid_playstation ia recusar lá na frente, com um erro que
    não diz nada sobre a causa.
    """
    try:
        with open(f"/sys/class/hidraw/{node}/device/uevent") as handle:
            uevent = handle.read()
    except OSError:
        return False
    match = re.search(r"^HID_ID=[0-9A-Fa-f]+:0*([0-9A-Fa-f]+):0*([0-9A-Fa-f]+)",
                      uevent, re.MULTILINE)
    if match is None:
        return False
    vendor, product = int(match.group(1), 16), int(match.group(2), 16)
    return (vendor, product) == (DUALSENSE_VENDOR, DUALSENSE_PRODUCT)


def capture_dualsense_blueprint(hidraw_path: str) -> dict[str, Any] | None:
    """Lê do DualSense físico o mesmo shape do blueprint canônico (DIAGNÓSTICO).

    Fora do caminho de criação desde VPAD-03/BT-01: o vpad usa o blueprint
    canônico embutido (`uhid_blueprint.canonical_blueprint`) e nunca mais lê o
    físico — por BT, um controle ocioso não responde features e cada GET_REPORT
    estoura o timeout de 5 s do hidp com EIO (janelas de minutos), o que
    derrubava o vpad para uinput. A função fica para diagnóstico/recaptura
    (irmã de `scripts/capture_blueprint.py`).

    Devolve ``{"descriptor": bytes, "features": {id: bytes}}`` ou None quando o
    controle não está acessível ou não é um DualSense.
    """
    node = os.path.basename(hidraw_path.rstrip("/"))
    if not re.fullmatch(r"hidraw\d+", node):
        logger.warning("uhid_hidraw_path_invalido", path=hidraw_path)
        return None
    if not _is_dualsense(node):
        logger.warning("uhid_nao_e_dualsense", path=hidraw_path)
        return None

    descriptor_path = f"/sys/class/hidraw/{node}/device/report_descriptor"
    try:
        with open(descriptor_path, "rb") as handle:
            descriptor = handle.read()
    except OSError as exc:
        logger.warning("uhid_descriptor_read_failed", path=descriptor_path, err=str(exc))
        return None
    if not descriptor or len(descriptor) > HID_MAX_DESCRIPTOR_SIZE:
        logger.warning("uhid_descriptor_invalido", tamanho=len(descriptor))
        return None

    if b"\x85\x31" in descriptor:
        logger.info("uhid_descriptor_bt_diagnostico", path=hidraw_path,
                    tamanho=len(descriptor))

    features: dict[int, bytes] = {}
    from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
        PortaFechadaError,
        abrir_hidraw,
    )

    try:
        aberto = abrir_hidraw(hidraw_path, escrita=True)
    except PortaFechadaError as exc:
        logger.warning("uhid_hidraw_open_failed", path=hidraw_path, err=str(exc))
        return None
    logger.debug("uhid_blueprint_porta", path=hidraw_path, porta=aberto.porta,
                 motivo=aberto.motivo)
    try:
        for report_id, size in _FEATURE_SIZES:
            try:
                features[report_id] = _hidiocgfeature(aberto.fd, report_id, size)
            except OSError as exc:
                logger.warning("uhid_feature_read_failed", report=hex(report_id),
                               err=str(exc))
    finally:
        aberto.fechar()

    mac_report = features.get(0x09, b"")
    if len(mac_report) < 7:
        logger.warning("uhid_blueprint_sem_mac", path=hidraw_path,
                       tamanho=len(mac_report))
        return None
    return {"descriptor": descriptor, "features": features}


def uhid_available() -> bool:
    """True quando dá para abrir /dev/uhid para escrita (udev aplicado)."""
    return os.access(UHID_NODE, os.R_OK | os.W_OK)

def _e_a_parada_do_sdl(body: bytes) -> bool:
    """True quando o report é a PARADA de vibração que o SDL emite."""
    if len(body) <= _RUMBLE_STRONG_OFFSET:
        return False
    if body[_VALID_FLAG0_OFFSET] or body[_VALID_FLAG1_OFFSET]:
        return False
    return not (body[_RUMBLE_WEAK_OFFSET] or body[_RUMBLE_STRONG_OFFSET])


def _fala_de_vibracao(body: bytes) -> bool:
    """True quando o report do jogo AUTORIZA os bytes 2-3 como vibração.

    RUMBLE-QUE-NAO-SE-SENTE-01. São DUAS codificações, e o gate histórico
    conhecia só uma.

    * **v1** — `valid_flag0` com `COMPATIBLE_VIBRATION` (0x01) e/ou
      `HAPTICS_SELECT` (0x02): é o :data:`_VIBRATION_FLAGS`;
    * **v2** — `valid_flag2` com `COMPATIBLE_VIBRATION2` (0x04). O firmware
      2.21+ trocou o método de vibração, e quem escreve pode mandar SÓ o bit
      v2. O nosso próprio `core/ds_output_report.py` já nomeia essa constante,
      e o `core/backend_pydualsense.py` já a manipula ao ESCREVER no controle
      físico — mas o caminho de LEITURA (o jogo → vpad) nunca a consultou.

    O flag2 é lido com guarda de tamanho: um report curto (jogo que manda só
    o cabeçalho de vibração) não pode levantar `IndexError` dentro do pump.

    Aceitar o bit v2 NÃO afrouxa o gate que o RUMBLE-PRESO-01 instalou: o
    report de gatilho liga `flag0 & 0x0C`, o de luz liga `flag1 & 0x14` e o de
    brilho/setup de lightbar liga `flag2 & 0x03` — nenhum deles encosta no
    0x04 do flag2. O que era descartado aqui era vibração de verdade.
    """
    if len(body) <= _RUMBLE_STRONG_OFFSET:
        return False
    if body[_VALID_FLAG0_OFFSET] & _VIBRATION_FLAGS:
        return True
    return (
        len(body) > rep.COMMON_VALID_FLAG2
        and bool(body[rep.COMMON_VALID_FLAG2] & rep.VALID_FLAG2_COMPATIBLE_VIBRATION2)
    )


@dataclass
class UhidDualSense:
    """DualSense virtual criado via /dev/uhid, com passthrough de rumble.

    A interface espelha a de `UinputGamepad` (`start`/`stop`/`is_active`/
    `pump_ff`) para o co-op e o gamepad primário trocarem de backend sem
    cirurgia. O que muda: aqui o input vai em **report HID** (INPUT2), não em
    eventos evdev — quem monta o report é `send_report()`.
    """

    player: int = 1
    identity: str | None = None
    product: int = VPAD_PRODUCT
    blueprint: dict[str, Any] | None = None
    #: do físico, o 0x05 precisa ser o DAQUELA unidade — o canônico veio de UMA
    calibration_0x05: bytes | None = None
    rumble_sink: Callable[[int, int], None] | None = None
    trigger_sink: Callable[[str, bytes], None] | None = None
    lightbar_sink: Callable[[int, int, int], None] | None = None
    player_led_sink: Callable[[tuple[bool, bool, bool, bool, bool]], None] | None = None
    session_end_sink: Callable[[], None] | None = None
    mic_led_sink: Callable[[int | None], bool | None] | None = None
    mic_mute_sink: Callable[[bool], bool | None] | None = None
    time_fn: Callable[[], float] = time.monotonic
    sleep_fn: Callable[[float], None] = time.sleep

    _fd: int | None = None
    _features: dict[int, bytes] = field(default_factory=dict)
    _last_sent: tuple[int, int] = (0, 0)
    _rumble_visto_em: float | None = None
    _output_count: int = 0
    _rumble_count: int = 0
    _rumble_nao_nulo_count: int = 0
    _rumble_maior_pedido: tuple[int, int] = (0, 0)
    _rumble_no_fisico: tuple[int, int] | None = None
    _rumble_no_fisico_em: float | None = None
    _rumble_descartado_count: int = 0
    _rumble_descartado_amostra: tuple[int, int, int, int, int] | None = None
    _rumble_v2_count: int = 0
    _rumble_parada_sdl_count: int = 0
    _output_id_estranho_count: int = 0
    _output_id_estranho_amostra: tuple[int, int] | None = None
    _rumble_anel: list[tuple[float, int, int, int, int, int, str]] = field(
        default_factory=list
    )
    _started: bool = False
    _game_open: bool = False
    _bound_at: float | None = None
    _game_dirty: bool = False
    _replica_last: dict[str, Any] = field(default_factory=dict)
    _replica_pending: dict[str, Any] = field(default_factory=dict)
    _replica_ts: dict[str, float] = field(default_factory=dict)
    _trigger_replicas: int = 0
    _lightbar_replicas: int = 0
    _player_led_replicas: int = 0
    _mic_led_do_jogo: int = 0
    _mic_mudo_do_jogo: int = 0
    _mic_do_jogo_retido: int = 0
    _mic_eco_do_driver: int = 0
    _mic_led_do_jogo_amostra: int | None = None
    _mic_mudo_do_jogo_amostra: bool | None = None
    _mic_luz_entregue: bool = False
    _mic_solta_a_entregar: bool = False
    _janelas_do_eco: collections.deque[float] = field(
        default_factory=lambda: collections.deque(maxlen=_JANELAS_DO_ECO_MAX)
    )
    _mic_bit_que_saiu: bool = False
    _visto_em: dict[str, float] = field(default_factory=dict)
    _audio_do_jogo_amostra: tuple[int, int, int, int, int] | None = None
    _lock: threading.RLock = field(default_factory=threading.RLock)
    _axes: tuple[int, int, int, int, int, int] = _AXES_NEUTRAL
    _buttons: frozenset[str] = field(default_factory=frozenset)
    _status_byte: int = _STATUS_DESCONHECIDO
    _status1_byte: int = _STATUS1_NEUTRO
    _jack_forward_count: int = 0
    _battery_forward_count: int = 0
    _motion_window: bytes = _MOTION_NEUTRAL
    _motion_streaming: bool = False
    _motion_count: int = 0
    _touchpad_click: bool = False
    _touchpad_click_count: int = 0
    _mic_button: bool = False
    _mic_button_count: int = 0
    _motion_invalid_logged: bool = False
    _last_body: bytes | None = None
    _seq: int = 0
    _fio_do_uhid: threading.Thread | None = None
    _pare_o_fio: threading.Event | None = None
    _despertador: tuple[int, int] | None = None
    _trava_da_saida: threading.RLock = field(default_factory=threading.RLock)
    _rumble_a_entregar: tuple[int, int] | None = None
    _fim_de_sessao_a_entregar: bool = False
    _gadget: _GadgetDoPad | None = None
    _gadget_prazo: float | None = None
    _gadget_falhou: bool = False
    _gadget_caiu: bool = False
    _sem_gadget: bool = False

    @classmethod
    def for_flavor(
        cls,
        flavor: str | None = None,
        *,
        rumble_sink: Callable[[int, int], None] | None = None,
        trigger_sink: Callable[[str, bytes], None] | None = None,
        lightbar_sink: Callable[[int, int, int], None] | None = None,
        player_led_sink: Callable[[tuple[bool, bool, bool, bool, bool]], None]
        | None = None,
        session_end_sink: Callable[[], None] | None = None,
        player: int = 1,
        blueprint: dict[str, Any] | None = None,
        calibration_0x05: bytes | None = None,
        identity: str | None = None,
        mic_led_sink: Callable[[int | None], bool | None] | None = None,
        mic_mute_sink: Callable[[bool], bool | None] | None = None,
    ) -> UhidDualSense | None:
        """Vpad uhid para o flavor pedido, ou **None** = "use o UinputGamepad".

        No uhid a máscara é sempre DualSense — é a graça do backend: o device tem
        hidraw de verdade, então o SDL usa o driver PS5 e a vibração funciona
        (com uinput+máscara DualSense ela é impossível). Forjar um Xbox 360 aqui
        seria pior que o uinput: o `hid_playstation` só faz bind em VID/PID da
        Sony (0ce6, 0df2...), e sem driver o device HID não vira gamepad nenhum.
        Por isso `xbox` devolve None e o chamador segue no `UinputGamepad`, que
        faz Xbox muito bem.

        `flavor=None` significa "sem preferência" e resolve para dualsense — de
        propósito NÃO passa pelo `normalize_flavor`, cujo default é xbox: quem
        chega aqui já escolheu o backend uhid, e herdar aquele default desligaria
        o uhid em silêncio justo no caso comum.

        `identity` (MÁSCARA-POR-JOGADOR-01, 15/08/2026) é o MAC canônico do
        controle FÍSICO deste jogador. Quando ESTE aparelho tem máscara escolhida
        no `external_mask`, é ela que decide — inclusive para dizer **não**: um
        controle marcado como `xbox` devolve None aqui e segue para o
        `UinputGamepad`, mesmo que a máscara do jogo seja dualsense. Sem escolha
        registrada, a regra do `flavor` acima vale intacta, com o `None` a
        significar dualsense como sempre significou.
        """
        from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
            registro_de_mascaras,
        )
        from hefesto_dualsense4unix.integrations.uinput_gamepad import normalize_flavor

        escolhida = registro_de_mascaras().mask_for(identity)
        if escolhida is not None:
            if escolhida != "dualsense":
                return None
        elif flavor is not None and normalize_flavor(flavor) != "dualsense":
            return None
        return cls(
            player=player,
            identity=identity,
            blueprint=blueprint,
            calibration_0x05=calibration_0x05,
            rumble_sink=rumble_sink,
            trigger_sink=trigger_sink,
            lightbar_sink=lightbar_sink,
            player_led_sink=player_led_sink,
            session_end_sink=session_end_sink,
            mic_led_sink=mic_led_sink,
            mic_mute_sink=mic_mute_sink,
        )

    @property
    def name(self) -> str:
        """O nome HID do vpad, com a substring que os jogos procuram.

        BT-E-VPAD-01, furo 1. Ele era `Hefesto Virtual DualSense P1`, e sob
        Proton esse nome vira o `FriendlyName` do lado Windows — **jogos casam
        pela substring "Wireless Controller"** para achar o controle e o
        device de áudio associado a ele.

        Havia incoerência interna que denunciava o furo: o fallback uinput
        acerta (`Sony Interactive Entertainment DualSense Edge Wireless
        Controller`) e o uhid, que é o caminho bom, não.

        A distinção humana fica — ela é o que separa este device do físico na
        lista do sistema, e é o que ela vê. E nada quebra: o discriminador
        real do daemon nunca foi o nome, é o `phys` (`hefesto-vpad`) e o
        `uniq` (o MAC forjado por jogador).
        """
        return f"DualSense Wireless Controller (Hefesto P{self.player})"

    @property
    def flavor(self) -> str:
        """Sempre "dualsense" — o único flavor que este backend faz (`for_flavor`)."""
        return "dualsense"

    @property
    def backend(self) -> str:
        """Sempre "uhid": o daemon/GUI usa isto para saber que o vpad é o DualSense
        HID real (Edge 0x0DF2) — e não o uinput. O botão de Launch Options decide
        a variante por aqui: "uhid" ⇒ IGNORE_DEVICES do físico é seguro (o vpad
        tem PID próprio); "uinput" no flavor dualsense = fallback degradado."""
        return "uhid"

    @property
    def mac(self) -> str:
        """O `uniq` que o vpad carimba no feature 0x09 e o kernel republica."""
        return _MACS_DOS_VPADS_VIVOS.vestido_por(self) or vpad_mac(self.identity, self.player)

    @property
    def ff_last_sent(self) -> tuple[int, int]:
        """Último par (weak, strong) entregue ao sink (rumble do jogo)."""
        return self._last_sent

    @property
    def ff_play_count(self) -> int:
        """Nº de pedidos de RUMBLE do jogo (diagnóstico: "o jogo está vibrando?")."""
        return self._rumble_count

    @property
    def ff_nao_nulo_count(self) -> int:
        """Nº de pedidos do jogo com motor NÃO-NULO (`weak` ou `strong` > 0)."""
        return self._rumble_nao_nulo_count

    @property
    def ff_maior_pedido(self) -> tuple[int, int]:
        """Maior par (weak, strong) que o jogo pediu na sessão."""
        return self._rumble_maior_pedido

    def registrar_rumble_no_fisico(self, weak: int, strong: int) -> None:
        """Anota o par que FOI ESCRITO no controle físico (MOTOR-QUE-NAO-SE-VE-01)."""
        self._rumble_no_fisico = (int(weak), int(strong))
        self._rumble_no_fisico_em = self.time_fn()

    @property
    def rumble_no_fisico(self) -> tuple[int, int] | None:
        """Último par (weak, strong) escrito no controle FÍSICO; None = nenhum."""
        return self._rumble_no_fisico

    @property
    def rumble_no_fisico_ha_s(self) -> float | None:
        """Há quantos segundos o último par foi escrito no físico; None = nunca."""
        quando = self._rumble_no_fisico_em
        if quando is None:
            return None
        return round(max(0.0, self.time_fn() - quando), 1)

    @property
    def ff_descartado_count(self) -> int:
        """Nº de reports com motor não-nulo que o gate de vibração DESCARTOU."""
        return self._rumble_descartado_count

    @property
    def ff_descartado_amostra(self) -> tuple[int, int, int, int, int] | None:
        """(flag0, flag1, flag2, weak, strong) do último descarte, ou None."""
        return self._rumble_descartado_amostra

    @property
    def ff_v2_count(self) -> int:
        """Nº de pedidos aceitos SÓ pelo bit v2 (`COMPATIBLE_VIBRATION2`)."""
        return self._rumble_v2_count

    @property
    def ff_parada_sdl_count(self) -> int:
        """Nº de paradas de vibração do SDL honradas (QUEM ESCREVEU-01)."""
        return self._rumble_parada_sdl_count

    @property
    def ff_report_estranho_count(self) -> int:
        """Nº de reports de output com report id diferente de 0x02."""
        return self._output_id_estranho_count

    @property
    def ff_report_estranho_amostra(self) -> tuple[int, int] | None:
        """(report_id, tamanho) do último report de id estranho, ou None."""
        return self._output_id_estranho_amostra

    @property
    def ff_ultimos_reports(self) -> list[tuple[float, int, int, int, int, int, str]]:
        """Os últimos reports de vibração, com a IDADE já resolvida em segundos.

        QUEM ESCREVEU-01. Cada item é
        ``(ha_s, flag0, flag1, flag2, weak, strong, ramo)``. A idade vem
        resolvida (e não o instante cru) pela mesma razão do `visto_ha_s`:
        quem lê é a janela, noutro processo, e ela não tem este relógio.

        Cópia a cada leitura, e não a lista viva: o anel é escrito na thread do
        poll loop e lido pelo `state_full`.
        """
        agora = self.time_fn()
        return [
            (round(max(0.0, agora - quando), 1), f0, f1, f2, w, s, ramo)
            for quando, f0, f1, f2, w, s, ramo in self._rumble_anel
        ]

    @property
    def output_count(self) -> int:
        """Nº total de reports de output do jogo (rumble + LED + gatilhos + mic)."""
        return self._output_count

    @property
    def trigger_replicas(self) -> int:
        """Nº de efeitos de gatilho do jogo REPLICADOS ao físico (REPLICA-03)."""
        return self._trigger_replicas

    @property
    def lightbar_replicas(self) -> int:
        """Nº de cores de lightbar do jogo REPLICADAS ao físico (REPLICA-03)."""
        return self._lightbar_replicas

    @property
    def player_led_replicas(self) -> int:
        """Nº de padrões de player-LED do jogo REPLICADOS ao físico (REPLICA-03)."""
        return self._player_led_replicas

    def _carimbar(self, categoria: str) -> None:
        """Marca AGORA como o último instante em que ``categoria`` aconteceu.

        PAINEL-DA-VERDADE-01. Reatribui o dicionário em vez de mutá-lo: as
        leituras vêm da thread do IPC e as escritas do pump, e uma
        reatribuição de nome é atômica sob o GIL — um `dict` mutado durante um
        `items()` levanta `RuntimeError` no meio do `state_full`. É barato:
        são seis chaves.
        """
        self._visto_em = {**self._visto_em, categoria: self.time_fn()}

    @property
    def visto_ha_s(self) -> dict[str, float]:
        """Há quantos segundos cada categoria aconteceu pela última vez."""
        agora = self.time_fn()
        return {
            categoria: round(max(0.0, agora - quando), 1)
            for categoria, quando in self._visto_em.items()
        }

    @property
    def audio_do_jogo_amostra(self) -> dict[str, int] | None:
        """Os VALORES da última escrita de áudio do jogo, ou ``None``."""
        amostra = self._audio_do_jogo_amostra
        if amostra is None:
            return None
        flag0, fone, alto_falante, microfone, rota = amostra
        return {
            "flag0": flag0,
            "fone": fone,
            "alto_falante": alto_falante,
            "microfone": microfone,
            "rota": rota,
        }

    @property
    def ff_supported(self) -> bool:
        """No caminho uhid o rumble sempre existe — é hidraw de verdade."""
        return True

    @property
    def game_open(self) -> bool:
        """True enquanto há sessão uhid ABERTA neste vpad (UHID_OPEN..CLOSE)."""
        return self._game_open

    def is_active(self) -> bool:
        return self._fd is not None

    @property
    def gadget_enumerando(self) -> bool:
        """O pad em USB de pé, à espera do `hidraw` do gadget (até `_GADGET_ENUMERA_S`).

        Nesse intervalo o `_started` ainda é False, e quem pergunta pela VIDA
        do pad (`gamepad.vpad_vivo`) tem de ouvir «vivo»: senão o co-op desmonta
        e renasce o jogador a cada tique, e o gadget nunca chega a enumerar.
        """
        gadget = self._gadget
        return bool(
            gadget is not None
            and not self._gadget_falhou
            and not self._gadget_caiu
            and gadget.hidraw is None
        )


    def _criar_o_device(self) -> bool:
        """O corpo do `start` (que mora no fim da classe): False = indisponível."""
        if self._fd is not None:
            return True
        if self.blueprint is None:
            logger.warning("uhid_sem_blueprint", player=self.player)
            return False
        try:
            features = self._features_com_mac_proprio()
            create_event = self._create2_event(self.blueprint["descriptor"])
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("uhid_blueprint_invalido", err=str(exc), player=self.player)
            return False
        if _o_pad_em_usb(self, features):
            return True

        try:
            fd = os.open(UHID_NODE, os.O_RDWR)
        except OSError as exc:
            level = "uhid_sem_permissao" if exc.errno == errno.EACCES else "uhid_indisponivel"
            logger.warning(level, err=str(exc), node=UHID_NODE)
            return False

        try:
            os.write(fd, create_event)
        except OSError as exc:
            logger.warning("uhid_create_failed", err=str(exc), player=self.player)
            os.close(fd)
            return False
        os.set_blocking(fd, False)
        with self._lock:
            self._features = features
            self._fd = fd
        self._iniciar_o_fio_do_uhid(fd)
        logger.info("uhid_device_created", name=self.name, mac=self.mac,
                    player=self.player)
        return True

    def _features_com_mac_proprio(self) -> dict[int, bytes]:
        """Copia os features do blueprint carimbando o MAC do jogador no 0x09."""
        assert self.blueprint is not None
        features = dict(self.blueprint["features"])
        report09 = bytearray(features[0x09])
        if len(report09) < 7:
            raise ValueError(f"feature 0x09 curto demais: {len(report09)} bytes")
        report09[1:7] = _mac_to_report_bytes(self.mac)
        assert len(report09) == len(features[0x09])
        features[0x09] = bytes(report09)
        calib = self.calibration_0x05
        if calib is not None:
            if (
                len(calib) == _CALIBRATION_FEATURE_SIZE
                and calib[0] == _CALIBRATION_FEATURE_ID
            ):
                features[_CALIBRATION_FEATURE_ID] = bytes(calib)
                logger.info("uhid_calibration_por_unidade", player=self.player)
            else:
                logger.warning(
                    "uhid_calibration_invalida_usando_canonica",
                    tamanho=len(calib),
                    player=self.player,
                )
        return features

    def _destruir_o_device(self) -> None:
        self._parar_o_fio_do_uhid()
        with self._a_trava_da_saida(), self._lock:
            fd = self._fd
            if fd is None:
                return
            self._fd = None
            self._entregar_o_pendente()
            self._silence_rumble()
            self._end_game_session()
            if not _soltar_o_gadget(self):
                with contextlib.suppress(OSError):
                    os.write(fd, struct.pack("<I", UHID_DESTROY))
                with contextlib.suppress(OSError):
                    os.close(fd)
            self._features = {}
            self._last_sent = (0, 0)
            self._output_count = 0
            self._rumble_count = 0
            self._rumble_nao_nulo_count = 0
            self._rumble_maior_pedido = (0, 0)
            self._rumble_no_fisico = None
            self._rumble_no_fisico_em = None
            self._rumble_descartado_count = 0
            self._rumble_descartado_amostra = None
            self._rumble_v2_count = 0
            self._rumble_parada_sdl_count = 0
            self._output_id_estranho_count = 0
            self._output_id_estranho_amostra = None
            self._rumble_anel = []
            self._started = False
            self._game_open = False
            self._bound_at = None
            self._trigger_replicas = 0
            self._lightbar_replicas = 0
            self._player_led_replicas = 0
            self._visto_em = {}
            self._audio_do_jogo_amostra = None
            self._axes = _AXES_NEUTRAL
            self._buttons = frozenset()
            self._pendentes = frozenset()
            self._last_body = None
            self._seq = 0
            self._motion_window = _MOTION_NEUTRAL
            self._motion_streaming = False
            self._motion_count = 0
            self._status_byte = _STATUS_DESCONHECIDO
            self._battery_forward_count = 0
            self._mic_button = False
            self._mic_button_count = 0
            self._esquecer_o_microfone_do_jogo()

    def _silence_rumble(self) -> None:
        """Zera os motores do controle físico se o jogo os deixou ligados.

        O vpad some e ninguém mais mandaria o stop — sem isto o DualSense fica
        vibrando para sempre (mesma proteção do UinputGamepad.stop).
        """
        self._rumble_visto_em = None
        if self._last_sent == (0, 0) or self.rumble_sink is None:
            return
        if self._no_fio_do_uhid():
            self._rumble_a_entregar = (0, 0)
        else:
            with contextlib.suppress(Exception):
                self.rumble_sink(0, 0)
        self._last_sent = (0, 0)

    def _create2_event(self, descriptor: bytes) -> bytes:
        event = struct.pack("<I", UHID_CREATE2)
        event += self.name.encode("utf-8").ljust(128, b"\0")[:128]
        event += VPAD_HID_PHYS.encode("ascii").ljust(64, b"\0")[:64]
        event += self.mac.encode("ascii").ljust(64, b"\0")[:64]
        event += struct.pack("<HH", len(descriptor), BUS_USB)
        event += struct.pack("<IIII", DUALSENSE_VENDOR, self.product, 0x0100, 0)
        event += descriptor.ljust(HID_MAX_DESCRIPTOR_SIZE, b"\0")[:HID_MAX_DESCRIPTOR_SIZE]
        return event


    def forward_analog(
        self,
        *,
        lx: int,
        ly: int,
        rx: int,
        ry: int,
        l2: int,
        r2: int,
    ) -> None:
        """Guarda os analógicos do controle físico e emite o report (se mudou)."""
        if self._fd is None:
            return
        self._axes = (lx & 0xFF, ly & 0xFF, rx & 0xFF, ry & 0xFF, l2 & 0xFF, r2 & 0xFF)
        self._emit_if_changed()

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        """Idem para os botões (vocabulário do `EvdevReader.BUTTON_MAP` + d-pad).

        Nomes desconhecidos são ignorados: o report do DualSense não tem onde
        pôr o que não existe no controle real.
        """
        if self._fd is None:
            return
        with self._lock:
            novos = frozenset(pressed) - self._buttons
            self._pendentes = self._pendentes | novos
            self._buttons = frozenset(pressed)
            self._emit_if_changed()

    def forward_motion(self, window: bytes) -> None:
        """Espelha a janela de MOTION do físico (25 B = payload[15:40]) e emite."""
        if len(window) != _MOTION_WINDOW_LEN:
            if not self._motion_invalid_logged:
                self._motion_invalid_logged = True
                logger.warning(
                    "uhid_motion_window_invalida",
                    tamanho=len(window),
                    player=self.player,
                )
            return
        if self._fd is None:
            return
        with self._lock:
            self._motion_window = bytes(window)
            if self._emit_if_changed(from_reader=True):
                self._motion_count += 1

    def forward_touchpad_click(self, pressed: bool) -> None:
        """Espelha o CLIQUE do touchpad do físico no report do vpad."""
        if self._fd is None:
            return
        with self._lock:
            alvo = bool(pressed)
            if alvo == self._touchpad_click:
                return
            self._touchpad_click = alvo
            if self._emit_if_changed(from_reader=True) and alvo:
                self._touchpad_click_count += 1
                self._carimbar(ATIVIDADE_TOUCHPAD_CLICK)

    def forward_mic_button(self, pressed: bool) -> None:
        """Espelha o BOTÃO do microfone do físico no report do vpad.

        O-BOTAO-E-A-LUZ-DO-MICROFONE-NO-JOGO-01 — irmão exato do
        `forward_touchpad_click`: mesmo chamador (o `PhysicalReportReader`),
        mesmo byte (`buttons[2]`, bit 0x04 = `DS_BUTTONS2_MIC_MUTE`), por
        BORDA e na hora. O ato do mudo continua do Hefesto; isto só deixa o
        jogo ver o aperto, como vê qualquer DualSense no PC.
        """
        if self._fd is None:
            return
        with self._lock:
            alvo = bool(pressed)
            if alvo == self._mic_button:
                return
            self._mic_button = alvo
            if self._emit_if_changed(from_reader=True) and alvo:
                self._mic_button_count += 1

    @property
    def mic_led_do_jogo(self) -> int:
        """Nº de pedidos de luz do microfone que o jogo fez e chegaram ao controle."""
        return self._mic_led_do_jogo

    @property
    def mic_led_do_jogo_amostra(self) -> int | None:
        """O `common[8]` do último pedido de luz do jogo; None = nenhum nesta sessão."""
        return self._mic_led_do_jogo_amostra

    @property
    def mic_button(self) -> bool:
        """True enquanto o botão do microfone espelhado do físico está apertado."""
        return self._mic_button

    @property
    def mic_button_count(self) -> int:
        """Nº de APERTOS do botão do microfone que chegaram ao jogo."""
        return self._mic_button_count

    @property
    def touchpad_click(self) -> bool:
        """True enquanto o clique espelhado do físico está pressionado."""
        return self._touchpad_click

    @property
    def touchpad_click_count(self) -> int:
        """Nº de PRESSIONADAS do touchpad entregues ao jogo (TOUCH-CLICK-01)."""
        return self._touchpad_click_count

    def set_motion_streaming(self, on: bool) -> None:
        """Liga/desliga o modo "o reader é o relógio" (GYRO-01)."""
        with self._lock:
            alvo = bool(on)
            if alvo == self._motion_streaming:
                return
            self._motion_streaming = alvo
            logger.info("uhid_motion_streaming", on=alvo, player=self.player)
            if not alvo:
                self._motion_window = _MOTION_NEUTRAL
                self._touchpad_click = False
                self._mic_button = False
                self._status1_byte = _STATUS1_NEUTRO
                self._status_byte = _STATUS_DESCONHECIDO
                self._emit_if_changed()

    @property
    def motion_streaming(self) -> bool:
        """True enquanto um `PhysicalReportReader` dita o ritmo da emissão."""
        return self._motion_streaming

    @property
    def motion_forward_count(self) -> int:
        """Nº de janelas de motion emitidas (telemetria GYRO-03)."""
        return self._motion_count

    @property
    def jack_forward_count(self) -> int:
        """Nº de mudanças do byte 53 que SAÍRAM no report (JACK-QUE-NAO-LIGOU-01)."""
        return self._jack_forward_count

    @property
    def battery_forward_count(self) -> int:
        """Nº de mudanças do byte 52 que SAÍRAM no report (BATERIA-QUE-NAO-CHEGOU-01)."""
        return self._battery_forward_count

    @property
    def bateria_anunciada(self) -> tuple[int | None, bool]:
        """``(percentual, carregando)`` que o vpad DIZ AO JOGO; None = não sei.

        BATERIA-QUE-NAO-CHEGOU-01. Não é leitura do controle físico (essa é o
        `battery_pct` da aba Status): é o que o gamepad VIRTUAL declara no byte
        52, decodificado pela conta do kernel — a mesma que o `hid-playstation`
        vai aplicar do outro lado. A diferença é a pergunta inteira: com o
        `forward_battery` órfão, o físico podia estar em 95% e o vpad seguia
        anunciando `_STATUS_DESCONHECIDO` para sempre.
        """
        byte = self._status_byte
        if byte == _STATUS_DESCONHECIDO:
            return (None, False)
        estado = (byte & 0xF0) >> _CHARGING_SHIFT
        return (min((byte & 0x0F) * 10 + 5, 100), estado == 0x1)

    @property
    def jack(self) -> dict[str, bool]:
        """O que o vpad DIZ AO JOGO sobre fone/microfone do controle."""
        byte = self._status1_byte
        return {
            "fone": bool(byte & _STATUS1_HP_DETECT),
            "microfone": bool(byte & _STATUS1_MIC_DETECT),
            "mudo": bool(byte & _STATUS1_MIC_MUTE),
        }

    def _emit_if_changed(self, *, from_reader: bool = False) -> bool:
        """Emite o report 0x01 só quando o payload mudou."""
        with self._lock:
            if self._motion_streaming and not from_reader:
                return False
            body = self._encode_body()
            chave = bytes(body)
            if chave == self._last_body:
                return False
            self._last_body = chave
            self._seq = (self._seq + 1) & 0xFF
            body[_SEQ_OFFSET] = self._seq
            if not self.send_report(bytes([_INPUT_REPORT_USB]) + bytes(body)):
                return False
            self._pendentes = frozenset()
            self._abrir_a_janela_do_eco(body)
            return True

    def _encode_body(self) -> bytearray:
        """Payload do report 0x01 a partir do estado, com o seq ZERADO."""
        body = bytearray(_INPUT_PAYLOAD_SIZE)
        body[_MOTION_WINDOW] = self._motion_window
        body[_STATUS_OFFSET] = self._status_byte
        body[_STATUS1_OFFSET] = self._status1_byte
        body[0:6] = bytes(self._axes)
        pressed = self._buttons | self._pendentes
        body[_BUTTONS0_OFFSET] = self._dpad_hat(pressed) | _bitmask(pressed, _BUTTONS0_BITS)
        body[_BUTTONS1_OFFSET] = _bitmask(pressed, _BUTTONS1_BITS)
        buttons2 = _bitmask(pressed, _BUTTONS2_BITS)
        if self._touchpad_click or (pressed & _TOUCHPAD_BUTTONS):
            buttons2 |= _TOUCHPAD_BIT
        if self._mic_button:
            buttons2 |= _BUTTONS2_BITS["mic_btn"]
        body[_BUTTONS2_OFFSET] = buttons2
        return body

    def forward_jack(self, status1: int) -> None:
        """Espelha o byte 53 do físico (fone / microfone / mudo) no vpad."""
        with self._lock:
            novo = int(status1) & _STATUS1_BITS_CONHECIDOS
            if novo == self._status1_byte:
                return
            self._status1_byte = novo
            if self._emit_if_changed(from_reader=True):
                self._jack_forward_count += 1
                self._carimbar(ATIVIDADE_JACK)

    def forward_battery(
        self,
        percent: int | None,
        *,
        charging: bool = False,
        from_reader: bool = False,
    ) -> None:
        """Espelha a bateria do controle físico no vpad (opcional)."""
        if percent is None:
            novo = _STATUS_DESCONHECIDO
        else:
            estado = 0x1 if charging else 0x0
            novo = (estado << _CHARGING_SHIFT) | _percent_para_nibble(percent)
        with self._lock:
            if novo == self._status_byte:
                return
            self._status_byte = novo
            if self._emit_if_changed(from_reader=from_reader):
                self._battery_forward_count += 1

    @staticmethod
    def _dpad_hat(pressed: frozenset[str]) -> int:
        """D-pad → HAT (0-7, 8=neutro)."""
        x = -1 if "dpad_left" in pressed else (1 if "dpad_right" in pressed else 0)
        y = -1 if "dpad_up" in pressed else (1 if "dpad_down" in pressed else 0)
        return _HAT_BY_VECTOR[(x, y)]

    def wait_for_bind(self, timeout_s: float = 2.0) -> bool:
        """Bloqueia até o `hid_playstation` REGISTRAR o controle, ou estourar."""
        if self._fd is None:
            return False
        if self._gadget is not None:
            return True  # a enumeração pelo vhci leva segundos: o fio a vigia
        deadline = self.time_fn() + timeout_s
        while not self._started:
            self.pump_ff()
            if self._started:
                break
            if self.time_fn() >= deadline:
                logger.warning("uhid_bind_timeout", player=self.player,
                               timeout_s=timeout_s)
                return False
            self.sleep_fn(_BIND_POLL_INTERVAL_S)

        settle_deadline = self.time_fn() + _BIND_SETTLE_S
        while self.time_fn() < settle_deadline:
            self.pump_ff()
            if not self._started:
                logger.warning("uhid_probe_recusou", player=self.player, mac=self.mac)
                return False
            self.sleep_fn(_BIND_POLL_INTERVAL_S)
        return True

    @property
    def is_bound(self) -> bool:
        """True quando o driver fez bind no device (UHID_START recebido)."""
        return self._started

    def send_report(self, report: bytes) -> bool:
        """Entrega um input report HID ao kernel (UHID_INPUT2)."""
        if self._gadget is not None:
            return _enviar_pelo_gadget(self, report)
        if len(report) > HID_MAX_DESCRIPTOR_SIZE:
            logger.warning("uhid_input_grande_demais", tamanho=len(report))
            return False
        # e zera o resto, então mandar o report cru poupa ~4 KB de copy_from_user
        event = struct.pack("<IH", UHID_INPUT2, len(report)) + report
        with self._lock:
            fd = self._fd
            if fd is None:
                return False
            try:
                os.write(fd, event)
                return True
            except OSError as exc:
                logger.warning("uhid_input_failed", err=str(exc), player=self.player)
                return False


    def pump_ff(self) -> None:
        """Drena os eventos do uhid; entrega o rumble do jogo ao `rumble_sink`."""
        if self._gadget is not None:
            return _bombear_o_gadget(self)
        fd = self._fd
        if fd is None:
            return
        with self._a_trava_da_saida():
            self._entregar_o_pendente()
            self._flush_replicas()
            self._expirar_rumble_preso()
            fio = self._fio_do_uhid
            if fio is not None and fio.is_alive():
                return
            for _ in range(_MAX_EVENTS_PER_PUMP):
                try:
                    data = os.read(fd, UHID_EVENT_SIZE)
                except BlockingIOError:
                    return
                except OSError as exc:
                    if exc.errno != errno.EBADF:
                        logger.warning("uhid_read_failed", err=str(exc), player=self.player)
                    return
                if len(data) < 4:
                    return
                self._handle_event(data)

    def _handle_event(self, data: bytes) -> None:
        event_type = struct.unpack("<I", data[:4])[0]
        if event_type == UHID_START:
            self._started = True
            self._bound_at = self.time_fn()
            with self._lock:
                self._mic_bit_que_saiu = False
                self._as_janelas_do_eco().clear()
            logger.info("uhid_bind_ok", player=self.player, name=self.name)
        elif event_type == UHID_OPEN:
            self._game_open = True
        elif event_type in (UHID_STOP, UHID_CLOSE):
            self._started = self._started and event_type == UHID_CLOSE
            self._game_open = False
            self._silence_rumble()
            self._end_game_session()
        elif event_type == UHID_OUTPUT:
            self._handle_output(data)
        elif event_type == UHID_GET_REPORT:
            self._reply_get_report(data)
        elif event_type == UHID_SET_REPORT:
            self._reply_set_report(data)

    def _handle_output(self, data: bytes) -> None:
        """UHID_OUTPUT = o jogo escreveu no hidraw do vpad (rumble/LED/gatilhos)."""
        payload_size = struct.unpack("<H", data[4 + HID_MAX_DESCRIPTOR_SIZE:
                                                6 + HID_MAX_DESCRIPTOR_SIZE])[0]
        report = data[4:4 + min(payload_size, HID_MAX_DESCRIPTOR_SIZE)]
        if len(report) < 2 or report[0] != _OUTPUT_REPORT_USB:
            if len(report) >= 1:
                self._output_id_estranho_count += 1
                self._output_id_estranho_amostra = (report[0], len(report))
            return
        eco = self._e_eco_do_driver(report[1:])
        if eco and _e_eco_puro(report[1:]):
            return
        self._output_count += 1
        self._carimbar(ATIVIDADE_OUTPUT)
        body = report[1:]
        if (
            len(body) > rep.COMMON_AUDIO_PATH
            and body[_VALID_FLAG0_OFFSET] & _AUDIO_FLAGS_DO_JOGO
            and any(body[rep.COMMON_HEADPHONE_VOLUME : rep.COMMON_AUDIO_PATH + 1])
            and self._replicating()
        ):
            self._carimbar(ATIVIDADE_AUDIO_DO_JOGO)
            self._audio_do_jogo_amostra = (
                body[_VALID_FLAG0_OFFSET] & _AUDIO_FLAGS_DO_JOGO,
                body[rep.COMMON_HEADPHONE_VOLUME],
                body[rep.COMMON_SPEAKER_VOLUME],
                body[rep.COMMON_MIC_VOLUME],
                body[rep.COMMON_AUDIO_PATH],
            )
        if len(body) > _VALID_FLAG1_OFFSET:
            self._replicate_from_output(body)
            if not eco:
                self._o_jogo_pede_o_microfone(body)
        if len(body) <= _RUMBLE_STRONG_OFFSET:
            return
        if _e_a_parada_do_sdl(body):
            self._carimbar(ATIVIDADE_RUMBLE)
            self._rumble_visto_em = None
            self._rumble_parada_sdl_count += 1
            self._anotar_no_anel(body, 0, 0, RAMO_PARADA_SDL)
            if self._last_sent != (0, 0):
                self._last_sent = (0, 0)
                self._emit_rumble(0, 0)
                logger.info("uhid_parada_do_sdl_honrada", player=self.player)
            return
        weak = body[_RUMBLE_WEAK_OFFSET]
        strong = body[_RUMBLE_STRONG_OFFSET]
        if not _fala_de_vibracao(body):
            if weak or strong:
                self._rumble_descartado_count += 1
                self._rumble_descartado_amostra = (
                    body[_VALID_FLAG0_OFFSET],
                    body[_VALID_FLAG1_OFFSET],
                    body[rep.COMMON_VALID_FLAG2]
                    if len(body) > rep.COMMON_VALID_FLAG2
                    else 0,
                    weak,
                    strong,
                )
                self._anotar_no_anel(body, weak, strong, RAMO_DESCARTADO)
            return
        self._rumble_count += 1
        e_v2 = bool(
            len(body) > rep.COMMON_VALID_FLAG2
            and body[rep.COMMON_VALID_FLAG2] & rep.VALID_FLAG2_COMPATIBLE_VIBRATION2
            and not body[_VALID_FLAG0_OFFSET] & _VIBRATION_FLAGS
        )
        if e_v2:
            self._rumble_v2_count += 1
        self._anotar_no_anel(body, weak, strong, RAMO_V2 if e_v2 else RAMO_V1)
        if weak or strong:
            self._rumble_nao_nulo_count += 1
            self._rumble_maior_pedido = pedido_mais_forte(
                self._rumble_maior_pedido, (weak, strong)
            )
        # mesmo sem haver o que reenviar ao hardware.
        self._rumble_visto_em = self.time_fn() if (weak or strong) else None
        self._carimbar(ATIVIDADE_RUMBLE)
        if (weak, strong) == self._last_sent:
            return
        self._last_sent = (weak, strong)
        self._emit_rumble(weak, strong)

    def _anotar_no_anel(
        self, body: bytes, weak: int, strong: int, ramo: str
    ) -> None:
        """Guarda os BYTES do report de vibração no anel (QUEM ESCREVEU-01)."""
        flag2 = (
            body[rep.COMMON_VALID_FLAG2] if len(body) > rep.COMMON_VALID_FLAG2 else 0
        )
        self._rumble_anel.append(
            (
                self.time_fn(),
                body[_VALID_FLAG0_OFFSET],
                body[_VALID_FLAG1_OFFSET] if len(body) > _VALID_FLAG1_OFFSET else 0,
                flag2,
                int(weak),
                int(strong),
                ramo,
            )
        )
        if len(self._rumble_anel) > _ANEL_DE_VIBRACAO_MAX:
            del self._rumble_anel[:-_ANEL_DE_VIBRACAO_MAX]

    def _expirar_rumble_preso(self) -> None:
        """Zera um rumble do jogo que ficou pendurado além do teto de silêncio."""
        if self._last_sent == (0, 0) or self._rumble_visto_em is None:
            return
        silencio = self.time_fn() - self._rumble_visto_em
        if silencio < _RUMBLE_STALE_SEC:
            return
        logger.warning(
            "uhid_rumble_preso_expirado",
            player=self.player,
            ultimo=self._last_sent,
            teto_s=_RUMBLE_STALE_SEC,
            silencio_s=round(silencio, 2),
        )
        self._rumble_visto_em = None
        self._last_sent = (0, 0)
        self._emit_rumble(0, 0)

    def _emit_rumble(self, weak: int, strong: int) -> None:
        if self._no_fio_do_uhid():
            self._rumble_a_entregar = (weak, strong)
            return
        if self.rumble_sink is None:
            return
        try:
            self.rumble_sink(weak, strong)
        except Exception as exc:
            logger.warning("uhid_rumble_sink_failed", err=str(exc), player=self.player)


    def _replicating(self) -> bool:
        """True quando a replicação está armada: sessão aberta + graça vencida."""
        if not self._game_open:
            return False
        bound_at = self._bound_at
        if bound_at is None:
            return False
        return (self.time_fn() - bound_at) >= _GAME_REPLICA_GRACE_S

    def _replicate_from_output(self, body: bytes) -> None:
        """Enfileira as categorias presentes no report 0x02 (bits de valid_flag)."""
        if not self._replicating():
            return
        flag0 = body[_VALID_FLAG0_OFFSET]
        flag1 = body[_VALID_FLAG1_OFFSET]
        fim_r = _TRIGGER_R_BLOCK_OFFSET + _TRIGGER_BLOCK_LEN
        if flag0 & _TRIGGER_R_EFFECT_ENABLE and len(body) >= fim_r:
            self._queue_replica(
                "trigger_right", bytes(body[_TRIGGER_R_BLOCK_OFFSET:fim_r])
            )
        fim_l = _TRIGGER_L_BLOCK_OFFSET + _TRIGGER_BLOCK_LEN
        if flag0 & _TRIGGER_L_EFFECT_ENABLE and len(body) >= fim_l:
            self._queue_replica(
                "trigger_left", bytes(body[_TRIGGER_L_BLOCK_OFFSET:fim_l])
            )
        if flag1 & _PLAYER_INDICATOR_CONTROL_ENABLE and len(body) > _PLAYER_LEDS_OFFSET:
            mask = body[_PLAYER_LEDS_OFFSET] & _PLAYER_LEDS_MASK
            self._queue_replica(
                "player_leds", tuple(bool(mask & (1 << i)) for i in range(5))
            )
        if flag1 & _LIGHTBAR_CONTROL_ENABLE and len(body) >= _LIGHTBAR_RGB_OFFSET + 3:
            self._queue_replica(
                "lightbar",
                (
                    body[_LIGHTBAR_RGB_OFFSET],
                    body[_LIGHTBAR_RGB_OFFSET + 1],
                    body[_LIGHTBAR_RGB_OFFSET + 2],
                ),
            )
        if not self._no_fio_do_uhid():
            self._flush_replicas()

    def _queue_replica(self, categoria: str, valor: Any) -> None:
        """Dedup por valor: igual ao último ENTREGUE (e sem pendência) = drop."""
        if valor == self._replica_last.get(categoria) and (
            categoria not in self._replica_pending
        ):
            return
        self._replica_pending[categoria] = valor

    def _flush_replicas(self) -> None:
        """Entrega as pendências respeitando o rate-limit por categoria."""
        if not self._replica_pending:
            return
        now = self.time_fn()
        for categoria in list(self._replica_pending):
            valor = self._replica_pending[categoria]
            if valor == self._replica_last.get(categoria):
                del self._replica_pending[categoria]
                continue
            ts = self._replica_ts.get(categoria)
            if ts is not None and (now - ts) < _REPLICA_MIN_INTERVAL_S:
                continue
            del self._replica_pending[categoria]
            primeira = categoria not in self._replica_ts
            self._replica_ts[categoria] = now
            self._replica_last[categoria] = valor
            self._forward_replica(categoria, valor, primeira=primeira)

    def _forward_replica(self, categoria: str, valor: Any, *, primeira: bool) -> None:
        """Entrega UMA réplica ao sink da categoria (contadores + telemetria)."""
        if primeira:
            logger.info(
                "uhid_replica_ativa", categoria=categoria, player=self.player
            )
        try:
            if categoria == "trigger_right":
                if self.trigger_sink is None:
                    return
                self._carimbar(_ATIVIDADE_POR_CATEGORIA[categoria])
                self._trigger_replicas += 1
                self._game_dirty = True
                self.trigger_sink("right", valor)
            elif categoria == "trigger_left":
                if self.trigger_sink is None:
                    return
                self._carimbar(_ATIVIDADE_POR_CATEGORIA[categoria])
                self._trigger_replicas += 1
                self._game_dirty = True
                self.trigger_sink("left", valor)
            elif categoria == "lightbar":
                if self.lightbar_sink is None:
                    return
                self._carimbar(_ATIVIDADE_POR_CATEGORIA[categoria])
                self._lightbar_replicas += 1
                self._game_dirty = True
                self.lightbar_sink(valor[0], valor[1], valor[2])
            elif categoria == "player_leds":
                if self.player_led_sink is None:
                    return
                self._carimbar(_ATIVIDADE_POR_CATEGORIA[categoria])
                self._player_led_replicas += 1
                self._game_dirty = True
                self.player_led_sink(valor)
            elif categoria in (_REPLICA_MIC_LED, _REPLICA_MIC_MUDO):
                self._entregar_o_microfone(categoria, valor)
        except Exception as exc:
            logger.warning(
                "uhid_replica_sink_failed",
                categoria=categoria,
                err=str(exc),
                player=self.player,
            )

    def _end_game_session(self) -> None:
        """Fim da sessão (CLOSE/STOP/stop): devolve a posse do output ao perfil."""
        self._replica_pending.clear()
        self._replica_last.clear()
        self._replica_ts.clear()
        self._soltar_a_luz_do_microfone()
        if not self._game_dirty:
            return
        self._game_dirty = False
        logger.info("uhid_game_session_end", player=self.player)
        if self.session_end_sink is None:
            return
        if self._no_fio_do_uhid():
            self._fim_de_sessao_a_entregar = True
            return
        try:
            self.session_end_sink()
        except Exception as exc:
            logger.warning(
                "uhid_session_end_sink_failed", err=str(exc), player=self.player
            )

    def _reply_get_report(self, data: bytes) -> None:
        """struct uhid_get_report_req { __u32 id; __u8 rnum; __u8 rtype; }"""
        if self._fd is None:
            return
        request_id = struct.unpack("<I", data[4:8])[0]
        report_num = data[8]
        payload = self._features.get(report_num, b"")
        reply = struct.pack("<IIH", UHID_GET_REPORT_REPLY, request_id, 0)
        reply += struct.pack("<H", len(payload))
        reply += payload.ljust(HID_MAX_DESCRIPTOR_SIZE, b"\0")[:HID_MAX_DESCRIPTOR_SIZE]
        with contextlib.suppress(OSError):
            os.write(self._fd, reply)

    def _reply_set_report(self, data: bytes) -> None:
        if self._fd is None:
            return
        request_id = struct.unpack("<I", data[4:8])[0]
        with contextlib.suppress(OSError):
            os.write(self._fd,
                     struct.pack("<IIH", UHID_SET_REPORT_REPLY, request_id, 0))


    def start(self) -> bool:
        """Cria o device HID vestindo um MAC que nenhum outro vpad vivo veste."""
        if self._fd is not None:
            return True
        self._as_janelas_do_eco().clear()
        self._mic_bit_que_saiu = False
        _MACS_DOS_VPADS_VIVOS.vestir(self)
        if self._criar_o_device():
            return True
        _MACS_DOS_VPADS_VIVOS.despir(self)
        return False

    def stop(self) -> None:
        """Destrói o device e só DEPOIS devolve o MAC."""
        self._destruir_o_device()
        _MACS_DOS_VPADS_VIVOS.despir(self)


    def _a_trava_da_saida(self) -> threading.RLock:
        """A trava da saída, garantida pelo dono: nasce no `__init__` e, se não nasceu, aqui."""
        trava: threading.RLock | None = self.__dict__.get("_trava_da_saida")
        if trava is None:
            trava = self.__dict__.setdefault("_trava_da_saida", threading.RLock())
        assert trava is not None
        return trava

    def _no_fio_do_uhid(self) -> bool:
        """Esta chamada vem do fio do uhid? (Lá, a entrega ao físico fica anotada.)"""
        fio = self._fio_do_uhid
        return fio is not None and threading.current_thread() is fio

    def _iniciar_o_fio_do_uhid(self, fd: int) -> None:
        """Sobe o fio que atende o fd do uhid por prontidão (só com fd de verdade)."""
        try:
            os.fstat(fd)
        except (OSError, TypeError, ValueError):
            return
        try:
            leitura, escrita = os.pipe()
        except OSError as exc:
            logger.warning("uhid_fio_sem_despertador", err=str(exc), player=self.player)
            return
        os.set_blocking(leitura, False)
        os.set_blocking(escrita, False)
        self._despertador = (leitura, escrita)
        pare = threading.Event()
        self._pare_o_fio = pare
        fio = threading.Thread(
            target=self._atender_o_uhid if self._gadget is None else _fio_do_gadget(self),
            args=(fd, leitura, pare),
            name=f"hefesto-uhid-p{self.player}",
            daemon=True,
        )
        self._fio_do_uhid = fio
        try:
            fio.start()
        except RuntimeError as exc:
            logger.warning("uhid_fio_nao_nasceu", err=str(exc), player=self.player)
            self._fio_do_uhid = None
            self.__dict__.pop("_despertador", None)
            for ponta in (leitura, escrita):
                with contextlib.suppress(OSError):
                    os.close(ponta)

    def _atender_o_uhid(self, fd: int, despertador: int, pare: threading.Event) -> None:
        """O laço do fio: acorda quando o fd tem evento e o atende na hora."""
        while not pare.is_set():
            try:
                prontos = prontos_para_ler([fd, despertador], _UHID_FIO_ACORDA_S)
            except (OSError, ValueError):
                return
            if pare.is_set():
                return
            if fd not in prontos:
                continue
            while not pare.is_set():
                try:
                    data = os.read(fd, UHID_EVENT_SIZE)
                except BlockingIOError:
                    break
                except OSError as exc:
                    if exc.errno != errno.EBADF:
                        logger.warning("uhid_read_failed", err=str(exc), player=self.player)
                    return
                if len(data) < 4:
                    return
                with self._a_trava_da_saida():
                    try:
                        self._handle_event(data)
                    except Exception as exc:
                        logger.warning("uhid_evento_falhou", err=str(exc),
                                       player=self.player)

    def _parar_o_fio_do_uhid(self) -> None:
        """Acorda o fio, espera ele sair e fecha o despertador. Idempotente."""
        fio = self._fio_do_uhid
        if fio is None:
            return
        if self._pare_o_fio is not None:
            self._pare_o_fio.set()
        despertador: tuple[int, int] | None = self.__dict__.pop("_despertador", None)
        if despertador is not None:
            with contextlib.suppress(OSError):
                os.write(despertador[1], b"x")
        if fio is not threading.current_thread():
            fio.join(timeout=_UHID_FIO_ACORDA_S + 0.5)
            if fio.is_alive():
                logger.warning("uhid_fio_nao_saiu", player=self.player)
        if self._fio_do_uhid is fio:
            self._fio_do_uhid = None
        if despertador is not None:
            for ponta in despertador:
                with contextlib.suppress(OSError):
                    os.close(ponta)

    def _entregar_o_pendente(self) -> None:
        """Entrega ao controle físico o que o fio atendeu: o fim da sessão e a vibração."""
        if self._fim_de_sessao_a_entregar:
            self._fim_de_sessao_a_entregar = False
            if self.session_end_sink is not None:
                try:
                    self.session_end_sink()
                except Exception as exc:
                    logger.warning(
                        "uhid_session_end_sink_failed", err=str(exc), player=self.player
                    )
        if self._mic_solta_a_entregar:
            self._mic_solta_a_entregar = False
            self._dizer_que_o_jogo_soltou_a_luz()
        par = self._rumble_a_entregar
        if par is not None:
            self._rumble_a_entregar = None
            self._emit_rumble(*par)

    # `hid-playstation` que o adotou faz o que faria num DualSense: na borda de

    @property
    def mic_mudo_do_jogo(self) -> int:
        """Nº de pedidos de mudo do jogo que chegaram ao controle."""
        return self._mic_mudo_do_jogo

    @property
    def mic_mudo_do_jogo_amostra(self) -> bool | None:
        """O mudo do último pedido do jogo; None = nenhum nesta sessão."""
        return self._mic_mudo_do_jogo_amostra

    @property
    def mic_do_jogo_retido(self) -> int:
        """Nº de pedidos do microfone retidos (sem jogo: autoridade `daemon`)."""
        return self._mic_do_jogo_retido

    @property
    def mic_eco_do_driver(self) -> int:
        """Nº de 0x02 do driver deste pad depois de uma borda do botão (não contam)."""
        return self._mic_eco_do_driver

    def _abrir_a_janela_do_eco(self, body: bytes | bytearray) -> None:
        """Um report SAIU: se ele traz a subida do botão, o driver vai ecoar.

        Roda sob `_lock`, na thread de quem emitiu (o leitor do físico ou o
        laço). Só ANEXA ao `deque` (atômico no CPython): tomar a trava da
        saída aqui inverteria a ordem das travas do `_destruir_o_device`.
        """
        bit = bool(body[_BUTTONS2_OFFSET] & _BUTTONS2_BITS["mic_btn"])
        if bit and not self._mic_bit_que_saiu:
            self._as_janelas_do_eco().append(self.time_fn())
        self._mic_bit_que_saiu = bit

    def _e_eco_do_driver(self, body: bytes) -> bool:
        """O report tem a assinatura do eco e há uma janela aberta? Consome UMA."""
        if not _tem_a_assinatura_do_eco(body):
            return False
        with self._lock:
            janelas = self._as_janelas_do_eco()
            agora = self.time_fn()
            while janelas and agora - janelas[0] > ECO_DO_DRIVER_S:
                janelas.popleft()
            if not janelas:
                return False
            janelas.popleft()
            self._mic_eco_do_driver += 1
            return True

    def _as_janelas_do_eco(self) -> collections.deque[float]:
        """As janelas do eco, garantidas pelo dono (o molde de `_a_trava_da_saida`).

        As bancadas da suíte que montam o pad sem o `__init__` do dataclass não
        têm o campo; o `setdefault` é atômico sob o GIL.
        """
        janelas: collections.deque[float] | None = self.__dict__.get("_janelas_do_eco")
        if janelas is None:
            janelas = self.__dict__.setdefault(
                "_janelas_do_eco", collections.deque(maxlen=_JANELAS_DO_ECO_MAX)
            )
        assert janelas is not None
        return janelas

    def _o_jogo_pede_o_microfone(self, body: bytes) -> None:
        """Fora do eco, a luz e o mudo do report vão à fila das réplicas."""
        if not self._replicating():
            return
        self._pedido_do_microfone(body[_VALID_FLAG1_OFFSET], body)
        if not self._no_fio_do_uhid():
            self._flush_replicas()

    def _pedido_do_microfone(self, flag1: int, body: bytes) -> None:
        """Enfileira a luz e o mudo que o jogo pediu, com o dedup de sempre."""
        if flag1 & rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE and len(body) > _MIC_LED_OFFSET:
            luz = int(body[_MIC_LED_OFFSET])
            self._mic_led_do_jogo_amostra = luz
            self._queue_replica(_REPLICA_MIC_LED, luz)
        if flag1 & rep.VALID_FLAG1_POWER_SAVE_CONTROL_ENABLE and len(body) > _MIC_MUDO_OFFSET:
            mudo = bool(body[_MIC_MUDO_OFFSET] & rep.POWER_SAVE_MIC_MUTE)
            self._mic_mudo_do_jogo_amostra = mudo
            self._queue_replica(_REPLICA_MIC_MUDO, mudo)

    def _entregar_o_microfone(self, categoria: str, valor: Any) -> None:
        """Entrega UM pedido do microfone ao ralo do jogador e conta o desfecho."""
        luz = categoria == _REPLICA_MIC_LED
        ralo = self.mic_led_sink if luz else self.mic_mute_sink
        if ralo is None:
            return
        desfecho = ralo(valor)
        if not desfecho:
            if desfecho is not None:
                self._mic_do_jogo_retido += 1
            self._replica_last.pop(categoria, None)
            return
        if luz:
            self._mic_led_do_jogo += 1
            self._mic_luz_entregue = True
        else:
            self._mic_mudo_do_jogo += 1

    def _soltar_a_luz_do_microfone(self) -> None:
        """Fim da sessão: se ela entregou alguma luz, o jogo a solta."""
        if not self._mic_luz_entregue:
            return
        self._mic_luz_entregue = False
        if self._no_fio_do_uhid():
            self._mic_solta_a_entregar = True
            return
        self._dizer_que_o_jogo_soltou_a_luz()

    def _dizer_que_o_jogo_soltou_a_luz(self) -> None:
        if self.mic_led_sink is None:
            return
        try:
            self.mic_led_sink(None)
        except Exception as exc:
            logger.warning("uhid_mic_solta_falhou", err=str(exc), player=self.player)

    def _esquecer_o_microfone_do_jogo(self) -> None:
        """A próxima vida do pad nasce sem conta, amostra nem janela da anterior."""
        self._mic_led_do_jogo = 0
        self._mic_mudo_do_jogo = 0
        self._mic_do_jogo_retido = 0
        self._mic_eco_do_driver = 0
        self._mic_led_do_jogo_amostra = None
        self._mic_mudo_do_jogo_amostra = None
        self._mic_luz_entregue = False
        self._mic_solta_a_entregar = False
        self._as_janelas_do_eco().clear()
        self._mic_bit_que_saiu = False

    _pendentes: frozenset[str] = frozenset()


_MACS_POR_APARELHO = 64


def vpad_macs_do_aparelho(identity: str | None, player: int) -> Iterator[str]:
    """Os MACs que o vpad deste aparelho pode vestir, na ordem em que o dono os tenta."""
    import hashlib

    yield vpad_mac(identity, player)
    digitos = _somente_hex(identity)
    for n in range(1, _MACS_POR_APARELHO):
        if len(digitos) == 12:
            bruto = bytearray(
                hashlib.blake2b(f"{digitos}/{n}".encode("ascii"), digest_size=4).digest()
            )
            bruto[0] |= _VPAD_MAC_BIT_DERIVADO
            yield f"{VPAD_MAC_PREFIXO}:" + ":".join(f"{b:02x}" for b in bruto)
        else:
            yield f"{VPAD_MAC_PREFIXO}:00:00:{n:02x}:{player:02x}"


class _MacsDosVpadsVivos:
    """Quem veste cada MAC agora — o espelho, deste lado, da lista do `hid_playstation`."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._vestido_por: dict[str, Any] = {}

    def vestir(self, pad: UhidDualSense) -> str:
        """Veste em `pad` o primeiro MAC do aparelho dele que ninguém veste."""
        import weakref

        pedido = vpad_mac(pad.identity, pad.player)
        with self._lock:
            ja = self._de(pad)
            if ja is not None:
                return ja
            for mac in vpad_macs_do_aparelho(pad.identity, pad.player):
                dono = self._vestido_por.get(mac)
                if dono is None or dono() is None:
                    self._vestido_por[mac] = weakref.ref(pad)
                    break
            else:
                logger.warning("uhid_mac_sem_alternativa_livre", pedido=pedido,
                               player=pad.player)
                return pedido
        if mac != pedido:
            logger.info("uhid_mac_do_aparelho_ja_vestido", pedido=pedido, vestido=mac,
                        player=pad.player)
        return mac

    def despir(self, pad: UhidDualSense) -> None:
        """Devolve o MAC que `pad` veste. Idempotente."""
        with self._lock:
            for mac, dono in list(self._vestido_por.items()):
                if dono() is pad or dono() is None:
                    del self._vestido_por[mac]

    def vestido_por(self, pad: UhidDualSense) -> str | None:
        """O MAC que `pad` veste agora, ou None (parado, ou nunca nasceu)."""
        with self._lock:
            return self._de(pad)

    def _de(self, pad: UhidDualSense) -> str | None:
        return next(
            (mac for mac, dono in self._vestido_por.items() if dono() is pad), None
        )


_MACS_DOS_VPADS_VIVOS = _MacsDosVpadsVivos()


#: módulo para não deslocar as citações `arquivo:linha` do meio.
_MIC_LED_OFFSET = 8

_MIC_MUDO_OFFSET = 9

_REPLICA_MIC_LED = "mic_led"
_REPLICA_MIC_MUDO = "mic_mudo"

ECO_DO_DRIVER_S = 1.0

_JANELAS_DO_ECO_MAX = 8

_FLAG1_DO_ECO_PURO = (
    rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE
    | rep.VALID_FLAG1_POWER_SAVE_CONTROL_ENABLE
    | rep.VALID_FLAG1_AUDIO_CONTROL2_ENABLE
)


def _tem_a_assinatura_do_eco(body: bytes) -> bool:
    """A forma do 0x02 que o driver manda ao alternar o mudo dele."""
    if len(body) <= _MIC_MUDO_OFFSET:
        return False
    ambos = (
        rep.VALID_FLAG1_MIC_MUTE_LED_CONTROL_ENABLE
        | rep.VALID_FLAG1_POWER_SAVE_CONTROL_ENABLE
    )
    if body[_VALID_FLAG1_OFFSET] & ambos != ambos:
        return False
    luz = body[_MIC_LED_OFFSET]
    if luz not in (0, 1):
        return False
    return bool(body[_MIC_MUDO_OFFSET] & rep.POWER_SAVE_MIC_MUTE) == bool(luz)


def _e_eco_puro(body: bytes) -> bool:
    """O eco veio sozinho: sem vibração, sem gatilho, sem luz, sem som."""
    if body[_VALID_FLAG0_OFFSET]:
        return False
    if len(body) > rep.COMMON_VALID_FLAG2 and body[rep.COMMON_VALID_FLAG2]:
        return False
    if len(body) > _RUMBLE_STRONG_OFFSET and (
        body[_RUMBLE_WEAK_OFFSET] or body[_RUMBLE_STRONG_OFFSET]
    ):
        return False
    return not body[_VALID_FLAG1_OFFSET] & ~_FLAG1_DO_ECO_PURO & 0xFF


# --- O PAD EM USB (O-PAD-VIRTUAL-E-O-SOM-DELE-NASCEM-NO-MESMO-USB-01, 07/10/2026) ---
#
# O vpad nascia só por uhid, sem `usb_device` pai, e o jogo com a biblioteca da
# Sony não casava o som dele pelo contêiner (o engasgo do Sackboy). Onde o
# kernel cumpre o contrato (`pad_usb.contrato_que_falta`), o MESMO
# `UhidDualSense` nasce num gadget só HID que o broker monta, prende ao
# `usbip-vudc` e liga pelo `vhci_hcd`; o resto da classe não sabe a diferença.
# O fd do `/dev/hidgN` faz o papel do `/dev/uhid`, e o que ele diz se traduz
# nos eventos do uhid que a classe já atende:
#   - a entrada (o report 0x01) se escreve crua, um report por `write()`;
#   - o output do jogo (o 0x02, que sem endpoint OUT chega por SET_REPORT) se
#     lê do `read()` e vira um UHID_OUTPUT;
#   - as features do probe (0x05, 0x09, 0x20) se guardam no `f_hid` antes do
#     `attach` (`GADGET_HID_WRITE_GET_REPORT`), e o GET_REPORT que sobrar
#     (`POLLPRI`) se responde com elas;
#   - o 0x08 que o jogo manda é SET_FEATURE: o `f_hid` já o confirmou, e ele
#     não vai ao controle (é o que o uhid fazia com o UHID_SET_REPORT);
#   - o bind é o `hidraw` do lado do jogo nascer sob o `usb_device` com o serial
#     do gadget, e vira o UHID_START + UHID_OPEN de sempre (o `hid_playstation`
#     abre o aparelho no probe).
# A enumeração leva segundos (~9 s na prova): o `wait_for_bind` aceita o gadget
# montado, e o fio vigia a enumeração; se ela não vier em
# `_GADGET_ENUMERA_S`, o pad volta ao uhid e o contrato que faltou vai ao doctor.

_GADGET_ENUMERA_S = 15.0
_GADGET_VARRE_S = 5.0
_GADGET_VIGIA_S = 0.25
_GADGET_VEZ_DA_ESCRITA_MS = 8
_GADGET_LEITURA = 512
_GADGET_PERGUNTA_A_CADA = 8
_FEATURES_DO_PROBE = (0x05, 0x09, 0x20)
#: o contrato que só se mede montando: o gadget não enumerou pelo `vhci_hcd`.
CONTRATO_DA_ENUMERACAO = "enumeração pelo vhci_hcd"


@dataclass
class _GadgetDoPad:
    """Um gadget de pé: a conexão com o broker é a lease dele."""

    cliente: Any
    fd: int
    gadget: str
    serial: str
    identidade: str = ""
    hidraw: str | None = None
    interface: str | None = None
    escrita_falhou: int = 0
    falhas_seguidas: int = 0

    def desmontar(self) -> None:
        with contextlib.suppress(OSError):
            os.close(self.fd)
        with contextlib.suppress(Exception):
            self.cliente.desmontar_pad_usb(self.gadget)
        with contextlib.suppress(Exception):
            self.cliente.close()
        if self.identidade:
            pad_usb.esquecer_gadget(self.identidade)
        logger.info("pad_usb_desmontado", gadget=self.gadget)


def _pedir_ao_broker(serial: str, descritor: bytes, identidade: str) -> _GadgetDoPad | None:
    """O gadget pedido ao broker, numa conexão só dele (a lease), ou None."""
    from hefesto_dualsense4unix.integrations.hidraw_broker_client import HidrawBrokerClient

    cliente = HidrawBrokerClient()
    fd, resposta = cliente.montar_pad_usb(serial, descritor)
    if fd is None:
        with contextlib.suppress(Exception):
            cliente.close()
        contrato = (resposta or {}).get("contrato")
        if contrato:
            pad_usb.anotar_contrato_que_faltou(str(contrato))
        logger.info(
            "pad_usb_indisponivel_fica_o_uhid",
            motivo=(resposta or {}).get("error", "broker_fora_do_ar"),
        )
        return None
    return _GadgetDoPad(
        cliente=cliente,
        fd=fd,
        gadget=str((resposta or {}).get("gadget", "")),
        serial=serial,
        identidade=identidade,
    )


def _ha_jogo_aberto() -> bool:
    """A pergunta do nó de háptica (`quem_o_jogo_le.pids_de_jogo`)."""
    from hefesto_dualsense4unix.integrations.quem_o_jogo_le import pids_de_jogo

    try:
        return bool(pids_de_jogo())
    except Exception:  # pragma: no cover - defensivo: na dúvida, há jogo
        return True


#: as portas do pad em USB, injetáveis pela régua (a suíte nunca fala com o
#: broker dela: o `conftest` desvia o socket, e a régua troca estas).
PEDIR_O_PAD_USB: Callable[[str, bytes, str], _GadgetDoPad | None] = _pedir_ao_broker
HIDRAW_DO_GADGET: Callable[[str], tuple[str, str] | None] = pad_usb.hidraw_do_gadget
JOGO_ABERTO: Callable[[], bool] = _ha_jogo_aberto
#: o aparelho físico ainda está na máquina? Só o que CAIU estaciona o gadget.
APARELHO_PRESENTE: Callable[[str], bool] = pad_usb.aparelho_presente
#: a mesma pergunta do doctor (`system_check.contrato_do_pad_em_usb`): o que não
#: se lê volta «não sei» (``["?"]``), e na dúvida o pad nasce uhid.
CONTRATO_QUE_FALTA: Callable[[], list[str]] = system_check.contrato_do_pad_em_usb


class _GadgetsEstacionados:
    """O gadget do aparelho que caiu espera o jogo fechar (a cura 7).

    O jogo grava o device KS no lançamento com o GUID daquela hora, e o GUID
    sai do `usb_device` (`DEVNUM`, `USEC_INITIALIZED`): remontar o gadget
    muda o GUID e o som se perde. Por isso, com jogo aberto, o gadget do
    aparelho que saiu fica de pé, parado no neutro, e o aparelho que volta o
    retoma; sem jogo, ele desce. É a regra do nó de háptica.
    """

    def __init__(self) -> None:
        self._trava = threading.Lock()
        self._por_aparelho: dict[str, _GadgetDoPad] = {}
        self._vigia: threading.Thread | None = None

    def estacionar(self, identidade: str, gadget: _GadgetDoPad) -> None:
        chave = pad_usb._so_hex(identidade)
        with self._trava:
            antigo = self._por_aparelho.pop(chave, None)
            self._por_aparelho[chave] = gadget
            if self._vigia is None or not self._vigia.is_alive():
                self._vigia = threading.Thread(
                    target=self._vigiar, name="hefesto-pad-usb-estacionados", daemon=True
                )
                self._vigia.start()
        if antigo is not None and antigo is not gadget:
            antigo.desmontar()

    def retomar(self, identidade: str | None) -> _GadgetDoPad | None:
        if not identidade:
            return None
        with self._trava:
            return self._por_aparelho.pop(pad_usb._so_hex(identidade), None)

    def quantos(self) -> int:
        with self._trava:
            return len(self._por_aparelho)

    def varrer(self) -> int:
        """Sem jogo aberto, todo gadget estacionado desce. Devolve quantos."""
        with self._trava:
            if not self._por_aparelho:
                return 0
        if JOGO_ABERTO():
            return 0
        with self._trava:
            todos = list(self._por_aparelho.values())
            self._por_aparelho.clear()
        for gadget in todos:
            gadget.desmontar()
        return len(todos)

    def _vigiar(self) -> None:
        while True:
            time.sleep(_GADGET_VARRE_S)
            self.varrer()
            with self._trava:
                if not self._por_aparelho:
                    self._vigia = None
                    return


_GADGETS_ESTACIONADOS = _GadgetsEstacionados()
_CONTRATOS_JA_AVISADOS: set[tuple[str, ...]] = set()


def _avisar_o_contrato_que_falta(faltam: list[str]) -> None:
    """Uma linha por conjunto de contratos: o pad nasce uhid, e o log diz por quê."""
    chave = tuple(faltam)
    if chave in _CONTRATOS_JA_AVISADOS:
        return
    _CONTRATOS_JA_AVISADOS.add(chave)
    logger.warning("pad_usb_sem_contrato_fica_o_uhid", contratos=list(faltam))


def _o_pad_em_usb(pad: UhidDualSense, features: dict[int, bytes]) -> bool:
    """O pad nasce no gadget? False = segue o uhid de sempre, intacto."""
    if pad._sem_gadget or pad.product != VPAD_PRODUCT or pad.blueprint is None:
        return False
    gadget = _GADGETS_ESTACIONADOS.retomar(pad.identity)
    if gadget is None:
        faltam = CONTRATO_QUE_FALTA()
        if faltam:
            _avisar_o_contrato_que_falta(faltam)
            return False
        try:
            serial = pad_usb.serial_do_pad(pad.mac)
        except ValueError:
            return False
        gadget = PEDIR_O_PAD_USB(serial, bytes(pad.blueprint["descriptor"]), pad.identity or "")
        if gadget is None:
            return False
    try:
        for report_id in _FEATURES_DO_PROBE:
            if report_id in features:
                pad_usb.escrever_get_report(gadget.fd, report_id, features[report_id])
    except (OSError, ValueError) as exc:
        if getattr(exc, "errno", None) == errno.ENOTTY:
            pad_usb.anotar_contrato_que_faltou(pad_usb.CONTRATO_DO_IOCTL)
        logger.warning("pad_usb_features_recusadas_fica_o_uhid", err=str(exc),
                       player=pad.player)
        gadget.desmontar()
        return False
    with pad._lock:
        pad._features = features
        pad._fd = gadget.fd
        pad._gadget = gadget
        pad._gadget_prazo = pad.time_fn() + _GADGET_ENUMERA_S
    pad._iniciar_o_fio_do_uhid(gadget.fd)
    logger.info("pad_usb_montado", gadget=gadget.gadget, mac=pad.mac, player=pad.player)
    _vigiar_a_enumeracao(pad)
    return True


def _vigiar_a_enumeracao(pad: UhidDualSense) -> None:
    """O `hidraw` do gadget nasceu do lado do jogo? Então o bind aconteceu."""
    gadget = pad._gadget
    if gadget is None or pad._started:
        return
    achado = gadget.hidraw and gadget.interface and (gadget.hidraw, gadget.interface)
    if not achado:
        achado = HIDRAW_DO_GADGET(gadget.serial)
    if not achado:
        prazo = pad._gadget_prazo
        if prazo is not None and pad.time_fn() >= prazo:
            pad._gadget_falhou = True
        return
    gadget.hidraw, gadget.interface = achado
    if gadget.identidade:
        pad_usb.registrar_gadget(gadget.identidade, gadget.interface)
    with pad._a_trava_da_saida():
        pad._handle_event(struct.pack("<I", UHID_START))
        pad._handle_event(struct.pack("<I", UHID_OPEN))
    logger.info("pad_usb_enumerou", gadget=gadget.gadget, hidraw=gadget.hidraw,
                player=pad.player)


def _drenar_o_gadget(pad: UhidDualSense, fd: int, eventos: int) -> None:
    """Atende o `/dev/hidgN`: o GET_REPORT pendente e o output do jogo."""
    import select

    if eventos & select.POLLPRI:
        try:
            report_id = pad_usb.ler_o_id_do_get_report(fd)
            pad_usb.escrever_get_report(fd, report_id, pad._features.get(report_id, b""))
        except (OSError, ValueError) as exc:
            logger.debug("pad_usb_get_report_falhou", err=str(exc), player=pad.player)
    if not eventos & select.POLLIN:
        return
    for _ in range(_MAX_EVENTS_PER_PUMP):
        try:
            report = os.read(fd, _GADGET_LEITURA)
        except OSError as exc:
            # EAGAIN é a fila do f_hid vazia (o fim normal da drenagem); EBADF,
            # o fd que o stop fechou. O resto é falha e vai ao diário.
            if exc.errno not in (errno.EAGAIN, errno.EBADF):
                logger.warning("pad_usb_leitura_falhou", err=str(exc), player=pad.player)
            return
        if not report:
            return
        if report[0] != _OUTPUT_REPORT_USB:
            continue
        evento = (
            struct.pack("<I", UHID_OUTPUT)
            + report.ljust(HID_MAX_DESCRIPTOR_SIZE, b"\0")[:HID_MAX_DESCRIPTOR_SIZE]
            + struct.pack("<HB", len(report), 1)
        )
        with pad._a_trava_da_saida():
            pad._handle_event(evento)


def _fio_do_gadget(pad: UhidDualSense) -> Callable[[int, int, threading.Event], None]:
    """O laço do fio quando o fd é o `/dev/hidgN` (o par do `_atender_o_uhid`)."""
    import select

    def atender(fd: int, despertador: int, pare: threading.Event) -> None:
        sondador = select.poll()
        sondador.register(fd, select.POLLIN | select.POLLPRI)
        sondador.register(despertador, select.POLLIN)
        while not pare.is_set():
            espera = _GADGET_VIGIA_S if not pad._started or pad._last_body is None else (
                _UHID_FIO_ACORDA_S
            )
            try:
                prontos = dict(sondador.poll(int(espera * 1000)))
            except (OSError, ValueError) as exc:
                logger.warning("pad_usb_fio_saiu", err=str(exc), player=pad.player)
                return
            if pare.is_set():
                return
            if not pad._started:
                _vigiar_a_enumeracao(pad)
            elif pad._last_body is None:
                with pad._a_trava_da_saida():
                    pad._emit_if_changed(from_reader=True)
            if fd in prontos:
                try:
                    _drenar_o_gadget(pad, fd, prontos[fd])
                except Exception as exc:
                    logger.warning("pad_usb_evento_falhou", err=str(exc), player=pad.player)

    return atender


def _bombear_o_gadget(pad: UhidDualSense) -> None:
    """O `pump_ff` do gadget: o mesmo serviço, e a volta ao uhid se não enumerou."""
    import select

    if pad._gadget_caiu or pad._gadget_falhou:
        if pad._gadget_falhou:
            logger.warning("pad_usb_nao_enumerou_fica_o_uhid", player=pad.player,
                           prazo_s=_GADGET_ENUMERA_S)
            pad_usb.anotar_contrato_que_faltou(CONTRATO_DA_ENUMERACAO)
        pad._destruir_o_device()
        pad._sem_gadget = True
        pad._criar_o_device()
        return
    fd = pad._fd
    if fd is None:
        return
    with pad._a_trava_da_saida():
        pad._entregar_o_pendente()
        pad._flush_replicas()
        pad._expirar_rumble_preso()
        fio = pad._fio_do_uhid
        if fio is not None and fio.is_alive():
            return
        _vigiar_a_enumeracao(pad)
        _drenar_o_gadget(pad, fd, select.POLLIN | select.POLLPRI)


def _enviar_pelo_gadget(pad: UhidDualSense, report: bytes) -> bool:
    """Um input report no `/dev/hidgN`. O `f_hid` guarda UM em voo por vez."""
    import select

    with pad._lock:
        gadget, fd = pad._gadget, pad._fd
        if gadget is None or fd is None:
            return False
        for tentativa in (0, 1):
            try:
                os.write(fd, report)
                gadget.falhas_seguidas = 0
                return True
            except BlockingIOError:
                if tentativa:
                    break
                sondador = select.poll()
                sondador.register(fd, select.POLLOUT)
                with contextlib.suppress(OSError):
                    sondador.poll(_GADGET_VEZ_DA_ESCRITA_MS)
            except OSError as exc:
                if pad._started:
                    if not gadget.escrita_falhou:
                        logger.warning("pad_usb_escrita_falhou", err=str(exc),
                                       player=pad.player)
                    gadget.escrita_falhou += 1
                    gadget.falhas_seguidas += 1
                    _o_gadget_caiu(pad, gadget)
                break
        # O estado que não saiu sai no próximo compasso do fio: nada fica preso.
        pad._last_body = None
        return False


def _o_gadget_caiu(pad: UhidDualSense, gadget: _GadgetDoPad) -> None:
    """A escrita falha: o gadget ainda existe do lado do jogo?

    O broker que cai ou reinicia, ou o ``vhci`` que solta a porta, tira o
    gadget de baixo do pad com o ``_started`` ainda True: sem esta pergunta o
    pad ficaria mudo para sempre. Pergunta na primeira falha e a cada
    ``_GADGET_PERGUNTA_A_CADA`` seguidas; sumido o ``hidraw``, o bombeio do
    tique desmonta e o pad renasce no uhid (o contrato não faltou: não se anota).
    """
    if pad._gadget_caiu or (gadget.falhas_seguidas - 1) % _GADGET_PERGUNTA_A_CADA:
        return
    if HIDRAW_DO_GADGET(gadget.serial) is None:
        pad._gadget_caiu = True
        logger.warning("pad_usb_caiu_fica_o_uhid", gadget=gadget.gadget, player=pad.player)


def _report_neutro(pad: UhidDualSense) -> bytes:
    """O 0x01 de um controle largado: eixos no centro, nada apertado."""
    body = bytearray(_INPUT_PAYLOAD_SIZE)
    body[_MOTION_WINDOW] = _MOTION_NEUTRAL
    body[_STATUS_OFFSET] = pad._status_byte
    body[_STATUS1_OFFSET] = pad._status1_byte
    body[0:6] = bytes(_AXES_NEUTRAL)
    body[_BUTTONS0_OFFSET] = _DPAD_NEUTRAL
    body[_SEQ_OFFSET] = (pad._seq + 1) & 0xFF
    return bytes([_INPUT_REPORT_USB]) + bytes(body)


def _soltar_o_gadget(pad: UhidDualSense) -> bool:
    """A metade do `_destruir_o_device` do gadget. False = o fd é do uhid."""
    gadget = pad._gadget
    if gadget is None:
        return False
    falhou = pad._gadget_falhou or pad._gadget_caiu
    pad._gadget = None
    pad._gadget_prazo = None
    pad._gadget_falhou = False
    pad._gadget_caiu = False
    # Estaciona só o gadget do aparelho que CAIU com o jogo aberto (a cura 7).
    # Com o aparelho aqui (a troca de máscara, a emulação desligada, o co-op
    # desfeito) o gadget desce: de pé, ele seria um DualSense fantasma ao lado
    # do pad novo ou do físico devolvido.
    if (
        not falhou
        and gadget.hidraw is not None
        and pad.identity
        and JOGO_ABERTO()
        and not APARELHO_PRESENTE(pad.identity)
    ):
        with contextlib.suppress(OSError):
            os.write(gadget.fd, _report_neutro(pad))
        _GADGETS_ESTACIONADOS.estacionar(pad.identity, gadget)
        logger.info("pad_usb_espera_o_jogo_fechar", gadget=gadget.gadget, player=pad.player)
        return True
    gadget.desmontar()
    return True


__all__ = [
    "CONTRATO_DA_ENUMERACAO",
    "UHID_NODE",
    "VPAD_HID_PHYS",
    "VPAD_MAC_PREFIXO",
    "VPAD_PRODUCT",
    "UhidDualSense",
    "capture_dualsense_blueprint",
    "player_mac",
    "uhid_available",
    "vpad_mac",
    "vpad_macs_do_aparelho",
]
