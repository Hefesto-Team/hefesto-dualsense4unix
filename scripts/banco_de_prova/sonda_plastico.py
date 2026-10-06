#!/usr/bin/env python3
"""A sonda do banco de prova: o plástico de mentira mínimo, nos dois transportes.

PARTE 0 de O-FORJA-E-O-BANCO-DE-PROVA-DO-HEFESTO-01 (06/10/2026). Isto NÃO é o
plástico da parte 1 (`plastico_de_mentira.py`, da L4): é o menor aparelho que
responde a pergunta «este kernel deixa o `hid_playstation` registrar um
DualSense de mentira?», para o job `banco-de-prova-sonda` do CI gravar a resposta
antes de qualquer decisão da casa. Só stdlib, e só roda onde há `/dev/uhid` (o
runner do CI, uma VM): na máquina dela o `uhid` é do produto, e este arquivo
nunca é chamado ali.

Três verbos:

* `radio`: cria um DualSense no barramento `0005` (BLUETOOTH) pelo `UHID_CREATE2`,
  responde os três feature reports que o probe pede (`0x05`, `0x09`, `0x20`) com o
  CRC-32 que o `hid_playstation` confere nos reports de rádio (semente `0xA3`),
  espera o kernel registrar e escreve o veredito em `--saida` (`chave=valor`).
  Com `--fica` o aparelho continua vivo, servindo os reports, até `SIGTERM`.
* `cabo-features`: entrega ao `/dev/hidgN` do gadget os três feature reports
  (`GADGET_HID_WRITE_GET_REPORT`, `userspace_req=0`: valem para todo GET_REPORT
  futuro), que é o que o probe do `hid_playstation` pede pelo cabo. O ioctl só
  existe nos kernels que respondem GET_REPORT pelo `usb_f_hid`; o `ENOTTY` dele é a
  resposta «sem plástico de cabo nesta casa».
* `acl`: com o daemon de pé, mede se QUEM RODA o jogo (este processo, sem `sudo`) abre
  o hidraw e o evdev do pad que o Hefesto criou. O `uaccess` só dá ACL a quem tem sessão
  num assento, e o runner não tem: sem ela o jogo não vê o pad.

Os endereços são da faixa sintética `aa:bb:cc:00:00:0N`: nunca um endereço real.
"""
from __future__ import annotations

import argparse
import fcntl
import os
import select
import signal
import struct
import sys
import time
import zlib
from collections.abc import Callable
from pathlib import Path

UHID_DESTROY = 1
UHID_START = 2
UHID_STOP = 3
UHID_OPEN = 4
UHID_CLOSE = 5
UHID_OUTPUT = 6
UHID_GET_REPORT = 9
UHID_GET_REPORT_REPLY = 10
UHID_CREATE2 = 11
UHID_SET_REPORT = 13
UHID_SET_REPORT_REPLY = 14

BUS_USB = 0x03
BUS_BLUETOOTH = 0x05
VENDOR_SONY = 0x054C
PRODUTO_DUALSENSE = 0x0CE6
HID_MAX = 4096

#: A semente do CRC dos feature reports de rádio (`PS_FEATURE_CRC32_SEED` do
#: `hid-playstation.c`): ver `core/ds_output_report.py::BT_FEATURE_CRC_SEED`.
SEMENTE_DO_FEATURE = 0xA3

#: O `phys` do vpad do Hefesto (`uhid_gamepad.VPAD_HID_PHYS`): é por ele que o job
#: acha o nó do pad do produto entre os do plástico.
PHYS_DO_VPAD_DO_HEFESTO = "hefesto-vpad"

TAMANHO_DOS_FEATURES = {0x05: 41, 0x09: 20, 0x20: 64}

#: `struct usb_hidg_report` do `<linux/usb/g_hid.h>`: report_id, userspace_req,
#: length, data[64] e 4 de padding, 72 bytes. `_IOW('g', 0x42, ...)`.
_HIDG_REPORT = struct.Struct("<BBH64s4s")
GADGET_HID_WRITE_GET_REPORT = (1 << 30) | (_HIDG_REPORT.size << 16) | (ord("g") << 8) | 0x42

PASTA_DAS_FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "hid"


def crc_do_feature(corpo: bytes) -> int:
    """O que o kernel confere: `~crc32_le(crc32_le(-1, &0xA3, 1), corpo)`."""
    return zlib.crc32(bytes([SEMENTE_DO_FEATURE]) + bytes(corpo)) & 0xFFFFFFFF


def com_crc_de_radio(report: bytes) -> bytes:
    """Troca os 4 últimos bytes do report pelo CRC do rádio (o id entra na conta)."""
    corpo = bytes(report[:-4])
    return corpo + struct.pack("<I", crc_do_feature(corpo))


def mac_em_bytes(mac: str) -> bytes:
    """`aa:bb:cc:00:00:01` -> os 6 bytes do feature 0x09, em little-endian."""
    octetos = bytes.fromhex(mac.replace(":", ""))
    if len(octetos) != 6:
        raise ValueError(f"endereço sem seis octetos: {mac!r}")
    return octetos[::-1]


def feature_pareamento(mac: str) -> bytes:
    """O 0x09 (20 bytes): o id, o endereço e o resto zerado; o CRC entra depois."""
    return (b"\x09" + mac_em_bytes(mac)).ljust(TAMANHO_DOS_FEATURES[0x09], b"\0")


def features_do_aparelho(mac: str, pasta: Path = PASTA_DAS_FIXTURES) -> dict[int, bytes]:
    """Os três features pelo cabo (sem CRC): as capturas da casa e o endereço da faixa."""
    cal = (pasta / "dualsense_usb_feature_0x05_calibracao.bin").read_bytes()
    fw = (pasta / "dualsense_usb_feature_0x20_firmware.bin").read_bytes()
    saida = {0x05: cal, 0x09: feature_pareamento(mac), 0x20: fw}
    for numero, tamanho in TAMANHO_DOS_FEATURES.items():
        if len(saida[numero]) != tamanho:
            raise ValueError(
                f"feature 0x{numero:02x} com {len(saida[numero])} bytes, o driver pede {tamanho}")
    return saida


def features_de_radio(mac: str, pasta: Path = PASTA_DAS_FIXTURES) -> dict[int, bytes]:
    """Os mesmos três, com o CRC que o `hid_playstation` confere quando o barramento é o 0005."""
    return {n: com_crc_de_radio(r) for n, r in features_do_aparelho(mac, pasta).items()}


def evento_create2(descritor: bytes, mac: str, barramento: int, nome: str = "DualSense Sonda",
                   phys: str = "sonda-plastico") -> bytes:
    """`struct uhid_create2_req` (mesmo layout de `uhid_gamepad._create2_event`)."""
    corpo = struct.pack("<I", UHID_CREATE2)
    corpo += nome.encode("utf-8").ljust(128, b"\0")[:128]
    corpo += phys.encode("ascii").ljust(64, b"\0")[:64]
    corpo += mac.encode("ascii").ljust(64, b"\0")[:64]
    corpo += struct.pack("<HH", len(descritor), barramento)
    corpo += struct.pack("<IIII", VENDOR_SONY, PRODUTO_DUALSENSE, 0x0100, 0)
    corpo += descritor.ljust(HID_MAX, b"\0")[:HID_MAX]
    return corpo


def resposta_de_get_report(pedido: bytes, features: dict[int, bytes]) -> bytes:
    """`UHID_GET_REPORT_REPLY` ao `uhid_get_report_req { id, rnum, rtype }`."""
    identificador = struct.unpack("<I", pedido[4:8])[0]
    numero = pedido[8]
    carga = features.get(numero, b"")
    erro = 0 if carga else 5  # EIO: o report que o aparelho de mentira não tem
    resposta = struct.pack("<IIH", UHID_GET_REPORT_REPLY, identificador, erro)
    resposta += struct.pack("<H", len(carga))
    return resposta + carga.ljust(HID_MAX, b"\0")[:HID_MAX]


def resposta_de_set_report(pedido: bytes) -> bytes:
    identificador = struct.unpack("<I", pedido[4:8])[0]
    return struct.pack("<IIH", UHID_SET_REPORT_REPLY, identificador, 0)


def veredito_do_kernel(raiz_sys: Path, barramento: int) -> dict[str, str]:
    """O que o kernel diz DEPOIS do `UHID_CREATE2`, lido do `/sys` (sem tocar em nada).

    `registrou=sim` quando o driver `playstation` tem um nó HID neste barramento; o
    nó do evdev e o do hidraw vêm da mesma pasta.
    """
    prefixo = f"{barramento:04X}:054C:0CE6."
    driver = raiz_sys / "bus" / "hid" / "drivers" / "playstation"
    ligados = sorted(p.name for p in driver.glob("*") if p.name.upper().startswith(prefixo))
    return {
        "registrou": "sim" if ligados else "não",
        "no_hid": ligados[0] if ligados else "",
        "driver_existe": "sim" if driver.is_dir() else "não",
    }


def nos_do_aparelho(raiz_sys: Path, no_hid: str) -> dict[str, str]:
    """O hidraw e o evdev que nascem do nó HID `no_hid`."""
    base = raiz_sys / "bus" / "hid" / "devices" / no_hid
    hidraw = sorted(p.name for p in (base / "hidraw").glob("hidraw*")) if base.is_dir() else []
    eventos = sorted(
        p.name for p in base.glob("input/input*/event*")) if base.is_dir() else []
    return {"hidraw": f"/dev/{hidraw[0]}" if hidraw else "",
            "evdev": f"/dev/input/{eventos[0]}" if eventos else ""}


def nos_do_vpad(raiz_sys: Path, phys: str = PHYS_DO_VPAD_DO_HEFESTO) -> dict[str, list[str]]:
    """Os nós `/dev` do pad que o PRODUTO criou, achados pelo `phys` que ele carimba.

    O plástico de mentira tem outro `phys`: é isto que separa o pad do Hefesto (o que o
    jogo abriria) do aparelho que a sonda inventou.
    """
    hidraw: list[str] = []
    for uevent in sorted((raiz_sys / "class" / "hidraw").glob("hidraw*/device/uevent")):
        try:
            texto = uevent.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if f"HID_PHYS={phys}" in texto.splitlines():
            hidraw.append(f"/dev/{uevent.parents[1].name}")
    evdev: list[str] = []
    for arquivo in sorted((raiz_sys / "class" / "input").glob("event*/device/phys")):
        try:
            achado = arquivo.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if achado == phys:
            evdev.append(f"/dev/input/{arquivo.parents[1].name}")
    return {"hidraw": hidraw, "evdev": evdev}


def abre_como_quem_roda(caminho: str) -> str:
    """`sim` se o usuário de agora abre o nó para leitura; `não: <errno>` se o kernel recusa."""
    try:
        os.close(os.open(caminho, os.O_RDONLY | os.O_NONBLOCK))
    except OSError as erro:
        return f"não: {erro.__class__.__name__} errno={erro.errno}"
    return "sim"


def veredito_da_acl(
        raiz_sys: Path, abre: Callable[[str], str] = abre_como_quem_roda) -> dict[str, str]:
    """Se quem roda o jogo (este processo, sem `sudo`) abre o pad do Hefesto.

    Sem nó achado o veredito é `não-achou`, e NUNCA `sim`: ACL que não se mediu não é ACL.
    Nada aqui concede permissão: medir com `chmod` ou grupo mediria outra permissão que
    não a do produto.
    """
    nos = nos_do_vpad(raiz_sys)
    saida: dict[str, str] = {}
    for tipo, caminhos in nos.items():
        saida[f"acl_{tipo}_nos"] = ",".join(caminhos)
        if not caminhos:
            saida[f"acl_{tipo}"] = "não-achou"
        else:
            respostas = [abre(c) for c in caminhos]
            saida[f"acl_{tipo}"] = "sim" if all(r == "sim" for r in respostas) else respostas[0]
    return saida


def _escrever_saida(saida: Path, pares: dict[str, str]) -> None:
    saida.write_text("".join(f"{k}={v}\n" for k, v in pares.items()), encoding="utf-8")


def _servir(fd: int, features: dict[int, bytes], ate: float) -> list[str]:
    """Atende os eventos do uhid até `ate`; devolve os tipos vistos (para o relatório)."""
    vistos: list[str] = []
    nomes = {UHID_START: "START", UHID_OPEN: "OPEN", UHID_CLOSE: "CLOSE", UHID_STOP: "STOP",
             UHID_GET_REPORT: "GET_REPORT", UHID_SET_REPORT: "SET_REPORT", UHID_OUTPUT: "OUTPUT"}
    while time.monotonic() < ate:
        pronto, _, _ = select.select([fd], [], [], 0.2)
        if not pronto:
            continue
        try:
            evento = os.read(fd, HID_MAX + 64)
        except OSError:
            break
        if len(evento) < 4:
            continue
        tipo = struct.unpack("<I", evento[:4])[0]
        vistos.append(nomes.get(tipo, str(tipo)))
        if tipo == UHID_GET_REPORT:
            os.write(fd, resposta_de_get_report(evento, features))
        elif tipo == UHID_SET_REPORT:
            os.write(fd, resposta_de_set_report(evento))
    return vistos


def verbo_radio(args: argparse.Namespace) -> int:
    pasta = Path(args.fixtures)
    descritor = (pasta / "dualsense_usb_descriptor_054c0ce6.bin").read_bytes()
    features = features_de_radio(args.mac, pasta)
    saida = Path(args.saida)
    try:
        fd = os.open("/dev/uhid", os.O_RDWR | os.O_NONBLOCK)
    except OSError as erro:
        _escrever_saida(saida, {"abriu_uhid": "não", "motivo": f"{erro.__class__.__name__}: {erro}"})
        return 0
    parar = {"sim": False}
    signal.signal(signal.SIGTERM, lambda *_: parar.__setitem__("sim", True))
    os.write(fd, evento_create2(descritor, args.mac, BUS_BLUETOOTH))
    raiz = Path(args.sys)
    limite = time.monotonic() + args.segundos
    vistos: list[str] = []
    veredito = veredito_do_kernel(raiz, BUS_BLUETOOTH)
    while time.monotonic() < limite and veredito["registrou"] != "sim":
        vistos += _servir(fd, features, min(limite, time.monotonic() + 0.5))
        veredito = veredito_do_kernel(raiz, BUS_BLUETOOTH)
    nos = nos_do_aparelho(raiz, veredito["no_hid"]) if veredito["no_hid"] else {}
    _escrever_saida(saida, {
        "abriu_uhid": "sim", **veredito, **nos,
        "eventos_vistos": ",".join(sorted(set(vistos))),
        "get_report_atendidos": str(vistos.count("GET_REPORT")),
    })
    if args.fica:
        while not parar["sim"]:
            _servir(fd, features, time.monotonic() + 1.0)
    os.write(fd, struct.pack("<I", UHID_DESTROY))
    os.close(fd)
    return 0


def verbo_cabo_features(args: argparse.Namespace) -> int:
    features = features_do_aparelho(args.mac, Path(args.fixtures))
    saida = Path(args.saida)
    try:
        fd = os.open(args.hidg, os.O_RDWR | os.O_NONBLOCK)
    except OSError as erro:
        _escrever_saida(saida, {"abriu_hidg": "não", "motivo": f"{erro.__class__.__name__}: {erro}"})
        return 0
    pares = {"abriu_hidg": "sim", "ioctl": hex(GADGET_HID_WRITE_GET_REPORT)}
    for numero, report in sorted(features.items()):
        pedido = _HIDG_REPORT.pack(numero, 0, len(report), report.ljust(64, b"\0"), b"\0" * 4)
        try:
            fcntl.ioctl(fd, GADGET_HID_WRITE_GET_REPORT, pedido)
            pares[f"feature_0x{numero:02x}"] = "entregue"
        except OSError as erro:
            pares[f"feature_0x{numero:02x}"] = f"recusado: {erro.__class__.__name__} errno={erro.errno}"
    os.close(fd)
    _escrever_saida(saida, pares)
    return 0


def verbo_acl(args: argparse.Namespace) -> int:
    _escrever_saida(Path(args.saida), veredito_da_acl(Path(args.sys)))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="verbo", required=True)
    comum = argparse.ArgumentParser(add_help=False)
    comum.add_argument("--saida", required=True, help="arquivo chave=valor com o veredito")
    comum.add_argument("--mac", default="aa:bb:cc:00:00:01", help="endereço da faixa sintética")
    comum.add_argument("--fixtures", default=str(PASTA_DAS_FIXTURES))
    radio = sub.add_parser("radio", parents=[comum])
    radio.add_argument("--segundos", type=float, default=8.0)
    radio.add_argument("--fica", action="store_true", help="continua vivo até SIGTERM")
    radio.add_argument("--sys", default="/sys", help="raiz do sysfs (os testes trocam)")
    radio.set_defaults(func=verbo_radio)
    acl = sub.add_parser("acl", parents=[comum])
    acl.add_argument("--sys", default="/sys")
    acl.set_defaults(func=verbo_acl)
    cabo = sub.add_parser("cabo-features", parents=[comum])
    cabo.add_argument("--hidg", default="/dev/hidg0")
    cabo.set_defaults(func=verbo_cabo_features)
    args = ap.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
