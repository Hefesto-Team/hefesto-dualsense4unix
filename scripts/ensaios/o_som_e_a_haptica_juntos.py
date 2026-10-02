#!/usr/bin/env python3
"""o_som_e_a_haptica_juntos.py — o som e a vibração fina no MESMO report do rádio.

O-SOM-E-A-HAPTICA-CHEGAM-JUNTOS-PELO-RADIO-01, o passo 0. A resposta [21] dela,
29/09/2026: *«1, por hora mas no ps5 não é assim que funciona no bt. Lá os dois
chegam ao mesmo tempo.»* <!-- noqa-acento: citação literal dela -->

Hoje a ponte de cada controle no rádio escolhe UM arranjo (o `0x35` do som ou o
`0x32` da háptica). A passada azul de 18/09 provou que o `0x35` aceita o bloco
háptico, mas no assento do som ([11] tag, [13..76]); os dois nunca estiveram no
mesmo report. Este ensaio monta os dois juntos e os manda, com a orelha e a mão
dela como veredito.

AS PASSADAS (``--passada``):

    A   o ``0x35`` de 334 B: [2] o bloco ``0x11`` (AudioControl, 7 B em [4..10]),
        [11] o som (tag ``0x93``, 200 B de Opus em [13..212]) e [213] o bloco
        háptico (tag ``0x92``, 64 B em [215..278]), o CRC nos quatro últimos.
    B   o ``0x36`` de 398 B, o do console. ESPERA: a fonte desta casa
        (``docs/protocol/dualsense-modo-de-relatorio.md`` §5.4) diz só que o
        ``common`` de 47 B mora no offset 13; o háptico e o áudio depois dele
        não estão ditos, e a passada A decide sozinha até estarem.

O SOM é o tom de 1300 Hz (o da prova 0 da A-PONTE-DO-SOM), em Opus pelo
codificador do PRODUTO; a HÁPTICA é a senoide de 150 Hz, int8 estéreo a 3 kHz
(32 amostras por canal, os mesmos 10,667 ms do quadro de Opus). Um report a
cada 10,667 ms, um quadro de cada.

AS MORDIDAS: ``--sem-haptico`` (o ``0x35`` de hoje, sem o bloco háptico: o tom
tem de sair igual, e é o par que separa «o háptico cortou o som»), ``--sem-som``
(o mesmo arranjo com o Opus de silêncio no assento do som: a cadeia de blocos
fica a mesma, e o motor tem de vibrar igual) e ``--crc-errado`` (nada vale).

AS GUARDAS, as do ``scripts/ensaios/historico/a_haptica_pelo_radio.py``: sem
``--tocar`` não abre porta nenhuma, só mostra os bytes e os relê; com o daemon
no ar ele RECUSA, e não há escape (dois escritores do contador do ``0x35`` foi
o que travou o microfone em 10/09); a porta é a do broker; e o controle é
devolvido no fim (a porta fecha, e o daemon o retoma ao subir de novo).

    o_som_e_a_haptica_juntos.py                         # os bytes, relidos
    o_som_e_a_haptica_juntos.py --tocar                 # 20 s no controle do rádio
    o_som_e_a_haptica_juntos.py --tocar --sem-haptico   # a mordida do som
    o_som_e_a_haptica_juntos.py --tocar --todos --segundos 60   # o ar dos quatro

O VEREDITO É DELA: o tom sai inteiro, sem corte (a orelha), e o motor vibra ao
mesmo tempo (a mão). ``write()`` aceito não prova nenhum dos dois.
"""

from __future__ import annotations

import argparse
import math
import os
import struct
import sys
import time
from dataclasses import dataclass

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)
_SRC = os.path.join(os.path.dirname(os.path.dirname(_AQUI)), "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import hefesto_dualsense4unix.core.ds_output_report as rep
from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    AMOSTRAS_POR_QUADRO,
    BYTES_DO_BLOCO_HAPTICO,
    BYTES_POR_QUADRO_OPUS,
    CANAIS_DO_ENCODER,
    INTERVALO_DE_ENVIO_035,
    TAMANHO_DO_DEGRAU,
    TAXA_DA_FONTE_DO_SOM,
    controle_de_audio_035,
    tag_tlv,
)
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
    BLOCO_AUDIO_CONTROL,
    BLOCO_HAPTICS,
    BLOCO_SPEAKER,
)

#: OS ASSENTOS DA PASSADA A — do ensaio, e não de um ``Arranjo`` do produto: a
#: régua que relê o report compara contra estes números, e o produto que um dia
#: os adotar será medido contra eles.
DEGRAU_A = 0x35
POS_TAG_CONTROLE = 2
LEN_CONTROLE = 7
POS_TAG_SOM = 11
POS_SOM = 13
POS_TAG_HAPTICO = POS_SOM + BYTES_POR_QUADRO_OPUS
POS_HAPTICO = POS_TAG_HAPTICO + 2

#: As três tags, com o bit de presença; nenhuma dobrada.
TAG_CONTROLE = tag_tlv(BLOCO_AUDIO_CONTROL)
TAG_SOM = tag_tlv(BLOCO_SPEAKER)
TAG_HAPTICO = tag_tlv(BLOCO_HAPTICS)

#: A háptica: 32 amostras por canal a 3 kHz, int8 estéreo entrelaçado.
TAXA_HAPTICA = 3000
AMOSTRAS_HAPTICAS = BYTES_DO_BLOCO_HAPTICO // 2

PASSADAS = ("A", "B")
FRASE_DA_PASSADA_B = (
    "a passada B (o 0x36) espera: o layout depois do common de 47 B não está "
    "dito inteiro por fonte nenhuma desta casa, e a passada A decide sozinha."
)


def quadros_do_tom(total: int, *, frequencia: float, amplitude: int) -> list[bytes]:
    """``total`` quadros de PCM ``s16le`` estéreo (480 amostras) do tom.

    O seno anda na taxa da FONTE (45 kHz), não na do Opus: o aparelho toca as
    480 amostras de cada quadro em 10,667 ms, e é nessa taxa que o tom sai
    com a frequência pedida (a prova 0 da A-PONTE-DO-SOM ouviu 1300 Hz a
    48 kHz sair em 1219,4 Hz).
    """
    quadros: list[bytes] = []
    n = 0
    for _ in range(total):
        amostras = []
        for _i in range(AMOSTRAS_POR_QUADRO):
            v = round(amplitude * math.sin(2 * math.pi * frequencia * n / TAXA_DA_FONTE_DO_SOM))
            amostras.extend([v] * CANAIS_DO_ENCODER)
            n += 1
        quadros.append(struct.pack(f"<{len(amostras)}h", *amostras))
    return quadros


def blocos_da_vibracao(total: int, *, frequencia: float, amplitude: int) -> list[bytes]:
    """``total`` blocos hápticos de 64 B: a senoide int8 nos dois motores."""
    blocos: list[bytes] = []
    n = 0
    for _ in range(total):
        corpo = bytearray(BYTES_DO_BLOCO_HAPTICO)
        for i in range(AMOSTRAS_HAPTICAS):
            v = round(amplitude * math.sin(2 * math.pi * frequencia * n / TAXA_HAPTICA)) & 0xFF
            corpo[2 * i] = v
            corpo[2 * i + 1] = v
            n += 1
        blocos.append(bytes(corpo))
    return blocos


def montar_junto(
    quadro: bytes,
    bloco: bytes,
    *,
    seq: int,
    contador: int,
    sem_haptico: bool = False,
    crc_errado: bool = False,
) -> bytes:
    """O ``0x35`` da passada A: o AudioControl, o som e o bloco háptico, e o CRC.

    ``sem_haptico`` monta o ``0x35`` de hoje (a cadeia acaba no som). O
    AudioControl é o do produto (:func:`controle_de_audio_035`), sem microfone:
    o contador conta quadros de áudio, um por report.
    """
    if len(quadro) > BYTES_POR_QUADRO_OPUS:
        raise ValueError(f"quadro de Opus de {len(quadro)} B não cabe em {BYTES_POR_QUADRO_OPUS}")
    if len(bloco) != BYTES_DO_BLOCO_HAPTICO:
        raise ValueError(f"bloco háptico de {len(bloco)} B; são {BYTES_DO_BLOCO_HAPTICO}")
    pkt = bytearray(TAMANHO_DO_DEGRAU[DEGRAU_A])
    pkt[0] = DEGRAU_A
    pkt[1] = (seq & 0x0F) << 4
    pkt[POS_TAG_CONTROLE] = TAG_CONTROLE
    pkt[POS_TAG_CONTROLE + 1] = LEN_CONTROLE
    controle = controle_de_audio_035(contador_de_quadros=contador)
    pkt[POS_TAG_CONTROLE + 2 : POS_TAG_CONTROLE + 2 + LEN_CONTROLE] = controle
    pkt[POS_TAG_SOM] = TAG_SOM
    pkt[POS_TAG_SOM + 1] = BYTES_POR_QUADRO_OPUS
    pkt[POS_SOM : POS_SOM + len(quadro)] = quadro
    if not sem_haptico:
        pkt[POS_TAG_HAPTICO] = TAG_HAPTICO
        pkt[POS_TAG_HAPTICO + 1] = BYTES_DO_BLOCO_HAPTICO
        pkt[POS_HAPTICO : POS_HAPTICO + BYTES_DO_BLOCO_HAPTICO] = bloco
    crc = rep.bt_crc32(bytes(pkt[:-4]), seed=rep.BT_CRC_SEED)
    if crc_errado:
        crc ^= 0xFFFFFFFF
    pkt[-4:] = crc.to_bytes(4, "little")
    return bytes(pkt)


@dataclass(frozen=True)
class Relido:
    """O report relido pela cadeia TLV: o id, o CRC e ``(tag, início, len)`` de cada bloco."""

    id: int
    crc_ok: bool
    blocos: tuple[tuple[int, int, int], ...]


def reler(pkt: bytes) -> Relido:
    """Relê o report pela cadeia TLV, sem os assentos: o que cada tag diz que carrega.

    Anda de ``[2]`` em diante, tag e ``len``, até a primeira tag sem o bit de
    presença (``0x80``); o bit ``0x40`` dobra o ``len``.
    """
    blocos: list[tuple[int, int, int]] = []
    i = 2
    fim = len(pkt) - 4
    while i + 1 < fim and pkt[i] & 0x80:
        tag, tamanho = pkt[i], pkt[i + 1]
        corpo = tamanho * (2 if tag & 0x40 else 1)
        if i + 2 + corpo > fim:
            break
        blocos.append((tag, i + 2, corpo))
        i += 2 + corpo
    crc = rep.bt_crc32(bytes(pkt[:-4]), seed=rep.BT_CRC_SEED)
    return Relido(pkt[0], int.from_bytes(pkt[-4:], "little") == crc, tuple(blocos))


def _codificar(pcm: list[bytes]) -> list[bytes]:
    from hefesto_dualsense4unix.integrations.alto_falante_bt import CodificadorOpus

    codificador = CodificadorOpus()
    saida = []
    for quadro in pcm:
        opus = codificador.codificar(quadro)
        if opus is None:
            raise SystemExit("ERRO: a libopus recusou um quadro do tom")
        saida.append(opus)
    return saida


def main() -> int:
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

    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--passada", choices=PASSADAS, default="A")
    ap.add_argument("--tocar", action="store_true", help="manda (ESCREVE no aparelho)")
    ap.add_argument("--segundos", type=float, default=20.0)
    ap.add_argument("--tom", type=float, default=1300.0, help="Hz do som")
    ap.add_argument("--vibracao", type=float, default=150.0, help="Hz da háptica")
    ap.add_argument("--volume", type=int, default=8000, help="pico do tom (s16)")
    ap.add_argument("--amplitude", type=int, default=100, help="pico da háptica (1..127)")
    ap.add_argument("--exigir-mac", default="", help="o controle, com mais de um no rádio")
    ap.add_argument("--todos", action="store_true", help="todos os DualSense do rádio (o ar)")
    ap.add_argument("--sem-som", action="store_true", help="mordida: o Opus de silêncio")
    ap.add_argument("--sem-haptico", action="store_true", help="mordida: só o som")
    ap.add_argument("--crc-errado", action="store_true", help="mordida: CRC corrompido")
    args = ap.parse_args()
    if not 1 <= args.amplitude <= 127:
        ap.error("--amplitude vai de 1 a 127")

    print(cabecalho_do_instrumento(
        "o_som_e_a_haptica_juntos",
        "o som e a vibração fina no mesmo report do rádio",
        bibliotecas=["hefesto_dualsense4unix.core.ds_output_report",
                     "hefesto_dualsense4unix.integrations.alto_falante_bt"],
        escreve_no_aparelho=bool(args.tocar),
        daemon_precisa_parar=bool(args.tocar)))
    if args.passada == "B":
        print(resumo(FRASE_DA_PASSADA_B))
        return 1

    total = max(1, round(args.segundos / INTERVALO_DE_ENVIO_035))
    volume = 0 if args.sem_som else args.volume
    opus = _codificar(quadros_do_tom(total, frequencia=args.tom, amplitude=volume))
    blocos = blocos_da_vibracao(total, frequencia=args.vibracao, amplitude=args.amplitude)
    marcas = {"sem_haptico": args.sem_haptico, "crc_errado": args.crc_errado}
    exemplo = montar_junto(opus[min(3, total - 1)], blocos[min(3, total - 1)],
                           seq=1, contador=1, **marcas)
    lido = reler(exemplo)
    print(f"o report: {DEGRAU_A:#04x}, {len(exemplo)} B · {total} reports "
          f"({args.segundos:g} s a {INTERVALO_DE_ENVIO_035 * 1000:.3f} ms)")
    print(f"relido: crc {'certo' if lido.crc_ok else 'ERRADO'} · blocos "
          + ", ".join(f"{t:#04x}@[{i}..{i + n - 1}]" for t, i, n in lido.blocos))
    if not args.tocar:
        print(resumo("leitura pura — nenhuma porta aberta, nenhum byte escrito."))
        return 0

    if estado_do_daemon().rodando:
        print(resumo("o daemon está NO AR e escreve o 0x35 nos controles do rádio — "
                     "pare-o antes (systemctl --user stop hefesto-dualsense4unix). "
                     "Não há escape: dois escritores do contador é o que travou o "
                     "microfone em 10/09."))
        return 1
    no_radio = [a for a in fisicos(descobrir_aparelhos()) if a.transporte == RADIO]
    if args.exigir_mac:
        pedido = args.exigir_mac.lower().replace(":", "")
        no_radio = [a for a in no_radio if a.mac.lower().replace(":", "") == pedido]
    alvos = no_radio if args.todos else no_radio[:1] if len(no_radio) == 1 else []
    if not alvos:
        print(resumo("preciso de EXATAMENTE UM DualSense no rádio (ou --exigir-mac, "
                     "ou --todos)."))
        return 1
    portas = []
    try:
        for alvo in alvos:
            no = abrir_no_hidraw(alvo.caminho_hidraw, escrita=True)
            portas.append((alvo, no, {"enviados": 0, "recusas": 0}))
            print(f"o controle: {mascarar(alvo.mac)} ({alvo.caminho_hidraw}) · "
                  f"{getattr(no, 'linha_de_relatorio', 'porta: broker')}")
        print(f"\n  >>> SEGURE O CONTROLE E ESCUTE — {args.segundos:g} s, o tom de "
              f"{args.tom:g} Hz e a vibração de {args.vibracao:g} Hz juntos", flush=True)
        proximo = time.monotonic()
        for n in range(total):
            pkt = montar_junto(opus[n], blocos[n], seq=n + 1, contador=n + 1, **marcas)
            for _alvo, no, conta in portas:
                if conta["recusas"]:
                    continue
                try:
                    os.write(no.fd, pkt)
                    conta["enviados"] += 1
                except OSError as erro:
                    conta["recusas"] += 1
                    print(f"  RECUSA na escrita {n + 1}: {erro.__class__.__name__} "
                          f"{erro.errno} — {erro.strerror}")
            proximo += INTERVALO_DE_ENVIO_035
            espera = proximo - time.monotonic()
            if espera > 0:
                time.sleep(espera)
    finally:
        for _alvo, no, _conta in portas:
            fechar = getattr(no, "fechar", None)
            if callable(fechar):
                fechar()
    for alvo, _no, conta in portas:
        print(f"  {mascarar(alvo.mac)}: {conta['enviados']} report(s) aceitos, "
              f"{conta['recusas']} recusa(s)")
    print(resumo("o veredito é dela: o tom saiu inteiro? o motor vibrou junto? "
                 "O controle está devolvido; suba o daemon de novo."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
