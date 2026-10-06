#!/usr/bin/env python3
"""o_envelope_do_som_no_radio.py — o MESMO som por rádio, em DOIS envelopes HID."""

from __future__ import annotations

import argparse
import errno
import fcntl
import math
import os
import struct
import sys
import time

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)

from comum import RADIO, abrir_no_hidraw, cabecalho_do_instrumento, resumo
from escrita_pelo_broker import (
    alvos_da_mesa,
    common_vazio,
    escolher_alvo,
    linha_do_caderno,
    listar,
    mascarar,
    perguntar,
)
from hefesto_dualsense4unix.core.ds_output_report import (
    VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE,
    build_bt_report,
)
from hefesto_dualsense4unix.integrations import alto_falante_bt as af

LINHA_DO_MAPA = "audio.alto_falante@dualsense"
TAXA = 48000
AMOSTRAS_POR_QUADRO = 480
ENVELOPES = ("data", "set_report")


def hidiocsoutput(tamanho: int) -> int:
    """`HIDIOCSOUTPUT(len)` = `_IOC(_IOC_READ|_IOC_WRITE, 'H', 0x0B, len)` — Linux ≥ 5.11."""
    _IOC_WRITE, _IOC_READ = 1, 2
    return ((_IOC_READ | _IOC_WRITE) << 30) | ((tamanho & 0x3FFF) << 16) | (ord("H") << 8) | 0x0B


def pcm_do_tom(segundos: float, hz: float = 440.0, amplitude: float = 0.3) -> list[bytes]:
    """O tom em quadros de 10 ms (1920 B: 480 amostras x 2 canais x 2 B), como o encoder pede."""
    quadros = []
    total = int(segundos * TAXA)
    for inicio in range(0, total - AMOSTRAS_POR_QUADRO + 1, AMOSTRAS_POR_QUADRO):
        pcm = bytearray()
        for i in range(inicio, inicio + AMOSTRAS_POR_QUADRO):
            v = int(amplitude * 32767 * math.sin(2 * math.pi * hz * i / TAXA))
            pcm += struct.pack("<hh", v, v)
        quadros.append(bytes(pcm))
    return quadros


def enviar(fd: int, report: bytes, envelope: str) -> int:
    """Um report pelo envelope pedido. Devolve os bytes aceitos — que NÃO é a medição."""
    if envelope == "data":
        return os.write(fd, report)
    if envelope == "set_report":
        buf = bytearray(report)
        fcntl.ioctl(fd, hidiocsoutput(len(buf)), buf, True)
        return len(buf)
    raise ValueError(f"envelope desconhecido: {envelope}")


def corromper_crc(report: bytes) -> bytes:
    """O CRC-32 do rabo invertido — o negativo que nenhum envelope pode transformar em som."""
    corpo = bytearray(report)
    for i in range(len(corpo) - 4, len(corpo)):
        corpo[i] ^= 0xFF
    return bytes(corpo)


def report_de_cor(r: int, g: int, b: int, seq: int) -> bytes:
    """Um `0x31` que pede só uma cor — o passo 0, para saber se o envelope CHEGA."""
    c = common_vazio()
    c[1] |= VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE
    c[44], c[45], c[46] = r, g, b
    return bytes(build_bt_report(c, seq=seq))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--alvo", help="MAC (inteira ou mascarada) do controle NO RÁDIO")
    ap.add_argument("--envelope", choices=ENVELOPES, action="append", help="padrão: os dois")
    ap.add_argument("--arranjo", action="append", help=f"padrão: todos ({', '.join(af.ARRANJO_POR_NOME)})")
    ap.add_argument("--segundos", type=float, default=3.0, help="a duração do tom por passo")
    ap.add_argument("--crc-errado", action="store_true", help="o negativo: CRC corrompido em todo report")
    ap.add_argument("--so-a-luz", action="store_true", help="passo 0: um 0x31 de cor pelos dois envelopes")
    args = ap.parse_args()

    aparelhos = [a for a in alvos_da_mesa() if a.transporte == RADIO]
    pergunta = "o áudio por rádio fala num envelope HID e cala no outro?"
    if args.listar or not args.alvo:
        print(cabecalho_do_instrumento(
            "o_envelope_do_som_no_radio", pergunta,
            bibliotecas=["hefesto_dualsense4unix.integrations.alto_falante_bt"],
            escreve_no_aparelho=True))
        print("\ncontroles NO RÁDIO (o envelope só existe neles):")
        print(listar(aparelhos, so_transporte=RADIO))
        print(f"\narranjos do produto: {', '.join(af.ARRANJO_POR_NOME)}")
        return 0

    alvo = escolher_alvo(aparelhos, args.alvo)
    if alvo is None:
        print(f"alvo {args.alvo!r} não está no rádio. Conhecidos: {[mascarar(a.mac) for a in aparelhos]}")
        return 1
    envelopes = tuple(args.envelope) if args.envelope else ENVELOPES
    nomes = tuple(args.arranjo) if args.arranjo else tuple(af.ARRANJO_POR_NOME)
    for nome in nomes:
        if nome not in af.ARRANJO_POR_NOME:
            print(f"arranjo desconhecido: {nome!r}; o produto tem {list(af.ARRANJO_POR_NOME)}")
            return 2

    print(cabecalho_do_instrumento(
        "o_envelope_do_som_no_radio", pergunta,
        bibliotecas=["hefesto_dualsense4unix.integrations.alto_falante_bt"],
        escreve_no_aparelho=True))
    print(f"\nalvo ........ {mascarar(alvo.mac)}  ({alvo.caminho_hidraw})")
    print(f"envelopes ... {', '.join(envelopes)}   arranjos ... {', '.join(nomes)}")
    print(f"CRC ......... {'*** DELIBERADAMENTE ERRADO ***' if args.crc_errado else 'do produto (semente 0xA2)'}")

    try:
        no = abrir_no_hidraw(alvo.caminho_hidraw, escrita=True)
    except Exception as erro:
        print(f"sem porta para {mascarar(alvo.mac)}: {erro}")
        return 1
    print(f"porta ....... {getattr(no, 'linha_de_relatorio', 'broker')}")
    print("\nO RETORNO DO write/ioctl NÃO É A MEDIÇÃO — quem mede é a orelha (e, no passo 0, o olho) dela.\n")

    respostas: list[tuple[str, str, str]] = []
    seq = 0
    try:
        if args.so_a_luz:
            for envelope in envelopes:
                seq = (seq + 1) & 0x0F
                pacote = report_de_cor(0, 0, 255, seq)
                if args.crc_errado:
                    pacote = corromper_crc(pacote)
                try:
                    enviar(no.fd, pacote, envelope)
                    print(f"PASSO 0 [{envelope}] — 0x31 de cor AZUL enviado")
                except OSError as erro:
                    print(f"PASSO 0 [{envelope}] — o kernel recusou: {erro} "
                          f"({'sem HIDIOCSOUTPUT neste kernel' if erro.errno in (errno.EINVAL, errno.ENOTTY) else 'ver acima'})")
                respostas.append(("luz", envelope, perguntar("  -> a barra ficou AZUL? (verbatim)  ")))
                seq = (seq + 1) & 0x0F
                enviar(no.fd, report_de_cor(0, 0, 0, seq), "data")
                time.sleep(0.6)
            return 0

        try:
            codificador = af.CodificadorOpus()
        except Exception as exc:
            print(f"SEM ENCODER: {exc} — o produto não codifica nesta máquina; nada a mandar.")
            return 1
        with codificador:
            quadros_opus = []
            for pcm in pcm_do_tom(args.segundos):
                q = codificador.codificar(pcm)
                if q is None:
                    print("a libopus recusou um quadro — nada a montar")
                    return 1
                quadros_opus.append(q)
        print(f"tom ......... {args.segundos:g} s em {len(quadros_opus)} quadros Opus de {len(quadros_opus[0])} B\n")

        for nome in nomes:
            arranjo = af.ARRANJO_POR_NOME[nome]
            por_report = max(1, int(getattr(arranjo, "quadros_de_audio", 1)))
            common = af.common_de_audio() if arranjo.common_preservado else None
            for envelope in envelopes:
                print(f"PASSO [{nome}] x [{envelope}] — {por_report} quadro(s) por report, "
                      f"um report a cada {por_report * 10} ms")
                enviados, recusas = 0, 0
                inicio = time.monotonic()
                for i in range(0, len(quadros_opus), por_report):
                    lote = quadros_opus[i:i + por_report]
                    if len(lote) < por_report:
                        break
                    seq = (seq + 1) & 0x0F
                    pacote = arranjo.montar(lote, seq=seq, common=common)
                    if args.crc_errado:
                        pacote = corromper_crc(pacote)
                    try:
                        enviar(no.fd, pacote, envelope)
                        enviados += 1
                    except OSError as erro:
                        recusas += 1
                        if recusas == 1:
                            print(f"  o kernel recusou: {erro}")
                        if erro.errno in (errno.EINVAL, errno.ENOTTY):
                            print("  (este kernel não tem HIDIOCSOUTPUT — o envelope SET_REPORT não é testável aqui)")
                            break
                    alvo_t = inicio + (i // por_report + 1) * por_report * 0.010
                    atraso = alvo_t - time.monotonic()
                    if atraso > 0:
                        time.sleep(atraso)
                print(f"  {enviados} report(s) de {len(pacote)} B enviados, {recusas} recusa(s), "
                      f"{time.monotonic() - inicio:.1f} s")
                respostas.append((nome, envelope, perguntar("  -> saiu som do controle? (verbatim)  ")))
    finally:
        fechar = getattr(no, "fechar", None)
        if callable(fechar):
            fechar()
        print("\nporta fechada.")

    print("\nLINHAS PROPOSTAS PARA O CADERNO (docs/data/ensaios.csv — quem roda escreve):")
    for nome, envelope, resposta in respostas:
        print(linha_do_caderno(
            id=f"som-radio-envelope-{envelope}-{nome}-{'crc-errado-' if args.crc_errado else ''}{time.strftime('%d%m')}",
            linha_id=LINHA_DO_MAPA,
            transporte="radio",
            suspeito="o áudio por rádio depende do ENVELOPE HID (DATA no canal de interrupção vs SET_REPORT no de controle)",
            presente="sim" if envelope == "set_report" else "não",
            resultado="",
            observado_por="olho-dela",
            fonte="scripts/ensaios/o_envelope_do_som_no_radio.py",
            nota=f"arranjo {nome}, envelope {envelope}, CRC {'errado' if args.crc_errado else 'certo'}; ela: {resposta or '(sem resposta)'}",
        ))
    print(resumo("som num envelope e silêncio no outro fecha o ensaio 13; silêncio nos dois com a luz do passo 0 acesa pelos dois é do áudio, não do envelope."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
