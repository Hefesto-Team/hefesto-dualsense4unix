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
   precisa do seu MAC, na faixa localmente administrada (ver `player_mac`).
2. **Responder UHID_GET_REPORT é obrigatório** durante o probe — sem isso o
   driver não registra o controle.
3. **UHID_SET_REPORT também precisa de reply**, senão o probe trava.

Degradação: sem `/dev/uhid` (ou sem permissão, ou kernel sem `hid_playstation`),
`start()` devolve False e o chamador cai no `UinputGamepad` — sem crash, mas
avisando que a vibração da máscara DualSense não vai funcionar.
"""
from __future__ import annotations

import contextlib
import errno
import fcntl
import os
import re
import struct
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Nó de caractere do uhid. Nasce root-only; o install.sh põe a regra udev
#: (mesmo tratamento do /dev/uinput).
UHID_NODE = "/dev/uhid"

# --- linux/uhid.h ---------------------------------------------------------
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

#: HID_MAX_DESCRIPTOR_SIZE do kernel — o tamanho dos campos rd_data/data.
HID_MAX_DESCRIPTOR_SIZE = 4096

#: `struct uhid_event` é packed e tem o tamanho do maior membro da union
#: (uhid_create2_req). Ler menos que isso trunca eventos.
_CREATE2_HEAD = 128 + 64 + 64 + 2 + 2 + 4 + 4 + 4 + 4
UHID_EVENT_SIZE = 4 + _CREATE2_HEAD + HID_MAX_DESCRIPTOR_SIZE

BUS_USB = 0x03

#: VID/PID do DualSense FÍSICO. É o que o `_is_dualsense` exige do controle de
#: onde copiamos o blueprint, e o que o botão de Launch Options manda o SDL
#: IGNORAR (IGNORE_DEVICES) para esconder o físico do jogo.
DUALSENSE_VENDOR = 0x054C
DUALSENSE_PRODUCT = 0x0CE6

#: PID que o VPAD apresenta — de propósito DIFERENTE do físico (0x0CE6). É a chave
#: do fim do controle duplicado (UHID-04): com físico E vpad no MESMO 054c:0ce6,
#: nenhuma Launch Option por VID/PID conseguia separá-los — `IGNORE_DEVICES` para
#: 054c:0ce6 escondia os dois e o jogo ficava sem controle nenhum. Como o vpad é
#: forjado, ele vira um DualSense **Edge** (0x0DF2): o `hid_playstation` o
#: registra como DualSense COMPLETO (validado ao vivo — hidraw+lightbar+motion+
#: touchpad+rumble; dmesg "Registered DualSense controller") e o SDL o reconhece
#: como PS5 (prompts PlayStation). Assim
#: `SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6` esconde SÓ o físico e o vpad
#: (0x0DF2) sobrevive: layout PS, vibração e nada de duplicado.
#:
#: Invariante VPAD-06 (travado por teste dedicado): NENHUM caminho de criação de
#: vpad com flavor dualsense produz 054c:0ce6 — o fallback uinput também nasce
#: Edge 0x0DF2 (`uinput_gamepad.DUALSENSE_EDGE_PRODUCT` espelha esta constante),
#: então a launch option persistida (`IGNORE_DEVICES=0x054c/0x0ce6`) nunca mais
#: esconde o vpad junto do físico. Duas ressalvas honestas: (1) `DUALSENSE_PIDS`
#: trata 0x0DF2 como PID de FÍSICO (o Edge real existe) — quem impede o daemon de
#: adotar o próprio vpad é o filtro de ancestralidade (`_is_virtual_evdev` /
#: `_is_virtual_hidraw`), nunca o VID/PID; (2) o dono de um Edge FÍSICO divide
#: VID/PID com o vpad — só a dedup por ancestralidade na regra udev (Fase B do
#: sprint) cobre esse caso.
VPAD_PRODUCT = 0x0DF2

#: Feature reports que o probe do hid_playstation lê, com os tamanhos que o
#: driver espera: 0x05 calibração, 0x09 MAC/pairing, 0x20 firmware.
_FEATURE_SIZES: tuple[tuple[int, int], ...] = ((0x05, 41), (0x09, 20), (0x20, 64))

#: Report de output do DualSense em USB (rumble/lightbar/gatilhos do jogo).
_OUTPUT_REPORT_USB = 0x02

#: Offsets dentro do report 0x02 (payload após o report id):
#: byte 0 = valid_flag0, 1 = valid_flag1, 2 = motor direito (weak),
#: 3 = motor esquerdo (strong).
_VALID_FLAG0_OFFSET = 0
_RUMBLE_WEAK_OFFSET = 2
_RUMBLE_STRONG_OFFSET = 3

#: Bits de vibração do valid_flag0 (hid-playstation.c):
#:   0x01 DS_OUTPUT_VALID_FLAG0_COMPATIBLE_VIBRATION — firmware antigo e SDL/HIDAPI
#:   0x02 DS_OUTPUT_VALID_FLAG0_HAPTICS_SELECT       — presente nos dois caminhos
#:
#: Sem estes bits os bytes 2-3 do report NÃO são pedido de rumble: o jogo usa o
#: MESMO report 0x02 para lightbar/gatilhos/mic, e lá os motores vêm zerados —
#: forwardá-los MATAVA a vibração em curso (o update_rumble do driver é one-shot,
#: então o controle ficava mudo até o jogo mudar o valor de FF).
#:
#: É MÁSCARA, não bit único: com firmware >= 0x0215 o driver liga `use_vibration_v2`
#: e manda COMPATIBLE_VIBRATION2 no valid_flag2, deixando o valid_flag0 com
#: 0x02 SOZINHO. Os dois DualSense da máquina de teste são 0x0630 — testar só o
#: 0x01 descartava TODO o rumble justamente no hardware alvo.
_VIBRATION_FLAGS = 0x03

#: Cap de eventos drenados por tick — o jogo pode mandar output em rajada.
_MAX_EVENTS_PER_PUMP = 64

#: Report de input do DualSense em USB (sticks/gatilhos/botões → jogo).
_INPUT_REPORT_USB = 0x01

#: Tamanho do payload do report 0x01 — 64 bytes COM o report id, que é o
#: `DS_INPUT_REPORT_USB_SIZE` do hid-playstation.c. O driver compara o tamanho
#: (`size == DS_INPUT_REPORT_USB_SIZE`) e **descarta calado** o report que não
#: bate: com 1 byte a menos o vpad nascia mudo — o kernel aceitava o INPUT2 sem
#: erro e o evdev nunca saía do repouso.
#:
#: A conta pelo descriptor engana: os campos de bits (4 do d-pad + 15 + 13) somam
#: 32 bits = 4 bytes, e arredondá-los para baixo um a um dá 3. Confira sempre
#: contra um report cru do controle: `os.read(open('/dev/hidraw4'), 128)` -> 64 B.
_INPUT_PAYLOAD_SIZE = 63

#: Offsets dentro do payload do report 0x01 (depois do report id), medidos num
#: report cru do controle físico: `01 7f 7f 7d 7c 00 00 97 08 00 ...`.
_SEQ_OFFSET = 6
_BUTTONS0_OFFSET = 7
_BUTTONS1_OFFSET = 8
_BUTTONS2_OFFSET = 9

#: Sticks em repouso. Um payload zerado NÃO é neutro: 0 é o canto do stick, e um
#: report emitido por `forward_buttons` antes do primeiro `forward_analog`
#: mandaria o personagem correndo para a diagonal superior-esquerda.
_STICK_CENTER = 0x80
_AXES_NEUTRAL = (_STICK_CENTER, _STICK_CENTER, _STICK_CENTER, _STICK_CENTER, 0, 0)

#: Nibble ALTO do buttons0 (o baixo é o d-pad).
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

#: Todos viram o MESMO bit de click do touchpad (0x02): a regionalização
#: (esquerda/meio/direita) é invenção nossa para o modo mouse, o DualSense real
#: só reporta "o touchpad foi clicado".
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

#: Byte de `status` do report 0x01 (bateria + carga). O `dualsense_parse_report` lê
#: ``battery_data = status & 0x0F`` e ``charging_status = (status & 0xF0) >> 4``;
#: no caso 0x0 a capacidade vira ``min(battery_data * 10 + 5, 100)``.
#:
#: Zerado, o vpad anuncia **5% descarregando para sempre** — o jogo mostra alerta
#: de bateria fraca num controle carregado. Medido: o físico manda 0x29 (= 95%).
#: Espelhamos a bateria do controle físico daquele jogador; sem dado, "cheio e
#: carregando" (0x1F) é a mentira menos daninha — não dispara alerta.
_STATUS_OFFSET = 52
_STATUS_DESCONHECIDO = 0x1F
_CHARGING_SHIFT = 4
_BATTERY_MAX_NIBBLE = 0x0A

#: D-pad é HAT, não bitmask: 0=N, 1=NE, 2=E, 3=SE, 4=S, 5=SW, 6=W, 7=NW.
_DPAD_NEUTRAL = 0x08
_HAT_BY_VECTOR: dict[tuple[int, int], int] = {
    (0, -1): 0, (1, -1): 1, (1, 0): 2, (1, 1): 3,
    (0, 1): 4, (-1, 1): 5, (-1, 0): 6, (-1, -1): 7,
    (0, 0): _DPAD_NEUTRAL,
}

#: Intervalo entre bombeadas do `wait_for_bind`. O probe do hid_playstation faz
#: várias idas e voltas (GET_REPORT 0x09/0x20/0x05) antes do UHID_START.
_BIND_POLL_INTERVAL_S = 0.01

#: Graça após o UHID_START para o probe do hid_playstation se decidir.
#:
#: O `wait_for_bind` roda DENTRO do poll loop (o co-op promove jogador em
#: `sync`/`forward_all`), então cada milissegundo aqui é input congelado do P1.
#: Medido ao vivo: o probe que recusa manda CLOSE+STOP em ~2 ms → 50 ms são 25x de
#: folga, pagos uma vez por promoção de jogador. (Começou em 150 ms, que davam 75x
#: sem necessidade: o poll loop travava 3x mais para nada.)
_BIND_SETTLE_S = 0.05


def player_mac(player: int) -> str:
    """MAC próprio do vpad do jogador (1-based).

    O probe do `hid_playstation` recusa MAC repetido (-EEXIST), então copiar o do
    físico não serve. Usamos a faixa **localmente administrada** (bit 1 do
    primeiro octeto), que por definição não colide com hardware real.
    """
    return f"02:fe:00:00:00:{player:02x}"


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
    # HID_ID=0003:0000054C:00000CE6 (bus:vendor:product)
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

    # Diagnóstico: o descriptor de BT declara o report de INPUT 0x31 (item HID
    # `85 31`), enquanto o USB usa 0x01. Como blueprint de vpad ele é impróprio
    # por construção (o vpad é BUS_USB emitindo report 0x01 de 64 B) — e é por
    # isso que o caminho de criação usa o descriptor USB canônico embutido, não
    # esta captura. Aqui só se registra o fato, para quem estiver inspecionando.
    if b"\x85\x31" in descriptor:
        logger.info("uhid_descriptor_bt_diagnostico", path=hidraw_path,
                    tamanho=len(descriptor))

    features: dict[int, bytes] = {}
    try:
        fd = os.open(hidraw_path, os.O_RDWR)
    except OSError as exc:
        logger.warning("uhid_hidraw_open_failed", path=hidraw_path, err=str(exc))
        return None
    try:
        for report_id, size in _FEATURE_SIZES:
            try:
                features[report_id] = _hidiocgfeature(fd, report_id, size)
            except OSError as exc:
                logger.warning("uhid_feature_read_failed", report=hex(report_id),
                               err=str(exc))
    finally:
        os.close(fd)

    # O probe do hid_playstation lê o 0x09 para o MAC — e nós sobrescrevemos os
    # bytes 1..6 dele com o MAC do jogador. Um report vazio/truncado passava no
    # `0x09 not in features` e só quebrava lá na frente, no start().
    mac_report = features.get(0x09, b"")
    if len(mac_report) < 7:
        logger.warning("uhid_blueprint_sem_mac", path=hidraw_path,
                       tamanho=len(mac_report))
        return None
    return {"descriptor": descriptor, "features": features}


def uhid_available() -> bool:
    """True quando dá para abrir /dev/uhid para escrita (udev aplicado)."""
    return os.access(UHID_NODE, os.R_OK | os.W_OK)


@dataclass
class UhidDualSense:
    """DualSense virtual criado via /dev/uhid, com passthrough de rumble.

    A interface espelha a de `UinputGamepad` (`start`/`stop`/`is_active`/
    `pump_ff`) para o co-op e o gamepad primário trocarem de backend sem
    cirurgia. O que muda: aqui o input vai em **report HID** (INPUT2), não em
    eventos evdev — quem monta o report é `send_report()`.
    """

    #: 1-based; define o MAC e o nome do device.
    player: int = 1
    #: PID que o vpad apresenta ao kernel/jogo. Default Edge (`VPAD_PRODUCT`) —
    #: distinto do físico para desduplicar; ver a constante para o porquê.
    product: int = VPAD_PRODUCT
    #: Blueprint no shape de `uhid_blueprint.canonical_blueprint` — o que a
    #: factory injeta (descriptor + features). `capture_dualsense_blueprint`
    #: produz o mesmo shape (hoje só diagnóstico).
    blueprint: dict[str, Any] | None = None
    #: Recebe (weak, strong) 0-255 pedidos pelo JOGO — igual ao vpad uinput.
    rumble_sink: Callable[[int, int], None] | None = None
    #: Relógio/sleep injetáveis (testes herméticos do `wait_for_bind`).
    time_fn: Callable[[], float] = time.monotonic
    sleep_fn: Callable[[float], None] = time.sleep

    _fd: int | None = None
    _features: dict[int, bytes] = field(default_factory=dict)
    _last_sent: tuple[int, int] = (0, 0)
    _output_count: int = 0
    _rumble_count: int = 0
    _started: bool = False
    _lock: threading.RLock = field(default_factory=threading.RLock)
    #: Estado do controle físico que o encoder transforma em report 0x01.
    _axes: tuple[int, int, int, int, int, int] = _AXES_NEUTRAL
    _buttons: frozenset[str] = field(default_factory=frozenset)
    _status_byte: int = _STATUS_DESCONHECIDO
    #: Último payload EMITIDO, com o seq zerado — é a chave do delta. Comparar o
    #: payload (e não o (axes, buttons) cru) mata os falsos "mudou": trocar
    #: touchpad_left_press por touchpad_middle_press dá o MESMO bit no report.
    _last_body: bytes | None = None
    #: Contador de sequência do report (0-255, wrap). O hid_playstation o usa
    #: para detectar perda de pacote, então só anda quando um report SAI.
    _seq: int = 0

    @classmethod
    def for_flavor(
        cls,
        flavor: str | None = None,
        *,
        rumble_sink: Callable[[int, int], None] | None = None,
        player: int = 1,
        blueprint: dict[str, Any] | None = None,
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
        """
        from hefesto_dualsense4unix.integrations.uinput_gamepad import normalize_flavor

        if flavor is not None and normalize_flavor(flavor) != "dualsense":
            return None
        return cls(player=player, blueprint=blueprint, rumble_sink=rumble_sink)

    @property
    def name(self) -> str:
        return f"Hefesto Virtual DualSense P{self.player}"

    @property
    def flavor(self) -> str:
        """Sempre "dualsense" — o único flavor que este backend faz (`for_flavor`).

        Não é enfeite: o daemon compara `vpad.flavor` com a máscara desejada para
        decidir se recria o vpad (`coop.sync`, `start_gamepad_emulation`). Sem esta
        propriedade o getattr daria None, o mismatch seria eterno e cada tick de
        sync derrubaria e recriaria os vpads do co-op.
        """
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
        return player_mac(self.player)

    @property
    def ff_last_sent(self) -> tuple[int, int]:
        """Último par (weak, strong) entregue ao sink (rumble do jogo)."""
        return self._last_sent

    @property
    def ff_play_count(self) -> int:
        """Nº de pedidos de RUMBLE do jogo (diagnóstico: "o jogo está vibrando?").

        Conta só os reports com a flag de vibração — o jogo usa o mesmo report
        0x02 para lightbar/gatilhos/mic, e contá-los aqui dava um diagnóstico
        falso-positivo ("o jogo pediu rumble") para quem só acendeu um LED.
        """
        return self._rumble_count

    @property
    def output_count(self) -> int:
        """Nº total de reports de output do jogo (rumble + LED + gatilhos + mic)."""
        return self._output_count

    @property
    def ff_supported(self) -> bool:
        """No caminho uhid o rumble sempre existe — é hidraw de verdade."""
        return True

    def is_active(self) -> bool:
        return self._fd is not None

    # --- ciclo de vida ---------------------------------------------------

    def start(self) -> bool:
        """Cria o device HID. False = indisponível (o chamador cai no uinput)."""
        if self._fd is not None:
            return True
        if self.blueprint is None:
            logger.warning("uhid_sem_blueprint", player=self.player)
            return False
        # Prepara TUDO antes de abrir o nó: qualquer falha aqui não pode deixar um
        # fd de /dev/uhid pendurado (o processo é longo; fd vazado nunca volta).
        try:
            features = self._features_com_mac_proprio()
            create_event = self._create2_event(self.blueprint["descriptor"])
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("uhid_blueprint_invalido", err=str(exc), player=self.player)
            return False

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
        logger.info("uhid_device_created", name=self.name, mac=self.mac,
                    player=self.player)
        return True

    def _features_com_mac_proprio(self) -> dict[int, bytes]:
        """Copia os features do blueprint carimbando o MAC do jogador no 0x09.

        O template canônico vem com as áreas de MAC ZERADAS (identidade nunca é
        fossilizada — regra de anonimato); é aqui que o vpad ganha o MAC forjado
        `02:fe:00:00:00:0N`. O probe do hid_playstation recusa MAC repetido
        (-EEXIST): sem MAC próprio por jogador, o co-op de 4 vira 1.
        """
        assert self.blueprint is not None
        features = dict(self.blueprint["features"])
        report09 = bytearray(features[0x09])
        if len(report09) < 7:
            raise ValueError(f"feature 0x09 curto demais: {len(report09)} bytes")
        # Slice assign em bytearray REDIMENSIONA quando os tamanhos diferem — com
        # um report curto isso mudaria o tamanho do report em vez de sobrescrever
        # o MAC. O guard acima garante os 6 bytes; a asserção trava o contrato.
        report09[1:7] = _mac_to_report_bytes(self.mac)
        assert len(report09) == len(features[0x09])
        features[0x09] = bytes(report09)
        return features

    def stop(self) -> None:
        # Sob o lock: o poll loop pode estar em send_report/pump_ff nesta hora, e
        # fechar o fd por baixo dele faria o write cair num fd já RECICLADO por
        # outra thread (escrita de 4 KB num destino aleatório).
        with self._lock:
            fd = self._fd
            if fd is None:
                return
            self._fd = None
            self._silence_rumble()
            with contextlib.suppress(OSError):
                os.write(fd, struct.pack("<I", UHID_DESTROY))
            with contextlib.suppress(OSError):
                os.close(fd)
            self._features = {}
            self._last_sent = (0, 0)
            self._output_count = 0
            self._rumble_count = 0
            self._started = False
            self._axes = _AXES_NEUTRAL
            self._buttons = frozenset()
            self._last_body = None
            self._seq = 0

    def _silence_rumble(self) -> None:
        """Zera os motores do controle físico se o jogo os deixou ligados.

        O vpad some e ninguém mais mandaria o stop — sem isto o DualSense fica
        vibrando para sempre (mesma proteção do UinputGamepad.stop).
        """
        if self._last_sent == (0, 0) or self.rumble_sink is None:
            return
        with contextlib.suppress(Exception):
            self.rumble_sink(0, 0)
        self._last_sent = (0, 0)

    def _create2_event(self, descriptor: bytes) -> bytes:
        event = struct.pack("<I", UHID_CREATE2)
        event += self.name.encode("utf-8").ljust(128, b"\0")[:128]
        event += b"hefesto-vpad".ljust(64, b"\0")[:64]
        event += self.mac.encode("ascii").ljust(64, b"\0")[:64]
        event += struct.pack("<HH", len(descriptor), BUS_USB)
        event += struct.pack("<IIII", DUALSENSE_VENDOR, self.product, 0x0100, 0)
        event += descriptor.ljust(HID_MAX_DESCRIPTOR_SIZE, b"\0")[:HID_MAX_DESCRIPTOR_SIZE]
        return event

    # --- input (nós → kernel) --------------------------------------------

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
        """Guarda os analógicos do controle físico e emite o report (se mudou).

        Mesma assinatura do `UinputGamepad.forward_analog` — o call site troca de
        backend sem cirurgia. A diferença é o destino: lá vira evento evdev, aqui
        vira o report HID 0x01 inteiro (sticks, gatilhos, botões e d-pad juntos).
        """
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
        self._buttons = frozenset(pressed)
        self._emit_if_changed()

    def _emit_if_changed(self) -> bool:
        """Emite o report 0x01 só quando o payload mudou.

        Espelha o delta do `UinputGamepad`: o forward roda a cada tick por vpad, e
        sem isto seriam ~250 writes/s por controle no /dev/uhid com tudo parado.
        """
        body = self._encode_body()
        chave = bytes(body)
        if chave == self._last_body:
            return False
        self._last_body = chave
        # O seq só anda quando um report SAI: ele existe para o hid_playstation
        # detectar perda de pacote, e furar a contagem em report suprimido pelo
        # delta seria reportar perda que não houve.
        self._seq = (self._seq + 1) & 0xFF
        body[_SEQ_OFFSET] = self._seq
        return self.send_report(bytes([_INPUT_REPORT_USB]) + bytes(body))

    def _encode_body(self) -> bytearray:
        """Payload do report 0x01 a partir do estado, com o seq ZERADO.

        Zerado de propósito: é assim que o payload serve de chave do delta (ver
        `_emit_if_changed`, que carimba o seq depois da comparação).
        """
        body = bytearray(_INPUT_PAYLOAD_SIZE)
        for offset in _TOUCH_POINT_OFFSETS:
            body[offset] = _TOUCH_INACTIVE
        body[_STATUS_OFFSET] = self._status_byte
        body[0:6] = bytes(self._axes)
        pressed = self._buttons
        body[_BUTTONS0_OFFSET] = self._dpad_hat(pressed) | _bitmask(pressed, _BUTTONS0_BITS)
        body[_BUTTONS1_OFFSET] = _bitmask(pressed, _BUTTONS1_BITS)
        buttons2 = _bitmask(pressed, _BUTTONS2_BITS)
        if pressed & _TOUCHPAD_BUTTONS:
            buttons2 |= _TOUCHPAD_BIT
        body[_BUTTONS2_OFFSET] = buttons2
        return body

    def forward_battery(self, percent: int | None, *, charging: bool = False) -> None:
        """Espelha a bateria do controle físico no vpad (opcional).

        Sem isto o vpad anuncia 5% descarregando para sempre e o jogo mostra
        alerta de bateria fraca num controle cheio. `percent=None` volta para
        "cheio e carregando", que não dispara alerta nenhum.
        """
        if percent is None:
            novo = _STATUS_DESCONHECIDO
        else:
            estado = 0x1 if charging else 0x0
            novo = (estado << _CHARGING_SHIFT) | _percent_para_nibble(percent)
        if novo == self._status_byte:
            return
        self._status_byte = novo
        self._emit_if_changed()

    @staticmethod
    def _dpad_hat(pressed: frozenset[str]) -> int:
        """D-pad → HAT (0-7, 8=neutro).

        Em opostos simultâneos (cima+baixo), esquerda e cima vencem — MESMA
        precedência do `UinputGamepad._dpad_vector`. O controle físico não
        produz esse estado (o hat de origem já é exclusivo), mas remap/testes
        produzem, e os dois backends têm de reagir igual à mesma tecla: divergir
        aqui daria um bug que só aparece depois de trocar de backend.
        """
        x = -1 if "dpad_left" in pressed else (1 if "dpad_right" in pressed else 0)
        y = -1 if "dpad_up" in pressed else (1 if "dpad_down" in pressed else 0)
        return _HAT_BY_VECTOR[(x, y)]

    def wait_for_bind(self, timeout_s: float = 2.0) -> bool:
        """Bloqueia até o `hid_playstation` REGISTRAR o controle, ou estourar.

        `start()` só diz que o CREATE2 foi aceito: o UHID_START chega depois, e
        vem do probe do driver — que pode recusar (MAC duplicado, kernel sem
        hid_playstation). Sem esta espera o fallback para o uinput seria
        desonesto: "deu certo" com o jogo sem controle nenhum.

        O UHID_START **não basta**: ele chega no começo do probe, não no fim.
        Medido ao vivo com dois vpads de MAC igual — o segundo recebeu
        ``START, OPEN, GET_REPORT, GET_REPORT, CLOSE, STOP`` em 2 ms enquanto o
        kernel logava ``Failed to create dualsense / probe failed -17``; parar no
        START devolvia True para um device natimorto. O probe que dá certo NUNCA
        manda STOP, então a confirmação é: viu START, e o STOP não veio no
        intervalo de graça.
        """
        if self._fd is None:
            return False
        deadline = self.time_fn() + timeout_s
        while not self._started:
            # Bombear aqui é obrigatório: quem consome os eventos é o pump_ff, e
            # no start() o poll loop do daemon ainda não está de pé.
            self.pump_ff()
            if self._started:
                break
            if self.time_fn() >= deadline:
                logger.warning("uhid_bind_timeout", player=self.player,
                               timeout_s=timeout_s)
                return False
            self.sleep_fn(_BIND_POLL_INTERVAL_S)

        # START visto: agora confirmar que o probe não desistiu logo em seguida.
        settle_deadline = self.time_fn() + _BIND_SETTLE_S
        while self.time_fn() < settle_deadline:
            self.pump_ff()
            if not self._started:  # veio UHID_STOP: o probe recusou o device
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
        if len(report) > HID_MAX_DESCRIPTOR_SIZE:
            logger.warning("uhid_input_grande_demais", tamanho=len(report))
            return False
        # Sem padding até 4 KB: o uhid_char_write copia só min(count, sizeof(event))
        # e zera o resto, então mandar o report cru poupa ~4 KB de copy_from_user
        # por evento — a 250 Hz x 4 controles isso era ~4 MB/s de cópia à toa.
        event = struct.pack("<IH", UHID_INPUT2, len(report)) + report
        # O lock cobre write+close juntos: sem ele o stop() podia fechar o fd entre
        # o teste e o write, e a escrita cairia num fd já reciclado.
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

    # --- output (kernel/jogo → nós) --------------------------------------

    def pump_ff(self) -> None:
        """Drena os eventos do uhid; entrega o rumble do jogo ao `rumble_sink`.

        Mesmo contrato do `UinputGamepad.pump_ff`: chamado a cada tick do poll
        loop, nunca bloqueia, e responde os GET/SET_REPORT do probe (sem isso o
        `hid_playstation` não registra o controle).
        """
        # Lê o fd UMA vez: `stop()` concorrente (o poll loop bombeia enquanto a GUI
        # troca de modo) zerava self._fd no meio do laço e o os.read(None) levantava
        # TypeError — que, ao contrário do OSError, ninguém pegava.
        fd = self._fd
        if fd is None:
            return
        for _ in range(_MAX_EVENTS_PER_PUMP):
            try:
                data = os.read(fd, UHID_EVENT_SIZE)
            except BlockingIOError:
                return
            except OSError as exc:
                # EBADF esperado quando o stop() fechou o fd entre o topo e aqui.
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
            logger.info("uhid_bind_ok", player=self.player, name=self.name)
        elif event_type in (UHID_STOP, UHID_CLOSE):
            # O driver largou o device (rmmod, jogo fechou o hidraw, unbind). Se o
            # jogo deixou motor ligado, ninguém mais mandaria o stop — o controle
            # físico ficaria vibrando até alguém desligar o Hefesto.
            self._started = self._started and event_type == UHID_CLOSE
            self._silence_rumble()
        elif event_type == UHID_OUTPUT:
            self._handle_output(data)
        elif event_type == UHID_GET_REPORT:
            self._reply_get_report(data)
        elif event_type == UHID_SET_REPORT:
            self._reply_set_report(data)

    def _handle_output(self, data: bytes) -> None:
        """UHID_OUTPUT = o jogo escreveu no hidraw do vpad (rumble/LED/gatilhos).

        struct uhid_output_req { __u8 data[4096]; __u16 size; __u8 rtype; }
        """
        payload_size = struct.unpack("<H", data[4 + HID_MAX_DESCRIPTOR_SIZE:
                                                6 + HID_MAX_DESCRIPTOR_SIZE])[0]
        report = data[4:4 + min(payload_size, HID_MAX_DESCRIPTOR_SIZE)]
        if len(report) < 2 or report[0] != _OUTPUT_REPORT_USB:
            return
        self._output_count += 1
        body = report[1:]
        if len(body) <= _RUMBLE_STRONG_OFFSET:
            return
        if not body[_VALID_FLAG0_OFFSET] & _VIBRATION_FLAGS:
            return
        self._rumble_count += 1
        weak = body[_RUMBLE_WEAK_OFFSET]
        strong = body[_RUMBLE_STRONG_OFFSET]
        if (weak, strong) == self._last_sent:
            return
        self._last_sent = (weak, strong)
        self._emit_rumble(weak, strong)

    def _emit_rumble(self, weak: int, strong: int) -> None:
        if self.rumble_sink is None:
            return
        try:
            self.rumble_sink(weak, strong)
        except Exception as exc:
            logger.warning("uhid_rumble_sink_failed", err=str(exc), player=self.player)

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


__all__ = [
    "UHID_NODE",
    "VPAD_PRODUCT",
    "UhidDualSense",
    "capture_dualsense_blueprint",
    "player_mac",
    "uhid_available",
]
