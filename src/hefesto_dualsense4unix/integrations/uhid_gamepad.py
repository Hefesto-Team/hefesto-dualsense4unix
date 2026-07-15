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
firmware) são **copiados do DualSense físico** via `HIDIOCGFEATURE` — é o que o
`hid_playstation` pede no probe (`dualsense_get_mac_address`,
`dualsense_get_calibration_data`, `dualsense_get_firmware_info`).

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

#: VID/PID do DualSense. O vpad usa os do controle real: é o que faz o
#: `hid_playstation` reconhecê-lo (e o jogo mostrar prompts de PlayStation).
DUALSENSE_VENDOR = 0x054C
DUALSENSE_PRODUCT = 0x0CE6

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


def player_mac(player: int) -> str:
    """MAC próprio do vpad do jogador (1-based).

    O probe do `hid_playstation` recusa MAC repetido (-EEXIST), então copiar o do
    físico não serve. Usamos a faixa **localmente administrada** (bit 1 do
    primeiro octeto), que por definição não colide com hardware real.
    """
    return f"02:fe:00:00:00:{player:02x}"


def _mac_to_report_bytes(mac: str) -> bytes:
    """MAC textual → os 6 bytes do report 0x09, em little-endian."""
    return bytes(reversed(bytes.fromhex(mac.replace(":", ""))))


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
    """Lê do DualSense físico tudo que o vpad precisa para se passar por um.

    Devolve ``{"descriptor": bytes, "features": {id: bytes}}`` ou None quando o
    controle não está acessível ou não é um DualSense (o chamador cai no uinput).
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
    #: Blueprint de `capture_dualsense_blueprint` (descriptor + features).
    blueprint: dict[str, Any] | None = None
    #: Recebe (weak, strong) 0-255 pedidos pelo JOGO — igual ao vpad uinput.
    rumble_sink: Callable[[int, int], None] | None = None

    _fd: int | None = None
    _features: dict[int, bytes] = field(default_factory=dict)
    _last_sent: tuple[int, int] = (0, 0)
    _output_count: int = 0
    _rumble_count: int = 0
    _started: bool = False
    _lock: threading.RLock = field(default_factory=threading.RLock)

    @property
    def name(self) -> str:
        return f"Hefesto Virtual DualSense P{self.player}"

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
        """Copia os features do físico trocando o MAC pelo do jogador.

        O probe do hid_playstation recusa MAC repetido (-EEXIST): sem esta troca,
        o vpad só sobe se o controle de onde copiamos estiver desligado.
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
        event += struct.pack("<IIII", DUALSENSE_VENDOR, DUALSENSE_PRODUCT, 0x0100, 0)
        event += descriptor.ljust(HID_MAX_DESCRIPTOR_SIZE, b"\0")[:HID_MAX_DESCRIPTOR_SIZE]
        return event

    # --- input (nós → kernel) --------------------------------------------

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
    "UhidDualSense",
    "capture_dualsense_blueprint",
    "player_mac",
    "uhid_available",
]
