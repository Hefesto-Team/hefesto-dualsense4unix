#!/usr/bin/env python3
"""Um cliente DSU que confere o servidor vivo, como o emulador o veria.

Só biblioteca padrão e nenhum import do produto: o cliente não pode herdar um
defeito do codec que está conferindo. Monta os pedidos e lê as respostas byte a
byte, pelo protocolo documentado em ``docs/protocol/o-protocolo-dsu.md``.

    python3 scripts/ensaios/o_dsu_chega_ao_emulador.py --slot 0 --segundos 10

Sai com 0 só quando tudo confere; com 1 nomeando o PRIMEIRO degrau que falhou.
``--sem-dono`` pula a conferência de quem é a porta (para provar contra um
servidor de teste, que não é o daemon). ``--json`` imprime o relato em JSON.
Só lê: não escreve no aparelho, no ``~/.config`` nem fala com o daemon.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import re
import socket
import struct
import sys
import time
import zlib
from pathlib import Path
from typing import Any

VERSAO = 1001
ID_DO_CLIENTE = 0x44535545  # qualquer número; o servidor só o devolve
PACOTES_POR_SEGUNDO_MINIMO = 8.0
GRAVIDADE_MIN, GRAVIDADE_MAX = 0.9, 1.1


def _pedido(tipo: int, corpo: bytes) -> bytes:
    pacote = bytearray(b"DSUC")
    pacote += struct.pack("<HHII", VERSAO, 4 + len(corpo), 0, ID_DO_CLIENTE)
    pacote += struct.pack("<I", tipo) + corpo
    struct.pack_into("<I", pacote, 8, zlib.crc32(bytes(pacote)) & 0xFFFFFFFF)
    return bytes(pacote)


def _crc_confere(pacote: bytes) -> bool:
    if len(pacote) < 20 or pacote[:4] != b"DSUS":
        return False
    zerado = bytearray(pacote)
    zerado[8:12] = bytes(4)
    declarado = struct.unpack_from("<I", pacote, 8)[0]
    return zlib.crc32(bytes(zerado)) & 0xFFFFFFFF == declarado


def dono_da_porta(porta: int) -> tuple[int, str] | None:
    """(pid, linha de comando) de quem escuta a ``porta`` UDP, ou ``None``."""
    try:
        alvo = f":{porta:04X}"
        inodes: set[str] = set()
        for linha in Path("/proc/net/udp").read_text().splitlines()[1:]:
            campos = linha.split()
            if len(campos) > 9 and campos[1].endswith(alvo) and campos[9] != "0":
                inodes.add(campos[9])
        if not inodes:
            return None
        for pasta in Path("/proc").iterdir():
            if not pasta.name.isdigit():
                continue
            try:
                for fd in (pasta / "fd").iterdir():
                    try:
                        destino = os.readlink(fd)
                    except OSError:
                        continue
                    if destino.startswith("socket:[") and destino[8:-1] in inodes:
                        bruto = (pasta / "cmdline").read_bytes()
                        texto = bruto.replace(b"\0", b" ").decode(errors="replace").strip()
                        return int(pasta.name), texto
            except OSError:
                continue
    except OSError:
        return None
    return None


def _e_o_daemon(cmdline: str) -> bool:
    """O daemon sobe como ``hefesto-dualsense4unix daemon start`` (ou ``-m …cli.app``)."""
    return "hefesto" in cmdline.lower() and re.search(r"\bdaemon\s+start\b", cmdline) is not None


def _receber(sock: socket.socket, limite: float) -> bytes | None:
    sock.settimeout(max(0.01, limite))
    try:
        return sock.recvfrom(2048)[0]
    except TimeoutError:
        return None


class Falha(Exception):
    """Um degrau do ensaio que não passou; a mensagem nomeia qual."""


def ensaiar(args: argparse.Namespace) -> dict[str, Any]:
    relato: dict[str, Any] = {"porta": args.porta, "slot": args.slot}
    host = (args.host, args.porta)

    dono = dono_da_porta(args.porta)
    relato["dono"] = None if dono is None else {"pid": dono[0], "cmdline": dono[1]}
    if not args.sem_dono:
        if dono is None:
            raise Falha(f"a {args.porta} não tem dono: o servidor DSU não está de pé")
        if not _e_o_daemon(dono[1]):
            raise Falha(f"a {args.porta} é de outro processo ({dono[1][:120]})")

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))

        # 1 · a versão
        sock.sendto(_pedido(0x100000, b""), host)
        resposta = _receber(sock, 2.0)
        if resposta is None:
            raise Falha("sem resposta de versão em 2 s")
        if not _crc_confere(resposta) or len(resposta) < 22:
            raise Falha("a resposta de versão veio com CRC ou tamanho errado")
        lida = struct.unpack_from("<H", resposta, 20)[0]
        relato["versao_do_protocolo"] = lida
        if lida != VERSAO:
            raise Falha(f"a versão é {lida}, o emulador espera {VERSAO}")

        # 2 · as portas
        sock.sendto(_pedido(0x100001, struct.pack("<i", 4) + bytes([0, 1, 2, 3])), host)
        portas: dict[int, dict[str, Any]] = {}
        fim = time.monotonic() + 1.5
        while len(portas) < 4 and time.monotonic() < fim:
            pacote = _receber(sock, fim - time.monotonic())
            if pacote is None:
                break
            if not _crc_confere(pacote) or len(pacote) < 32:
                raise Falha("uma resposta de portas veio com CRC ou tamanho errado")
            portas[pacote[20]] = {
                "estado": pacote[21],
                "mac": ":".join(f"{b:02x}" for b in pacote[24:30]),
            }
        relato["portas"] = portas
        escolhida = portas.get(args.slot)
        if escolhida is None:
            raise Falha(f"o servidor não respondeu a porta do slot {args.slot}")
        if escolhida["estado"] != 2:
            raise Falha(f"o slot {args.slot} está desconectado (estado {escolhida['estado']})")
        if not escolhida["mac"].startswith("02:fe:"):
            raise Falha(
                f"o MAC do slot {args.slot} não é o do controle virtual "
                f"({escolhida['mac']}): o emulador veria o físico"
            )

        # 3 · os dados
        sock.sendto(_pedido(0x100002, bytes([1, args.slot]) + bytes(6)), host)
        inicio = time.monotonic()
        contadores: list[int] = []
        modulos: list[float] = []
        giros: list[tuple[float, float, float]] = []
        xs: list[int] = []
        ys: list[int] = []
        crc_ruim = 0
        tempo_do_ultimo_pedido = inicio
        while time.monotonic() - inicio < args.segundos:
            if time.monotonic() - tempo_do_ultimo_pedido > 1.0:
                sock.sendto(_pedido(0x100002, bytes([1, args.slot]) + bytes(6)), host)
                tempo_do_ultimo_pedido = time.monotonic()
            pacote = _receber(sock, 0.2)
            if pacote is None:
                continue
            if len(pacote) != 100 or struct.unpack_from("<I", pacote, 16)[0] != 0x100002:
                continue
            if not _crc_confere(pacote):
                crc_ruim += 1
                continue
            contadores.append(struct.unpack_from("<I", pacote, 32)[0])
            ax, ay, az = struct.unpack_from("<fff", pacote, 76)
            modulos.append((ax * ax + ay * ay + az * az) ** 0.5)
            giros.append(struct.unpack_from("<fff", pacote, 88))
            for base in (56, 62):  # os dois toques: ativo, id, x, y
                if pacote[base]:
                    x, y = struct.unpack_from("<HH", pacote, base + 2)
                    xs.append(x)
                    ys.append(y)
        duracao = max(time.monotonic() - inicio, 1e-6)

    taxa = len(contadores) / duracao
    relato.update(
        pacotes=len(contadores),
        por_segundo=round(taxa, 1),
        crc_ruim=crc_ruim,
        aceleracao_media_g=round(sum(modulos) / len(modulos), 3) if modulos else None,
        giro_medio_graus_s=(
            [round(sum(g[i] for g in giros) / len(giros), 2) for i in range(3)] if giros else None
        ),
        contador=[contadores[0], contadores[-1]] if contadores else None,
        faixa_x=[min(xs), max(xs)] if xs else None,
        faixa_y=[min(ys), max(ys)] if ys else None,
    )
    if not contadores:
        raise Falha("sem pacote de dados do slot no prazo")
    if crc_ruim:
        raise Falha(f"{crc_ruim} pacote(s) de dados com CRC ruim")
    if taxa < PACOTES_POR_SEGUNDO_MINIMO:
        raise Falha(f"só {taxa:.1f} pacotes por segundo (o mínimo é {PACOTES_POR_SEGUNDO_MINIMO})")
    if any(b <= a for a, b in itertools.pairwise(contadores)):
        raise Falha("o contador de pacotes não cresce sempre")
    media = sum(modulos) / len(modulos)
    if not GRAVIDADE_MIN <= media <= GRAVIDADE_MAX:
        raise Falha(
            f"a aceleração média é {media:.2f} g com o controle parado "
            f"(esperado entre {GRAVIDADE_MIN} e {GRAVIDADE_MAX})"
        )
    return relato


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--porta", type=int, default=26760)
    ap.add_argument("--slot", type=int, default=0, choices=range(4))
    ap.add_argument("--segundos", type=float, default=10.0)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--sem-dono", action="store_true", help="não confere que a porta é do daemon")
    args = ap.parse_args(argv)
    try:
        relato = ensaiar(args)
    except Falha as exc:
        if args.json:
            print(json.dumps({"ok": False, "falha": str(exc)}, ensure_ascii=False))
        else:
            print(f"REPROVADO: {exc}")
        return 1
    if args.json:
        print(json.dumps({"ok": True, **relato}, ensure_ascii=False))
    else:
        _imprimir(relato)
        print(
            f"OK: slot {args.slot}, {relato['por_segundo']} pacotes/s, "
            f"{relato['aceleracao_media_g']} g, versão {relato['versao_do_protocolo']}"
        )
    return 0


def _imprimir(relato: dict[str, Any]) -> None:
    """O relato em texto: a tabela das portas e o que os pacotes de dados trouxeram."""
    dono = relato.get("dono")
    print(
        f"porta {relato['porta']}: "
        + (f"PID {dono['pid']}, {dono['cmdline']}" if dono else "sem dono lido")
    )
    for slot, porta in sorted(relato.get("portas", {}).items()):
        print(f"  slot {slot}: estado {porta['estado']}, MAC {porta['mac']}")
    sem_toque = "nenhum toque no período"
    print(
        f"pacotes {relato['pacotes']} ({relato['por_segundo']}/s), contador "
        f"{relato['contador']}, CRC ruins {relato['crc_ruim']}"
    )
    print(f"toque: x {relato['faixa_x'] or sem_toque}, y {relato['faixa_y'] or sem_toque}")
    print(
        f"aceleração |a| média {relato['aceleracao_media_g']} g; "
        f"giro médio {relato['giro_medio_graus_s']} °/s"
    )


if __name__ == "__main__":
    sys.exit(main())
