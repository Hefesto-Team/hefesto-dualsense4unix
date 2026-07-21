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
  - `open` (NOVO, desenho 2026-07-20): valida o nó, abre O_RDWR|O_CLOEXEC como
    root e devolve o fd via SCM_RIGHTS na MESMA conexão — o motion reader do
    daemon NUNCA reabre por caminho, então o hide deixa de ter qualquer
    interação com o ciclo de vida do gyro (a classe de bugs broker/motion morre).

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
    físico (054c:0ce6 em USB 0003 ou BT 0005). O vpad 0df2 é REJEITADO
    explicitamente — é por ele que o jogo fala com o controle.
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
#: Linha de protocolo maior que isto é rejeitada (`reject_oversize`).
MAX_LINE_BYTES = 4096

# Identidade canônica (HID_ID do pai HID imediato — transport-independent).
PHYS_VENDOR = 0x054C  # Sony
PHYS_PRODUCT = 0x0CE6  # DualSense físico
VPAD_PRODUCT = 0x0DF2  # DualSense Edge = NOSSO vpad — NUNCA esconder
BUS_USB = 0x0003
BUS_BT = 0x0005
ACCEPTED_BUSES = frozenset({BUS_USB, BUS_BT})

#: Identidade do vpad no HID — espelhada de `core/backend_pydualsense.py`
#: (`_VPAD_PHYS`/`_VPAD_UNIQ_PREFIX`). O broker é stdlib autocontido e não
#: importa o pacote; o teste de paridade trava os valores.
VPAD_PHYS_PREFIX = "hefesto-vpad"
VPAD_UNIQ_PREFIX = "02fe"

_HIDRAW_BASE_RE = re.compile(r"^hidraw[0-9]+$")
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
# Validador — SÓ nós filhos do DualSense físico 054c:0ce6 (BLUEZ-UHID-01)
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


def validate_physical_node(
    node: object,
    *,
    dev_root: str = "/dev",
    sys_class_hidraw: str = "/sys/class/hidraw",
    sys_class_bluetooth: str = "/sys/class/bluetooth",
    stat_fn: Callable[[str], Any] = os.stat,
    lstat_fn: Callable[[str], Any] = os.lstat,
) -> str | None:
    """Basename canônico `hidrawN` se `node` é DualSense FÍSICO 054c:0ce6; senão None.

    NUNCA abre o device. Barreiras, na ordem (1-3 e 5 herdadas do parkado; a 4
    é a decisão BLUEZ-UHID-01 do desenho de 2026-07-20):
      1. caminho canônico literal (`canonical_hidraw_base`);
      2. o nó não pode ser symlink e PRECISA ser char device;
      3. `(major, minor)` do nó casa o `/sys/class/hidraw/<base>/dev` (fecha
         "symlink/nó plantado apontando para outro device");
      4. identidade do pai HID imediato (uevent): `HID_ID` zero-preenchido
         BUS:VVVV:PPPP com bus∈{0003,0005}, vendor 054C, product 0CE6 (0DF2 =
         vpad, SEMPRE rejeitado ANTES do != geral; 057E Nintendo cai no
         vendor) + regras da subárvore `/devices/virtual/misc/uhid/`:
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
    match = _HID_ID_VALUE_RE.match(uevent.get("HID_ID", ""))
    if match is None:
        return None
    bus = int(match.group(1), 16)
    vendor = int(match.group(2), 16)
    product = int(match.group(3), 16)
    if bus not in ACCEPTED_BUSES or vendor != PHYS_VENDOR:
        return None
    if product == VPAD_PRODUCT:
        # Explícito ANTES do != geral: o vpad 0df2 JAMAIS é escondido/aberto —
        # é por ele que rumble/triggers/lightbar do jogo chegam.
        return None
    if product != PHYS_PRODUCT:
        return None
    # ---- decisão BLUEZ-UHID-01: /devices/virtual/ NÃO é veredito ----
    if "/devices/virtual/" in hid_parent:
        if "/misc/uhid/" not in hid_parent:
            return None  # uinput/virtual puro jamais é físico
        if bus != BUS_BT:
            return None  # (D1) USB real NUNCA é uhid: 0003 sob uhid = forjado
        phys = uevent.get("HID_PHYS", "").strip().lower()
        uniq = uevent.get("HID_UNIQ", "").strip().lower()
        if phys.startswith(VPAD_PHYS_PREFIX):
            return None  # (D2) nosso vpad, mesmo que anuncie 0CE6
        if uniq.replace(":", "").startswith(VPAD_UNIQ_PREFIX):
            return None  # (D2)
        if _MAC_RE.match(uniq) is None:
            return None  # (D3) BT real tem HID_UNIQ = MAC do controle
        if _MAC_RE.match(phys) is None:
            return None  # (D3) BT real tem HID_PHYS = MAC do adaptador
        adapters = _adapter_addresses(sys_class_bluetooth)
        if adapters is not None and adapters and phys not in adapters:
            return None  # (D4) belt: só decide com sysfs BT legível
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

    def __init__(self, *, sys_class_hidraw: str = "/sys/class/hidraw") -> None:
        self._sys_class_hidraw = sys_class_hidraw

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
        return fd


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
    ) -> None:
        self.allowed_uid = allowed_uid
        self._ops = ops if ops is not None else FsAclOps(sys_class_hidraw=sys_class_hidraw)
        self._validator = validator
        self._dev_root = dev_root
        self._sys_class_hidraw = sys_class_hidraw
        self._sys_class_bluetooth = sys_class_bluetooth
        self._log = log
        self._sleep = sleep_fn
        self.hidden: dict[str, _HiddenNode] = {}
        self.by_conn: dict[int, set[str]] = {}

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
            return ({"ok": True, "cmd": "status", "hidden": sorted(self.hidden)}, None)
        if cmd == "hide":
            return (self._cmd_hide(conn_id, peer_uid, request.get("node")), None)
        if cmd == "restore":
            return (self._cmd_restore(conn_id, request.get("node")), None)
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
                # `hidden`, mas nenhuma conexão viva o referencia). Adotar
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
            uid = entry.uid if entry is not None else self.allowed_uid
            response = self._fs_restore(canon, base, uid)
            if response.get("ok"):
                # Lição 2: só destrackear DEPOIS do fs OK (exposed OU gone).
                held.discard(canon)
                self.hidden.pop(canon, None)
            return response
        if entry is not None:
            if self._lease_holders(canon) > 0:
                # escondido por OUTRA conexão viva: não expõe
                return {"ok": True, "cmd": "restore", "node": canon, "state": "hidden"}
            # Achado Onda S #3: órfão sem lease viva — o restore explícito TEM
            # de tocar o fs (antes respondia "hidden" para sempre; só o
            # reinício do serviço curava um nó 0600 órfão).
            response = self._fs_restore(canon, base, entry.uid)
            if response.get("ok"):
                self.hidden.pop(canon, None)
                self._log("orphan_restored", node=canon, conn=conn_id)
            return response
        # Não rastreado: restore best-effort (idempotente), mas SÓ em nó que
        # valida como físico — nunca mexe em hidraw alheio (teclado etc.).
        if self._validate(canon) is None:
            return {
                "ok": False,
                "cmd": "restore",
                "node": canon,
                "error": "reject_not_physical_dualsense",
            }
        return self._fs_restore(canon, base, self.allowed_uid)

    def _cmd_restore_all(self, conn_id: int) -> dict[str, object]:
        # Lição 3: itera TODOS os nós SEMPRE — falha em um vira log + nó
        # mantido no rastreio, e o loop segue para os demais.
        restored: list[str] = []
        failed: list[str] = []
        for canon in sorted(self.by_conn.get(conn_id, set())):
            response = self._cmd_restore(conn_id, canon)
            if response.get("ok") and response.get("state") in ("exposed", "gone"):
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

    def _lease_holders(self, canon: str) -> int:
        """Nº de conexões VIVAS cuja lease segura `canon`.

        Achado Onda S #3: é a fonte da verdade para distinguir "outra lease
        viva segura o nó" (refcount soma/decrementa normal) de "nó ÓRFÃO"
        (lease morreu com o restore de fs falho — `on_conn_closed` mantém o
        nó em `hidden`, mas `by_conn` já não o referencia em lugar nenhum).
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
        """EOF da lease: restaura tudo que AQUELA conexão escondeu.

        Lição 3: falha num nó não derruba o loop — o falho fica rastreado em
        `hidden` (sem lease) e os belts cobrem (restore_all do shutdown,
        ExecStopPost, baseline do próximo start).
        """
        restored: list[str] = []
        failed: list[str] = []
        for canon in sorted(self.by_conn.get(conn_id, set())):
            entry = self.hidden.get(canon)
            if entry is None:
                continue
            if entry.refcount > 1:  # outra lease viva segura o nó
                entry.refcount -= 1
                continue
            response = self._fs_restore(canon, canon.rsplit("/", 1)[-1], entry.uid)
            if response.get("ok"):
                del self.hidden[canon]
                restored.append(canon)
            else:
                failed.append(canon)  # rastreado; belts cobrem
        self.by_conn.pop(conn_id, None)
        if restored:
            self._log("lease_closed_restored", conn=conn_id, nodes=",".join(restored))
        if failed:
            self._log("lease_restore_parcial", conn=conn_id, failed=",".join(failed))
        return restored

    def restore_everything(self) -> list[str]:
        """Belt do shutdown do broker: restaura TODO nó ainda escondido."""
        restored: list[str] = []
        for canon, entry in sorted(self.hidden.items()):
            response = self._fs_restore(canon, canon.rsplit("/", 1)[-1], entry.uid)
            if response.get("ok"):
                del self.hidden[canon]
                restored.append(canon)
        self.by_conn.clear()
        return restored


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

    Usado por `--restore-all-and-exit` (ExecStartPre/ExecStopPost): nunca herda
    um físico escondido órfão de uma vida anterior. Idempotente e best-effort.
    """
    fs_ops = ops if ops is not None else FsAclOps(sys_class_hidraw=sys_class_hidraw)
    restored: list[str] = []
    try:
        entries = sorted(os.listdir(sys_class_hidraw))
    except OSError:
        return restored
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

    if args.restore_all_and_exit:
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
    # execução manual/debug fica igualmente segura).
    restore_all_physical(uid=allowed_uid)

    listen = _sd_listen_socket()
    if listen is None:
        listen = _manual_listen_socket(args.socket_path)
        _log("listening_manual", path=args.socket_path)

    state = BrokerState(allowed_uid=allowed_uid)
    broker = Broker(state, listen)

    def _stop(_signum: int, _frame: object) -> None:
        broker.stopping = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    _sd_notify("READY=1")
    _log("ready", allowed_uid=allowed_uid)
    broker.run()
    return 0


if __name__ == "__main__":  # pragma: no cover - entrypoint real (root)
    sys.exit(main())
