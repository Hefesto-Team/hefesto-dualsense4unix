#!/usr/bin/env python3
"""Diagnóstico/recaptura do blueprint USB do DualSense (VPAD-03 / BT-01).

Lê — SEM escrever nada no controle — o report_descriptor (sysfs) e os feature
reports 0x05 (calibração), 0x09 (pairing) e 0x20 (firmware) de um DualSense
físico via HIDIOCGFEATURE: os mesmos bytes que o probe do `hid_playstation`
pede. Requer só a ACL de `uaccess` do hidraw (sem sudo).

Serve para:
  (a) regenerar as constantes de `integrations/uhid_blueprint.py` e os `.bin`
      de `captures/` quando um firmware novo justificar (o vpad usa o blueprint
      canônico EMBUTIDO; este script não participa do caminho de criação);
  (b) diagnosticar um controle que recusa features — por exemplo, o sintoma
      medido em BT: controle ocioso não responde features e cada GET_REPORT
      estoura o timeout de 5 s do hidp do kernel com EIO.

Uso: .venv/bin/python scripts/capture_blueprint.py hidraw2

A PORTA (A-PORTA-QUE-A-CASA-CONSTRUIU-01, 15/08/2026)
-----------------------------------------------------
Este script falhava com `'/dev/hidraw8' inacessível ([Errno 13] Permission
denied)` sempre que o co-op estava ligado — e a leitura fácil ("a regra udev
não cobre o Bluetooth") mandava consertar o lugar errado. A regra está certa e
pegou; quem tira a ACL é o **próprio Hefesto**, de propósito, para o jogo não
enxergar o físico. A porta certa é o broker, e é por ela que se entra agora.
O `open()` direto continua existindo como queda — e sai DECLARADO no relatório,
porque uma medição que não diz por onde entrou não pode ser comparada com a do
outro braço do ensaio.

ANONIMATO: o 0x09 carrega o MAC do controle e o MAC do host pareado. O script
imprime SEMPRE a versão sanitizada (bytes 1..6 e 10..15 zerados) — é a única
que pode aparecer em commit. O runtime nem usa esses bytes: o `start()` do
vpad carimba o MAC forjado do jogador (`02:fe:00:00:00:0N`, LE).
"""
from __future__ import annotations

import fcntl
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "ensaios"))

from comum import (
    PortaFechadaError,
    abrir_no_hidraw,
    declaracao_da_porta,
)

#: Features do probe do hid_playstation, com os tamanhos que o driver espera.
FEATURE_SIZES: tuple[tuple[int, int], ...] = ((0x05, 41), (0x09, 20), (0x20, 64))

#: Áreas de identidade do 0x09: bytes 1..6 = MAC do device, 10..15 = MAC do
#: host pareado. Zeradas antes de imprimir (regra de anonimato do repo).
_MAC_AREAS_0X09: tuple[tuple[int, int], ...] = ((1, 7), (10, 16))


def hidiocgfeature(fd: int, report_id: int, size: int) -> bytes:
    """HIDIOCGFEATURE(len) = _IOC(READ|WRITE, 'H', 0x07, len) — leitura pura."""
    buf = bytearray(size)
    buf[0] = report_id
    request = (3 << 30) | (size << 16) | (ord("H") << 8) | 0x07
    ret = fcntl.ioctl(fd, request, buf, True)
    return bytes(buf[:ret]) if ret > 0 else b""


def sanitize_pairing_report(report: bytes) -> bytes:
    """Zera as duas áreas de MAC do feature 0x09 (device + host pareado)."""
    limpo = bytearray(report)
    for inicio, fim in _MAC_AREAS_0X09:
        limpo[inicio:fim] = bytes(max(0, min(fim, len(limpo)) - inicio))
    return bytes(limpo)


def main(node: str) -> int:
    # A DECLARAÇÃO ANTES DA MEDIÇÃO: biblioteca (fcntl/ioctl, à mão) e porta.
    print("biblioteca ....... fcntl.ioctl (HIDIOCGFEATURE montado à mão)")
    print(f"  {declaracao_da_porta()}")
    try:
        with open(f"/sys/class/hidraw/{node}/device/report_descriptor", "rb") as handle:
            desc = handle.read()
    except OSError as exc:
        print(f"{node}: sem descriptor no sysfs ({exc})")
        return 1
    bt = b"\x85\x31" in desc
    print(f"{node}: descriptor={len(desc)} bytes, item_85_31={'SIM' if bt else 'não'}")
    if bt:
        print("  atenção: descriptor de transporte BT — impróprio como blueprint de")
        print("  vpad BUS_USB (o canônico embutido usa o descriptor USB de 289 B).")
    try:
        aberto = abrir_no_hidraw(f"/dev/{node}", escrita=True)
    except PortaFechadaError as exc:
        print(f"  {exc}")
        return 1
    fd = aberto.fd
    print(f"  {aberto.linha_de_relatorio}")
    try:
        for rid, size in FEATURE_SIZES:
            try:
                data = hidiocgfeature(fd, rid, size)
            except OSError as exc:
                print(f"  feature {rid:#04x}: OSError errno={exc.errno} ({exc})")
                continue
            if rid == 0x09:
                data = sanitize_pairing_report(data)
                print(f"  feature {rid:#04x} (SANITIZADO): {len(data)} bytes = {data.hex()}")
            else:
                print(f"  feature {rid:#04x}: {len(data)} bytes = {data.hex()}")
    finally:
        aberto.fechar()
    print(f"  descriptor_hex={desc.hex()}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("uso: capture_blueprint.py hidrawN")
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
