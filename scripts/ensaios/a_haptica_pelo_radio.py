#!/usr/bin/env python3
"""a_haptica_pelo_radio.py — qual report faz o motor voice-coil vibrar por Bluetooth?

HAPTICA-POR-RADIO-01, passo P1. No cabo a vibração dos jogos da Sony viaja como
áudio (os canais 3 e 4 da placa do controle, medido em 17/09/2026). Pelo rádio
não há placa de áudio: a háptica tem de ir dentro de um report HID, num bloco
TLV de tag ``0x12``. Ninguém nesta casa mediu QUAL report o firmware aceita.

O FORMATO DO BLOCO vem do DS5Dongle e do ``awalol/dualsense-bt-haptics``: int8
estéreo entrelaçado a 3 kHz, 64 B por bloco (32 amostras x 2 canais) — os mesmos
10,667 ms do quadro Opus do ``0x35``, que tocou o alto-falante em 10/09/2026.

AS VARIANTES (``--report``), uma por passada — a lição do som foi que variar o
report é o que separa "não existe" de "perguntei no lugar errado":

    32            0x32 de 142 B · [2]=0x92 [3]=64 [4..67]=o bloco
    32-com-11     0x32 · bloco 0x11 (AudioControl, 7 B) antes do 0x12
    35-com-11     0x35 de 334 B · o mesmo arranjo, no report que toca o som
    36-com-11     0x36 de 398 B (o do Senshi)
    39-com-11     0x39 de 547 B (o do DS5Dongle)

``--duplo`` troca a tag por ``0xD2`` com comprimento 32 (o bit 6 dobra o
comprimento — é a forma do Senshi). Os tamanhos e o lugar do CRC são os do
descritor destes controles, já medidos (``dualsense-referencia-canonica.md``).

AS MORDIDAS, e a terceira é a que importa:
  --crc-errado    nenhum report vale com o CRC corrompido;
  --tag-errada    ``0xD5`` no lugar da tag: o firmware tem de ignorar o bloco;
  --pcm-zerado    o MESMO report com as amostras em zero. O rumble clássico
                  também vibra; só o PCM zerado CALANDO prova que quem vibrou
                  foi o voice-coil movido pelo bloco.

ANTES DE RODAR: o daemon PARADO (`systemctl --user stop hefesto-dualsense4unix`).
Ele escreve ``0x35`` no mesmo controle ~94 vezes por segundo, e dois escritores
disputam o contador de sequência — foi assim que o microfone caía em 10/09. O
instrumento recusa rodar com o daemon vivo, a menos que ``--com-daemon``.

ESCREVE NO APARELHO? SIM, com ``--tocar``. Sem ele, mostra os bytes e não abre porta.

    a_haptica_pelo_radio.py --report 32               # só os bytes
    a_haptica_pelo_radio.py --report 32 --tocar       # 3 s de senoide nos motores
    a_haptica_pelo_radio.py --report 32 --tocar --pcm-zerado   # a mordida que decide

    a_haptica_pelo_radio.py --sequencia --tocar       # as cinco, cada uma com uma cor

A SEQUÊNCIA existe porque na bancada ela não vê o terminal: antes de cada
variante a barra acende numa cor (vermelho 32, verde 32-com-11, azul 35-com-11,
amarelo 36-com-11, branco 39-com-11), os motores recebem 3 s, a barra apaga, e a
próxima vem. Ela responde com as cores em que sentiu o voice-coil.

O VEREDITO É A MÃO DELA. ``write()`` com sucesso não prova vibração.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)
_SRC = os.path.join(os.path.dirname(os.path.dirname(_AQUI)), "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import hefesto_dualsense4unix.core.ds_output_report as rep
from hefesto_dualsense4unix.core.lightbar_gatilho import build_bt_lightbar_report
from comum import (
    RADIO,
    abrir_no_hidraw,
    cabecalho_do_instrumento,
    descobrir_aparelhos,
    estado_do_daemon,
    fisicos,
    resumo,
)
from escrita_pelo_broker import mascarar

#: O tamanho de cada degrau, do descritor destes controles (com o id).
TAMANHOS = {0x32: 142, 0x35: 334, 0x36: 398, 0x39: 547}

VARIANTES = {
    "32": (0x32, False),
    "32-com-11": (0x32, True),
    "35-com-11": (0x35, True),
    "36-com-11": (0x36, True),
    "39-com-11": (0x39, True),
}

#: A taxa do bloco e o tamanho dele: 32 amostras por canal a 3 kHz são os
#: 10,667 ms do quadro Opus — a cadência que o firmware consome no rádio.
TAXA_HAPTICA = 3000
AMOSTRAS_POR_CANAL = 32
BYTES_DO_BLOCO = AMOSTRAS_POR_CANAL * 2
INTERVALO = 512 / 48000

#: A cor que anuncia cada variante na sequência — ela lê a barra, não a tela.
CORES = {
    "32": ("vermelho", (255, 0, 0)),
    "32-com-11": ("verde", (0, 255, 0)),
    "35-com-11": ("azul", (0, 0, 255)),
    "36-com-11": ("amarelo", (255, 255, 0)),
    "39-com-11": ("branco", (255, 255, 255)),
}

TAG_AUDIO_CONTROL = 0x11 | 0x80
TAG_HAPTICA = 0x12 | 0x80
TAG_HAPTICA_DUPLA = 0x12 | 0x80 | 0x40
TAG_ERRADA = 0xD5
ENABLES_SEM_MIC = 0xFE
BUFFER_DO_SOM = bytes([0x00, 0x00, 0x00, 0x00, 0xFF])


def blocos_da_senoide(segundos: float, *, frequencia: float, amplitude: int,
                      zerado: bool = False) -> list[bytes]:
    """Senoide int8 estéreo entrelaçada, 64 B por bloco, os dois motores juntos."""
    total = max(1, round(segundos / INTERVALO))
    blocos: list[bytes] = []
    n = 0
    for _ in range(total):
        corpo = bytearray(BYTES_DO_BLOCO)
        for i in range(AMOSTRAS_POR_CANAL):
            v = 0 if zerado else round(amplitude * math.sin(2 * math.pi * frequencia * n / TAXA_HAPTICA))
            b = v & 0xFF
            corpo[2 * i] = b
            corpo[2 * i + 1] = b
            n += 1
        blocos.append(bytes(corpo))
    return blocos


def montar(report_id: int, com_11: bool, bloco: bytes, *, seq: int, contador: int,
           duplo: bool = False, tag_errada: bool = False,
           crc_errado: bool = False) -> bytes:
    """Um report de háptica: [id][seq<<4][bloco 0x11?][bloco 0x12][…][CRC]."""
    pkt = bytearray(TAMANHOS[report_id])
    pkt[0] = report_id
    pkt[1] = (seq & 0x0F) << 4
    i = 2
    if com_11:
        pkt[i] = TAG_AUDIO_CONTROL
        pkt[i + 1] = 7
        pkt[i + 2] = ENABLES_SEM_MIC
        pkt[i + 3 : i + 8] = BUFFER_DO_SOM
        pkt[i + 8] = contador & 0xFF
        i += 9
    if tag_errada:
        pkt[i] = TAG_ERRADA
    else:
        pkt[i] = TAG_HAPTICA_DUPLA if duplo else TAG_HAPTICA
    pkt[i + 1] = BYTES_DO_BLOCO // 2 if duplo else BYTES_DO_BLOCO
    pkt[i + 2 : i + 2 + BYTES_DO_BLOCO] = bloco
    crc = rep.bt_crc32(bytes(pkt[:-4]), seed=rep.BT_CRC_SEED)
    if crc_errado:
        crc ^= 0xFFFFFFFF
    pkt[-4:] = crc.to_bytes(4, "little")
    return bytes(pkt)


def barra(rgb: tuple[int, int, int], *, seq: int) -> bytes:
    """O ``0x31`` mínimo do produto: só a cor, sem vibração nem áudio."""
    pkt = bytearray(build_bt_lightbar_report(rgb))
    rep.stamp_bt_seq(pkt, seq)
    return bytes(pkt)


def tocar(fd: int, report_id: int, com_11: bool, blocos: list[bytes], args, seq: int) -> tuple[int, int, int]:
    """Manda os blocos na cadência do rádio. Devolve (seq, enviados, recusas)."""
    enviados = recusas = contador = 0
    proximo = time.monotonic()
    for bloco in blocos:
        seq = (seq + 1) & 0x0F
        contador = (contador + 1) & 0xFF
        pkt = montar(report_id, com_11, bloco, seq=seq, contador=contador,
                     duplo=args.duplo, tag_errada=args.tag_errada,
                     crc_errado=args.crc_errado)
        try:
            os.write(fd, pkt)
            enviados += 1
        except OSError as erro:
            recusas += 1
            print(f"  RECUSA na escrita {enviados + 1}: "
                  f"{erro.__class__.__name__} {erro.errno} — {erro.strerror}")
            break
        proximo += INTERVALO
        espera = proximo - time.monotonic()
        if espera > 0:
            time.sleep(espera)
    return seq, enviados, recusas


def escolher_alvo(exigir_mac: str):  # o tipo é o `Aparelho` de `comum`
    reais = [a for a in fisicos(descobrir_aparelhos()) if a.transporte == RADIO]
    if exigir_mac:
        pedido = exigir_mac.lower().replace(":", "")
        reais = [a for a in reais if a.mac.lower().replace(":", "") == pedido]
    return reais[0] if len(reais) == 1 else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report", choices=list(VARIANTES), default="32")
    ap.add_argument("--sequencia", action="store_true",
                    help="as cinco variantes em fila, cada uma anunciada por uma cor da barra")
    ap.add_argument("--so", action="append", choices=list(VARIANTES), default=[],
                    help="na sequência, só estas variantes (repetível) — uma cor por vez")
    ap.add_argument("--tocar", action="store_true", help="manda (ESCREVE no aparelho)")
    ap.add_argument("--duplo", action="store_true", help="tag 0xD2 com comprimento 32")
    ap.add_argument("--crc-errado", action="store_true", help="mordida: CRC corrompido")
    ap.add_argument("--tag-errada", action="store_true", help="mordida: tag 0xD5")
    ap.add_argument("--pcm-zerado", action="store_true", help="mordida: amostras em zero")
    ap.add_argument("--frequencia", type=float, default=160.0, help="Hz da senoide")
    ap.add_argument("--amplitude", type=int, default=100, help="pico int8 (1..127)")
    ap.add_argument("--segundos", type=float, default=3.0)
    ap.add_argument("--exigir-mac", default="", help="endereço do controle, com dois no rádio")
    ap.add_argument("--com-daemon", action="store_true",
                    help="roda mesmo com o daemon vivo (dois escritores — não é a medida)")
    args = ap.parse_args()
    if not 1 <= args.amplitude <= 127:
        ap.error("--amplitude vai de 1 a 127")

    print(cabecalho_do_instrumento(
        "a_haptica_pelo_radio",
        "qual report faz o motor voice-coil vibrar por Bluetooth?",
        bibliotecas=["hefesto_dualsense4unix.core.ds_output_report"],
        escreve_no_aparelho=bool(args.tocar)))

    report_id, com_11 = VARIANTES[args.report]
    blocos = blocos_da_senoide(args.segundos, frequencia=args.frequencia,
                               amplitude=args.amplitude, zerado=args.pcm_zerado)
    exemplo = montar(report_id, com_11, blocos[min(3, len(blocos) - 1)], seq=1, contador=1,
                     duplo=args.duplo, tag_errada=args.tag_errada,
                     crc_errado=args.crc_errado)
    mordidas = [m for m, on in (("CRC ERRADO", args.crc_errado), ("TAG 0xD5", args.tag_errada),
                                ("PCM ZERADO", args.pcm_zerado)) if on]
    print(f"o report: {report_id:#04x}, {len(exemplo)} B · variante {args.report}"
          f"{' · duplo' if args.duplo else ''} · senoide {args.frequencia:g} Hz, "
          f"pico {args.amplitude}")
    print(f"os 24 primeiros bytes: {exemplo[:24].hex(' ')}")
    print(f"blocos: {len(blocos)} ({args.segundos:g} s a 10,667 ms cada)")
    print(f"mordida: {', '.join(mordidas) if mordidas else 'nenhuma — é a passada que pode vibrar'}")

    if not args.tocar:
        print(resumo("leitura pura — nenhuma porta aberta, nenhum byte escrito."))
        return 0

    if estado_do_daemon().rodando and not args.com_daemon:
        print(resumo("o daemon está VIVO e escreve 0x35 no mesmo controle — pare-o "
                     "(systemctl --user stop hefesto-dualsense4unix) ou use --com-daemon."))
        return 1

    alvo = escolher_alvo(args.exigir_mac)
    if alvo is None:
        print(resumo("preciso de EXATAMENTE UM DualSense no rádio (ou --exigir-mac)."))
        return 1
    print(f"o controle do rádio: {mascarar(alvo.mac)}  ({alvo.caminho_hidraw})\n")

    no = abrir_no_hidraw(alvo.caminho_hidraw, escrita=True)
    print(getattr(no, "linha_de_relatorio", "porta: broker"))
    try:
        seq = 0
        fila = (args.so or list(VARIANTES)) if args.sequencia else [args.report]
        for nome in fila:
            rid, c11 = VARIANTES[nome]
            if args.sequencia:
                cor, rgb = CORES[nome]
                seq = (seq + 1) & 0x0F
                os.write(no.fd, barra(rgb, seq=seq))
                print(f"\n  [{cor.upper()}] variante {nome} — a barra acende, os motores em 2 s",
                      flush=True)
                time.sleep(2.0)
            else:
                print(f"\n  >>> SEGURE O CONTROLE DO RÁDIO — {args.segundos:g} s"
                      f"{' · ' + ', '.join(mordidas) + ' (tem de CALAR)' if mordidas else ''}",
                      flush=True)
            seq, enviados, recusas = tocar(no.fd, rid, c11, blocos, args, seq)
            print(f"  {nome}: {enviados} report(s) enviados, {recusas} recusa(s)")
            if args.sequencia:
                seq = (seq + 1) & 0x0F
                os.write(no.fd, barra((0, 0, 0), seq=seq))
                time.sleep(2.0)
    finally:
        fechar = getattr(no, "fechar", None)
        if callable(fechar):
            fechar()

    print(resumo("o veredito é a mão: vibrou, não vibrou, ou vibrou com o PCM zerado "
                 "(e aí não era o bloco)."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
