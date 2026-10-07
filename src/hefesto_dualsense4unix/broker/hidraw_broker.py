#!/usr/bin/env python3
"""hefesto-hidraw-broker — broker root que esconde o hidraw do DualSense FÍSICO.

BROKER-01 (FUT-01/PLAT-02), reimplementado na Onda S com FD-INJECTION: daemon,
Steam e o jogo rodam com o MESMO uid, então o DAC não separa quem pode abrir o
hidraw do físico. Este serviço (o PRIMEIRO serviço systemd de SISTEMA do
projeto) roda como root isolado/hardened e, a pedido do daemon:

  - `hide`/`restore`: tira/devolve a ACL do uaccess do nó (`setfacl -b` +
    `chmod 0600`  `chmod 0660` + ACL `u:<uid>:rw`) — o jogo não consegue mais
    `open(2)`, em QUALQUER backend (SDL, winebus-hidraw, libScePad, HIDAPI).
    O fd JÁ ABERTO do daemon sobrevive: permissão só é checada no open(2).
  - `expose`/`unexpose` (O-NO-NASCE-FECHADO-01, 2026-09-20): a lease
    INVERTIDA. Com o `assets/73-hefesto-ps5-controller.rules` da cura, o nó do físico
    NASCE `0600 root` (`TAG-="uaccess"`) e o broker é quem o abre — enquanto
    alguém pedir. É para quem só sabe `open(path)` e não pode receber fd: o
    `hidapi.Device(path=...)` do handle de controle do daemon, e o JOGO no
    Modo Nativo. Mesmo refcount, mesmo EOF e mesmo fail-safe do `hide`.
  - `open` (NOVO, desenho 2026-07-20): valida o nó, abre O_RDWR|O_CLOEXEC como
    root e devolve o fd via SCM_RIGHTS na MESMA conexão — o motion reader do
    daemon NUNCA reabre por caminho, então o hide deixa de ter qualquer
    interação com o ciclo de vida do gyro (a classe de bugs broker/motion morre).
  - os nós de ENTRADA (HIDE-SO-O-HIDRAW-02, 24/09/2026): o evdev e o joydev
    do MESMO aparelho seguem o hidraw — fechados com ele, e abertos só pelo
    pedido do Modo Nativo (`expose` com `"entradas": true`). O `open` serve
    também o `/dev/input/eventN` do físico, que é por onde o daemon lê o
    gamepad, o touchpad e os sensores de movimento.

Desenho vigente: o estudo «desenho-onda-s-broker-fd-injection» de 20/07/2026
(spec original da mecânica ACL: o estudo «estudo-broker-hide-hidraw» de 18/07/2026).

Regras de ouro (invariante "duplicado > zero controles"):
  - A conexão do daemon É a lease: EOF (daemon morreu) restaura TUDO que aquela
    conexão escondeu — sem heartbeat, o kernel garante o EOF.
  - `--restore-all-and-exit` (ExecStartPre/ExecStopPost) restaura qualquer
    físico deixado escondido por uma vida anterior do broker.
  - Um nó NUNCA é "esquecido" com o fs em 0600: só sai do rastreio DEPOIS do
    restore de fs verificado (lição 2 da auditoria que parkou a 1ª versão).
  - A lease é do APARELHO, e não do nome (29/09/2026): ela guarda o pai HID
    do nó no pedido, e o nome cujo pai mudou ou sumiu sai do rastreio sem
    tocar no fs (`_podar_o_que_saiu`). O `0600` do aparelho que saiu não
    existe mais, e o aparelho que herdou o nome não é do usuário.
  - O validador SÓ aceita hidraw cujo pai HID imediato tem HID_ID de DualSense
    físico (054c:0ce6, ou o Edge 054c:0df2, em USB 0003 ou BT 0005). O NOSSO
    vpad também anuncia 0df2, e é REJEITADO pela topologia e pela identidade
    (D1/D2 abaixo) — é por ele que o jogo fala com o controle.
  - ARMADILHA BLUEZ-UHID-01: com BlueZ ≥5.73 os controles BT FÍSICOS moram em
    /devices/virtual/misc/uhid/ — topologia NÃO é veredito; a identidade vem
    do uevent do pai HID (HID_ID/HID_PHYS/HID_UNIQ), como no fix do daemon.

ESCOLHA DE IMPLEMENTAÇÃO DA ACL (documentada, exigência da spec §5.2): xattr
direto via `os.setxattr`/`os.removexattr` no `system.posix_acl_access` — é o
MESMO xattr que a rota ctypes→libacl escreveria (`acl_set_file` é um setxattr
deste blob) e que o `setfacl` produz. Verificado byte a byte ao vivo na máquina
de referência (blob de 44 bytes, header versão 2 LE + entradas `<HHI`). Ganhos
sobre as duas rotas do estudo: ZERO execve (o `SystemCallFilter=@system-service
~@privileged` da unit fica intacto — `setxattr` já está em `@file-system`) e
zero dependência de ABI da libacl.so. Formato estável do kernel
(`include/uapi/linux/posix_acl_xattr.h`).

TOCTOU/minor-reuse (lição 5): toda operação de fs é PINADA por inode — O_PATH
no nó + `fstat` cruzado com o rdev do sysfs; hide/restore agem via
`/proc/self/fd/N` (ProcSubset=pid mantém /proc/self acessível) e o cmd `open`
revalida o rdev NO PRÓPRIO fd depois do open(2).

Arquivo 100% stdlib e AUTOCONTIDO de propósito: o install copia só este arquivo
para /usr/local/lib/hefesto-dualsense4unix/hefesto-hidraw-broker e ele roda no
python3 do sistema, sem venv e sem importar o pacote.
"""
from __future__ import annotations

import argparse
import contextlib
import errno
import fcntl
import hashlib
import json
import os
import re
import selectors
import signal
import socket
import stat as stat_mod
import struct
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

DEFAULT_SOCKET_PATH = "/run/hefesto-hidraw-broker/broker.sock"
#: Env com o uid autorizado (renderizado pelo install a partir de SUDO_UID).
ALLOWED_UID_ENV = "HEFESTO_BROKER_ALLOWED_UID"
#: controller.rules` instalado FECHA o nó do DualSense físico (`TAG-="uaccess"`, 0600
NO_NASCE_FECHADO_ENV = "HEFESTO_BROKER_NO_NASCE_FECHADO"
MAX_LINE_BYTES = 4096

PHYS_VENDOR = 0x054C
PHYS_PRODUCT = 0x0CE6  # DualSense físico
VPAD_PRODUCT = 0x0DF2  # DualSense Edge: o do NOSSO vpad e o do Edge físico
#: STEAM-NO-FISICO-01 (24/09/2026) — os PIDs de DualSense FÍSICO que o broker
PHYS_PRODUCTS = frozenset({PHYS_PRODUCT, VPAD_PRODUCT})
BUS_USB = 0x0003
BUS_BT = 0x0005
ACCEPTED_BUSES = frozenset({BUS_USB, BUS_BT})

#: Identidade do vpad no HID — espelhada de `core/backend_pydualsense.py`
VPAD_PHYS_PREFIX = "hefesto-vpad"
VPAD_UNIQ_PREFIX = "02fe"
#: O começo do serial USB do pad em USB (``pad_usb.SERIAL_PREFIXO``).
PAD_USB_SERIAL_PREFIX = "hefesto-pad-"
_USB_DEVICE_RE = re.compile(r"^\d+-[\d.]+$")

_HIDRAW_BASE_RE = re.compile(r"^hidraw[0-9]+$")

# mesmo DualSense aparece em três superfícies: o hidraw, o evdev
# (`/dev/input/eventN`: o gamepad, o touchpad, os sensores de movimento e a
DEV_INPUT_ROOT = "/dev/input"
_ENTRADA_BASE_RE = re.compile(r"^(event|js)[0-9]+$")
_EVENT_BASE_RE = re.compile(r"^event[0-9]+$")
_SUFIXO_DO_MOVIMENTO = "Motion Sensors"
_EVIOCGID = 0x80084502
_INPUT_ID_FMT = "=HHHH"

REINICIO_SEM_ABRIR_PATH = "/run/hefesto-hidraw-broker/reinicio-sem-abrir"
REINICIO_SEM_ABRIR_VALIDADE_S = 120.0

_HIDIOCGRAWINFO = 0x80084803
_HIDRAW_DEVINFO_FMT = "=Ihh"


def _hidraw_devinfo_identity_ok(vendor: int, product: int) -> bool:
    """True sse (vendor, product) do devinfo é um DualSense 054c:0ce6/0df2.

    A família que `validate_physical_node` aceita — nunca device alheio. O
    devinfo não separa o Edge físico do nosso vpad (os dois são 0003:054c:0df2
    pelo cabo); quem separa é a topologia, e ela já foi julgada no
    `validate_physical_node` antes do open. O pior caso de uma corrida aqui é
    servir o vpad, que já é `0660` da sessão — nenhum acesso novo.
    vendor/product vêm do kernel como __s16 assinado; a máscara 0xFFFF
    normaliza a representação.
    """
    return (vendor & 0xFFFF) == PHYS_VENDOR and (product & 0xFFFF) in PHYS_PRODUCTS


_HID_ID_VALUE_RE = re.compile(r"^([0-9A-Fa-f]{4}):([0-9A-Fa-f]{8}):([0-9A-Fa-f]{8})$")
_MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")


def _log(event: str, **fields: object) -> None:
    """Log estruturado simples no stdout (vai ao journal via systemd)."""
    parts = [event] + [f"{key}={value}" for key, value in fields.items()]
    print("[hidraw-broker] " + " ".join(parts), flush=True)


# Validador — SÓ nós filhos do DualSense físico 054c:0ce6/0df2 (BLUEZ-UHID-01)


def canonical_hidraw_base(node: object, *, dev_root: str = "/dev") -> str | None:
    """Basename `hidrawN` se `node` é EXATAMENTE `<dev_root>/hidrawN`; senão None."""
    if not isinstance(node, str) or not node:
        return None
    base = os.path.basename(node)
    if _HIDRAW_BASE_RE.match(base) is None:
        return None
    if node != f"{dev_root}/{base}":
        return None
    return base


def _parse_uevent_text(raw: str) -> dict[str, str]:
    """Pares chave=valor do texto de um uevent do sysfs."""
    pares: dict[str, str] = {}
    for linha in raw.splitlines():
        chave, sep, valor = linha.partition("=")
        if sep:
            pares[chave.strip()] = valor.strip()
    return pares


def _adapter_addresses(sys_class_bluetooth: str) -> set[str] | None:
    """MACs (minúsculos) dos adaptadores hci*; None = sysfs BT ilegível.

    Belt D4 do validador: SÓ pode rejeitar quando a leitura FUNCIONOU — sysfs
    instável (adaptador down, rfkill, hci sem `address` legível — visto ao
    vivo) devolve None/conjunto vazio e NÃO decide. Nunca pode matar um
    DualSense BT real por sysfs instável.
    """
    try:
        entries = os.listdir(sys_class_bluetooth)
    except OSError:
        return None
    addresses: set[str] = set()
    for entry in sorted(entries):
        try:
            with open(
                f"{sys_class_bluetooth}/{entry}/address", encoding="ascii", errors="replace"
            ) as fh:
                address = fh.read().strip().lower()
        except OSError:
            continue
        if _MAC_RE.match(address) is not None:
            addresses.add(address)
    return addresses


def _e_o_nosso_vpad(uevent: dict[str, str], hid_parent: str, bus: int) -> bool:
    """True quando o pai HID é um pad do daemon (D1/D2), qualquer que seja o PID.

    ESPELHO de ``integrations/pad_usb.e_pad_nosso`` (O-PAD-VIRTUAL-E-O-SOM-DELE-
    NASCEM-NO-MESMO-USB-01, 07/10/2026): este arquivo roda no ``python3`` do
    sistema, sem o pacote, e não pode importá-lo. A régua
    ``tests/unit/test_o_pad_nasce_no_mesmo_usb_do_som.py`` passa a mesma tabela
    pelas duas funções e reprova a primeira divergência. O pad é o uhid de
    sempre OU o gadget USB sob o ``vhci_hcd``, que tem ``usb_device`` pai como
    um controle no cabo e passaria por físico sem a última perna.
    """
    phys = uevent.get("HID_PHYS", "").strip().lower()
    uniq = uevent.get("HID_UNIQ", "").strip().lower()
    if phys.startswith(VPAD_PHYS_PREFIX):
        return True
    if uniq.replace(":", "").startswith(VPAD_UNIQ_PREFIX) or uniq.startswith(
        PAD_USB_SERIAL_PREFIX
    ):
        return True
    if "/misc/uhid/" in hid_parent and bus != BUS_BT:
        return True
    if "/vhci_hcd." in hid_parent:
        usb_device = _usb_device_do_caminho(hid_parent)
        if usb_device:
            try:
                with open(f"{usb_device}/serial", encoding="utf-8", errors="replace") as fh:
                    serial = fh.read().strip().lower()
            except OSError:
                return False
            return serial.startswith(PAD_USB_SERIAL_PREFIX)
    return False


def _usb_device_do_caminho(caminho: str) -> str:
    """O ``usb_device`` (``X-P``) mais fundo do caminho — espelho do ``pad_usb``."""
    partes = caminho.rstrip("/").split("/")
    for fim in range(len(partes), 0, -1):
        if _USB_DEVICE_RE.match(partes[fim - 1]):
            return "/".join(partes[:fim])
    return ""


def validate_physical_node(
    node: object,
    *,
    dev_root: str = "/dev",
    sys_class_hidraw: str = "/sys/class/hidraw",
    sys_class_bluetooth: str = "/sys/class/bluetooth",
    stat_fn: Callable[[str], Any] = os.stat,
    lstat_fn: Callable[[str], Any] = os.lstat,
) -> str | None:
    """Basename canônico `hidrawN` se `node` é DualSense FÍSICO 054c:0ce6/0df2; senão None.

    NUNCA abre o device. Barreiras, na ordem (1-3 e 5 herdadas do parkado; a 4
    é a decisão BLUEZ-UHID-01 do desenho de 2026-07-20):
      1. caminho canônico literal (`canonical_hidraw_base`);
      2. o nó não pode ser symlink e PRECISA ser char device;
      3. `(major, minor)` do nó casa o `/sys/class/hidraw/<base>/dev` (fecha
         "symlink/nó plantado apontando para outro device");
      4. identidade do pai HID imediato (uevent): `HID_ID` zero-preenchido
         BUS:VVVV:PPPP com bus∈{0003,0005}, vendor 054C, product 0CE6 ou 0DF2
         (o Edge; o NOSSO vpad também é 0DF2 e cai no D1/D2; 057E Nintendo
         cai no vendor) + regras da subárvore `/devices/virtual/misc/uhid/`:
           D1. USB real NUNCA é uhid — bus 0003 sob uhid = forjado;
           D2. identidade do NOSSO vpad (HID_PHYS `hefesto-vpad*` ou HID_UNIQ
               prefixo 02:fe) rejeita mesmo anunciando 0CE6;
           D3. BT real tem HID_UNIQ = MAC do controle e HID_PHYS = MAC do
               adaptador (bem-formados);
           D4. belt best-effort: HID_PHYS deve casar o address de algum hci*
               — SÓ rejeita se a leitura dos adaptadores funcionou e nenhum
               casou (sysfs BT ilegível/vazio não decide).
         `/devices/virtual/` FORA de `/misc/uhid/` (uinput puro) jamais é
         físico. Topologia NUNCA é veredito de aceitação — só a identidade.
      5. o caminho do cliente nunca é reconcatenado — só o basename validado.

    uevent ilegível ⇒ None (fail-closed): o broker é o INVERSO do daemon aqui
    — em `_is_virtual_hidraw` a dúvida vira "virtual" porque o risco maior lá
    é auto-adoção; aqui a dúvida vira "rejeita" porque o risco maior é agir
    sobre nó errado. As duas escolhas derivam do mesmo "na dúvida, o lado
    seguro". `stat_fn`/`lstat_fn` são injetáveis só para os testes herméticos
    (não dá para criar char device sem root); default = os.stat/os.lstat.
    """
    if not isinstance(node, str):
        return None
    base = canonical_hidraw_base(node, dev_root=dev_root)
    if base is None:
        return None
    sys_dir = f"{sys_class_hidraw}/{base}"
    try:
        if stat_mod.S_ISLNK(lstat_fn(node).st_mode):
            return None
        st = stat_fn(node)
        if not stat_mod.S_ISCHR(st.st_mode):
            return None
        with open(f"{sys_dir}/dev", encoding="ascii") as fh:
            dev_sysfs = fh.read().strip()
        if dev_sysfs != f"{os.major(st.st_rdev)}:{os.minor(st.st_rdev)}":
            return None
        hid_parent = os.path.realpath(f"{sys_dir}/device")
        with open(f"{sys_dir}/device/uevent", encoding="ascii", errors="replace") as fh:
            uevent = _parse_uevent_text(fh.read())
    except OSError:
        return None
    if not _pai_hid_e_dualsense_fisico(
        hid_parent, uevent, sys_class_bluetooth=sys_class_bluetooth
    ):
        return None
    return base


def _pai_hid_e_dualsense_fisico(
    hid_parent: str, uevent: dict[str, str], *, sys_class_bluetooth: str
) -> bool:
    """A barreira 4 do validador: o pai HID é um DualSense FÍSICO?

    HIDE-SO-O-HIDRAW-02 (24/09/2026): extraída do `validate_physical_node`
    sem mudar uma vírgula do critério, porque o nó de ENTRADA
    (`validate_physical_input_node`) tem de responder a MESMA pergunta sobre o
    mesmo pai HID. Duas cópias do D1-D4 divergiriam na primeira correção — e
    a divergência seria o broker abrir por um caminho o vpad que recusa pelo
    outro.
    """
    match = _HID_ID_VALUE_RE.match(uevent.get("HID_ID", ""))
    if match is None:
        return False
    bus = int(match.group(1), 16)
    vendor = int(match.group(2), 16)
    product = int(match.group(3), 16)
    if bus not in ACCEPTED_BUSES or vendor != PHYS_VENDOR:
        return False
    if product not in PHYS_PRODUCTS:
        return False
    if "/vhci_hcd." in hid_parent and _e_o_nosso_vpad(uevent, hid_parent, bus):
        return False  # o pad em USB: tem pai USB, mas é o que o Hefesto entrega ao jogo
    if "/devices/virtual/" in hid_parent:
        if "/misc/uhid/" not in hid_parent:
            return False
        if bus != BUS_BT:
            return False
        phys = uevent.get("HID_PHYS", "").strip().lower()
        uniq = uevent.get("HID_UNIQ", "").strip().lower()
        if phys.startswith(VPAD_PHYS_PREFIX):
            return False
        if uniq.replace(":", "").startswith(VPAD_UNIQ_PREFIX):
            return False
        if _MAC_RE.match(uniq) is None:
            return False
        if _MAC_RE.match(phys) is None:
            return False  # (D3) BT real tem HID_PHYS = MAC do adaptador
        adapters = _adapter_addresses(sys_class_bluetooth)
        if adapters is not None and adapters and phys not in adapters:
            return False
    return True


def canonical_input_base(node: object, *, dev_input_root: str = DEV_INPUT_ROOT) -> str | None:
    """Basename `eventN` se `node` é EXATAMENTE `<dev_input_root>/eventN`; senão None."""
    if not isinstance(node, str) or not node:
        return None
    base = os.path.basename(node)
    if _EVENT_BASE_RE.match(base) is None:
        return None
    if node != f"{dev_input_root}/{base}":
        return None
    return base


def validate_physical_input_node(
    node: object,
    *,
    dev_input_root: str = DEV_INPUT_ROOT,
    sys_class_input: str = "/sys/class/input",
    sys_class_bluetooth: str = "/sys/class/bluetooth",
    stat_fn: Callable[[str], Any] = os.stat,
    lstat_fn: Callable[[str], Any] = os.lstat,
) -> str | None:
    """Basename `eventN` se `node` é um nó de ENTRADA de DualSense FÍSICO; senão None.

    HIDE-SO-O-HIDRAW-02 (24/09/2026). O daemon lê o gamepad, o touchpad e os
    sensores de movimento pelo evdev, e com esses nós nascendo `0600 root` o
    único jeito de ele continuar lendo é o broker servir o fd, como já serve
    o do hidraw. Mesmas barreiras do `validate_physical_node`, na mesma ordem:

      1. caminho canônico literal (`canonical_input_base`);
      2. nem symlink, e char device;
      3. `(major, minor)` do nó casa `/sys/class/input/<base>/dev`;
      4. o pai HID do nó (`<base>/device` é o `inputNN`, e o `device` dele é
         o device HID) passa pelo MESMO `_pai_hid_e_dualsense_fisico` — o
         vpad é recusado aqui pelas mesmas marcas D1/D2 que o recusam no
         hidraw.

    NUNCA abre o device; na dúvida, recusa (fail-closed, como o do hidraw).
    """
    if not isinstance(node, str):
        return None
    base = canonical_input_base(node, dev_input_root=dev_input_root)
    if base is None:
        return None
    sys_dir = f"{sys_class_input}/{base}"
    try:
        if stat_mod.S_ISLNK(lstat_fn(node).st_mode):
            return None
        st = stat_fn(node)
        if not stat_mod.S_ISCHR(st.st_mode):
            return None
        with open(f"{sys_dir}/dev", encoding="ascii") as fh:
            dev_sysfs = fh.read().strip()
        if dev_sysfs != f"{os.major(st.st_rdev)}:{os.minor(st.st_rdev)}":
            return None
        hid_parent = os.path.realpath(f"{sys_dir}/device/device")
        with open(f"{hid_parent}/uevent", encoding="ascii", errors="replace") as fh:
            uevent = _parse_uevent_text(fh.read())
    except OSError:
        return None
    if not _pai_hid_e_dualsense_fisico(
        hid_parent, uevent, sys_class_bluetooth=sys_class_bluetooth
    ):
        return None
    return base


_ACL_XATTR = "system.posix_acl_access"
_SEM_ACL = frozenset({errno.ENODATA, errno.EOPNOTSUPP})
_ACL_VERSION = 2
_ACL_TAG_USER_OBJ = 0x01
_ACL_TAG_USER = 0x02
_ACL_TAG_GROUP_OBJ = 0x04
_ACL_TAG_MASK = 0x10
_ACL_TAG_OTHER = 0x20
_ACL_PERM_RW = 0x06
_ACL_ID_UNDEFINED = 0xFFFFFFFF


def encode_access_acl(uid: int) -> bytes:
    """ACL binária equivalente a `chmod 0660` + `setfacl -m u:<uid>:rw`."""
    entries = (
        (_ACL_TAG_USER_OBJ, _ACL_PERM_RW, _ACL_ID_UNDEFINED),
        (_ACL_TAG_USER, _ACL_PERM_RW, uid),
        (_ACL_TAG_GROUP_OBJ, _ACL_PERM_RW, _ACL_ID_UNDEFINED),
        (_ACL_TAG_MASK, _ACL_PERM_RW, _ACL_ID_UNDEFINED),
        (_ACL_TAG_OTHER, 0x00, _ACL_ID_UNDEFINED),
    )
    return struct.pack("<I", _ACL_VERSION) + b"".join(
        struct.pack("<HHI", tag, perm, eid) for tag, perm, eid in entries
    )


def decode_acl_user_uids(blob: bytes) -> set[int]:
    """uids com entrada USER de leitura+escrita na ACL binária (verificação)."""
    uids: set[int] = set()
    if len(blob) < 4 or struct.unpack("<I", blob[:4])[0] != _ACL_VERSION:
        return uids
    offset = 4
    while offset + 8 <= len(blob):
        tag, perm, eid = struct.unpack("<HHI", blob[offset : offset + 8])
        if tag == _ACL_TAG_USER and perm & _ACL_PERM_RW == _ACL_PERM_RW:
            uids.add(eid)
        offset += 8
    return uids


class StaleNodeError(Exception):
    """O nome `hidrawN` foi reciclado para OUTRO device entre validar e agir."""


class FsAclOps:
    """Operações REAIS de fs (hide/restore/verify/open) — injetável nos testes."""

    def __init__(
        self,
        *,
        sys_class_hidraw: str = "/sys/class/hidraw",
        dev_input_root: str = DEV_INPUT_ROOT,
        sys_class_input: str = "/sys/class/input",
        sys_class_bluetooth: str = "/sys/class/bluetooth",
    ) -> None:
        self._sys_class_hidraw = sys_class_hidraw
        self._dev_input_root = dev_input_root
        self._sys_class_input = sys_class_input
        self._sys_class_bluetooth = sys_class_bluetooth

    def _sysfs_rdev(self, base: str) -> tuple[int, int] | None:
        """(major, minor) de /sys/class/hidraw/<base>/dev; None = ilegível."""
        try:
            with open(f"{self._sys_class_hidraw}/{base}/dev", encoding="ascii") as fh:
                raw = fh.read().strip()
            major_s, sep, minor_s = raw.partition(":")
            if not sep:
                return None
            return (int(major_s), int(minor_s))
        except (OSError, ValueError):
            return None

    def _sysfs_hid_identity_ok(self, base: str) -> bool:
        """True sse o pai HID de `base` é DualSense 054c:0ce6/0df2 FÍSICO, OU o
        uevent é ILEGÍVEL. Cinto do S-4 contra minor-reuse no hide/restore (o fd
        O_PATH do _pin não faz HIDIOCGRAWINFO): re-lê o HID_ID do uevent;
        identidade legível e != DualSense ⇒ False (gone, nunca chmod/ACL num
        device alheio). Ilegível ⇒ True: esconder/apagar o uevent exige root, e
        um atacante não-root (a ameaça do minor-reuse) nunca chega a esse estado.

        STEAM-NO-FISICO-01: desde que o Edge físico (0df2) entrou, o PID não
        separa mais o físico do NOSSO vpad — os dois são 0003:054C:0DF2 pelo
        cabo. O cinto então pergunta também o que só o vpad tem
        (`_e_o_nosso_vpad`): um nome reciclado para um vpad NUNCA recebe chmod,
        porque fechar o vpad é tirar o controle do jogo.
        """
        try:
            with open(
                f"{self._sys_class_hidraw}/{base}/device/uevent", encoding="ascii"
            ) as fh:
                uevent = _parse_uevent_text(fh.read())
        except OSError:
            return True
        match = _HID_ID_VALUE_RE.match(uevent.get("HID_ID", ""))
        if match is None:
            return False  # sem HID_ID (ou malformado) = não é o DualSense validado
        if int(match.group(2), 16) != PHYS_VENDOR:
            return False
        if int(match.group(3), 16) not in PHYS_PRODUCTS:
            return False
        pai = os.path.realpath(f"{self._sys_class_hidraw}/{base}/device")
        return not _e_o_nosso_vpad(uevent, pai, int(match.group(1), 16))

    def pai_hid_do_no(self, base: str) -> str | None:
        """O aparelho que o nome `base` é AGORA: o pai HID dele. Só leitura."""
        classe = f"{self._sys_class_hidraw}/{base}"
        try:
            os.lstat(classe)
        except FileNotFoundError:
            return ""
        except OSError:
            return None
        try:
            os.readlink(f"{classe}/device")
        except OSError:
            return None
        return os.path.realpath(f"{classe}/device")

    def _pin(self, node: str, base: str) -> int | None:
        """O_PATH no nó + fstat cruzado com o sysfs. None = sumiu/reciclado (gone)."""
        try:
            fd = os.open(node, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC)
        except OSError:
            return None
        st = os.fstat(fd)
        if not stat_mod.S_ISCHR(st.st_mode) or self._sysfs_rdev(base) != (
            os.major(st.st_rdev),
            os.minor(st.st_rdev),
        ):
            os.close(fd)
            return None
        if not self._sysfs_hid_identity_ok(base):
            os.close(fd)
            return None
        return fd

    def hide(self, node: str, base: str) -> None:
        """`setfacl -b` + `chmod 0600` → só root abre. Fd já aberto sobrevive."""
        fd = self._pin(node, base)
        if fd is None:
            raise FileNotFoundError(node)
        try:
            ref = f"/proc/self/fd/{fd}"
            if self._ja_esta_no_alvo(fd, None):
                return
            with contextlib.suppress(OSError):
                os.removexattr(ref, _ACL_XATTR)
            os.chmod(ref, 0o600)
        finally:
            os.close(fd)

    def restore(self, node: str, base: str, uid: int) -> None:
        """`chmod 0660` + ACL `u:<uid>:rw` — reverte exatamente o hide."""
        fd = self._pin(node, base)
        if fd is None:
            raise FileNotFoundError(node)
        try:
            ref = f"/proc/self/fd/{fd}"
            if self._ja_esta_no_alvo(fd, uid):
                return
            os.chmod(ref, 0o660)
            os.setxattr(ref, _ACL_XATTR, encode_access_acl(uid))
        finally:
            os.close(fd)

    @staticmethod
    def _ja_esta_no_alvo(fd: int, uid: int | None) -> bool:
        """O nó pinado já está como a escrita o deixaria? Na dúvida, «não»."""
        try:
            modo = stat_mod.S_IMODE(os.fstat(fd).st_mode)
        except OSError:
            return False
        ref = f"/proc/self/fd/{fd}"
        if uid is None:
            if modo != 0o600:
                return False
            try:
                os.getxattr(ref, _ACL_XATTR)
            except OSError as exc:
                return exc.errno in _SEM_ACL
            return False
        if modo != 0o660:
            return False
        try:
            return os.getxattr(ref, _ACL_XATTR) == encode_access_acl(uid)
        except OSError:
            return False

    def is_exposed_to(self, node: str, uid: int) -> bool:
        """True se o nó está no estado canônico exposto (0660 + ACL do uid)."""
        try:
            st = os.stat(node)
            if stat_mod.S_IMODE(st.st_mode) != 0o660:
                return False
            blob = os.getxattr(node, _ACL_XATTR)
        except OSError:
            return False
        return uid in decode_acl_user_uids(blob)

    def open_node(self, node: str, base: str) -> int:
        """open(2) O_RDWR|O_CLOEXEC|O_NOFOLLOW + revalidação pós-open NO fd."""
        fd = os.open(node, os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            st = os.fstat(fd)
        except OSError:
            os.close(fd)
            raise
        if not stat_mod.S_ISCHR(st.st_mode) or self._sysfs_rdev(base) != (
            os.major(st.st_rdev),
            os.minor(st.st_rdev),
        ):
            os.close(fd)
            raise StaleNodeError(node)
        # HIDIOCGRAWINFO prova que o fd É um DualSense 054c:0ce6/0df2 (à prova de
        try:
            buf = bytearray(struct.calcsize(_HIDRAW_DEVINFO_FMT))
            fcntl.ioctl(fd, _HIDIOCGRAWINFO, buf, True)
            _bus, vendor, product = struct.unpack(_HIDRAW_DEVINFO_FMT, bytes(buf))
        except OSError:
            os.close(fd)
            raise StaleNodeError(node) from None
        if not _hidraw_devinfo_identity_ok(vendor, product):
            os.close(fd)
            raise StaleNodeError(node)
        if not self._sysfs_hid_identity_ok(base):
            os.close(fd)
            raise StaleNodeError(node)
        return fd


    def entradas_do_no(self, base: str) -> list[tuple[str, str]]:
        """`(nó em /dev/input, diretório dele no sysfs)` de cada nó de entrada do aparelho."""
        try:
            hid = os.path.realpath(f"{self._sys_class_hidraw}/{base}/device")
            with open(f"{hid}/uevent", encoding="ascii", errors="replace") as fh:
                uevent = _parse_uevent_text(fh.read())
            inputs = sorted(os.listdir(f"{hid}/input"))
        except OSError:
            return []
        if not _pai_hid_e_dualsense_fisico(
            hid, uevent, sys_class_bluetooth=self._sys_class_bluetooth
        ):
            return []
        saida: list[tuple[str, str]] = []
        for pasta in inputs:
            if not pasta.startswith("input"):
                continue
            input_dir = f"{hid}/input/{pasta}"
            try:
                with open(f"{input_dir}/name", encoding="utf-8", errors="replace") as fh:
                    nome = fh.read().strip()
                filhos = sorted(os.listdir(input_dir))
            except OSError:
                continue
            for filho in filhos:
                if _ENTRADA_BASE_RE.match(filho) is None:
                    continue
                if filho.startswith("js") and nome.endswith(_SUFIXO_DO_MOVIMENTO):
                    continue
                saida.append((f"{self._dev_input_root}/{filho}", f"{input_dir}/{filho}"))
        return saida

    _e_char_device = staticmethod(stat_mod.S_ISCHR)

    def _pin_entrada(self, node: str, sys_dir: str) -> int | None:
        """O_PATH no nó de entrada + fstat cruzado com o `dev` do sysfs DELE."""
        try:
            fd = os.open(node, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC)
        except OSError:
            return None
        try:
            st = os.fstat(fd)
            with open(f"{sys_dir}/dev", encoding="ascii") as fh:
                dev_sysfs = fh.read().strip()
        except OSError:
            os.close(fd)
            return None
        if not self._e_char_device(st.st_mode) or dev_sysfs != (
            f"{os.major(st.st_rdev)}:{os.minor(st.st_rdev)}"
        ):
            os.close(fd)
            return None
        return fd

    @staticmethod
    def _entrada_aberta_a_alguem(st: os.stat_result) -> bool:
        """O nó abre para alguém além do root?"""
        return stat_mod.S_IMODE(st.st_mode) & 0o077 != 0

    def fechar_entradas(self, base: str) -> tuple[list[str], list[str]]:
        """`setfacl -b` + `chmod 0600` em cada nó de entrada: `(mudados, falhos)`."""
        mudados: list[str] = []
        falhos: list[str] = []
        for node, sys_dir in self.entradas_do_no(base):
            fd = self._pin_entrada(node, sys_dir)
            if fd is None:
                continue
            try:
                aberto = self._entrada_aberta_a_alguem(os.fstat(fd))
                if self._ja_esta_no_alvo(fd, None):
                    continue
                ref = f"/proc/self/fd/{fd}"
                with contextlib.suppress(OSError):
                    os.removexattr(ref, _ACL_XATTR)
                os.chmod(ref, 0o600)
                if aberto:
                    mudados.append(node)
            except OSError:
                falhos.append(node)
            finally:
                os.close(fd)
        return mudados, falhos

    def abrir_entradas(self, base: str, uid: int) -> tuple[list[str], list[str]]:
        """`chmod 0660` + ACL `u:<uid>:rw` em cada nó de entrada: `(mudados, falhos)`."""
        mudados: list[str] = []
        falhos: list[str] = []
        for node, sys_dir in self.entradas_do_no(base):
            fd = self._pin_entrada(node, sys_dir)
            if fd is None:
                continue
            try:
                ja_aberto = self._exposta_ao_uid(fd, uid)
                if self._ja_esta_no_alvo(fd, uid):
                    continue
                ref = f"/proc/self/fd/{fd}"
                os.chmod(ref, 0o660)
                os.setxattr(ref, _ACL_XATTR, encode_access_acl(uid))
                if not ja_aberto:
                    mudados.append(node)
            except OSError:
                falhos.append(node)
            finally:
                os.close(fd)
        return mudados, falhos

    @staticmethod
    def _exposta_ao_uid(fd: int, uid: int) -> bool:
        """O nó pinado está no estado canônico exposto (0660 + ACL do uid)?"""
        try:
            if stat_mod.S_IMODE(os.fstat(fd).st_mode) != 0o660:
                return False
            blob = os.getxattr(f"/proc/self/fd/{fd}", _ACL_XATTR)
        except OSError:
            return False
        return uid in decode_acl_user_uids(blob)

    def entradas_abertas(self, base: str) -> list[str]:
        """Os nós de entrada do aparelho que abrem para alguém além do root."""
        abertas: list[str] = []
        for node, _sys_dir in self.entradas_do_no(base):
            try:
                if self._entrada_aberta_a_alguem(os.stat(node)):
                    abertas.append(node)
            except OSError:
                continue
        return abertas

    def entradas_fechadas_para(self, base: str, uid: int) -> list[str]:
        """Os nós de entrada do aparelho que NÃO estão expostos ao `uid`."""
        fechadas: list[str] = []
        for node, _sys_dir in self.entradas_do_no(base):
            if not self.is_exposed_to(node, uid):
                fechadas.append(node)
        return fechadas

    def open_entrada(self, node: str, base: str) -> int:
        """open(2) de um nó de ENTRADA + revalidação pós-open NO fd.

        O espelho do `open_node` para o evdev: o rdev do fd tem de casar o
        sysfs do `base`, o EVIOCGID do PRÓPRIO fd tem de ser DualSense
        054c:0ce6/0df2 por USB ou BT, e o pai HID não pode ter as marcas do
        nosso vpad (o EVIOCGID não separa o Edge físico do vpad, os dois são
        0003:054c:0df2 pelo cabo). Qualquer falha fecha o fd e levanta
        `StaleNodeError`; nenhum caminho vaza fd.
        """
        fd = os.open(node, os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            st = os.fstat(fd)
            with open(f"{self._sys_class_input}/{base}/dev", encoding="ascii") as fh:
                dev_sysfs = fh.read().strip()
        except OSError:
            os.close(fd)
            raise StaleNodeError(node) from None
        if not self._e_char_device(st.st_mode) or dev_sysfs != (
            f"{os.major(st.st_rdev)}:{os.minor(st.st_rdev)}"
        ):
            os.close(fd)
            raise StaleNodeError(node)
        try:
            bus, vendor, product, _versao = self._ler_input_id(fd)
        except OSError:
            os.close(fd)
            raise StaleNodeError(node) from None
        if bus not in ACCEPTED_BUSES or vendor != PHYS_VENDOR or product not in PHYS_PRODUCTS:
            os.close(fd)
            raise StaleNodeError(node)
        try:
            pai = os.path.realpath(f"{self._sys_class_input}/{base}/device/device")
            with open(f"{pai}/uevent", encoding="ascii", errors="replace") as fh:
                uevent = _parse_uevent_text(fh.read())
        except OSError:
            os.close(fd)
            raise StaleNodeError(node) from None
        if _e_o_nosso_vpad(uevent, pai, bus):
            os.close(fd)
            raise StaleNodeError(node)
        return fd

    @staticmethod
    def _ler_input_id(fd: int) -> tuple[int, int, int, int]:
        """EVIOCGID do PRÓPRIO fd: `(bustype, vendor, product, version)`."""
        buf = bytearray(struct.calcsize(_INPUT_ID_FMT))
        fcntl.ioctl(fd, _EVIOCGID, buf, True)
        bus, vendor, product, versao = struct.unpack(_INPUT_ID_FMT, bytes(buf))
        return int(bus), int(vendor), int(product), int(versao)


def reinicio_sem_abrir_pedido(
    path: str = REINICIO_SEM_ABRIR_PATH,
    *,
    agora: Callable[[], float] = time.time,
    dono_esperado: int = 0,
) -> bool:
    """O broker está sendo REINICIADO de propósito, e não pode abrir o físico?"""
    try:
        st = os.lstat(path)
    except OSError:
        return False
    if not stat_mod.S_ISREG(st.st_mode):
        return False
    if st.st_uid != dono_esperado:
        return False
    if stat_mod.S_IMODE(st.st_mode) & 0o022:
        return False
    idade = agora() - st.st_mtime
    return -5.0 <= idade <= REINICIO_SEM_ABRIR_VALIDADE_S


# --- O PAD EM USB (O-PAD-VIRTUAL-E-O-SOM-DELE-NASCEM-NO-MESMO-USB-01, 07/10/2026) ---
#
# O pad virtual nascia só por uhid, sem `usb_device` pai, e o jogo com a
# biblioteca da Sony não casava o som dele pelo contêiner (o engasgo do
# Sackboy). A cura é um gadget `libcomposite` SÓ HID, preso ao `usbip-vudc` e
# ligado de volta pelo `vhci_hcd`: o pad ganha um pai USB de verdade. A raiz é
# deste broker, com o pedido mínimo: montar, ligar, entregar o fd do
# `/dev/hidgN` e desmontar. Nada aqui é escolhido pelo cliente além do serial
# (no formato do Hefesto) e do descritor, que só passa se for o do DualSense
# que o produto já usa (`PAD_USB_DESCRITORES_SHA256`): o broker nunca vira uma
# fábrica de teclado USB para quem fala com ele.
#
# O que a prova mediu e este código honra (rodadas 18 a 22):
#   - SEM endpoint OUT (`no_out_endpoint=1`): com OUT, o `f_hid` estala o
#     SET_REPORT e o jogo recusa o pad;
#   - SEM a função `uac2`: o isócrono pelo `vhci` congela o jogo;
#   - no máximo quatro pads (`PAD_USB_MAX`): o Sackboy só inicializa quatro.
# O `attach` vai pelo sysfs com um par de sockets AF_UNIX (o `usbip_sockfd` do
# `vudc` e o `attach` do `vhci`), sem o `usbipd` por TCP da prova.

CONFIGFS_GADGETS = "/sys/kernel/config/usb_gadget"
SYS_PLATFORM = "/sys/devices/platform"
SYS_CLASS_UDC = "/sys/class/udc"
PAD_USB_MAX = 4
PAD_USB_NOME = "hefesto-pad-"
PAD_USB_FUNCAO = "hid.usb0"
PAD_USB_CONFIG = "c.1"
#: sha256 do descritor do DualSense que o pad usa
#: (`integrations/uhid_blueprint.CANONICAL_DESCRIPTOR_USB`); a régua do pad
#: reprova se o blueprint mudar sem esta linha.
PAD_USB_DESCRITORES_SHA256 = frozenset(
    {"4f48767516627510521512af13c20a064877465122b7bcc7cac1f3b608d37994"}
)
_SERIAL_DO_PAD_RE = re.compile(r"^hefesto-pad-[0-9a-f]{12}$")
_VUDC_RE = re.compile(r"^usbip-vudc\.[0-9]+$")
_VHCI_LIVRE = 4  # VDEV_ST_NULL
_VELOCIDADES = {"low-speed": 1, "full-speed": 2, "high-speed": 3, "super-speed": 5}
_VELOCIDADE_PADRAO = 3  # o gadget declara bcdUSB 0x0200 (alta velocidade)


class PadUsbSemContratoError(OSError):
    """O kernel não cumpre um contrato do pad em USB; ``contrato`` diz qual."""

    def __init__(self, contrato: str, detalhe: str = "") -> None:
        super().__init__(errno.ENODEV, f"{contrato}: {detalhe}".rstrip(": "))
        self.contrato = contrato


@dataclass
class RaizesDoPad:
    """Onde o pad em USB mexe — injetável para a régua (nunca o /sys real)."""

    configfs: str = CONFIGFS_GADGETS
    plataforma: str = SYS_PLATFORM
    classe_udc: str = SYS_CLASS_UDC
    dev: str = "/dev"


def _escrever_attr(caminho: str, valor: str | bytes) -> None:
    """Escreve num atributo que o kernel JÁ publicou (sem ``O_CREAT``: o que
    falta é contrato que falta, e não arquivo a criar)."""
    dados = valor if isinstance(valor, bytes) else valor.encode("ascii")
    fd = os.open(caminho, os.O_WRONLY | os.O_CLOEXEC | os.O_TRUNC)
    try:
        os.write(fd, dados)
    finally:
        os.close(fd)


def _conceder_ao_uid(fd: int, uid: int) -> None:
    """``chmod 0660`` + ACL ``u:<uid>:rw`` no inode pinado (o ``restore``)."""
    ref = f"/proc/self/fd/{fd}"
    os.chmod(ref, 0o660)
    os.setxattr(ref, _ACL_XATTR, encode_access_acl(uid))


def _ler_attr(caminho: str) -> str:
    try:
        with open(caminho, encoding="ascii", errors="replace") as fh:
            return fh.read().strip()
    except OSError:
        return ""


class PadUsbOps:
    """As operações de raiz do pad em USB: configfs, vudc, vhci e /dev/hidgN.

    ``remover`` é o ``rmdir`` (a régua injeta um que recusa, como o configfs,
    diretório com grupo dentro); ``povoar`` faz, na régua, o que o configfs
    faz sozinho ao nascer um grupo (publicar os atributos dele); ``abrir``,
    ``rdev_de`` e ``conceder`` servem ao ``/dev/hidgN``, que não se cria sem root.

    O broker NÃO abre o ``/dev/hidgN`` para ler e escrever: o grupo ``hidg``
    só aparece no ``/proc/devices`` quando nasce a primeira instância da
    função (medido em 07/10/2026: com o ``usb_f_hid`` carregado e nenhum
    gadget, não há linha ``hidg``), e o ``DeviceAllow=char-hidg`` da unit,
    resolvido no start, não acharia o grupo. O broker pina o nó por
    ``O_PATH`` (que o cgroup de device não barra), concede ``rw`` ao uid da
    sessão no MESMO inode (``chmod 0660`` + ACL, como o ``restore``) e
    entrega o fd ``O_PATH``; o daemon reabre por ``/proc/self/fd/N``, sem
    janela de troca de nó.
    """

    def __init__(
        self,
        raizes: RaizesDoPad | None = None,
        *,
        remover: Callable[[str], None] = os.rmdir,
        abrir: Callable[[str], int] | None = None,
        rdev_de: Callable[[int], int] | None = None,
        conceder: Callable[[int, int], None] | None = None,
        par_de_sockets: Callable[[], tuple[socket.socket, socket.socket]] | None = None,
        povoar: Callable[[str], None] | None = None,
    ) -> None:
        self.raizes = raizes if raizes is not None else RaizesDoPad()
        self._remover = remover
        self._povoar = povoar or (lambda _grupo: None)
        self._abrir = abrir or (
            lambda p: os.open(p, os.O_PATH | os.O_CLOEXEC | os.O_NOFOLLOW)
        )
        self._rdev_de = rdev_de or (lambda fd: os.fstat(fd).st_rdev)
        self._conceder = conceder or _conceder_ao_uid
        self._par = par_de_sockets or (
            lambda: socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        )

    # -- leitura -----------------------------------------------------------

    def gadgets_nossos(self) -> list[str]:
        try:
            nomes = os.listdir(self.raizes.configfs)
        except OSError:
            return []
        return sorted(n for n in nomes if n.startswith(PAD_USB_NOME))

    def udcs_livres(self) -> list[str]:
        try:
            udcs = sorted(n for n in os.listdir(self.raizes.classe_udc) if _VUDC_RE.match(n))
        except OSError:
            udcs = []
        try:
            gadgets = os.listdir(self.raizes.configfs)
        except OSError:
            gadgets = []
        presos = {_ler_attr(f"{self.raizes.configfs}/{g}/UDC") for g in gadgets}
        return [u for u in udcs if u not in presos]

    def porta_livre(self) -> int:
        """A primeira porta de alta velocidade livre do ``vhci_hcd.0``."""
        status = f"{self.raizes.plataforma}/vhci_hcd.0/status"
        try:
            with open(status, encoding="ascii", errors="replace") as fh:
                linhas = fh.read().splitlines()
        except OSError as exc:
            raise PadUsbSemContratoError("vhci_hcd", "sem o status do vhci_hcd.0") from exc
        for linha in linhas[1:]:
            campos = linha.split()
            if len(campos) < 3 or campos[0] != "hs":
                continue
            if not (campos[1].isdigit() and campos[2].isdigit()):
                continue
            if int(campos[2]) == _VHCI_LIVRE:
                return int(campos[1])
        raise OSError(errno.EBUSY, "nenhuma porta livre no vhci_hcd.0")

    # -- montar, ligar, desmontar -----------------------------------------

    def montar(self, nome: str, serial: str, descritor: bytes, udc: str) -> None:
        """O gadget com UMA função ``hid``, sem OUT, preso ao ``udc``."""
        if not os.path.isdir(self.raizes.configfs):
            raise PadUsbSemContratoError("libcomposite", "sem o configfs de usb_gadget")
        g = f"{self.raizes.configfs}/{nome}"
        os.mkdir(g)
        self._povoar(g)
        try:
            _escrever_attr(f"{g}/idVendor", "0x054c")
            _escrever_attr(f"{g}/idProduct", "0x0df2")
            _escrever_attr(f"{g}/bcdDevice", "0x0100")
            _escrever_attr(f"{g}/bcdUSB", "0x0200")
            self._grupo(f"{g}/strings/0x409")
            _escrever_attr(f"{g}/strings/0x409/manufacturer", "Sony Interactive Entertainment")
            _escrever_attr(f"{g}/strings/0x409/product", "DualSense Edge Wireless Controller")
            _escrever_attr(f"{g}/strings/0x409/serialnumber", serial)
            self._grupo(f"{g}/configs/{PAD_USB_CONFIG}")
            _escrever_attr(f"{g}/configs/{PAD_USB_CONFIG}/MaxPower", "500")
            funcao = f"{g}/functions/{PAD_USB_FUNCAO}"
            try:
                self._grupo(funcao)
            except OSError as exc:
                raise PadUsbSemContratoError("usb_f_hid", str(exc)) from exc
            _escrever_attr(f"{funcao}/protocol", "0")
            _escrever_attr(f"{funcao}/subclass", "0")
            _escrever_attr(f"{funcao}/report_length", "64")
            try:
                _escrever_attr(f"{funcao}/no_out_endpoint", "1")
            except OSError as exc:
                raise PadUsbSemContratoError("usb_f_hid", "sem o no_out_endpoint") from exc
            _escrever_attr(f"{funcao}/report_desc", descritor)
            os.symlink(funcao, f"{g}/configs/{PAD_USB_CONFIG}/{PAD_USB_FUNCAO}")
            _escrever_attr(f"{g}/UDC", udc)
        except BaseException:
            with contextlib.suppress(OSError):
                self.desmontar(nome, None)
            raise

    def _grupo(self, caminho: str) -> None:
        """Um grupo do configfs (o ``mkdir`` que faz o kernel publicar atributos)."""
        os.mkdir(caminho)
        self._povoar(caminho)

    def ligar(self, udc: str) -> int:
        """Liga o ``udc`` ao ``vhci_hcd`` por um par de sockets; devolve a porta."""
        vudc = f"{self.raizes.plataforma}/{udc}/usbip_sockfd"
        attach = f"{self.raizes.plataforma}/vhci_hcd.0/attach"
        if not os.path.exists(attach):
            raise PadUsbSemContratoError("vhci_hcd", "sem o attach do vhci_hcd.0")
        if not os.path.exists(vudc):
            raise PadUsbSemContratoError("usbip_vudc", f"sem o usbip_sockfd de {udc}")
        porta = self.porta_livre()
        velocidade = _VELOCIDADES.get(
            _ler_attr(f"{self.raizes.classe_udc}/{udc}/maximum_speed"), _VELOCIDADE_PADRAO
        )
        servidor, cliente = self._par()
        try:
            _escrever_attr(vudc, str(servidor.fileno()))
            # devid 0: o `usbip` lê busnum/devnum zerados do vudc, e nem o
            # vudc nem o vhci validam o campo (a bancada confirma no fecho).
            _escrever_attr(attach, f"{porta} {cliente.fileno()} 0 {velocidade}")
        finally:
            servidor.close()
            cliente.close()
        return porta

    def ceder_hidg(self, nome: str, uid: int) -> int:
        """O fd ``O_PATH`` do ``/dev/hidgN`` DESTE gadget, já concedido ao ``uid``.

        O nó se casa pelo ``dev`` da função no configfs, conferido no fd
        pinado (``fstat``), nunca pelo nome: o ``hidgN`` de outro gadget não
        passa.
        """
        alvo = _ler_attr(f"{self.raizes.configfs}/{nome}/functions/{PAD_USB_FUNCAO}/dev")
        if ":" not in alvo:
            raise OSError(errno.ENOENT, f"o gadget {nome} não publicou o dev da função")
        maior, menor = (int(x) for x in alvo.split(":", 1))
        try:
            nos = sorted(n for n in os.listdir(self.raizes.dev) if n.startswith("hidg"))
        except OSError:
            nos = []
        for no in nos:
            try:
                fd = self._abrir(f"{self.raizes.dev}/{no}")
            except OSError as exc:
                _log("pad_usb_hidg_ilegivel", no=no, errno=exc.errno)
                continue
            try:
                if self._rdev_de(fd) == os.makedev(maior, menor):
                    self._conceder(fd, uid)
                    return fd
            except OSError:
                os.close(fd)
                raise
            os.close(fd)
        raise OSError(errno.ENOENT, f"nenhum /dev/hidg* tem o dev {alvo}")

    def desmontar(self, nome: str, porta: int | None) -> None:
        """Desliga do ``vhci``, solta o ``udc`` e desfaz o configfs, nesta ordem."""
        if porta is not None:
            with contextlib.suppress(OSError):
                _escrever_attr(f"{self.raizes.plataforma}/vhci_hcd.0/detach", str(porta))
        g = f"{self.raizes.configfs}/{nome}"
        if not os.path.isdir(g):
            return
        with contextlib.suppress(OSError):
            if _ler_attr(f"{g}/UDC"):
                _escrever_attr(f"{g}/UDC", "\n")
        elo = f"{g}/configs/{PAD_USB_CONFIG}/{PAD_USB_FUNCAO}"
        if os.path.islink(elo):
            os.unlink(elo)
        for grupo in (
            f"{g}/configs/{PAD_USB_CONFIG}/strings/0x409",
            f"{g}/configs/{PAD_USB_CONFIG}",
            f"{g}/functions/{PAD_USB_FUNCAO}",
            f"{g}/strings/0x409",
        ):
            if os.path.isdir(grupo):
                self._remover(grupo)
        self._remover(g)

    def desmontar_todos(self) -> list[str]:
        """O cinto do início e do fim do broker: nenhum pad sobrevive a ele."""
        feitos: list[str] = []
        for nome in self.gadgets_nossos():
            try:
                self.desmontar(nome, None)
            except OSError as exc:
                _log("pad_usb_desmontar_falhou", gadget=nome, errno=exc.errno)
                continue
            feitos.append(nome)
        return feitos


_RESTORE_BACKOFF_S = (0.0, 0.05, 0.2)


@dataclass
class _HiddenNode:
    """Um nó escondido: uid gravado NO HIDE (fail-safe restaura por ele)."""

    uid: int
    refcount: int = 1
    pai: str | None = None


@dataclass
class _ExpostoNode:
    """Um nó mantido ABERTO a pedido: a lease INVERTIDA do `cmd expose`."""

    uid: int
    refcount: int = 1
    pai: str | None = None


class BrokerState:
    """Protocolo + contabilidade de lease. Puro (fs injetável) e testável."""

    def __init__(
        self,
        *,
        allowed_uid: int,
        ops: Any | None = None,
        validator: Callable[[str], str | None] | None = None,
        dev_root: str = "/dev",
        sys_class_hidraw: str = "/sys/class/hidraw",
        sys_class_bluetooth: str = "/sys/class/bluetooth",
        log: Callable[..., None] = _log,
        sleep_fn: Callable[[float], None] = time.sleep,
        no_nasce_fechado: bool = False,
        dev_input_root: str = DEV_INPUT_ROOT,
        sys_class_input: str = "/sys/class/input",
        validator_entrada: Callable[[str], str | None] | None = None,
        reinicio_sem_abrir: Callable[[], bool] = reinicio_sem_abrir_pedido,
        pad_ops: PadUsbOps | None = None,
    ) -> None:
        self.allowed_uid = allowed_uid
        self.no_nasce_fechado = bool(no_nasce_fechado)
        self._ops = (
            ops
            if ops is not None
            else FsAclOps(
                sys_class_hidraw=sys_class_hidraw,
                dev_input_root=dev_input_root,
                sys_class_input=sys_class_input,
                sys_class_bluetooth=sys_class_bluetooth,
            )
        )
        self._validator = validator
        self._validator_entrada = validator_entrada
        self._dev_root = dev_root
        self._dev_input_root = dev_input_root
        self._sys_class_hidraw = sys_class_hidraw
        self._sys_class_input = sys_class_input
        self._sys_class_bluetooth = sys_class_bluetooth
        self._log = log
        self._sleep = sleep_fn
        self._reinicio_sem_abrir = reinicio_sem_abrir
        self.hidden: dict[str, _HiddenNode] = {}
        self.by_conn: dict[int, set[str]] = {}
        self.expostos: dict[str, _ExpostoNode] = {}
        self.expostos_by_conn: dict[int, set[str]] = {}
        self.entradas_by_conn: dict[int, set[str]] = {}
        self.podados_by_conn: dict[int, set[str]] = {}
        self._pad_ops = pad_ops if pad_ops is not None else PadUsbOps()
        #: {conexão: {gadget: porta do vhci}} — a lease do pad em USB.
        self.pads_by_conn: dict[int, dict[str, int]] = {}
        self._serial_do_gadget: dict[str, str] = {}


    def _validate(self, node: str) -> str | None:
        if self._validator is not None:
            return self._validator(node)
        return validate_physical_node(
            node,
            dev_root=self._dev_root,
            sys_class_hidraw=self._sys_class_hidraw,
            sys_class_bluetooth=self._sys_class_bluetooth,
        )

    def _validate_entrada(self, node: str) -> str | None:
        if self._validator_entrada is not None:
            return self._validator_entrada(node)
        return validate_physical_input_node(
            node,
            dev_input_root=self._dev_input_root,
            sys_class_input=self._sys_class_input,
            sys_class_bluetooth=self._sys_class_bluetooth,
        )


    def _entradas_holders(self, canon: str) -> int:
        """Nº de conexões VIVAS que pediram os nós de ENTRADA de `canon` abertos."""
        return sum(1 for held in self.entradas_by_conn.values() if canon in held)

    def _entradas_devem_abrir(self, canon: str) -> bool:
        """O estado dos nós de entrada, derivado SÓ da contabilidade."""
        if self._entradas_holders(canon) > 0:
            return True
        if self._lease_holders(canon) > 0:
            return False
        return not self.no_nasce_fechado

    def _aplicar_entradas(self, canon: str) -> None:
        """Leva os nós de entrada de `canon` ao estado que a lease manda."""
        base = canonical_hidraw_base(canon, dev_root=self._dev_root)
        if base is None:
            return
        abrir = self._entradas_devem_abrir(canon)
        op = getattr(self._ops, "abrir_entradas" if abrir else "fechar_entradas", None)
        if not callable(op):
            return
        try:
            mudados, falhos = op(base, self.allowed_uid) if abrir else op(base)
        except OSError as exc:
            self._log("entradas_falharam", node=canon, abrir=abrir, err=str(exc))
            return
        if falhos:
            self._log("entradas_parcial", node=canon, abrir=abrir, falhos=",".join(falhos))
        if mudados:
            evento = "entradas_abertas" if abrir else "entradas_fechadas"
            self._log(evento, node=canon, nos=",".join(mudados))

    def _entradas_seguem(self, resposta: dict[str, object]) -> dict[str, object]:
        """Depois de um comando sobre UM nó, os nós de entrada dele seguem."""
        erro = resposta.get("error")
        if isinstance(erro, str) and erro.startswith("reject_"):
            return resposta
        if resposta.get("state") == "gone":
            return resposta
        node = resposta.get("node")
        if isinstance(node, str):
            self._aplicar_entradas(node)
        return resposta


    def _pai_hid(self, base: str) -> str | None:
        """A pergunta do `FsAclOps`; ops sem ela (dublê antigo) não sabe."""
        pergunta = getattr(self._ops, "pai_hid_do_no", None)
        if not callable(pergunta):
            return None
        try:
            resposta = pergunta(base)
        except OSError:
            return None
        return resposta if isinstance(resposta, str) else None

    @staticmethod
    def _lembrar_o_aparelho(entry: _HiddenNode | _ExpostoNode, pai: str | None) -> None:
        """A lease guarda o aparelho do pedido, quando ainda não sabe qual é."""
        if entry.pai is None and pai:
            entry.pai = pai

    def _nomes_que_o_pedido_solta(
        self, conn_id: int, cmd: object, request: dict[str, Any]
    ) -> frozenset[str]:
        """Os nomes que ESTE pedido solta da lease da própria conexão."""
        if cmd == "restore_all":
            return frozenset(self.by_conn.get(conn_id, set()))
        if cmd not in ("restore", "unexpose"):
            return frozenset()
        base = canonical_hidraw_base(request.get("node"), dev_root=self._dev_root)
        if base is None:
            return frozenset()
        canon = f"{self._dev_root}/{base}"
        dela = self.by_conn if cmd == "restore" else self.expostos_by_conn
        return frozenset({canon}) if canon in dela.get(conn_id, set()) else frozenset()

    def _podar_o_que_saiu(self, *, exceto: frozenset[str] = frozenset()) -> None:
        """Tira da contabilidade a lease cujo aparelho saiu. Não escreve no fs."""
        if not callable(getattr(self._ops, "pai_hid_do_no", None)):
            return
        for canon in sorted((set(self.hidden) | set(self.expostos)) - exceto):
            escondido = self.hidden.get(canon)
            exposto = self.expostos.get(canon)
            guardados = [e.pai for e in (escondido, exposto) if e is not None and e.pai]
            if not guardados:
                continue
            base = canonical_hidraw_base(canon, dev_root=self._dev_root)
            if base is None:
                continue
            agora = self._pai_hid(base)
            if agora is None:
                continue
            de = ""
            if escondido is not None and escondido.pai and escondido.pai != agora:
                de = escondido.pai
                del self.hidden[canon]
                for conn, held in self.by_conn.items():
                    if canon in held:
                        held.discard(canon)
                        self.podados_by_conn.setdefault(conn, set()).add(canon)
            if exposto is not None and exposto.pai and exposto.pai != agora:
                de = de or exposto.pai
                del self.expostos[canon]
                for held in self.expostos_by_conn.values():
                    held.discard(canon)
                for held in self.entradas_by_conn.values():
                    held.discard(canon)
            if de:
                self._log(
                    "lease_do_aparelho_que_saiu",
                    node=canon,
                    de=os.path.basename(de),
                    agora=os.path.basename(agora) or "-",
                )


    def handle_line(
        self, conn_id: int, peer_uid: int, line: bytes
    ) -> tuple[dict[str, object], int | None]:
        """Uma requisição JSON-por-linha → (resposta, fd|None). NUNCA levanta."""
        if len(line) > MAX_LINE_BYTES:
            return ({"ok": False, "error": "reject_oversize"}, None)
        try:
            request = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return ({"ok": False, "error": "reject_malformed"}, None)
        if not isinstance(request, dict):
            return ({"ok": False, "error": "reject_malformed"}, None)
        cmd = request.get("cmd")
        self._podar_o_que_saiu(exceto=self._nomes_que_o_pedido_solta(conn_id, cmd, request))
        if cmd == "ping":
            return ({"ok": True, "cmd": "ping", "peer_uid": peer_uid}, None)
        if cmd == "status":
            return (
                {
                    "ok": True,
                    "cmd": "status",
                    "hidden": sorted(self.hidden),
                    "expostos": sorted(self.expostos),
                    "entradas_expostas": sorted(
                        {no for held in self.entradas_by_conn.values() for no in held}
                    ),
                    "no_nasce_fechado": self.no_nasce_fechado,
                },
                None,
            )
        if cmd == "expose":
            entradas = request.get("entradas") is True
            return (
                self._entradas_seguem(
                    self._cmd_expose(conn_id, peer_uid, request.get("node"), entradas=entradas)
                ),
                None,
            )
        if cmd == "unexpose":
            return (self._entradas_seguem(self._cmd_unexpose(conn_id, request.get("node"))), None)
        if cmd == "hide":
            return (
                self._entradas_seguem(self._cmd_hide(conn_id, peer_uid, request.get("node"))),
                None,
            )
        if cmd == "restore":
            return (self._entradas_seguem(self._cmd_restore(conn_id, request.get("node"))), None)
        if cmd == "restore_all":
            return (self._cmd_restore_all(conn_id), None)
        if cmd == "open":
            return self._cmd_open(conn_id, request.get("node"))
        if cmd == "pad_usb_montar":
            return self._cmd_pad_usb_montar(conn_id, request)
        if cmd == "pad_usb_desmontar":
            return (self._cmd_pad_usb_desmontar(conn_id, request.get("gadget")), None)
        return (
            {
                "ok": False,
                "cmd": cmd if isinstance(cmd, str) else None,
                "error": "reject_unknown_cmd",
            },
            None,
        )

    def _cmd_expose(
        self, conn_id: int, peer_uid: int, node: object, *, entradas: bool = False
    ) -> dict[str, object]:
        """«Mantenha este nó ABERTO enquanto eu viver» — o abrir sob pedido."""
        raw = node if isinstance(node, str) else None
        if canonical_hidraw_base(raw, dev_root=self._dev_root) is None:
            return {"ok": False, "cmd": "expose", "node": raw, "error": "reject_bad_path"}
        assert raw is not None
        base = self._validate(raw)
        if base is None:
            return {
                "ok": False,
                "cmd": "expose",
                "node": raw,
                "error": "reject_not_physical_dualsense",
            }
        canon = f"{self._dev_root}/{base}"
        pai = self._pai_hid(base)
        resposta = self._fs_restore(canon, base, peer_uid)
        resposta["cmd"] = "expose"
        if not resposta.get("ok"):
            return resposta
        if resposta.get("state") == "gone":
            return resposta
        held = self.expostos_by_conn.setdefault(conn_id, set())
        entry = self.expostos.get(canon)
        if entry is None:
            self.expostos[canon] = _ExpostoNode(uid=peer_uid)
            self._log("node_exposto", node=canon, conn=conn_id, uid=peer_uid)
        elif canon not in held:
            if self._exposicao_holders(canon) > 0:
                entry.refcount += 1
            else:
                entry.refcount = 1
                entry.uid = peer_uid
                self._log("exposto_orfao_adotado", node=canon, conn=conn_id, uid=peer_uid)
        self._lembrar_o_aparelho(self.expostos[canon], pai)
        held.add(canon)
        if entradas:
            self.entradas_by_conn.setdefault(conn_id, set()).add(canon)
        return resposta

    def _cmd_unexpose(self, conn_id: int, node: object) -> dict[str, object]:
        """Solta a lease de exposição e devolve o nó ao REPOUSO."""
        raw = node if isinstance(node, str) else None
        base = canonical_hidraw_base(raw, dev_root=self._dev_root)
        if base is None:
            return {"ok": False, "cmd": "unexpose", "node": raw, "error": "reject_bad_path"}
        canon = f"{self._dev_root}/{base}"
        held = self.expostos_by_conn.get(conn_id, set())
        entry = self.expostos.get(canon)
        self.entradas_by_conn.get(conn_id, set()).discard(canon)
        if canon in held:
            held.discard(canon)
            if entry is not None and entry.refcount > 1:
                entry.refcount -= 1
                return {"ok": True, "cmd": "unexpose", "node": canon, "state": "exposed"}
            self.expostos.pop(canon, None)
        elif entry is not None and self._exposicao_holders(canon) > 0:
            return {"ok": True, "cmd": "unexpose", "node": canon, "state": "exposed"}
        else:
            self.expostos.pop(canon, None)
        return self._repouso(canon, base, cmd="unexpose")

    def _exposicao_holders(self, canon: str) -> int:
        """Nº de conexões VIVAS cuja lease de EXPOSIÇÃO segura `canon`."""
        return sum(1 for held in self.expostos_by_conn.values() if canon in held)

    def _repouso(self, canon: str, base: str, *, cmd: str) -> dict[str, object]:
        """Devolve o nó ao estado de REPOUSO e responde o que ficou."""
        if self._exposicao_holders(canon) > 0:
            return {"ok": True, "cmd": cmd, "node": canon, "state": "exposed"}
        if self._lease_holders(canon) > 0:
            return self._fs_fechar(canon, base, cmd=cmd)
        if not self.no_nasce_fechado:
            resposta = self._fs_restore(canon, base, self.allowed_uid)
            resposta["cmd"] = cmd
            return resposta
        return self._fs_fechar(canon, base, cmd=cmd)

    def _fs_fechar(self, canon: str, base: str, *, cmd: str) -> dict[str, object]:
        """`hide` de fs sem mexer em lease: põe o nó de volta em `0600 root`."""
        try:
            self._ops.hide(canon, base)
        except FileNotFoundError:
            self._log("fechar_node_gone", node=canon)
            return {"ok": True, "cmd": cmd, "node": canon, "state": "gone"}
        except OSError as exc:
            self._log("fechar_failed", node=canon, err=str(exc))
            return {"ok": False, "cmd": cmd, "node": canon, "error": "fechar_failed"}
        self._log("node_em_repouso_fechado", node=canon)
        return {"ok": True, "cmd": cmd, "node": canon, "state": "fechado"}

    def _cmd_hide(self, conn_id: int, peer_uid: int, node: object) -> dict[str, object]:
        raw = node if isinstance(node, str) else None
        if canonical_hidraw_base(raw, dev_root=self._dev_root) is None:
            return {"ok": False, "cmd": "hide", "node": raw, "error": "reject_bad_path"}
        assert raw is not None
        base = self._validate(raw)
        if base is None:
            return {
                "ok": False,
                "cmd": "hide",
                "node": raw,
                "error": "reject_not_physical_dualsense",
            }
        canon = f"{self._dev_root}/{base}"
        pai = self._pai_hid(base)
        self.podados_by_conn.get(conn_id, set()).discard(canon)
        held = self.by_conn.setdefault(conn_id, set())
        entry = self.hidden.get(canon)
        if self._exposicao_holders(canon) > 0:
            if entry is None:
                self.hidden[canon] = _HiddenNode(uid=peer_uid, refcount=1)
            elif canon not in held and self._lease_holders(canon) > 0:
                entry.refcount += 1
            self._lembrar_o_aparelho(self.hidden[canon], pai)
            held.add(canon)
            self._log("hide_adiado_por_exposicao", node=canon, conn=conn_id)
            return {"ok": True, "cmd": "hide", "node": canon, "state": "exposed"}
        try:
            self._ops.hide(canon, base)
        except FileNotFoundError:
            self._log("hide_node_gone", node=canon)
            return {"ok": False, "cmd": "hide", "node": canon, "error": "hide_node_gone"}
        except OSError as exc:
            self._log("hide_failed", node=canon, err=str(exc))
            return {"ok": False, "cmd": "hide", "node": canon, "error": "hide_failed"}
        if entry is None:
            self.hidden[canon] = _HiddenNode(uid=peer_uid)
            self._log("node_hidden", node=canon, conn=conn_id, uid=peer_uid)
        elif canon not in held:
            if self._lease_holders(canon) > 0:
                entry.refcount += 1
            else:
                # `hidden`, mas nenhuma conexão viva o referencia). Adotar  # (noqa-acento)
                entry.refcount = 1
                entry.uid = peer_uid
                self._log("orphan_adopted", node=canon, conn=conn_id, uid=peer_uid)
        self._lembrar_o_aparelho(self.hidden[canon], pai)
        held.add(canon)
        return {"ok": True, "cmd": "hide", "node": canon, "state": "hidden"}

    def _cmd_restore(self, conn_id: int, node: object) -> dict[str, object]:
        raw = node if isinstance(node, str) else None
        base = canonical_hidraw_base(raw, dev_root=self._dev_root)
        if base is None:
            return {"ok": False, "cmd": "restore", "node": raw, "error": "reject_bad_path"}
        canon = f"{self._dev_root}/{base}"
        podado = canon in self.podados_by_conn.get(conn_id, set())
        self.podados_by_conn.get(conn_id, set()).discard(canon)
        held = self.by_conn.get(conn_id, set())
        entry = self.hidden.get(canon)
        if canon in held:
            if entry is not None and entry.refcount > 1:
                entry.refcount -= 1
                held.discard(canon)
                return {"ok": True, "cmd": "restore", "node": canon, "state": "hidden"}
            held.discard(canon)
            response = self._repouso(canon, base, cmd="restore")
            if response.get("ok"):
                self.hidden.pop(canon, None)
            else:
                held.add(canon)
            return response
        if entry is not None:
            if self._lease_holders(canon) > 0:
                return {"ok": True, "cmd": "restore", "node": canon, "state": "hidden"}
            response = self._repouso(canon, base, cmd="restore")
            if response.get("ok"):
                self.hidden.pop(canon, None)
                self._log("orphan_restored", node=canon, conn=conn_id)
            return response
        if self._validate(canon) is None:
            if podado:
                self._log("restore_node_gone", node=canon, conn=conn_id)
                return {"ok": True, "cmd": "restore", "node": canon, "state": "gone"}
            return {
                "ok": False,
                "cmd": "restore",
                "node": canon,
                "error": "reject_not_physical_dualsense",
            }
        return self._repouso(canon, base, cmd="restore")

    def _cmd_restore_all(self, conn_id: int) -> dict[str, object]:
        restored: list[str] = []
        failed: list[str] = []
        nomes = self.by_conn.get(conn_id, set()) | self.podados_by_conn.get(conn_id, set())
        for canon in sorted(nomes):
            response = self._entradas_seguem(self._cmd_restore(conn_id, canon))
            if response.get("ok") and response.get("state") in ("exposed", "fechado", "gone"):
                restored.append(canon)
            elif not response.get("ok"):
                failed.append(canon)
        if failed:
            self._log("restore_all_parcial", conn=conn_id, failed=",".join(failed))
        return {"ok": True, "cmd": "restore_all", "restored": restored, "failed": failed}

    def _cmd_open(self, conn_id: int, node: object) -> tuple[dict[str, object], int | None]:
        """Valida, abre O_RDWR|O_CLOEXEC|O_NOFOLLOW e devolve (resposta, fd|None)."""
        raw = node if isinstance(node, str) else None
        if canonical_input_base(raw, dev_input_root=self._dev_input_root) is not None:
            assert raw is not None
            return self._cmd_open_entrada(conn_id, raw)
        base_canon = canonical_hidraw_base(raw, dev_root=self._dev_root)
        if base_canon is None:
            return ({"ok": False, "cmd": "open", "node": raw, "error": "reject_bad_path"}, None)
        assert raw is not None
        base = self._validate(raw)
        if base is None:
            return (
                {"ok": False, "cmd": "open", "node": raw, "error": "reject_not_physical_dualsense"},
                None,
            )
        canon = f"{self._dev_root}/{base}"
        try:
            fd = self._ops.open_node(canon, base)
        except StaleNodeError:
            self._log("open_stale_node", node=canon)
            return ({"ok": False, "cmd": "open", "node": canon, "error": "reject_stale_node"}, None)
        except OSError as exc:
            self._log("open_failed", node=canon, errno=exc.errno)
            return (
                {"ok": False, "cmd": "open", "node": canon, "error": "open_failed",
                 "errno": exc.errno},
                None,
            )
        state = "hidden" if canon in self.hidden else "exposed"
        self._log("node_fd_servido", node=canon, conn=conn_id, state=state)
        return ({"ok": True, "cmd": "open", "node": canon, "state": state}, fd)

    def _cmd_pad_usb_montar(
        self, conn_id: int, request: dict[str, Any]
    ) -> tuple[dict[str, object], int | None]:
        """Monta o pad em USB, liga ao ``vhci`` e cede o ``/dev/hidgN`` (``O_PATH``).

        A lease é a conexão, como a do ``hide``: o EOF desmonta. No máximo
        :data:`PAD_USB_MAX` pads, um por serial (o MAC da 0x09 tem de ser
        único: o ``hid_playstation`` recusa o repetido com ``-17``).
        """
        cmd = "pad_usb_montar"
        serial = request.get("serial")
        if not isinstance(serial, str) or _SERIAL_DO_PAD_RE.match(serial) is None:
            return ({"ok": False, "cmd": cmd, "error": "reject_bad_serial"}, None)
        hexa = request.get("descritor")
        try:
            descritor = bytes.fromhex(hexa) if isinstance(hexa, str) else b""
        except ValueError:
            descritor = b""
        if hashlib.sha256(descritor).hexdigest() not in PAD_USB_DESCRITORES_SHA256:
            return ({"ok": False, "cmd": cmd, "error": "reject_bad_descriptor"}, None)
        if serial in self._serial_do_gadget.values():
            return ({"ok": False, "cmd": cmd, "error": "reject_serial_repetido"}, None)
        existentes = set(self._pad_ops.gadgets_nossos()) | set(self._serial_do_gadget)
        livres = [f"{PAD_USB_NOME}{i}" for i in range(PAD_USB_MAX)]
        livres = [n for n in livres if n not in existentes]
        if not livres:
            return ({"ok": False, "cmd": cmd, "error": "reject_quinto_pad"}, None)
        nome = livres[0]
        udcs = self._pad_ops.udcs_livres()
        if not udcs:
            return (
                {"ok": False, "cmd": cmd, "error": "pad_usb_sem_contrato",
                 "contrato": "usbip_vudc"},
                None,
            )
        porta: int | None = None
        try:
            self._pad_ops.montar(nome, serial, descritor, udcs[0])
            porta = self._pad_ops.ligar(udcs[0])
            fd = self._pad_ops.ceder_hidg(nome, self.allowed_uid)
        except OSError as exc:
            with contextlib.suppress(OSError):
                self._pad_ops.desmontar(nome, porta)
            contrato = getattr(exc, "contrato", None)
            self._log("pad_usb_montar_falhou", gadget=nome, errno=exc.errno,
                      contrato=contrato or "-")
            if contrato:
                return (
                    {"ok": False, "cmd": cmd, "error": "pad_usb_sem_contrato",
                     "contrato": contrato},
                    None,
                )
            return ({"ok": False, "cmd": cmd, "error": "pad_usb_falhou", "errno": exc.errno},
                    None)
        self.pads_by_conn.setdefault(conn_id, {})[nome] = porta
        self._serial_do_gadget[nome] = serial
        self._log("pad_usb_montado", gadget=nome, udc=udcs[0], porta=porta, conn=conn_id)
        return ({"ok": True, "cmd": cmd, "gadget": nome, "porta": porta, "udc": udcs[0]}, fd)

    def _cmd_pad_usb_desmontar(self, conn_id: int, gadget: object) -> dict[str, object]:
        cmd = "pad_usb_desmontar"
        pads = self.pads_by_conn.get(conn_id, {})
        if not isinstance(gadget, str) or gadget not in pads:
            return {"ok": False, "cmd": cmd, "error": "reject_not_held"}
        porta = pads.pop(gadget)
        self._serial_do_gadget.pop(gadget, None)
        try:
            self._pad_ops.desmontar(gadget, porta)
        except OSError as exc:
            self._log("pad_usb_desmontar_falhou", gadget=gadget, errno=exc.errno)
            return {"ok": False, "cmd": cmd, "gadget": gadget, "error": "pad_usb_falhou",
                    "errno": exc.errno}
        self._log("pad_usb_desmontado", gadget=gadget, conn=conn_id)
        return {"ok": True, "cmd": cmd, "gadget": gadget}

    def _desmontar_os_pads_da(self, conn_id: int) -> None:
        for gadget, porta in sorted(self.pads_by_conn.pop(conn_id, {}).items()):
            self._serial_do_gadget.pop(gadget, None)
            try:
                self._pad_ops.desmontar(gadget, porta)
            except OSError as exc:
                self._log("pad_usb_desmontar_falhou", gadget=gadget, errno=exc.errno)
                continue
            self._log("pad_usb_desmontado_no_eof", gadget=gadget, conn=conn_id)

    def _cmd_open_entrada(
        self, conn_id: int, raw: str
    ) -> tuple[dict[str, object], int | None]:
        """O `open` de um nó de ENTRADA (`/dev/input/eventN`) — HIDE-SO-O-HIDRAW-02."""
        base = self._validate_entrada(raw)
        if base is None:
            return (
                {"ok": False, "cmd": "open", "node": raw, "error": "reject_not_physical_dualsense"},
                None,
            )
        canon = f"{self._dev_input_root}/{base}"
        abrir = getattr(self._ops, "open_entrada", None)
        if not callable(abrir):
            return (
                {"ok": False, "cmd": "open", "node": canon, "error": "reject_sem_entrada"},
                None,
            )
        try:
            fd = abrir(canon, base)
        except StaleNodeError:
            self._log("open_stale_node", node=canon)
            return ({"ok": False, "cmd": "open", "node": canon, "error": "reject_stale_node"}, None)
        except OSError as exc:
            self._log("open_failed", node=canon, errno=exc.errno)
            return (
                {"ok": False, "cmd": "open", "node": canon, "error": "open_failed",
                 "errno": exc.errno},
                None,
            )
        self._log("entrada_fd_servida", node=canon, conn=conn_id)
        return ({"ok": True, "cmd": "open", "node": canon, "state": "entrada"}, fd)

    def _lease_holders(self, canon: str) -> int:
        """Nº de conexões VIVAS cuja lease segura `canon`."""
        return sum(1 for held in self.by_conn.values() if canon in held)

    def _fs_restore(self, canon: str, base: str, uid: int) -> dict[str, object]:
        """Restore de fs com retry + verificação (lição 2). NUNCA levanta."""
        for tentativa in (1, 2, 3):
            try:
                self._ops.restore(canon, base, uid)
            except FileNotFoundError:
                self._log("restore_node_gone", node=canon)
                return {"ok": True, "cmd": "restore", "node": canon, "state": "gone"}
            except OSError as exc:
                if tentativa == 3:
                    self._log("restore_failed", node=canon, err=str(exc))
                    return {"ok": False, "cmd": "restore", "node": canon,
                            "error": "restore_failed"}
                self._sleep(_RESTORE_BACKOFF_S[tentativa])
                continue
            if self._ops.is_exposed_to(canon, uid):
                self._log("node_restored", node=canon, uid=uid)
                return {"ok": True, "cmd": "restore", "node": canon, "state": "exposed"}
            self._log("restore_verify_failed", node=canon, uid=uid, tentativa=tentativa)
        return {"ok": False, "cmd": "restore", "node": canon, "error": "restore_verify_failed"}


    def on_conn_closed(self, conn_id: int) -> list[str]:
        """EOF da lease: devolve ao REPOUSO tudo que AQUELA conexão mexeu.

        Lição 3: falha num nó não derruba o loop — o falho fica rastreado em
        `hidden` (sem lease) e os belts cobrem (restore_all do shutdown,
        ExecStopPost, baseline do próximo start).

        O-NO-NASCE-FECHADO-01: são DUAS leases agora, e as duas morrem aqui —
        o que a conexão escondeu e o que o usuário mandou manter ABERTO. O destino
        de cada nó é o `_repouso`, não mais o restore incondicional: no mundo
        em que o nó nasce fechado, abrir tudo no EOF seria entregar o físico à
        Steam exatamente no instante em que o daemon morreu.

        O-BROKER-ESQUECE-O-CONTROLE-QUE-SAIU-01: a poda roda ANTES de tudo.
        Sem ela, o `_repouso` e o `_aplicar_entradas` pediriam ao fs por um
        nome que já é de outro aparelho: o pad, que o `_pin` recusa, ou um
        físico que ninguém pediu para esconder.
        """
        self._podar_o_que_saiu()
        self._desmontar_os_pads_da(conn_id)
        restored: list[str] = []
        failed: list[str] = []
        entradas_da_conn = self.entradas_by_conn.pop(conn_id, set())
        tocados = set(entradas_da_conn) | set(self.by_conn.get(conn_id, set()))
        tocados |= set(self.expostos_by_conn.get(conn_id, set()))
        expostos_da_conn = sorted(self.expostos_by_conn.pop(conn_id, set()))
        for canon in expostos_da_conn:
            entry_exp = self.expostos.get(canon)
            if entry_exp is None:
                continue
            if entry_exp.refcount > 1:
                entry_exp.refcount -= 1
                continue
            del self.expostos[canon]
        ja_no_repouso: set[str] = set()
        for canon in sorted(self.by_conn.get(conn_id, set())):
            entry = self.hidden.get(canon)
            if entry is None:
                continue
            if entry.refcount > 1:
                entry.refcount -= 1
                continue
            base_do_no = canon.rsplit("/", 1)[-1]
            self.by_conn.get(conn_id, set()).discard(canon)
            ja_no_repouso.add(canon)
            response = self._repouso(canon, base_do_no, cmd="restore")
            if response.get("ok"):
                del self.hidden[canon]
                restored.append(canon)
            else:
                failed.append(canon)
        for canon in expostos_da_conn:
            if canon in self.expostos or canon in ja_no_repouso:
                continue
            adiado = canon in self.hidden and self._lease_holders(canon) > 0
            resposta = self._repouso(canon, canon.rsplit("/", 1)[-1], cmd="unexpose")
            if resposta.get("ok"):
                restored.append(canon)
                if adiado and resposta.get("state") == "fechado":
                    self._log("hide_adiado_cumprido", node=canon, conn=conn_id)
            else:
                failed.append(canon)
        self.by_conn.pop(conn_id, None)
        self.podados_by_conn.pop(conn_id, None)
        for canon in sorted(tocados):
            self._aplicar_entradas(canon)
        if restored:
            self._log("lease_closed_restored", conn=conn_id, nodes=",".join(restored))
        if failed:
            self._log("lease_restore_parcial", conn=conn_id, failed=",".join(failed))
        return restored

    def restore_everything(self) -> list[str]:
        """Belt do shutdown do broker: restaura TODO nó ainda escondido."""
        restored: list[str] = []
        if self.no_nasce_fechado and self._reinicio_sem_abrir():
            self._log(
                "reinicio_sem_abrir",
                escondidos=",".join(sorted(self.hidden)) or "-",
                expostos=",".join(sorted(self.expostos)) or "-",
            )
        else:
            abrir = getattr(self._ops, "abrir_entradas", None)
            for canon, entry in sorted(self.hidden.items()):
                base = canon.rsplit("/", 1)[-1]
                response = self._fs_restore(canon, base, entry.uid)
                if response.get("ok"):
                    del self.hidden[canon]
                    restored.append(canon)
                if callable(abrir) and response.get("state") != "gone":
                    with contextlib.suppress(OSError):
                        abrir(base, entry.uid)
            if callable(abrir):
                for canon in sorted(self.expostos):
                    with contextlib.suppress(OSError):
                        abrir(canon.rsplit("/", 1)[-1], self.allowed_uid)
        self.by_conn.clear()
        self.podados_by_conn.clear()
        self.expostos.clear()
        self.expostos_by_conn.clear()
        self.entradas_by_conn.clear()
        for conn_id in sorted(self.pads_by_conn):
            self._desmontar_os_pads_da(conn_id)
        with contextlib.suppress(OSError):
            self._pad_ops.desmontar_todos()
        return restored


def physical_nodes_exposure(
    uid: int,
    *,
    dev_root: str = "/dev",
    sys_class_hidraw: str = "/sys/class/hidraw",
    sys_class_bluetooth: str = "/sys/class/bluetooth",
    ops: Any | None = None,
    validator: Callable[[str], str | None] | None = None,
) -> dict[str, bool]:
    """{nó hidraw do DualSense FÍSICO: está exposto ao `uid`?} — só leitura.

    R-06 item 3 (auditoria 23/07): a exceção de Steam Input por appid tinha
    duas noções sendo confundidas numa só frase — "configurada" (o appid está
    no `steam_input_apps.txt`) e "EFETIVA" (o hidraw do físico é de fato
    legível pelo uid da usuária agora). A allowlist ficou inerte por meses
    justamente porque ninguém media a segunda; um status honesto precisa das  # (noqa-acento)
    duas. Quem consulta é o `doctor.sh`; a interface deixou de consultar em 13/09/2026.

    Espelho read-only de `restore_all_physical` (mesma varredura, mesmo
    validador, mesmo critério de exposição), sem root, sem mutar nada e sem
    falar com o broker — quem chama roda como a usuária, e é a permissão DO USUÁRIO
    que decide. Nunca levanta: sysfs ilegível devolve `{}`.
    """
    fs_ops = ops if ops is not None else FsAclOps(sys_class_hidraw=sys_class_hidraw)
    out: dict[str, bool] = {}
    try:
        entries = sorted(os.listdir(sys_class_hidraw))
    except OSError:
        return out
    for base in entries:
        node = f"{dev_root}/{base}"
        valid = (
            validator(node)
            if validator is not None
            else validate_physical_node(
                node,
                dev_root=dev_root,
                sys_class_hidraw=sys_class_hidraw,
                sys_class_bluetooth=sys_class_bluetooth,
            )
        )
        if valid is None:
            continue
        out[node] = bool(fs_ops.is_exposed_to(node, uid))
    return out


def restore_all_physical(
    *,
    uid: int,
    ops: Any | None = None,
    dev_root: str = "/dev",
    sys_class_hidraw: str = "/sys/class/hidraw",
    sys_class_bluetooth: str = "/sys/class/bluetooth",
    validator: Callable[[str], str | None] | None = None,
    log: Callable[..., None] = _log,
) -> list[str]:
    """Varre /sys/class/hidraw e restaura físicos não-expostos (baseline limpo)."""
    fs_ops = (
        ops
        if ops is not None
        else FsAclOps(sys_class_hidraw=sys_class_hidraw, sys_class_bluetooth=sys_class_bluetooth)
    )
    restored: list[str] = []
    try:
        entries = sorted(os.listdir(sys_class_hidraw))
    except OSError:
        return restored
    fechadas_fn = getattr(fs_ops, "entradas_fechadas_para", None)
    abrir_fn = getattr(fs_ops, "abrir_entradas", None)
    for base in entries:
        node = f"{dev_root}/{base}"
        valid = (
            validator(node)
            if validator is not None
            else validate_physical_node(
                node,
                dev_root=dev_root,
                sys_class_hidraw=sys_class_hidraw,
                sys_class_bluetooth=sys_class_bluetooth,
            )
        )
        if valid is None:
            continue
        if callable(fechadas_fn) and callable(abrir_fn) and fechadas_fn(base, uid):
            try:
                mudados, falhos = abrir_fn(base, uid)
            except OSError as exc:
                log("baseline_entradas_restore_failed", node=node, err=str(exc))
            else:
                if mudados:
                    log("baseline_entradas_restored", node=node, nos=",".join(mudados))
                if falhos:
                    log("baseline_entradas_restore_failed", node=node, nos=",".join(falhos))
        if fs_ops.is_exposed_to(node, uid):
            continue
        try:
            fs_ops.restore(node, base, uid)
        except OSError as exc:
            log("baseline_restore_failed", node=node, err=str(exc))
            continue
        restored.append(node)
        log("baseline_restored", node=node, uid=uid)
    return restored


def fechar_todo_fisico(
    *,
    uid: int,
    ops: Any | None = None,
    dev_root: str = "/dev",
    sys_class_hidraw: str = "/sys/class/hidraw",
    sys_class_bluetooth: str = "/sys/class/bluetooth",
    validator: Callable[[str], str | None] | None = None,
    log: Callable[..., None] = _log,
) -> list[str]:
    """Varre /sys/class/hidraw e FECHA (`0600 root`) todo físico ainda exposto."""
    fs_ops = (
        ops
        if ops is not None
        else FsAclOps(sys_class_hidraw=sys_class_hidraw, sys_class_bluetooth=sys_class_bluetooth)
    )
    fechados: list[str] = []
    try:
        entries = sorted(os.listdir(sys_class_hidraw))
    except OSError:
        return fechados
    abertas_fn = getattr(fs_ops, "entradas_abertas", None)
    fechar_fn = getattr(fs_ops, "fechar_entradas", None)
    for base in entries:
        node = f"{dev_root}/{base}"
        valid = (
            validator(node)
            if validator is not None
            else validate_physical_node(
                node,
                dev_root=dev_root,
                sys_class_hidraw=sys_class_hidraw,
                sys_class_bluetooth=sys_class_bluetooth,
            )
        )
        if valid is None:
            continue
        if callable(abertas_fn) and callable(fechar_fn) and abertas_fn(base):
            try:
                mudados, falhos = fechar_fn(base)
            except OSError as exc:
                log("baseline_entradas_fechar_failed", node=node, err=str(exc))
            else:
                if mudados:
                    log("baseline_entradas_fechadas", node=node, nos=",".join(mudados))
                if falhos:
                    log("baseline_entradas_fechar_failed", node=node, nos=",".join(falhos))
        if not fs_ops.is_exposed_to(node, uid):
            continue
        try:
            fs_ops.hide(node, base)
        except OSError as exc:
            log("baseline_fechar_failed", node=node, err=str(exc))
            continue
        fechados.append(node)
        log("baseline_fechado", node=node)
    return fechados


def peer_credentials(sock: socket.socket) -> tuple[int, int, int]:
    """(pid, uid, gid) do peer via SO_PEERCRED — kernel-autoritativo."""
    data = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    pid, uid, gid = struct.unpack("3i", data)
    return int(pid), int(uid), int(gid)


class Broker:
    """Loop de eventos do broker: accept, autoriza (SO_PEERCRED), serve linhas."""

    def __init__(
        self,
        state: BrokerState,
        listen_sock: socket.socket | None = None,
        *,
        peercred_fn: Callable[[socket.socket], tuple[int, int, int]] = peer_credentials,
        log: Callable[..., None] = _log,
    ) -> None:
        self._state = state
        self._peercred_fn = peercred_fn
        self._log = log
        self._sel = selectors.DefaultSelector()
        self._listen = listen_sock
        self._next_conn_id = 1
        self._buffers: dict[int, bytearray] = {}
        self._peer_uids: dict[int, int] = {}
        self.stopping = False
        if listen_sock is not None:
            listen_sock.setblocking(False)
            self._sel.register(listen_sock, selectors.EVENT_READ, ("accept", 0))

    def register_client(self, sock: socket.socket) -> int | None:
        """Autoriza e registra uma conexão; None = recusada (e fechada)."""
        try:
            pid, uid, _gid = self._peercred_fn(sock)
        except OSError:
            sock.close()
            return None
        if uid != self._state.allowed_uid:
            self._log("peer_rejected", peer_uid=uid, peer_pid=pid)
            sock.close()
            return None
        conn_id = self._next_conn_id
        self._next_conn_id += 1
        sock.setblocking(False)
        self._sel.register(sock, selectors.EVENT_READ, ("conn", conn_id))
        self._buffers[conn_id] = bytearray()
        self._peer_uids[conn_id] = uid
        self._log("peer_accepted", conn=conn_id, peer_uid=uid, peer_pid=pid)
        return conn_id

    def step(self, timeout: float | None = None) -> None:
        """Uma iteração do selector (testável sem thread)."""
        for key, _events in self._sel.select(timeout):
            kind, conn_id = key.data
            sock = key.fileobj
            assert isinstance(sock, socket.socket)
            if kind == "accept":
                try:
                    client, _addr = sock.accept()
                except OSError:
                    continue
                self.register_client(client)
            else:
                self._service(sock, conn_id)

    def run(self) -> None:
        try:
            while not self.stopping:
                self.step(timeout=1.0)
        finally:
            restored = self._state.restore_everything()
            if restored:
                self._log("shutdown_restored", nodes=",".join(restored))
            self._sel.close()


    def _service(self, sock: socket.socket, conn_id: int) -> None:
        try:
            data = sock.recv(4096)
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            data = b""
        if not data:
            self._close_conn(sock, conn_id)
            return
        buffer = self._buffers[conn_id]
        buffer.extend(data)
        if len(buffer) > MAX_LINE_BYTES and b"\n" not in buffer:
            self._send(sock, {"ok": False, "error": "reject_oversize"})
            self._close_conn(sock, conn_id)
            return
        while True:
            newline = buffer.find(b"\n")
            if newline < 0:
                return
            line = bytes(buffer[:newline])
            del buffer[: newline + 1]
            if not line.strip():
                continue
            response, fd = self._state.handle_line(conn_id, self._peer_uids[conn_id], line)
            sent = (
                self._send_with_fd(sock, response, fd)
                if fd is not None
                else self._send(sock, response)
            )
            if not sent:
                self._close_conn(sock, conn_id)
                return

    def _send(self, sock: socket.socket, payload: dict[str, object]) -> bool:
        try:
            sock.sendall(json.dumps(payload).encode("utf-8") + b"\n")
            return True
        except OSError:
            return False

    def _send_with_fd(self, sock: socket.socket, payload: dict[str, object], fd: int) -> bool:
        """Resposta ok do cmd `open`: o fd viaja NA MESMA mensagem da linha."""
        line = json.dumps(payload).encode("utf-8") + b"\n"
        try:
            sock.sendmsg([line], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, struct.pack("i", fd))])
            return True
        except OSError:
            return False
        finally:
            os.close(fd)

    def _close_conn(self, sock: socket.socket, conn_id: int) -> None:
        with contextlib.suppress(KeyError, ValueError):
            self._sel.unregister(sock)
        sock.close()
        self._buffers.pop(conn_id, None)
        self._peer_uids.pop(conn_id, None)
        self._state.on_conn_closed(conn_id)
        self._log("peer_closed", conn=conn_id)


def _sd_listen_socket() -> socket.socket | None:
    """fd 3 do systemd (LISTEN_FDS), ou None se não somos socket-activated."""
    if os.environ.get("LISTEN_PID") != str(os.getpid()):
        return None
    try:
        nfds = int(os.environ.get("LISTEN_FDS", "0"))
    except ValueError:
        return None
    if nfds < 1:
        return None
    return socket.socket(fileno=3)


def _sd_notify(message: str) -> None:
    """sd_notify mínimo (READY=1) — best-effort, sem libsystemd."""
    target = os.environ.get("NOTIFY_SOCKET")
    if not target:
        return
    if target.startswith("@"):
        target = "\0" + target[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.sendto(message.encode("utf-8"), target)
    except OSError:
        pass


def _manual_listen_socket(path: str) -> socket.socket:
    """Bind manual (debug/execução fora do systemd). Modo 0660."""
    with contextlib.suppress(FileNotFoundError):
        os.unlink(path)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(path)
    os.chmod(path, 0o660)
    sock.listen(8)
    return sock


DEFAULT_UNIT_PATH = "/etc/systemd/system/hefesto-hidraw-broker.service"


def _parse_allowed_uid_from_unit(unit_path: str) -> int | None:
    """Extrai o uid da linha `Environment=HEFESTO_BROKER_ALLOWED_UID=N` da unit."""
    try:
        with open(unit_path, encoding="utf-8", errors="replace") as fh:
            texto = fh.read()
    except OSError:
        return None
    match = re.search(
        rf"^Environment={ALLOWED_UID_ENV}=(\d+)\s*$", texto, flags=re.MULTILINE
    )
    if match is None:
        return None
    return int(match.group(1))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--restore-all-and-exit",
        action="store_true",
        help="restaura todo DualSense físico não-exposto e sai (baseline/stop)",
    )
    parser.add_argument(
        "--fechar-tudo-e-sair",
        action="store_true",
        help=(
            "baseline do ExecStartPre com a cura O-NO-NASCE-FECHADO-01: fecha "
            "(0600 root) todo DualSense físico ainda exposto e sai. SEM a cura "
            f"instalada ({NO_NASCE_FECHADO_ENV} != 1) cai no comportamento "
            "histórico de --restore-all-and-exit, para que a MESMA unit sirva "
            "às duas máquinas sem branch no systemd"
        ),
    )
    parser.add_argument(
        "--allowed-uid",
        type=int,
        default=None,
        help=(
            "uid da sessão para o modo --restore-all-and-exit quando a env "
            f"{ALLOWED_UID_ENV} não está presente (belt de uninstall/purge)"
        ),
    )
    parser.add_argument(
        "--unit-path",
        default=DEFAULT_UNIT_PATH,
        help="unit instalada de onde parsear o uid no belt (fallback final)",
    )
    parser.add_argument(
        "--socket-path",
        default=DEFAULT_SOCKET_PATH,
        help="socket de escuta quando NÃO socket-activated (debug)",
    )
    args = parser.parse_args(argv)

    uid_raw = os.environ.get(ALLOWED_UID_ENV)
    allowed_uid: int | None = None
    if uid_raw is not None and uid_raw.isdigit():
        allowed_uid = int(uid_raw)
    no_nasce_fechado = os.environ.get(NO_NASCE_FECHADO_ENV, "").strip() == "1"

    if args.restore_all_and_exit or args.fechar_tudo_e_sair:
        if allowed_uid is None:
            allowed_uid = args.allowed_uid
        if allowed_uid is None:
            allowed_uid = _parse_allowed_uid_from_unit(args.unit_path)
            if allowed_uid is not None:
                _log("allowed_uid_from_unit", unit=args.unit_path, uid=allowed_uid)
        if allowed_uid is None:
            _log("allowed_uid_missing", env=ALLOWED_UID_ENV)
            return 1
        if allowed_uid == 0:
            _log("allowed_uid_root_recusado", env=ALLOWED_UID_ENV)
            return 1
        # O pad em USB não sobrevive ao broker que o montou (a lease morreu).
        with contextlib.suppress(OSError):
            desmontados = PadUsbOps().desmontar_todos()
            if desmontados:
                _log("pad_usb_orfaos_desmontados", gadgets=",".join(desmontados))
        if args.fechar_tudo_e_sair and no_nasce_fechado:
            fechados = fechar_todo_fisico(uid=allowed_uid)
            _log("fechar_tudo_done", count=len(fechados))
            return 0
        if args.restore_all_and_exit and no_nasce_fechado and reinicio_sem_abrir_pedido():
            _log("reinicio_sem_abrir", belt="restore-all-and-exit")
            return 0
        restored = restore_all_physical(uid=allowed_uid)
        _log("restore_all_done", count=len(restored))
        return 0

    if allowed_uid is None:
        _log("allowed_uid_missing", env=ALLOWED_UID_ENV)
        return 1
    if allowed_uid == 0:
        _log("allowed_uid_root_recusado", env=ALLOWED_UID_ENV)
        return 1

    if no_nasce_fechado:
        fechar_todo_fisico(uid=allowed_uid)
    else:
        restore_all_physical(uid=allowed_uid)

    listen = _sd_listen_socket()
    if listen is None:
        listen = _manual_listen_socket(args.socket_path)
        _log("listening_manual", path=args.socket_path)

    state = BrokerState(allowed_uid=allowed_uid, no_nasce_fechado=no_nasce_fechado)
    broker = Broker(state, listen)

    def _stop(_signum: int, _frame: object) -> None:
        broker.stopping = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    _sd_notify("READY=1")
    _log("ready", allowed_uid=allowed_uid, no_nasce_fechado=no_nasce_fechado)
    broker.run()
    return 0


if __name__ == "__main__":  # pragma: no cover - entrypoint real (root)
    sys.exit(main())
