"""pad_usb.py — o dono único de «é pad nosso», e o registro do pad em USB.

POR QUE ESTE MÓDULO EXISTE (O-PAD-VIRTUAL-E-O-SOM-DELE-NASCEM-NO-MESMO-USB-01)
-------------------------------------------------------------------------------

O pad virtual nascia só por ``/dev/uhid``: um HID sem ``usb_device`` pai. Os dois
lados do Wine (o ``winebus`` e o ``winepulse``) calculam o contêiner do aparelho
pela mesma fórmula, a partir do ``usb_device`` pai; sem esse pai comum, o jogo
com a biblioteca da Sony não acha o som do pad e não desiste de procurar (o
engasgo do Sackboy, causa provada em 07/10/2026). A cura dá ao pad um pai USB de
verdade: um gadget ``libcomposite`` só HID (PID ``0df2``), preso ao
``usbip-vudc`` e ligado pelo ``vhci_hcd``.

Com isso o pad passa a existir em DOIS lugares do sysfs:

- o uhid de hoje, em ``/sys/devices/virtual/misc/uhid/``, onde também mora o
  DualSense FÍSICO pelo rádio (o BlueZ cria o HID dele por uhid); e
- o gadget, em ``/sys/devices/platform/vhci_hcd.N/usbX/X-P/``, que tem
  ``usb_device`` pai como um controle no cabo.

Seis lugares perguntavam «é o nosso vpad?» olhando só o ``misc/uhid``, e o
gadget passaria por FÍSICO em todos: o daemon o adotaria como um quinto
controle (medido na rodada 20: o co-op criou o P5) e o broker o esconderia do
jogo. Este módulo é a resposta única; quem pergunta é o ``evdev_reader``, o
``backend_pydualsense``, o ``usb_pai``, a ``sinal_da_barra``, o
``quem_o_jogo_le`` e o ``alto_falante`` (a lista de aparelhos que ganham som).
O broker é autocontido (roda no ``python3`` do sistema, sem
o pacote) e traz um ESPELHO desta função; a régua
``tests/unit/test_o_pad_nasce_no_mesmo_usb_do_som.py`` passa a mesma tabela de
casos pelos dois e reprova a primeira divergência.

AS MARCAS QUE SÓ O PRODUTO ESCREVE
----------------------------------

- ``HID_PHYS`` começando por ``hefesto-vpad`` (o uhid; o gadget herda o ``phys``
  do USB e não a traz);
- ``HID_UNIQ`` com o prefixo ``02:fe`` (o MAC forjado da feature 0x09: o
  ``hid_playstation`` sobrescreve o ``uniq`` com ele depois do probe, nos dois);
- o serial USB começando por ``hefesto-pad-`` (o gadget; antes do probe ele é
  também o ``HID_UNIQ``);
- e um barramento que não é o do rádio (``0005``) sob ``misc/uhid``: USB de
  verdade nunca nasce por uhid.

O Edge FÍSICO (``054c:0df2`` pelo cabo, ou por um ``usbip`` de verdade) não traz
nenhuma das quatro, e continua físico.

100% stdlib de propósito, como o broker e a ``sinal_da_barra``.
"""

from __future__ import annotations

import fcntl
import os
import re
import string
import struct
import threading
import time
from collections.abc import Callable, Iterable

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

VENDOR_SONY = 0x054C

#: O ``HID_PHYS`` que o uhid do pad declara (``uhid_gamepad.VPAD_HID_PHYS``).
VPAD_HID_PHYS = "hefesto-vpad"

#: Os dígitos hex do começo do MAC forjado (``uhid_gamepad.VPAD_MAC_PREFIXO``).
VPAD_UNIQ_PREFIXO = "02fe"

#: O começo do serial USB do gadget. O resto são os 12 hex do MAC do pad.
SERIAL_PREFIXO = "hefesto-pad-"

#: Quantos pads ganham porta USB própria: as oito portas de alta velocidade do
#: ``vhci_hcd.0`` (``CONFIG_USBIP_VHCI_HC_PORTS``, 8 no kernel das distros) e os
#: oito ``vudc`` que o broker carrega (``usbip-vudc num=8``). O teto de quatro
#: era do produto, não do kernel: o Sackboy só inicializa quatro pads, mas o
#: quinto sem porta fica uhid, sem par, e é o HID sem par que faz o jogo varrer
#: o áudio. O dono do teto no broker é ``hidraw_broker.PAD_USB_MAX``.
MAX_PADS_USB = 8

#: Quantas vagas o ``usbip_vudc`` carregado oferece, ou None sem o módulo. O
#: ``modprobe num=8`` não troca o que já está no kernel.
_VAGAS_DO_VUDC = "/sys/module/usbip_vudc/parameters/num"

#: Os módulos do kernel sem os quais o pad continua uhid (a cura 6).
MODULOS_DO_GADGET = ("libcomposite", "usb_f_hid", "usbip_vudc", "vhci_hcd")

#: O ioctl do ``f_hid`` que pré-carrega as features 0x05, 0x09 e 0x20.
CONTRATO_DO_IOCTL = "GADGET_HID_WRITE_GET_REPORT"

BUS_USB = 0x0003
BUS_BT = 0x0005

_SOB_O_UHID = "/misc/uhid/"
_SOB_O_VHCI = "/vhci_hcd."
_RE_USB_DEVICE = re.compile(r"^\d+-[\d.]+$")


def _ler_atributo(caminho: str) -> str:
    """Um atributo do sysfs, "" em qualquer erro (o sysfs some sob a mão)."""
    try:
        with open(caminho, encoding="utf-8", errors="replace") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def _so_hex(valor: str) -> str:
    return "".join(ch for ch in valor.lower() if ch in "0123456789abcdef")


def sob_o_vhci(caminho: str) -> bool:
    """O nó mora sob um ``vhci_hcd`` (o lugar do gadget ligado)."""
    return _SOB_O_VHCI in caminho


def usb_device_do_caminho(caminho: str) -> str:
    """O ``usb_device`` (``X-P``) mais fundo do caminho, ou "" — só texto.

    ``/sys/devices/platform/vhci_hcd.0/usb3/3-1/3-1:1.0/0003:054C:0DF2.0010``
    dá ``/sys/devices/platform/vhci_hcd.0/usb3/3-1``. A interface (``3-1:1.0``)
    e o barramento (``usb3``) não casam o padrão: parar neles casaria o HID só
    consigo mesmo, ou todos os aparelhos da controladora entre si.
    """
    partes = caminho.rstrip("/").split("/")
    for fim in range(len(partes), 0, -1):
        if _RE_USB_DEVICE.match(partes[fim - 1]):
            return "/".join(partes[:fim])
    return ""


def interface_do_gadget(usb_device: str) -> str:
    """A interface ``<bus>-<porta>:1.0`` do gadget — onde o som dele se ancora."""
    usb_device = usb_device.rstrip("/")
    return f"{usb_device}/{os.path.basename(usb_device)}:1.0"


def serial_do_pad(mac: str) -> str:
    """O serial USB do gadget: ``hefesto-pad-`` e os 12 hex do MAC do pad."""
    digitos = _so_hex(mac)
    if len(digitos) != 12:
        raise ValueError(f"MAC do pad sem 12 dígitos: {mac!r}")
    return SERIAL_PREFIXO + digitos


def e_pad_nosso(
    caminho: str,
    *,
    phys: str = "",
    uniq: str = "",
    bus: int | None = None,
    ler: Callable[[str], str] = _ler_atributo,
) -> bool:
    """True quando o nó é um pad do Hefesto — o uhid OU o gadget.

    ``caminho`` é o caminho REAL do HID pai ou de um filho dele (o ``inputN``
    do evdev serve). ``phys``/``uniq``/``bus`` são os do uevent do HID pai
    quando quem chama já os leu; o gadget, se as marcas não bastam, é
    reconhecido pelo serial do ``usb_device`` dele (lido por ``ler``, injetável
    para a régua montar um sysfs de mentira).

    Nunca levanta. O que não se deixa ler não é pad nosso AQUI; a dúvida de
    quem chama (o daemon trata o uhid ilegível como virtual, para não se
    auto-adotar) fica com quem chama, que é quem sabe qual lado é o seguro.
    """
    p = (phys or "").strip().lower()
    u = (uniq or "").strip().lower()
    if p.startswith(VPAD_HID_PHYS):
        return True
    if u.replace(":", "").startswith(VPAD_UNIQ_PREFIXO) or u.startswith(SERIAL_PREFIXO):
        return True
    if _SOB_O_UHID in caminho and bus is not None and bus != BUS_BT:
        return True
    if sob_o_vhci(caminho):
        usb_device = usb_device_do_caminho(caminho)
        if usb_device:
            serial = ler(os.path.join(usb_device, "serial")).lower()
            return serial.startswith(SERIAL_PREFIXO)
    return False


def e_hidraw_de_pad_nosso(
    no: str,
    *,
    raiz_class_hidraw: str = "/sys/class/hidraw",
    ler: Callable[[str], str] = _ler_atributo,
    real: Callable[[str], str] = os.path.realpath,
) -> bool:
    """A mesma pergunta para um ``hidrawN`` — pelo uevent do pai HID dele."""
    base = os.path.basename(no)
    if not base.startswith("hidraw"):
        return False
    dispositivo = os.path.join(raiz_class_hidraw, base, "device")
    try:
        caminho = real(dispositivo)
    except OSError:
        return False
    campos = campos_do_uevent(ler(os.path.join(dispositivo, "uevent")))
    return e_pad_nosso(
        caminho,
        phys=campos.get("HID_PHYS", ""),
        uniq=campos.get("HID_UNIQ", ""),
        bus=bus_do_hid_id(campos.get("HID_ID", "")),
        ler=ler,
    )


def hidraw_do_gadget(
    serial: str,
    *,
    raiz_class_hidraw: str = "/sys/class/hidraw",
    ler: Callable[[str], str] = _ler_atributo,
    real: Callable[[str], str] = os.path.realpath,
) -> tuple[str, str] | None:
    """``(hidrawN, interface)`` do lado do jogo para o gadget de ``serial``.

    É a prova de que o ``hid_playstation`` registrou o pad pelo ``vhci``: o
    ``hidraw`` nasce sob o ``usb_device`` cujo serial é o do gadget. A
    interface volta RELATIVA a ``/sys`` (``/devices/...``), o formato do
    ``sysfs.path`` do PipeWire. None = ainda não enumerou.
    """
    alvo = (serial or "").strip().lower()
    if not alvo.startswith(SERIAL_PREFIXO):
        return None
    try:
        nomes = sorted(os.listdir(raiz_class_hidraw))
    except OSError as exc:
        # Sem a classe hidraw o pad não enumera: o vigia da enumeração vence
        # o prazo e devolve o pad ao uhid; a linha diz por quê.
        logger.debug("pad_usb_classe_hidraw_ilegivel", raiz=raiz_class_hidraw, errno=exc.errno)
        return None
    for nome in nomes:
        if not nome.startswith("hidraw"):
            continue
        caminho = real(os.path.join(raiz_class_hidraw, nome, "device"))
        if not sob_o_vhci(caminho):
            continue
        usb_device = usb_device_do_caminho(caminho)
        if not usb_device:
            continue
        if ler(os.path.join(usb_device, "serial")).strip().lower() != alvo:
            continue
        interface = interface_do_gadget(usb_device)
        indice = interface.find("/devices/")
        return nome, interface[indice:] if indice >= 0 else interface
    return None


def aparelho_presente(
    identidade: str,
    *,
    raiz_class_hidraw: str = "/sys/class/hidraw",
    raiz_class_input: str = "/sys/class/input",
    ler: Callable[[str], str] = _ler_atributo,
    real: Callable[[str], str] = os.path.realpath,
) -> bool:
    """O aparelho de ``identidade`` (o MAC) ainda está na máquina?

    É a pergunta que separa «o aparelho caiu» (o gadget espera o jogo fechar)
    de «o pad trocou de máscara ou a emulação desligou com o aparelho aqui»
    (o gadget desce, senão o jogo vê um DualSense fantasma ao lado do pad
    novo). Procura o MAC no ``HID_UNIQ`` dos ``hidraw`` que não são pad nosso e
    no ``uniq`` dos ``inputN``. Na dúvida (identidade sem os 12 hex, classe
    ilegível) responde True: o lado seguro é não deixar fantasma.
    """
    alvo = _so_hex(identidade or "")
    if len(alvo) != 12:
        return True
    try:
        hidraws = sorted(os.listdir(raiz_class_hidraw))
        inputs = sorted(os.listdir(raiz_class_input))
    except OSError:
        return True
    for nome in hidraws:
        if not nome.startswith("hidraw"):
            continue
        dispositivo = os.path.join(raiz_class_hidraw, nome, "device")
        campos = campos_do_uevent(ler(os.path.join(dispositivo, "uevent")))
        if _so_hex(campos.get("HID_UNIQ", "")) != alvo:
            continue
        if not e_hidraw_de_pad_nosso(nome, raiz_class_hidraw=raiz_class_hidraw, ler=ler,
                                     real=real):
            return True
    for nome in inputs:
        if not nome.startswith("input"):
            continue
        if _so_hex(ler(os.path.join(raiz_class_input, nome, "uniq"))) == alvo:
            return True
    return False


# --- o GET_REPORT do f_hid (linux/usb/g_hid.h) -------------------------------

#: ``_IOR('g', 0x41, __u8)``: o id do GET_REPORT que o jogo pediu e espera.
GADGET_HID_READ_GET_REPORT_ID = 0x80016741
#: ``_IOW('g', 0x42, struct usb_hidg_report)``: a resposta de um GET_REPORT.
GADGET_HID_WRITE_GET_REPORT = 0x40486742
#: ``struct usb_hidg_report`` = id, userspace_req, length, data[64], padding[4].
_USB_HIDG_REPORT = struct.Struct("<BBH64s4x")
_MAX_REPORT_LENGTH = 64


def pacote_do_get_report(report_id: int, dados: bytes) -> bytes:
    """A ``struct usb_hidg_report`` que guarda ``dados`` para todo GET_REPORT futuro."""
    if len(dados) > _MAX_REPORT_LENGTH:
        raise ValueError(f"feature 0x{report_id:02x} com {len(dados)} bytes (> 64)")
    return _USB_HIDG_REPORT.pack(report_id & 0xFF, 0, len(dados), bytes(dados))


def escrever_get_report(
    fd: int,
    report_id: int,
    dados: bytes,
    *,
    ioctl: Callable[[int, int, bytes], object] = fcntl.ioctl,
) -> None:
    """Guarda no ``f_hid`` a resposta do GET_REPORT de ``report_id``.

    Um ``ENOTTY`` aqui é o kernel sem o ``GADGET_HID_WRITE_GET_REPORT``
    (:data:`CONTRATO_DO_IOCTL`): quem chama anota e devolve o pad ao uhid.
    """
    ioctl(fd, GADGET_HID_WRITE_GET_REPORT, pacote_do_get_report(report_id, dados))


def ler_o_id_do_get_report(
    fd: int, *, ioctl: Callable[[int, int, bytes], object] = fcntl.ioctl
) -> int:
    """O id do GET_REPORT pendente (o ``POLLPRI`` do ``/dev/hidgN``)."""
    resposta = ioctl(fd, GADGET_HID_READ_GET_REPORT_ID, b"\0")
    return bytes(resposta)[0] if isinstance(resposta, (bytes, bytearray)) else 0


def campos_do_uevent(texto: str) -> dict[str, str]:
    """Pares chave=valor de um uevent do sysfs."""
    campos: dict[str, str] = {}
    for linha in texto.splitlines():
        chave, sep, valor = linha.partition("=")
        if sep:
            campos[chave.strip()] = valor.strip()
    return campos


def bus_do_hid_id(hid_id: str) -> int | None:
    """O barramento do ``HID_ID`` (``0003:0000054C:00000DF2`` dá 3), ou None."""
    cabeca = hid_id.split(":", 1)[0]
    if not cabeca or cabeca.strip(string.hexdigits):
        return None
    return int(cabeca, 16)


# --- o registro dos gadgets vivos (o som se ancora nele) ---------------------

_TRAVA = threading.Lock()
_INTERFACE_DO_APARELHO: dict[str, str] = {}
_CONTRATO_QUE_FALTOU: list[str] = []
#: ``{serial do gadget: (12 hex do aparelho ou "", prazo monotônico)}``: o gadget
#: montado que ainda não deu a âncora. "" é o pad que montou antes de saber de
#: quem é (o P1 do boot, com o ``primary_uniq`` ainda vazio).
_A_CAMINHO: dict[str, tuple[str, float]] = {}
#: a chave de :data:`_A_CAMINHO` do aparelho que o co-op já pôs na mesa e cujo
#: pad ainda não nasceu (o grab, a calibração e a ordem levam segundos).
_CHAVE_DO_APARELHO = "aparelho:"
#: ``(12 hex de cada aparelho que o co-op viu, prazo monotônico)``: o co-op
#: renova a cada ``sync``; vencido (ou None) = o co-op fora do ar, e nenhum
#: aparelho espera por ele.
_A_MESA_VIU: tuple[frozenset[str], float] | None = None
#: quando o som perguntou pela primeira vez por um aparelho que o co-op ainda
#: não viu: a espera por ele dura no máximo :data:`_POR_DECIDIR_S`.
_PRIMEIRA_PERGUNTA: dict[str, float] = {}
#: uma volta do ``coop.sync`` (2 s) e folga: depois disso, o aparelho que o
#: co-op não viu não é dele (o primário sem MAC, um aparelho que o evdev não
#: lista) e o som cria o endpoint como sempre.
_POR_DECIDIR_S = 5.0


def registrar_gadget(identidade: str, interface: str) -> None:
    """O gadget do aparelho ``identidade`` (12 hex do controle) está de pé.

    ``interface`` é o caminho do sysfs RELATIVO a ``/sys`` (``/devices/...``),
    o mesmo formato do ``sysfs.path`` que o PipeWire publica.
    """
    chave = _so_hex(identidade)
    if not chave or not interface:
        return
    with _TRAVA:
        _INTERFACE_DO_APARELHO[chave] = interface


def esquecer_gadget(identidade: str, interface: str | None = None) -> None:
    """O gadget do aparelho desceu: o som dele volta à âncora emprestada.

    Com ``interface``, só esquece se o registro ainda for o DESTE gadget: o
    aparelho que trocou de pad (o P1 que passou a outro controle, o cedido ao
    primário) já pode estar registrado no gadget novo, e o velho que desce não
    o apaga.
    """
    chave = _so_hex(identidade)
    with _TRAVA:
        if interface is None or _INTERFACE_DO_APARELHO.get(chave) == interface:
            _INTERFACE_DO_APARELHO.pop(chave, None)


def anotar_gadget_a_caminho(serial: str, identidade: str, prazo_s: float) -> None:
    """O gadget de ``serial`` montou e a âncora dele chega em até ``prazo_s``.

    É a ordem que faz o endpoint de háptica NASCER casado: enquanto o gadget do
    aparelho está a caminho, o som não cria o endpoint dele numa âncora
    emprestada (:func:`gadget_a_caminho`). ``identidade`` vazia = o pad ainda
    não sabe de quem é, e espera por todos até saber ou vencer o prazo. A
    identidade que chega depois troca o dono e mantém o prazo da montagem.
    """
    if not serial:
        return
    with _TRAVA:
        ja = _A_CAMINHO.get(serial)
        prazo = ja[1] if ja is not None else time.monotonic() + max(0.0, prazo_s)
        _A_CAMINHO[serial] = (_so_hex(identidade), prazo)


def gadget_chegou(serial: str) -> None:
    """O gadget de ``serial`` deu a âncora, ou desceu: não está mais a caminho."""
    with _TRAVA:
        _A_CAMINHO.pop(serial, None)


def encurtar_a_caminho(serial: str, prazo_s: float) -> None:
    """O gadget de ``serial`` enumerou sem dono: a espera por ele cai para ``prazo_s``.

    O P1 que monta antes de saber de quem é segura o endpoint de TODO aparelho
    até a âncora dele chegar. Enumerado, ele só espera o relógio da identidade
    (uma volta, ~2 s); o que nunca ganha dono não segura o som pela montagem
    inteira.
    """
    with _TRAVA:
        ja = _A_CAMINHO.get(serial)
        if ja is not None:
            _A_CAMINHO[serial] = (ja[0], min(ja[1], time.monotonic() + max(0.0, prazo_s)))


def anotar_pad_a_caminho(identidade: str, prazo_s: float) -> None:
    """O co-op pôs o aparelho ``identidade`` na mesa, e o pad dele vai nascer.

    É o dono único de «este aparelho vai ganhar pad»: o co-op anota ao assentar
    o jogador e :func:`pad_decidido` limpa quando o pad nasce (o gadget, se
    montou, já está anotado pelo serial) ou o jogador sai. Até lá o som espera,
    como espera o gadget a caminho.
    """
    chave = _so_hex(identidade)
    if not chave:
        return
    with _TRAVA:
        _A_CAMINHO[_CHAVE_DO_APARELHO + chave] = (chave, time.monotonic() + max(0.0, prazo_s))


def pad_decidido(identidade: str) -> None:
    """O pad do aparelho nasceu (em USB ou não), ou o jogador saiu da mesa."""
    with _TRAVA:
        _A_CAMINHO.pop(_CHAVE_DO_APARELHO + _so_hex(identidade), None)


def a_mesa_viu(identidades: Iterable[str] | None, validade_s: float) -> None:
    """O co-op leu a mesa: estes aparelhos ele já viu. ``None`` só renova o prazo."""
    global _A_MESA_VIU
    prazo = time.monotonic() + max(0.0, validade_s)
    with _TRAVA:
        if identidades is None:
            if _A_MESA_VIU is None:
                return  # renovar o que nunca foi lido faria todo aparelho esperar
            vistos = _A_MESA_VIU[0]
        else:
            vistos = frozenset(h for h in (_so_hex(i) for i in identidades) if h)
            for chave in vistos:
                _PRIMEIRA_PERGUNTA.pop(chave, None)
        _A_MESA_VIU = (vistos, prazo)


def a_mesa_saiu() -> None:
    """O co-op saiu do ar: nenhum aparelho espera por ele."""
    global _A_MESA_VIU
    with _TRAVA:
        _A_MESA_VIU = None
        _PRIMEIRA_PERGUNTA.clear()


def _por_decidir_locked(chave: str, momento: float) -> bool:
    """O co-op está no ar e ainda não viu este aparelho (por no máximo ``_POR_DECIDIR_S``)."""
    if not chave or _A_MESA_VIU is None:
        return False
    vistos, prazo = _A_MESA_VIU
    if momento >= prazo or chave in vistos:
        return False
    primeira = _PRIMEIRA_PERGUNTA.setdefault(chave, momento)
    return momento - primeira < _POR_DECIDIR_S


def gadget_a_caminho(identidade: str, *, agora: float | None = None) -> bool:
    """Há gadget montado, ainda sem âncora, que pode ser o do aparelho ``identidade``?

    True para o gadget do próprio aparelho e para o que ainda não sabe de quem
    é; o que venceu o prazo não conta (o pad que não enumera volta ao uhid, e o
    aparelho fica com a âncora emprestada de sempre). True também enquanto o
    co-op não decidiu o pad deste aparelho: ele o pôs na mesa e o pad não
    nasceu (:func:`anotar_pad_a_caminho`), ou está no ar e ainda não o viu (o
    controle que entra com o jogo aberto, entre o sysfs e o ``sync``).
    """
    chave = _so_hex(identidade or "")
    momento = time.monotonic() if agora is None else agora
    with _TRAVA:
        for vencido in [s for s, (_i, prazo) in _A_CAMINHO.items() if momento >= prazo]:
            del _A_CAMINHO[vencido]
        if any(dono in ("", chave) for dono, _prazo in _A_CAMINHO.values()):
            return True
        return _por_decidir_locked(chave, momento)


def interface_do_aparelho(identidade: str) -> str | None:
    """A interface do gadget do aparelho, ou None quando ele não tem gadget."""
    with _TRAVA:
        return _INTERFACE_DO_APARELHO.get(_so_hex(identidade))


def anotar_contrato_que_faltou(contrato: str) -> None:
    """O daemon mediu, ao montar, um contrato que o kernel não cumpre."""
    with _TRAVA:
        if contrato and contrato not in _CONTRATO_QUE_FALTOU:
            _CONTRATO_QUE_FALTOU.append(contrato)


def contrato_que_faltou_ao_montar() -> list[str]:
    with _TRAVA:
        return list(_CONTRATO_QUE_FALTOU)


# --- o contrato do kernel (a cura 6) ----------------------------------------


def _modulo_disponivel(
    nome: str,
    *,
    raiz_modulos: str,
    lib_modules: str,
    ler: Callable[[str], str],
    existe: Callable[[str], bool],
) -> bool:
    """O módulo está carregado, embutido no kernel ou instalado para ele."""
    if existe(os.path.join(raiz_modulos, nome)):
        return True
    alvos = {nome, nome.replace("_", "-")}
    for indice in ("modules.builtin", "modules.dep"):
        texto = ler(os.path.join(lib_modules, indice))
        for linha in texto.splitlines():
            caminho = linha.split(":", 1)[0].strip()
            base = os.path.basename(caminho)
            for sufixo in (".ko.zst", ".ko.xz", ".ko.gz", ".ko"):
                if base.endswith(sufixo):
                    base = base[: -len(sufixo)]
                    break
            if base in alvos:
                return True
    return False


def vagas_do_vudc(caminho: str = _VAGAS_DO_VUDC) -> int | None:
    """As vagas do ``usbip_vudc`` carregado; None = o módulo não está no ar."""
    texto = _ler_atributo(caminho)
    return int(texto) if texto.isdigit() else None


def contrato_que_falta(
    *,
    raiz_modulos: str = "/sys/module",
    lib_modules: str | None = None,
    ler: Callable[[str], str] = _ler_atributo,
    existe: Callable[[str], bool] = os.path.exists,
    medidos: Iterable[str] | None = None,
) -> list[str]:
    """Os contratos do kernel que faltam para o pad nascer em USB; [] = todos.

    Os módulos se conferem pelo ``/sys/module`` e pelos índices do
    ``/lib/modules/<release>``. O ``GADGET_HID_WRITE_GET_REPORT`` não se confere
    sem montar um gadget: ele entra aqui quando o daemon o mediu ao montar
    (``ENOTTY`` no ioctl, :func:`anotar_contrato_que_faltou`).
    """
    if lib_modules is None:
        lib_modules = f"/lib/modules/{os.uname().release}"
    faltam = [
        nome
        for nome in MODULOS_DO_GADGET
        if not _modulo_disponivel(
            nome, raiz_modulos=raiz_modulos, lib_modules=lib_modules, ler=ler, existe=existe
        )
    ]
    for contrato in medidos if medidos is not None else contrato_que_faltou_ao_montar():
        if contrato not in faltam:
            faltam.append(contrato)
    return faltam


__all__ = [
    "CONTRATO_DO_IOCTL",
    "GADGET_HID_READ_GET_REPORT_ID",
    "GADGET_HID_WRITE_GET_REPORT",
    "MAX_PADS_USB",
    "MODULOS_DO_GADGET",
    "SERIAL_PREFIXO",
    "VPAD_HID_PHYS",
    "VPAD_UNIQ_PREFIXO",
    "a_mesa_saiu",
    "a_mesa_viu",
    "anotar_contrato_que_faltou",
    "anotar_gadget_a_caminho",
    "anotar_pad_a_caminho",
    "aparelho_presente",
    "bus_do_hid_id",
    "campos_do_uevent",
    "contrato_que_falta",
    "contrato_que_faltou_ao_montar",
    "e_hidraw_de_pad_nosso",
    "e_pad_nosso",
    "encurtar_a_caminho",
    "escrever_get_report",
    "esquecer_gadget",
    "gadget_a_caminho",
    "gadget_chegou",
    "hidraw_do_gadget",
    "interface_do_aparelho",
    "interface_do_gadget",
    "ler_o_id_do_get_report",
    "pacote_do_get_report",
    "pad_decidido",
    "registrar_gadget",
    "serial_do_pad",
    "sob_o_vhci",
    "usb_device_do_caminho",
    "vagas_do_vudc",
]
