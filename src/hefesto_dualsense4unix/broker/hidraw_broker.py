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
    INVERTIDA. Com o `assets/70-ps5-controller.rules` da cura, o nó do físico
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

Desenho vigente: docs/process/estudos/2026-07-20-desenho-onda-s-broker-fd-injection.md
(spec original da mecânica ACL: docs/process/estudos/2026-07-18-estudo-broker-hide-hidraw.md).

Regras de ouro (invariante "duplicado > zero controles"):
  - A conexão do daemon É a lease: EOF (daemon morreu) restaura TUDO que aquela
    conexão escondeu — sem heartbeat, o kernel garante o EOF.
  - `--restore-all-and-exit` (ExecStartPre/ExecStopPost) restaura qualquer
    físico deixado escondido por uma vida anterior do broker.
  - Um nó NUNCA é "esquecido" com o fs em 0600: só sai do rastreio DEPOIS do
    restore de fs verificado (lição 2 da auditoria que parkou a 1ª versão).
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
import fcntl
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

#: Socket de comando (criado pelo systemd via hefesto-hidraw-broker.socket).
DEFAULT_SOCKET_PATH = "/run/hefesto-hidraw-broker/broker.sock"
#: Env com o uid autorizado (renderizado pelo install a partir de SUDO_UID).
ALLOWED_UID_ENV = "HEFESTO_BROKER_ALLOWED_UID"
#: O-NO-NASCE-FECHADO-01 (20/09/2026) — "1" quando o `assets/70-ps5-controller.
#: rules` instalado FECHA o nó do DualSense físico (`TAG-="uaccess"`, 0600
#: root). Renderizada pelo install na unit, e é ela que acopla as duas metades
#: da cura: a udev decide o estado de NASCIMENTO, e este env conta ao broker
#: qual é o estado de REPOUSO para onde `restore`/EOF devolvem o nó. Sem o
#: acoplamento a cura teria dois donos que podem discordar — e o desfecho de
#: discordarem é um nó fechado que ninguém reabre, ou um `restore` de ungrab
#: reabrindo justo o que a regra fechou (a janela que a Steam usa).
NO_NASCE_FECHADO_ENV = "HEFESTO_BROKER_NO_NASCE_FECHADO"
#: Linha de protocolo maior que isto é rejeitada (`reject_oversize`).
MAX_LINE_BYTES = 4096

# Identidade canônica (HID_ID do pai HID imediato — transport-independent).
PHYS_VENDOR = 0x054C  # Sony
PHYS_PRODUCT = 0x0CE6  # DualSense físico
VPAD_PRODUCT = 0x0DF2  # DualSense Edge: o do NOSSO vpad e o do Edge físico
#: STEAM-NO-FISICO-01 (24/09/2026) — os PIDs de DualSense FÍSICO que o broker
#: esconde, expõe e abre. O Edge físico (0df2) entrou: o nó dele nasce fechado
#: como o do standard (`assets/70-ps5-controller.rules`), e sem o broker
#: aceitá-lo ninguém o abriria. O 0df2 é TAMBÉM o PID do nosso vpad uhid, então
#: ele deixou de ser recusado pelo PID e passou a ser recusado pelo que o
#: distingue do físico: USB sob `/misc/uhid/` (D1) e o `phys`/`uniq` do vpad
#: (D2). O Edge físico pelo cabo tem pai USB real; pelo rádio é bus 0005.
PHYS_PRODUCTS = frozenset({PHYS_PRODUCT, VPAD_PRODUCT})
BUS_USB = 0x0003
BUS_BT = 0x0005
ACCEPTED_BUSES = frozenset({BUS_USB, BUS_BT})

#: Identidade do vpad no HID — espelhada de `core/backend_pydualsense.py`
#: (`_VPAD_PHYS`/`_VPAD_UNIQ_PREFIX`). O broker é stdlib autocontido e não
#: importa o pacote; o teste de paridade trava os valores.
VPAD_PHYS_PREFIX = "hefesto-vpad"
VPAD_UNIQ_PREFIX = "02fe"

_HIDRAW_BASE_RE = re.compile(r"^hidraw[0-9]+$")

# HIDE-SO-O-HIDRAW-02 (24/09/2026) — os QUATRO nós de entrada do físico. O
# mesmo DualSense aparece em três superfícies: o hidraw, o evdev
# (`/dev/input/eventN`: o gamepad, o touchpad, os sensores de movimento e a
# tomada do fone) e o joydev (`/dev/input/jsN`). Decisão dela de 23/09,
# «Esconder tudo»: os nós de entrada somem para todos menos para o Hefesto,
# como o hidraw já some, e só o Modo Nativo os devolve.
#: Diretório dos nós de entrada.
DEV_INPUT_ROOT = "/dev/input"
#: Os nós de entrada que o broker fecha e abre junto com o hidraw do aparelho.
_ENTRADA_BASE_RE = re.compile(r"^(event|js)[0-9]+$")
#: O único nó de entrada que o broker SERVE por fd: o daemon lê evdev, nunca js.
_EVENT_BASE_RE = re.compile(r"^event[0-9]+$")
#: O `jsN` dos sensores de movimento é da `80-motion-joydev-hide.rules`
#: (`MODE="0000"` para todos): o broker nunca o abre nem o fecha, senão um
#: `restore` daria à sessão o joystick fantasma que aquela regra esconde.
_SUFIXO_DO_MOVIMENTO = "Motion Sensors"
#: EVIOCGID = _IOR('E', 0x02, struct input_id{__u16 bustype, vendor, product,
#: version}) — a identidade lida do PRÓPRIO fd, à prova de corrida, como o
#: HIDIOCGRAWINFO faz para o hidraw (S-4).
_EVIOCGID = 0x80084502
_INPUT_ID_FMT = "=HHHH"

#: O REINÍCIO QUE NÃO ABRE — HIDE-SO-O-HIDRAW-02, achado do install de 24/09.
#: Parar o broker ABRE todo físico (`restore_everything` e o ExecStopPost),
#: e é de propósito: broker fora do ar deixou de ser a porta. Num REINÍCIO
#: pedido (o install trocando o binário) a porta volta em um segundo, e abrir
#: nesse segundo é entregar o físico à Steam aberta, que vigia /dev por
#: inotify e pega o nó na hora. Quem reinicia de propósito grava este arquivo
#: (root, recente) antes do `systemctl restart`, e o broker que sai não abre.
REINICIO_SEM_ABRIR_PATH = "/run/hefesto-hidraw-broker/reinicio-sem-abrir"
#: Validade do pedido: passado isto, o arquivo é lixo de um install que caiu
#: no meio, e o broker volta a abrir ao parar — o piso de recuperação.
REINICIO_SEM_ABRIR_VALIDADE_S = 120.0

# S-4 (auditoria 21/07): identidade RACE-FREE do fd servido. O check
# rdev(fd)==sysfs(base) prova nó==base, NÃO a identidade do device — no
# minor-reuse (o nome `base` reciclado para OUTRO device com o mesmo
# major:minor entre validar e abrir) o broker serviria um fd O_RDWR de ROOT de
# um hidraw ALHEIO (ex.: teclado BT = primitiva de keylogger) a um processo do
# mesmo uid. HIDIOCGRAWINFO lê bustype/vendor/product do PRÓPRIO fd, direto do
# kernel: à prova de corrida. _IOR('H', 0x03, struct hidraw_devinfo{__u32
# bustype; __s16 vendor; __s16 product;}) == 0x80084803 (8 bytes).
_HIDIOCGRAWINFO = 0x80084803
_HIDRAW_DEVINFO_FMT = "=Ihh"  # bustype u32, vendor s16, product s16


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


#: Formato REAL (zero-preenchido) do valor de HID_ID no uevent do kernel:
#: BUS:0000VVVV:0000PPPP — ex.: 0003:0000054C:00000CE6 (USB),
#: 0005:0000054C:00000CE6 (BT, inclusive via uhid do BlueZ ≥5.73).
_HID_ID_VALUE_RE = re.compile(r"^([0-9A-Fa-f]{4}):([0-9A-Fa-f]{8}):([0-9A-Fa-f]{8})$")
#: MAC bem-formado (aa:bb:cc:dd:ee:ff, minúsculo) — HID_UNIQ/HID_PHYS de BT real.
_MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")


def _log(event: str, **fields: object) -> None:
    """Log estruturado simples no stdout (vai ao journal via systemd)."""
    parts = [event] + [f"{key}={value}" for key, value in fields.items()]
    print("[hidraw-broker] " + " ".join(parts), flush=True)


# ---------------------------------------------------------------------------
# Validador — SÓ nós filhos do DualSense físico 054c:0ce6/0df2 (BLUEZ-UHID-01)
# ---------------------------------------------------------------------------


def canonical_hidraw_base(node: object, *, dev_root: str = "/dev") -> str | None:
    """Basename `hidrawN` se `node` é EXATAMENTE `<dev_root>/hidrawN`; senão None.

    Checagem puramente textual (sem tocar o fs): rejeita `..`, barras extras,
    prefixo errado e basenames que não são `hidraw<N>`. Depois de validado, o
    broker SÓ opera em caminhos reconstruídos a partir do basename — o caminho
    do cliente nunca é reusado por concatenação.
    """
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
    """True quando o pai HID é o vpad do daemon (D1/D2), qualquer que seja o PID.

    STEAM-NO-FISICO-01 (24/09/2026): o Edge físico (0df2) passou a ser aceito,
    e o 0df2 é também o PID do vpad — a recusa do vpad deixou de poder ser pelo
    PID. Ela é pelo que só o vpad tem, as mesmas duas marcas do
    `validate_physical_node`:

    - D1: USB sob `/devices/virtual/misc/uhid/` — o cabo real nunca é uhid; o
      vpad é BUS_USB que nasce no uhid;
    - D2: o `phys` (`hefesto-vpad*`) ou o `uniq` (prefixo 02:fe) do vpad.
    """
    if "/misc/uhid/" in hid_parent and bus != BUS_BT:
        return True
    phys = uevent.get("HID_PHYS", "").strip().lower()
    uniq = uevent.get("HID_UNIQ", "").strip().lower()
    return phys.startswith(VPAD_PHYS_PREFIX) or uniq.replace(":", "").startswith(
        VPAD_UNIQ_PREFIX
    )


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
    # STEAM-NO-FISICO-01: o 0df2 é o Edge físico E o nosso vpad. O vpad JAMAIS
    # é escondido/aberto (é por ele que rumble/triggers/lightbar do jogo
    # chegam), e ele é USB sob `/misc/uhid/` — o D1 logo abaixo o recusa, e o
    # D2 é o cinto. O Edge físico pelo cabo tem pai USB real e nem entra no
    # ramo de baixo; pelo rádio é bus 0005 com o MAC dele, como o standard.
    # ---- decisão BLUEZ-UHID-01: /devices/virtual/ NÃO é veredito ----
    if "/devices/virtual/" in hid_parent:
        if "/misc/uhid/" not in hid_parent:
            return False  # uinput/virtual puro jamais é físico
        if bus != BUS_BT:
            return False  # (D1) USB real NUNCA é uhid: 0003 sob uhid = forjado
        phys = uevent.get("HID_PHYS", "").strip().lower()
        uniq = uevent.get("HID_UNIQ", "").strip().lower()
        if phys.startswith(VPAD_PHYS_PREFIX):
            return False  # (D2) nosso vpad, mesmo que anuncie 0CE6
        if uniq.replace(":", "").startswith(VPAD_UNIQ_PREFIX):
            return False  # (D2)
        if _MAC_RE.match(uniq) is None:
            return False  # (D3) BT real tem HID_UNIQ = MAC do controle
        if _MAC_RE.match(phys) is None:
            return False  # (D3) BT real tem HID_PHYS = MAC do adaptador
        adapters = _adapter_addresses(sys_class_bluetooth)
        if adapters is not None and adapters and phys not in adapters:
            return False  # (D4) belt: só decide com sysfs BT legível
    return True


def canonical_input_base(node: object, *, dev_input_root: str = DEV_INPUT_ROOT) -> str | None:
    """Basename `eventN` se `node` é EXATAMENTE `<dev_input_root>/eventN`; senão None.

    O espelho de `canonical_hidraw_base` para o evdev. Só `eventN`: o `jsN`
    nunca é servido por fd (o daemon lê evdev), então não há por que o
    protocolo aceitá-lo.
    """
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


# ---------------------------------------------------------------------------
# Mecânica de hide/restore/open — ACL via xattr direto, tudo pinado por inode
# ---------------------------------------------------------------------------

_ACL_XATTR = "system.posix_acl_access"
_ACL_VERSION = 2
_ACL_TAG_USER_OBJ = 0x01
_ACL_TAG_USER = 0x02
_ACL_TAG_GROUP_OBJ = 0x04
_ACL_TAG_MASK = 0x10
_ACL_TAG_OTHER = 0x20
_ACL_PERM_RW = 0x06
_ACL_ID_UNDEFINED = 0xFFFFFFFF


def encode_access_acl(uid: int) -> bytes:
    """ACL binária equivalente a `chmod 0660` + `setfacl -m u:<uid>:rw`.

    Byte-idêntica ao blob que o setfacl grava (validado ao vivo): header u32 LE
    versão 2 + entradas `<HHI` (tag, perm, id) ordenadas por tag.
    """
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
    """O nome `hidrawN` foi reciclado para OUTRO device entre validar e agir.

    NÃO herda de OSError de propósito: quem trata OSError (falha de fs
    genérica) nunca pode engolir por acidente a recusa de minor-reuse — o
    cliente re-tenta com o nó novo, não com backoff no nó velho.
    """


class FsAclOps:
    """Operações REAIS de fs (hide/restore/verify/open) — injetável nos testes.

    Lição 5 (minor-reuse): hide/restore PINAM o inode com O_PATH + fstat
    cruzado com o rdev do sysfs e agem via `/proc/self/fd/N` — nunca pelo nome
    (o nome pode ter sido reciclado para outro device entre validar e agir).
    O cmd open revalida o rdev NO PRÓPRIO fd devolvido pelo open(2).
    """

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
        # S-4: o rdev==sysfs prova que o inode pinado É o que o `base` aponta
        # AGORA, mas `base` pode ter sido reciclado para outro device entre o
        # _validate do chamador e aqui — re-checa a identidade pelo uevent.
        if not self._sysfs_hid_identity_ok(base):
            os.close(fd)
            return None
        return fd

    def hide(self, node: str, base: str) -> None:
        """`setfacl -b` + `chmod 0600` → só root abre. Fd já aberto sobrevive."""
        fd = self._pin(node, base)
        if fd is None:
            raise FileNotFoundError(node)  # nó sumiu/reciclado: tratar como gone
        try:
            ref = f"/proc/self/fd/{fd}"  # operações no INODE pinado, não no nome
            with contextlib.suppress(OSError):  # ENODATA = já sem ACL
                os.removexattr(ref, _ACL_XATTR)
            os.chmod(ref, 0o600)
        finally:
            os.close(fd)

    def restore(self, node: str, base: str, uid: int) -> None:
        """`chmod 0660` + ACL `u:<uid>:rw` — reverte exatamente o hide."""
        fd = self._pin(node, base)
        if fd is None:
            raise FileNotFoundError(node)  # nome stale ⇒ gone (replug nasce exposto)
        try:
            ref = f"/proc/self/fd/{fd}"
            os.chmod(ref, 0o660)
            os.setxattr(ref, _ACL_XATTR, encode_access_acl(uid))
        finally:
            os.close(fd)

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
        """open(2) O_RDWR|O_CLOEXEC|O_NOFOLLOW + revalidação pós-open NO fd.

        `fstat(fd)` pina o inode; se o rdev não casa mais o sysfs, o nome foi
        reciclado entre validar e abrir — fecha e levanta `StaleNodeError`
        (o cliente re-tenta com o nó novo). OSError do open(2) propaga.
        """
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
        # S-4: identidade do PRÓPRIO fd, não só rdev==sysfs. Um nó reciclado
        # para outro device no mesmo minor passaria o check de rdev; o
        # HIDIOCGRAWINFO prova que o fd É um DualSense 054c:0ce6/0df2 (à prova de
        # corrida — lê do kernel, não do sysfs por nome). Falha do ioctl (ex.:
        # não é hidraw) ⇒ stale, fd fechado (nenhum caminho vaza fd).
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
        # STEAM-NO-FISICO-01: o devinfo não separa o Edge físico do nosso vpad
        # (os dois são 0003:054c:0df2 pelo cabo). O mesmo cinto do hide/restore
        # pergunta ao sysfs o que só o vpad tem — nunca servir o vpad como físico.
        if not self._sysfs_hid_identity_ok(base):
            os.close(fd)
            raise StaleNodeError(node)
        return fd

    # -- os nós de ENTRADA do mesmo aparelho (HIDE-SO-O-HIDRAW-02) -------

    def entradas_do_no(self, base: str) -> list[tuple[str, str]]:
        """`(nó em /dev/input, diretório dele no sysfs)` de cada nó de entrada do aparelho.

        Derivados do device HID do hidraw `base` — `<hid>/input/input*/eventN`
        e `jsN`, o mesmo caminho que o doctor mede em
        `_nos_de_entrada_do_hidraw`. Fica de fora o `jsN` dos sensores de
        movimento, que a regra 80 fecha para todos.

        O pai HID passa ANTES pelo `_pai_hid_e_dualsense_fisico`: se o nome
        `hidrawN` foi reciclado para outro aparelho entre o pedido e aqui, os
        nós de entrada seriam os DELE — o teclado dela, no pior caso — e o
        broker não mexe em nó de aparelho que não validou. Sysfs ilegível
        devolve lista vazia, e vazia nunca é «tudo fechado».
        """
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
                    continue  # regra 80: MODE 0000 para todos, e fica assim
                saida.append((f"{self._dev_input_root}/{filho}", f"{input_dir}/{filho}"))
        return saida

    #: «É char device?» dos nós de ENTRADA. Hook de classe só para a suíte,
    #: que não cria char device sem root: a subclasse de teste troca isto, e
    #: todo o resto da decisão (o rdev contra o sysfs, a identidade) segue o
    #: de produção.
    _e_char_device = staticmethod(stat_mod.S_ISCHR)

    def _pin_entrada(self, node: str, sys_dir: str) -> int | None:
        """O_PATH no nó de entrada + fstat cruzado com o `dev` do sysfs DELE.

        O `sys_dir` vem de baixo do device HID já validado, e é isso que
        prende a identidade: se o `eventN` foi destruído e recriado para outro
        aparelho, o diretório velho some e a leitura falha. None = sumiu.
        """
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
        """O nó abre para alguém além do root?

        Os bits de grupo e de outros bastam, e a ACL não precisa ser lida: num
        nó com ACL, os bits de grupo SÃO a máscara, e a máscara limita toda
        entrada nomeada. Um `0600` com uma ACL velha de `user:ela:rw` tem
        máscara `---` — a entrada está lá e não vale nada.
        """
        return stat_mod.S_IMODE(st.st_mode) & 0o077 != 0

    def fechar_entradas(self, base: str) -> tuple[list[str], list[str]]:
        """`setfacl -b` + `chmod 0600` em cada nó de entrada: `(mudados, falhos)`.

        `mudados` são só os que ESTAVAM abertos — quem chama loga a
        transição, não a reafirmação (o rehide roda a cada 30 s, e o journal
        de 15/08 já teve 717 linhas da mesma frase).
        """
        mudados: list[str] = []
        falhos: list[str] = []
        for node, sys_dir in self.entradas_do_no(base):
            fd = self._pin_entrada(node, sys_dir)
            if fd is None:
                continue  # sumiu no meio: nada a fechar
            try:
                aberto = self._entrada_aberta_a_alguem(os.fstat(fd))
                ref = f"/proc/self/fd/{fd}"
                with contextlib.suppress(OSError):  # ENODATA = já sem ACL
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
    """O broker está sendo REINICIADO de propósito, e não pode abrir o físico?

    HIDE-SO-O-HIDRAW-02 — o achado do install de 24/09/2026. Quem reinicia o
    serviço de propósito (o install, trocando o binário) grava
    `REINICIO_SEM_ABRIR_PATH` antes do `systemctl restart`. Só vale o arquivo
    que prova quem o escreveu e quando: regular, do root, sem escrita de
    grupo nem de outros, e com no máximo `REINICIO_SEM_ABRIR_VALIDADE_S` de
    idade. O resto é lixo, e lixo não pode impedir o piso de recuperação —
    um nó `0600` sem broker só volta com `sudo`, e isto é um app de
    acessibilidade.
    """
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


# ---------------------------------------------------------------------------
# Estado do broker: protocolo JSON-por-linha + lease/refcount resilientes
# ---------------------------------------------------------------------------

#: Backoff entre tentativas de restore (lição 2): índice = nº da tentativa
#: que falhou (1-based); a 3ª falha desiste (nó SEGUE rastreado).
_RESTORE_BACKOFF_S = (0.0, 0.05, 0.2)


@dataclass
class _HiddenNode:
    """Um nó escondido: uid gravado NO HIDE (fail-safe restaura por ele)."""

    uid: int
    refcount: int = 1


@dataclass
class _ExpostoNode:
    """Um nó mantido ABERTO a pedido: a lease INVERTIDA do `cmd expose`.

    O-NO-NASCE-FECHADO-01. O `hide` tem lease desde a Onda S porque "escondido"
    era o estado excepcional; com o nó nascendo `0600 root` o excepcional passa
    a ser o contrário, e "aberto" precisa da MESMA contabilidade: refcount por
    nó, conjunto por conexão, e EOF que devolve o nó ao repouso. Sem isso, um
    `expose` seria one-shot e nada re-fecharia — sair do Modo Nativo deixaria
    o nó aberto e a Steam voltaria a pegá-lo no próximo replug.
    """

    uid: int
    refcount: int = 1


class BrokerState:
    """Protocolo + contabilidade de lease. Puro (fs injetável) e testável.

    `hidden` é o refcount global por nó; `by_conn` é o conjunto que CADA
    conexão escondeu (a lease). Dois daemons em takeover convivem: o novo
    abre lease nova (refcount 2); o velho morre e restaura só a dele — o
    refcount impede expor um nó que o novo re-escondeu.

    Lições 2-3 da auditoria, obrigatórias aqui:
      - `hide` re-aplica o fs MESMO para nó já rastreado (nó recriado com o
        mesmo hidrawN nasceu exposto; idempotência só em memória mentiria);
      - um nó só é destrackeado DEPOIS do restore de fs verificado (retry com
        backoff); falha mantém o nó na lease e no `hidden` — belts cobrem;
      - falha num nó NUNCA aborta o restore dos demais (EOF/restore_all).
    """

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
    ) -> None:
        self.allowed_uid = allowed_uid
        #: O-NO-NASCE-FECHADO-01: o nó do físico nasce `0600 root` pela regra
        #: udev instalada? Só quem instalou sabe, e é o install que renderiza
        #: `NO_NASCE_FECHADO_ENV` na unit. False = mundo histórico (o udev dá
        #: `uaccess` e o repouso é ABERTO); True = o repouso é FECHADO.
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
        #: A lease INVERTIDA (`cmd expose`): refcount global por nó e, por
        #: conexão, o conjunto que AQUELA conexão mandou manter aberto.
        self.expostos: dict[str, _ExpostoNode] = {}
        self.expostos_by_conn: dict[int, set[str]] = {}
        #: HIDE-SO-O-HIDRAW-02: por conexão, os nós cuja exposição pediu
        #: TAMBÉM os nós de entrada (`expose` com `"entradas": true`). É o
        #: pedido do Modo Nativo — o único que devolve os quatro nós ao jogo.
        #: A exposição transitória do handle de controle (`hidapi` abrindo por
        #: caminho) não pede, e os nós de entrada seguem fechados durante ela.
        self.entradas_by_conn: dict[int, set[str]] = {}

    # -- validação -------------------------------------------------------

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

    # -- os nós de entrada seguem a lease (HIDE-SO-O-HIDRAW-02) ------------

    def _entradas_holders(self, canon: str) -> int:
        """Nº de conexões VIVAS que pediram os nós de ENTRADA de `canon` abertos."""
        return sum(1 for held in self.entradas_by_conn.values() if canon in held)

    def _entradas_devem_abrir(self, canon: str) -> bool:
        """O estado dos nós de entrada, derivado SÓ da contabilidade.

        Três regras, nesta ordem, e a ordem é a decisão dela de 23/09
        («Esconder tudo; só o Modo Nativo devolve»):

        1. alguma conexão viva pediu os nós de entrada (o Modo Nativo) ⇒
           ABERTOS;
        2. alguma lease de hide viva ⇒ FECHADOS (o grab do daemon manda);
        3. senão, o repouso do mundo instalado: fechados com a regra da cura,
           abertos no mundo histórico (`--no-fechar-o-no`).

        A exposição transitória do hidraw NÃO aparece aqui de propósito: o
        `hidapi` do handle de controle precisa do hidraw por caminho, e de
        mais nada.
        """
        if self._entradas_holders(canon) > 0:
            return True
        if self._lease_holders(canon) > 0:
            return False
        return not self.no_nasce_fechado

    def _aplicar_entradas(self, canon: str) -> None:
        """Leva os nós de entrada de `canon` ao estado que a lease manda.

        Idempotente e best-effort: ops sem a mecânica de entrada (dublê antigo
        da suíte, que modela um aparelho sem nós de entrada) não fazem nada;
        falha num nó vira log e nunca derruba a resposta do hidraw — o
        controle continua usável pelo hidraw, e a próxima reconciliação
        (o rehide de 30 s) tenta de novo.
        """
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
        """Depois de um comando sobre UM nó, os nós de entrada dele seguem.

        Só para nó canônico que passou pelo validador: as recusas
        (`reject_*`) não tocam nada, e o nó que sumiu (`gone`) não tem nós
        de entrada.
        """
        erro = resposta.get("error")
        if isinstance(erro, str) and erro.startswith("reject_"):
            return resposta
        if resposta.get("state") == "gone":
            return resposta
        node = resposta.get("node")
        if isinstance(node, str):
            self._aplicar_entradas(node)
        return resposta

    # -- protocolo -------------------------------------------------------

    def handle_line(
        self, conn_id: int, peer_uid: int, line: bytes
    ) -> tuple[dict[str, object], int | None]:
        """Uma requisição JSON-por-linha → (resposta, fd|None). NUNCA levanta.

        Só o cmd `open` com sucesso devolve fd (≠ None) — o servidor o envia
        via SCM_RIGHTS JUNTO com a linha de resposta e fecha a cópia local.
        Erro nunca carrega fd.
        """
        if len(line) > MAX_LINE_BYTES:
            return ({"ok": False, "error": "reject_oversize"}, None)
        try:
            request = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return ({"ok": False, "error": "reject_malformed"}, None)
        if not isinstance(request, dict):
            return ({"ok": False, "error": "reject_malformed"}, None)
        cmd = request.get("cmd")
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
            # HIDE-SO-O-HIDRAW-02: `"entradas": true` é o pedido do Modo
            # Nativo, o único que devolve os nós de entrada. Quem não manda o
            # campo (o `with` transitório do handle, um daemon antigo) expõe
            # só o hidraw — e um broker antigo ignora o campo, expõe o hidraw
            # e o daemon segue funcionando.
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
        """«Mantenha este nó ABERTO enquanto eu viver» — o abrir sob pedido.

        HIDE-SO-O-HIDRAW-02: com `entradas=True` a conexão pede também os nós
        de entrada do aparelho (evdev e joydev). É o Modo Nativo, e o registro
        vai para `entradas_by_conn` — os nós seguem abertos enquanto houver
        UMA conexão viva que os pediu (`_entradas_devem_abrir`).

        O-NO-NASCE-FECHADO-01, item 2 da decisão dela de 20/09/2026. Com o nó
        do físico nascendo `0600 root`, quem precisa abri-lo POR CAMINHO — o
        `hidapi.Device(path=...)` do handle de controle do daemon, e o JOGO no
        Modo Nativo, que é processo de terceiro e só sabe `open(path)` — não
        tem como receber um fd por SCM_RIGHTS. Para esses, a única cura
        possível é o broker PÔR A ACL DE VOLTA enquanto o pedido durar.

        A mecânica de fs já existia inteira (`FsAclOps.restore` grava
        `chmod 0660` + `system.posix_acl_access` do uid por conta própria, sem
        depender do udev devolver nada). O que faltava era a CONTABILIDADE: sem
        lease, expor é one-shot e ninguém re-fecha.
        """
        raw = node if isinstance(node, str) else None
        if canonical_hidraw_base(raw, dev_root=self._dev_root) is None:
            return {"ok": False, "cmd": "expose", "node": raw, "error": "reject_bad_path"}
        assert raw is not None  # narrow p/ mypy: canonical exige str
        base = self._validate(raw)
        if base is None:
            return {
                "ok": False,
                "cmd": "expose",
                "node": raw,
                "error": "reject_not_physical_dualsense",
            }
        canon = f"{self._dev_root}/{base}"
        # Lição 2, espelhada: SEMPRE toca o fs. Um nó recriado com o mesmo
        # `hidrawN` nasceu FECHADO pela regra udev, e o estado em memória não
        # é prova de nada.
        resposta = self._fs_restore(canon, base, peer_uid)
        resposta["cmd"] = "expose"
        if not resposta.get("ok"):
            return resposta
        if resposta.get("state") == "gone":
            # Nó sumiu: não há o que rastrear (o replug refaz o pedido).
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
                # Órfão (a lease que pediu morreu com o fs falho): adota SEM
                # somar — o baseline fantasma nunca seria descontado. Mesma
                # aritmética do `hide`, e pela mesma razão.
                entry.refcount = 1
                entry.uid = peer_uid
                self._log("exposto_orfao_adotado", node=canon, conn=conn_id, uid=peer_uid)
        held.add(canon)
        if entradas:
            self.entradas_by_conn.setdefault(conn_id, set()).add(canon)
        return resposta

    def _cmd_unexpose(self, conn_id: int, node: object) -> dict[str, object]:
        """Solta a lease de exposição e devolve o nó ao REPOUSO.

        Repouso é o estado de nascimento do nó: fechado quando a regra udev da
        cura está instalada (`no_nasce_fechado`), aberto no mundo histórico.
        """
        raw = node if isinstance(node, str) else None
        base = canonical_hidraw_base(raw, dev_root=self._dev_root)
        if base is None:
            return {"ok": False, "cmd": "unexpose", "node": raw, "error": "reject_bad_path"}
        canon = f"{self._dev_root}/{base}"
        held = self.expostos_by_conn.get(conn_id, set())
        entry = self.expostos.get(canon)
        # HIDE-SO-O-HIDRAW-02: o pedido dos nós de entrada desta conexão sai
        # junto com a exposição dela — quem os segue abertos, se houver, é
        # outra conexão viva (`_entradas_devem_abrir`).
        self.entradas_by_conn.get(conn_id, set()).discard(canon)
        if canon in held:
            held.discard(canon)
            if entry is not None and entry.refcount > 1:
                entry.refcount -= 1  # outra lease viva ainda quer o nó aberto
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
        """Devolve o nó ao estado de REPOUSO e responde o que ficou.

        Três destinos, nesta ordem, e a ordem é a decisão dela («o Hefesto tem
        que ter prioridade em tudo»):

        1. alguma lease de EXPOSIÇÃO viva ⇒ aberto (alguém ainda precisa dele);
        2. alguma lease de HIDE viva ⇒ fechado (o grab do daemon manda);
        3. senão ⇒ o estado de NASCIMENTO: fechado com a regra udev da cura
           instalada, aberto sem ela.

        O ramo 3 é o que impede o defeito que a cura existe para matar: com o
        nó nascendo fechado, um `restore` de ungrab que ABRISSE o nó recriaria
        a janela em que a Steam o pega — e ele o faria por ACIDENTE, pelo ramo
        «não rastreado», não por desenho.
        """
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
        assert raw is not None  # narrow p/ mypy: canonical exige str
        base = self._validate(raw)
        if base is None:
            return {
                "ok": False,
                "cmd": "hide",
                "node": raw,
                "error": "reject_not_physical_dualsense",
            }
        canon = f"{self._dev_root}/{base}"
        held = self.by_conn.setdefault(conn_id, set())
        entry = self.hidden.get(canon)
        if self._exposicao_holders(canon) > 0:
            # O-NO-NASCE-FECHADO-01: um pedido EXPLÍCITO de exposição (o Modo
            # Nativo, o open por caminho do handle de controle) vence um hide
            # implícito. A lease do hide é registrada assim mesmo, para que o
            # `unexpose` do último pedido encontre o nó e o feche — o que
            # deixa de fora só o fs, que seria fechar a porta debaixo de quem
            # está entrando por ela. O gate de gamepad.py já evita o caso pelo
            # Modo Nativo; isto é o cinto, e ele mora onde a verdade está.
            if entry is None:
                self.hidden[canon] = _HiddenNode(uid=peer_uid, refcount=1)
            elif canon not in held and self._lease_holders(canon) > 0:
                entry.refcount += 1
            held.add(canon)
            self._log("hide_adiado_por_exposicao", node=canon, conn=conn_id)
            return {"ok": True, "cmd": "hide", "node": canon, "state": "exposed"}
        try:
            # Lição 2: SEMPRE toca o fs (idempotente e barato) — nó recriado
            # com o mesmo hidrawN renasceu exposto e o estado em memória não
            # é prova de nada.
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
                # Achado Onda S #3: nó ÓRFÃO — a lease que o escondeu morreu
                # com o restore de fs falho (`on_conn_closed` o manteve em
                # `hidden`, mas nenhuma conexão viva o referencia). Adotar  # (noqa-acento)
                # SEM somar refcount: o baseline fantasma de 1 nunca seria
                # descontado por ninguém e o `restore_all` da conexão nova
                # pararia em refcount 1 para sempre (nó 0600 até reiniciar o
                # serviço). Normaliza refcount = nº de leases vivas (esta) e
                # o uid segue o novo dono.
                entry.refcount = 1
                entry.uid = peer_uid
                self._log("orphan_adopted", node=canon, conn=conn_id, uid=peer_uid)
        held.add(canon)
        return {"ok": True, "cmd": "hide", "node": canon, "state": "hidden"}

    def _cmd_restore(self, conn_id: int, node: object) -> dict[str, object]:
        raw = node if isinstance(node, str) else None
        base = canonical_hidraw_base(raw, dev_root=self._dev_root)
        if base is None:
            return {"ok": False, "cmd": "restore", "node": raw, "error": "reject_bad_path"}
        canon = f"{self._dev_root}/{base}"
        held = self.by_conn.get(conn_id, set())
        entry = self.hidden.get(canon)
        if canon in held:
            if entry is not None and entry.refcount > 1:
                entry.refcount -= 1  # outra lease viva segura o nó
                held.discard(canon)
                return {"ok": True, "cmd": "restore", "node": canon, "state": "hidden"}
            held.discard(canon)  # a lease sai ANTES do repouso ser decidido
            response = self._repouso(canon, base, cmd="restore")
            if response.get("ok"):
                # Lição 2: só destrackear DEPOIS do fs OK (exposed/fechado/gone).
                self.hidden.pop(canon, None)
            else:
                held.add(canon)  # fs falhou: o nó SEGUE na lease e rastreado
            return response
        if entry is not None:
            if self._lease_holders(canon) > 0:
                # escondido por OUTRA conexão viva: não expõe
                return {"ok": True, "cmd": "restore", "node": canon, "state": "hidden"}
            # Achado Onda S #3: órfão sem lease viva — o restore explícito TEM
            # de tocar o fs (antes respondia "hidden" para sempre; só o
            # reinício do serviço curava um nó 0600 órfão).
            response = self._repouso(canon, base, cmd="restore")
            if response.get("ok"):
                self.hidden.pop(canon, None)
                self._log("orphan_restored", node=canon, conn=conn_id)
            return response
        # Não rastreado: repouso best-effort (idempotente), mas SÓ em nó que
        # valida como físico — nunca mexe em hidraw alheio (teclado etc.).
        #
        # O-NO-NASCE-FECHADO-01: é POR AQUI que o `restore` do ungrab
        # (`gamepad.py::_broker_sync_grab`) passa quando ninguém escondeu o nó
        # — e, no mundo em que o nó nasce fechado, ABRIR aqui recriaria a
        # janela que a Steam usa. O repouso decide: com a regra da cura
        # instalada e sem lease de exposição, este caminho FECHA. Quem precisa
        # do físico aberto passa a dizê-lo com `expose`, por desenho.
        if self._validate(canon) is None:
            return {
                "ok": False,
                "cmd": "restore",
                "node": canon,
                "error": "reject_not_physical_dualsense",
            }
        return self._repouso(canon, base, cmd="restore")

    def _cmd_restore_all(self, conn_id: int) -> dict[str, object]:
        # Lição 3: itera TODOS os nós SEMPRE — falha em um vira log + nó
        # mantido no rastreio, e o loop segue para os demais.
        restored: list[str] = []
        failed: list[str] = []
        for canon in sorted(self.by_conn.get(conn_id, set())):
            # HIDE-SO-O-HIDRAW-02: os nós de entrada de cada nó seguem a lease.
            response = self._entradas_seguem(self._cmd_restore(conn_id, canon))
            if response.get("ok") and response.get("state") in ("exposed", "fechado", "gone"):
                restored.append(canon)
            elif not response.get("ok"):
                failed.append(canon)
        if failed:
            self._log("restore_all_parcial", conn=conn_id, failed=",".join(failed))
        return {"ok": True, "cmd": "restore_all", "restored": restored, "failed": failed}

    def _cmd_open(self, conn_id: int, node: object) -> tuple[dict[str, object], int | None]:
        """Valida, abre O_RDWR|O_CLOEXEC|O_NOFOLLOW e devolve (resposta, fd|None).

        O fd devolvido é enviado pelo servidor via sendmsg(SCM_RIGHTS) JUNTO
        com a linha de resposta; a cópia local é fechada SEMPRE após o sendmsg.
        `open` NÃO altera lease/refcount — é ortogonal ao hide (o reader pode
        pedir fd antes, durante ou depois do hide; funciona nos dois estados,
        porque o broker é root com CAP_DAC_OVERRIDE — é exatamente esta
        assimetria que o design explora).
        """
        raw = node if isinstance(node, str) else None
        if canonical_input_base(raw, dev_input_root=self._dev_input_root) is not None:
            assert raw is not None  # narrow p/ mypy: canonical exige str
            return self._cmd_open_entrada(conn_id, raw)
        base_canon = canonical_hidraw_base(raw, dev_root=self._dev_root)
        if base_canon is None:
            return ({"ok": False, "cmd": "open", "node": raw, "error": "reject_bad_path"}, None)
        assert raw is not None  # narrow p/ mypy: canonical exige str
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
            # Lição 5 (minor-reuse): o nome foi reciclado entre validar e
            # abrir — recusa; o cliente re-tenta com o nó novo.
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

    def _cmd_open_entrada(
        self, conn_id: int, raw: str
    ) -> tuple[dict[str, object], int | None]:
        """O `open` de um nó de ENTRADA (`/dev/input/eventN`) — HIDE-SO-O-HIDRAW-02.

        Com os nós de entrada do físico nascendo `0600 root`, o gamepad, o
        touchpad e os sensores de movimento só chegam ao daemon por aqui, como
        o hidraw já chega. Mesmo contrato do `open` do hidraw: valida sem
        abrir, abre como root, revalida NO fd, e a lease não muda.
        """
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
        """Nº de conexões VIVAS cuja lease segura `canon`.

        Achado Onda S #3: é a fonte da verdade para distinguir "outra lease
        viva segura o nó" (refcount soma/decrementa normal) de "nó ÓRFÃO"
        (lease morreu com o restore de fs falho — `on_conn_closed` mantém o
        nó em `hidden`, mas `by_conn` já não o referencia em lugar nenhum).  # (noqa-acento)
        """
        return sum(1 for held in self.by_conn.values() if canon in held)

    def _fs_restore(self, canon: str, base: str, uid: int) -> dict[str, object]:
        """Restore de fs com retry + verificação (lição 2). NUNCA levanta."""
        for tentativa in (1, 2, 3):
            try:
                self._ops.restore(canon, base, uid)
            except FileNotFoundError:
                # Unplug: o nó sumiu — não é erro (o replug nasce exposto).
                self._log("restore_node_gone", node=canon)
                return {"ok": True, "cmd": "restore", "node": canon, "state": "gone"}
            except OSError as exc:
                if tentativa == 3:
                    self._log("restore_failed", node=canon, err=str(exc))
                    return {"ok": False, "cmd": "restore", "node": canon,
                            "error": "restore_failed"}
                self._sleep(_RESTORE_BACKOFF_S[tentativa])
                continue
            if self._ops.is_exposed_to(canon, uid):  # restore VERIFICADO
                self._log("node_restored", node=canon, uid=uid)
                return {"ok": True, "cmd": "restore", "node": canon, "state": "exposed"}
            self._log("restore_verify_failed", node=canon, uid=uid, tentativa=tentativa)
        # Sinal para o doctor; o nó SEGUE rastreado (nunca "esquecer" um 0600).
        return {"ok": False, "cmd": "restore", "node": canon, "error": "restore_verify_failed"}

    # -- lease (fail-safe) -------------------------------------------------

    def on_conn_closed(self, conn_id: int) -> list[str]:
        """EOF da lease: devolve ao REPOUSO tudo que AQUELA conexão mexeu.

        Lição 3: falha num nó não derruba o loop — o falho fica rastreado em
        `hidden` (sem lease) e os belts cobrem (restore_all do shutdown,
        ExecStopPost, baseline do próximo start).

        O-NO-NASCE-FECHADO-01: são DUAS leases agora, e as duas morrem aqui —
        o que a conexão escondeu e o que ela mandou manter ABERTO. O destino
        de cada nó é o `_repouso`, não mais o restore incondicional: no mundo
        em que o nó nasce fechado, abrir tudo no EOF seria entregar o físico à
        Steam exatamente no instante em que o daemon morreu.
        """
        restored: list[str] = []
        failed: list[str] = []
        # HIDE-SO-O-HIDRAW-02: o pedido dos nós de entrada morre junto, e
        # ANTES de tudo — é ele que os segura abertos no Modo Nativo.
        entradas_da_conn = self.entradas_by_conn.pop(conn_id, set())
        tocados = set(entradas_da_conn) | set(self.by_conn.get(conn_id, set()))
        tocados |= set(self.expostos_by_conn.get(conn_id, set()))
        # O-NO-NASCE-FECHADO-01: as exposições saem PRIMEIRO. Elas são o que
        # segura o nó aberto; soltá-las antes faz o `_repouso` do laço de
        # baixo (e o dos nós que esta conexão só expôs) enxergar a contagem
        # já correta, em vez de deixar aberto quem ninguém mais quer.
        expostos_da_conn = sorted(self.expostos_by_conn.pop(conn_id, set()))
        for canon in expostos_da_conn:
            entry_exp = self.expostos.get(canon)
            if entry_exp is None:
                continue
            if entry_exp.refcount > 1:  # outra lease viva quer o nó aberto
                entry_exp.refcount -= 1
                continue
            del self.expostos[canon]
        for canon in sorted(self.by_conn.get(conn_id, set())):
            entry = self.hidden.get(canon)
            if entry is None:
                continue
            if entry.refcount > 1:  # outra lease viva segura o nó
                entry.refcount -= 1
                continue
            base_do_no = canon.rsplit("/", 1)[-1]
            self.by_conn.get(conn_id, set()).discard(canon)
            response = self._repouso(canon, base_do_no, cmd="restore")
            if response.get("ok"):
                del self.hidden[canon]
                restored.append(canon)
            else:
                failed.append(canon)  # rastreado; belts cobrem
        # Os nós que esta conexão só EXPÔS (nunca escondeu) também têm de
        # voltar ao repouso — senão o Modo Nativo de um daemon que morreu
        # deixaria o físico aberto para a Steam pegar no próximo replug.
        for canon in expostos_da_conn:
            if canon in self.expostos or canon in self.hidden:
                continue
            resposta = self._repouso(canon, canon.rsplit("/", 1)[-1], cmd="unexpose")
            if resposta.get("ok"):
                restored.append(canon)
            else:
                failed.append(canon)
        self.by_conn.pop(conn_id, None)
        # HIDE-SO-O-HIDRAW-02: com a contabilidade já sem esta conexão, os nós
        # de entrada de cada nó que ela tocava vão para o estado que sobra.
        for canon in sorted(tocados):
            self._aplicar_entradas(canon)
        if restored:
            self._log("lease_closed_restored", conn=conn_id, nodes=",".join(restored))
        if failed:
            self._log("lease_restore_parcial", conn=conn_id, failed=",".join(failed))
        return restored

    def restore_everything(self) -> list[str]:
        """Belt do shutdown do broker: restaura TODO nó ainda escondido.

        Este belt ABRE, e abre mesmo com a cura do nó fechado instalada — de
        propósito, e é a única exceção ao repouso. Quando o broker está indo
        embora, ele deixa de ser a porta: um nó `0600 root` sem broker de pé é
        um controle que só volta com `sudo`, e isto é um app de acessibilidade.
        O ExecStartPre do serviço re-fecha no próximo start.

        HIDE-SO-O-HIDRAW-02 (24/09/2026), duas coisas:

        - os nós de ENTRADA abrem junto (`abrir_entradas`): sem o broker, o
          daemon não tem por onde lê-los, e o gamepad inteiro morreria;
        - o REINÍCIO PEDIDO não abre nada (`reinicio_sem_abrir_pedido`). Com o
          nó nascendo fechado, abrir num reinício é entregar o físico à Steam
          aberta no segundo em que o broker novo ainda não subiu — medido no
          install de 24/09, que trocou o binário e deixou o serviço com o
          código velho na memória desde 22/09. O broker novo sobe em ~1 s e o
          baseline dele fecha o que houver.
        """
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
            # Os nós que só foram EXPOSTOS já têm o hidraw aberto, mas os
            # nós de entrada deles podem estar fechados (a exposição
            # transitória não os abre): o broker que sai abre todos.
            if callable(abrir):
                for canon in sorted(self.expostos):
                    with contextlib.suppress(OSError):
                        abrir(canon.rsplit("/", 1)[-1], self.allowed_uid)
        self.by_conn.clear()
        self.expostos.clear()
        self.expostos_by_conn.clear()
        self.entradas_by_conn.clear()
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
    falar com o broker — quem chama roda como a usuária, e é a permissão DELA
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
    """Varre /sys/class/hidraw e restaura físicos não-expostos (baseline limpo).

    Usado por `--restore-all-and-exit` (ExecStopPost, e o ExecStartPre do
    mundo SEM a cura do nó fechado): nunca herda um físico escondido órfão de
    uma vida anterior. Idempotente e best-effort.

    O-NO-NASCE-FECHADO-01, e é a colisão que a sprint não previu: com o nó
    nascendo `0600 root`, chamar ISTO no start do broker DESFARIA a cura para
    todo controle conectado naquele instante. O «baseline limpo» foi escrito
    quando «exposto» era o estado natural do nó — deixou de ser, e o
    ExecStartPre passou a chamar `--fechar-tudo-e-sair`
    (`fechar_todo_fisico`), que é o baseline do mundo novo. Esta função fica
    como está, e continua sendo o piso de recuperação do ExecStopPost.
    """
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
    # HIDE-SO-O-HIDRAW-02: o piso de recuperação abre também os nós de
    # ENTRADA — sem broker, o daemon não tem outra porta para o gamepad, o
    # touchpad e os sensores de movimento.
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
    """Varre /sys/class/hidraw e FECHA (`0600 root`) todo físico ainda exposto.

    O-NO-NASCE-FECHADO-01 — o baseline do `ExecStartPre` no mundo em que o nó
    nasce fechado. Reconcilia o que a regra udev não alcançou: o controle que
    já estava conectado quando a cura foi instalada, e o nó que ficou aberto
    por uma lease de exposição que morreu com o broker anterior. É a tradução,
    em varredura, de «o Hefesto tem prioridade em tudo».

    Espelho exato do `restore_all_physical` (mesma varredura, mesmo validador,
    mesmo critério de exposição), com o sinal trocado. Idempotente e
    best-effort: falha num nó nunca aborta o laço.
    """
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
    # HIDE-SO-O-HIDRAW-02: o baseline fecha também os nós de ENTRADA. É o que
    # alcança o controle conectado ANTES de o socket do broker existir (a
    # regra 72 só fecha na criação do nó quando há broker para abri-lo) e o
    # controle que já estava na mesa quando a cura chegou.
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


# ---------------------------------------------------------------------------
# Servidor: accept + SO_PEERCRED + loop de conexões + SCM_RIGHTS
# ---------------------------------------------------------------------------


def peer_credentials(sock: socket.socket) -> tuple[int, int, int]:
    """(pid, uid, gid) do peer via SO_PEERCRED — kernel-autoritativo."""
    data = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    pid, uid, gid = struct.unpack("3i", data)
    return int(pid), int(uid), int(gid)


class Broker:
    """Loop de eventos do broker: accept, autoriza (SO_PEERCRED), serve linhas.

    `register_client` é público de propósito: os testes injetam uma ponta de
    `socketpair` sem precisar de socket de escuta nem de /dev real.
    """

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

    # -- interno ---------------------------------------------------------

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
            # Linha gigante sem fim de linha: cliente quebrado. Fechar é o
            # seguro — o EOF da lease restaura o que ela escondeu.
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
        """Resposta ok do cmd `open`: o fd viaja NA MESMA mensagem da linha.

        Nunca em mensagem separada — o pareamento respostafd tem de ser
        inambíguo. A cópia local do fd é fechada SEMPRE (a duplicata do kernel
        já está em trânsito no buffer do socket, ou perdida se o envio falhou).
        """
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


# ---------------------------------------------------------------------------
# Integração systemd (socket activation + notify) — stdlib pura
# ---------------------------------------------------------------------------


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


#: Unit instalada — fonte do uid para o belt quando a env não veio (S-3).
DEFAULT_UNIT_PATH = "/etc/systemd/system/hefesto-hidraw-broker.service"


def _parse_allowed_uid_from_unit(unit_path: str) -> int | None:
    """Extrai o uid da linha `Environment=HEFESTO_BROKER_ALLOWED_UID=N` da unit.

    Fallback do belt `--restore-all-and-exit` (S-3, auditoria 21/07): os
    callers de uninstall/prerm/postrm chamam o binário SEM a env (só a unit a
    tem) — sem este parse o belt saía 1 `allowed_uid_missing` engolido por
    `|| true` e nunca restaurou nada. Regex estrito (linha inteira, só
    dígitos); unit ausente/ilegível → None (o caller decide falhar).
    """
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
        # S-3 (auditoria 21/07): o belt aceita uid de 3 fontes, nesta ordem —
        # env (ExecStartPre/ExecStopPost da unit), --allowed-uid (caller
        # explícito) e parse da unit instalada (uninstall/prerm/postrm chamam
        # o binário pelado; a unit renderizada é a fonte da verdade que o
        # install gravou). Sem NENHUMA: exit 1 explícito, como antes.
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
        if args.fechar_tudo_e_sair and no_nasce_fechado:
            fechados = fechar_todo_fisico(uid=allowed_uid)
            _log("fechar_tudo_done", count=len(fechados))
            return 0
        if args.restore_all_and_exit and no_nasce_fechado and reinicio_sem_abrir_pedido():
            # HIDE-SO-O-HIDRAW-02: o ExecStopPost de um REINÍCIO pedido não
            # abre nada — o broker novo sobe em ~1 s e o baseline dele fecha
            # o que houver. Sem o pedido (parar de verdade, cair, desinstalar),
            # segue o piso de recuperação de sempre, logo abaixo.
            _log("reinicio_sem_abrir", belt="restore-all-and-exit")
            return 0
        restored = restore_all_physical(uid=allowed_uid)
        _log("restore_all_done", count=len(restored))
        return 0

    if allowed_uid is None:
        _log("allowed_uid_missing", env=ALLOWED_UID_ENV)
        return 1
    if allowed_uid == 0:
        # Lição 6: uid 0 renderizado = install rodado errado (sem sessão).
        # O broker autorizaria ROOT e nenhum daemon de usuária conectaria —
        # falha explícita em vez de serviço mudo/inútil.
        _log("allowed_uid_root_recusado", env=ALLOWED_UID_ENV)
        return 1

    # Baseline em processo também (idempotente; ExecStartPre já cobriu, mas
    # execução manual/debug fica igualmente segura). A DIREÇÃO segue a cura:
    # com o nó nascendo fechado, abrir tudo aqui seria desfazê-la em todo
    # start/restart do broker — a colisão medida em 20/09/2026.
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
