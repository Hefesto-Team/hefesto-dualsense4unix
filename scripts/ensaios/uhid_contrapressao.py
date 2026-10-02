#!/usr/bin/env python3
"""A MORDIDA DO PATCH DO UHID — a fila cheia é dita, ou é calada?"""
import glob
import os
import struct
import sys
import time

UHID = "/dev/uhid"
UHID_DESTROY, UHID_CREATE2 = 1, 11
UHID_DATA_MAX = 4096
HID_MAX_DESCRIPTOR_SIZE = 4096

RD = bytes([
    0x06, 0x00, 0xFF,
    0x09, 0x01,
    0xA1, 0x01,
    0x09, 0x02,
    0x15, 0x00,
    0x26, 0xFF, 0x00,
    0x75, 0x08,
    0x95, 0x40,
    0x91, 0x02,
    0x09, 0x03,
    0x95, 0x40,
    0x81, 0x02,
    0xC0,
])

def criar(fd: int, nome: bytes) -> None:
    req = (nome.ljust(128, b"\0") + b"hefesto-prova".ljust(64, b"\0")
           + b"ff:ff:ff:00:00:fe".ljust(64, b"\0")
           + struct.pack("<HHIIII", len(RD), 0x0003, 0xF1F1, 0xF2F2, 1, 0)
           + RD.ljust(HID_MAX_DESCRIPTOR_SIZE, b"\0"))
    os.write(fd, struct.pack("<I", UHID_CREATE2) + req)

def achar_hidraw(uniq: str, prazo: float = 5.0) -> str | None:
    fim = time.time() + prazo
    while time.time() < fim:
        for h in glob.glob("/sys/class/hidraw/hidraw*"):
            try:
                with open(os.path.join(h, "device", "uevent")) as arq:
                    ue = arq.read()
            except OSError:
                continue
            if uniq.upper() in ue.upper():
                return "/dev/" + os.path.basename(h)
        time.sleep(0.05)
    return None

def main() -> int:
    fd = os.open(UHID, os.O_RDWR)
    criar(fd, b"HEFESTO prova de contrapressao")
    no = achar_hidraw("ff:ff:ff:00:00:fe")
    if no is None:
        print("NAO ACHEI o hidraw do aparelho de mentira"); return 2
    print(f"aparelho de mentira em {no}; o /dev/uhid NAO sera lido")
    try:
        hraw = os.open(no, os.O_RDWR)
    except OSError as e:
        print(f"não consegui abrir {no}: {e}"); return 2

    aceitas = recusadas = 0
    primeiro_eagain = None
    for i in range(80):
        try:
            os.write(hraw, bytes([0x00]) + bytes([i & 0xFF]) * 64)
            aceitas += 1
        except OSError as e:
            recusadas += 1
            if primeiro_eagain is None:
                primeiro_eagain = (i, e.errno, os.strerror(e.errno))
    os.close(hraw)
    os.write(fd, struct.pack("<I", UHID_DESTROY)); os.close(fd)

    print(f"escritas aceitas   : {aceitas}")
    print(f"escritas recusadas : {recusadas}")
    print(f"primeira recusa    : {primeiro_eagain}")
    print("VEREDITO:", "O KERNEL DIZ (contrapressao viva)" if recusadas
          else "O KERNEL CALA (descarte invisivel)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
