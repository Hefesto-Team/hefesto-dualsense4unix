#!/usr/bin/env python3
"""o_som_pelo_035.py — o alto-falante por rádio pelo report que as implementações VIVAS usam.

DE ONDE ISTO VEM — a caçada de 10/09/2026, e ela derrubou três coisas nossas
--------------------------------------------------------------------------------
Cinco frentes de pesquisa leram o código de quem FAZ SOM no alto-falante do
DualSense por Bluetooth. O que voltou explica o silêncio desta casa, e não é uma
causa: são cinco, e todas ao mesmo tempo.

**1. O REPORT ESTAVA ERRADO.** Nenhuma das quatro implementações que tocam usa o
``0x39`` de 547 B, que é onde esta casa passou todas as passadas. Quem toca usa
``0x32`` (142 B, háptico puro), ``0x35`` (334 B, **alto-falante puro, um quadro
Opus**) ou ``0x36`` (398 B, estado + háptico + áudio juntos).

**2. FALTAVA O PRIMER QUE ARMA O ALTO-FALANTE.** O valor de fábrica de
``audio_control`` é ``0x00``, e ``0x00`` significa *L+R para o fone, alto-falante
MUDO*. Sem um ``0x31`` que peça ``OUTPUT_PATH`` = alto-falante, todo áudio que
chega é jogado num fone que não existe. **Esta casa nunca mandou esse primer
antes do áudio.**

**3. A TAG NÃO É ``tag|0x80``.** O byte de tag tem três campos, e o bit 6 diz
*"o comprimento declarado vale em DOBRO"*. Quem manda dois quadros escreve
``tag|0xC0`` com ``len=200`` e copia 400 bytes. **Esta casa escrevia
``[0x13|0x80][200]`` e copiava 400** — o firmware lia 200 e tentava ler o byte
201 do Opus como a próxima tag. O ``0x35`` não sofre disso: ele leva UM quadro.

**4. O primeiro byte do bloco ``0x11`` é ``0xFE``**, sete bits de enable — não o
``0b011`` que esta casa usa para o microfone. ``0xFF`` liga o mic junto.

**5. A CADÊNCIA É 10,667 ms** (512/48000), não 10 ms — e o erro não dá silêncio,
dá gagueira periódica.

E DUAS RESSALVAS DESTA CASA CAÍRAM
-----------------------------------
* *"o DS5Dongle é um dongle, fala L2CAP direto e nunca toca /dev/hidraw"* —
  ``GeorgLegato/LinuxAudio4Dualsense5`` é um sink PipeWire em C que **abre
  ``/dev/hidraw`` e escreve com ``write()``**, no Linux, pelo BlueZ, com o perfil
  de input padrão. O README dele diz: *"CRC-32 seed 0xA2; no application-layer
  crypto — plain hidraw writes work."* O hidraw BASTA;
* *"o MTU do BlueZ pode ser a parede"* — o DS5Dongle roda com ``MTU 672``, o
  MESMO do BlueZ. O ``setsockopt``/1024 que esta casa mediu em 10/09 não era
  necessário, e o silêncio por L2CAP direto com 1024 confirma que não era ali.

O QUE ESTE ENSAIO MANDA
------------------------
O ``0x35`` de 334 B do ``HeadsetPlayMusic`` (``awalol/dualsense-bt-haptics``),
que é o menor caminho conhecido até o som::

    [0]        0x35
    [1]        seq << 4
    [2]        0x11 | 0x80        tag AudioControl
    [3]        7                  comprimento do valor
    [4]        0xFE               os sete enables (0xFF liga o microfone junto)
    [5..9]     buffer length      `00 00 00 00 FF` no HeadsetPlayMusic,
                                  `40 40 40 40 40` nas outras três — as duas
                                  formas estão aqui, e é `--buffer` que escolhe
    [10]       contador de QUADROS de áudio (não de reports)
    [11]       0x13|0x80 alto-falante · 0x16|0x80 fone
    [12]       200                comprimento do quadro Opus
    [13..212]  o quadro Opus      48 kHz estéreo, 10 ms, CBR 160 kbps
    [213..329] zero
    [330..333] CRC-32 LE, seed 0xA2

E ANTES DELE, O PRIMER — um ``0x31`` que pede rota, volume e pré-amplificador.
Ele sai do produto (``alto_falante_bt.common_de_audio``), e o número que decide é
a rota: ``SAIDA_SO_NO_ALTO_FALANTE`` vira ``0x30`` no byte ``audio_control``,
que é exatamente o valor que as implementações vivas mandam.

A MORDIDA — e são duas, as duas nesta folha
--------------------------------------------
1. ``--sem-primer`` — o mesmo áudio sem armar o alto-falante. Se sair som sem o
   primer, o primer não era o que faltava, e este ensaio está se enganando;
2. ``--crc-errado`` — o negativo de sempre. Nenhum report pode dar som com o CRC
   corrompido; se der, quem está tocando não é este ensaio.

ESCREVE NO APARELHO? SIM, com `--tocar`. Sem ele, mostra os bytes e não abre porta.

USO
    o_som_pelo_035.py --listar
    o_som_pelo_035.py --tocar                      # o caminho completo
    o_som_pelo_035.py --tocar --sem-primer         # a mordida 1
    o_som_pelo_035.py --tocar --crc-errado         # a mordida 2
    o_som_pelo_035.py --tocar --rota fone --buffer 40
"""

from __future__ import annotations

import argparse
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
import hefesto_dualsense4unix.integrations.alto_falante_bt as af
from a_folha_do_som_por_controle import quadros_opus
from comum import RADIO, abrir_no_hidraw, cabecalho_do_instrumento, descobrir_aparelhos, fisicos, resumo
from escrita_pelo_broker import mascarar

#: O TAMANHO DO REPORT, e ele é do descritor do aparelho — não escolha nossa.
TAMANHO_035 = 334

#: A TAG DA ROTA. `0x13` alto-falante interno, `0x16` fone. O bit 7 diz "bloco
#: presente"; o bit 6 (que dobraria o comprimento) fica FORA aqui de propósito:
#: o `0x35` leva UM quadro de 200 B, e é essa simplicidade que o torna o
#: primeiro a tentar.
ROTAS = {"alto-falante": 0x13, "fone": 0x16}

#: OS CINCO BYTES DE `audio_buffer_length`, nas duas formas vivas. O
#: `HeadsetPlayMusic` escreve `00 00 00 00 FF`; o `LinuxAudio4Dualsense5`, o
#: `DualSenseClient` e o `DS5Dongle-OLED` escrevem `40` nos cinco. O autor de um
#: deles anotou no fonte que só o ÚLTIMO byte tem efeito — as duas formas estão
#: aqui porque a divergência é real e barata de varrer.
BUFFERS = {"ff": bytes([0x00, 0x00, 0x00, 0x00, 0xFF]), "40": bytes([0x40] * 5)}

#: O PRIMEIRO BYTE DO BLOCO `0x11`: sete bits de enable. `0xFF` liga o microfone
#: junto — e o bit 0 é o que uma casa inteira levou meses para achar, segundo o
#: relato público que a pesquisa trouxe.
ENABLES_SEM_MIC = 0xFE
ENABLES_COM_MIC = 0xFF

#: O VOLUME DO PRIMER. As implementações vivas mandam `0x64` (100), e há relato
#: de que o firmware só aceita entre `0x3D` e `0x64`.
VOLUME_DO_PRIMER = 0x64


def primer_que_arma(seq: int) -> bytes:
    """O `0x31` que pede a rota do alto-falante — o que faltava antes do áudio.

    O `common` sai do produto. A rota `SAIDA_SO_NO_ALTO_FALANTE` vira `0x30` no
    byte `audio_control`, que é o valor que as quatro implementações mandam.
    """
    common = af.common_de_audio(
        volume=VOLUME_DO_PRIMER,
        rota=rep.SAIDA_SO_NO_ALTO_FALANTE,
        preamp=rep.SP_PREAMP_GAIN_PADRAO,
    )
    return bytes(rep.build_bt_report(common, seq=seq))


def report_035(quadro: bytes, *, seq: int, contador: int, rota: int,
               buffer: bytes, com_mic: bool = False,
               crc_errado: bool = False) -> bytes:
    """Um `0x35` de 334 B com UM quadro Opus. O layout é o do HeadsetPlayMusic."""
    if len(quadro) != af.BYTES_POR_QUADRO_OPUS:
        raise ValueError(
            f"o quadro Opus tem {len(quadro)} B e o report pede "
            f"{af.BYTES_POR_QUADRO_OPUS} — CBR desligado?"
        )
    pkt = bytearray(TAMANHO_035)
    pkt[0] = 0x35
    pkt[1] = (seq & 0x0F) << 4
    pkt[2] = 0x11 | 0x80
    pkt[3] = 7
    pkt[4] = ENABLES_COM_MIC if com_mic else ENABLES_SEM_MIC
    pkt[5:10] = buffer
    pkt[10] = contador & 0xFF
    pkt[11] = rota | 0x80
    pkt[12] = af.BYTES_POR_QUADRO_OPUS
    pkt[13 : 13 + af.BYTES_POR_QUADRO_OPUS] = quadro
    crc = rep.bt_crc32(bytes(pkt[:-4]), seed=rep.BT_CRC_SEED)
    if crc_errado:
        crc ^= 0xFFFFFFFF
    pkt[-4:] = crc.to_bytes(4, "little")
    return bytes(pkt)


def o_controle_no_radio(): — o tipo é o `Aparelho` de `comum`
    """O DualSense do rádio. Um só: com dois, não se sabe de quem é o som."""
    reais = [a for a in fisicos(descobrir_aparelhos()) if a.transporte == RADIO]
    return reais[0] if len(reais) == 1 else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--listar", action="store_true", help="só lê: os bytes que ele mandaria")
    ap.add_argument("--tocar", action="store_true", help="manda (ESCREVE no aparelho)")
    ap.add_argument("--rota", choices=list(ROTAS), default="alto-falante")
    ap.add_argument("--buffer", choices=list(BUFFERS), default="ff",
                    help="os cinco bytes de audio_buffer_length: ff (HeadsetPlayMusic) ou 40")
    ap.add_argument("--com-mic", action="store_true", help="enables 0xFF em vez de 0xFE")
    ap.add_argument("--sem-primer", action="store_true", help="a mordida 1: sem armar o alto-falante")
    ap.add_argument("--desarmar", action="store_true",
                    help="ANTES de tudo, devolve a rota ao padrão de fábrica (fone) — "
                         "é o que torna a mordida 1 honesta")
    ap.add_argument("--crc-errado", action="store_true", help="a mordida 2: o negativo")
    ap.add_argument("--segundos", type=float, default=5.0)
    args = ap.parse_args()

    print(cabecalho_do_instrumento(
        "o_som_pelo_035",
        "o alto-falante toca pelo 0x35 de 334 B, com o primer que ARMA a rota?",
        bibliotecas=["hefesto_dualsense4unix.integrations.alto_falante_bt"],
        escreve_no_aparelho=bool(args.tocar)))

    alvo = o_controle_no_radio()
    if alvo is None:
        print(resumo("preciso de EXATAMENTE UM DualSense no rádio."))
        return 1
    print(f"o controle do rádio: {mascarar(alvo.mac)}  ({alvo.caminho_hidraw})\n")

    rota = ROTAS[args.rota]
    buffer = BUFFERS[args.buffer]
    try:
        quadros = quadros_opus(args.segundos)
    except af.OpusIndisponivelError as erro:
        print(resumo(f"o produto não codifica Opus nesta máquina: {erro}"))
        return 1

    exemplo = report_035(quadros[0], seq=1, contador=1, rota=rota, buffer=buffer,
                         com_mic=args.com_mic, crc_errado=args.crc_errado)
    print(f"o report: 0x35, {len(exemplo)} B · rota {args.rota} (tag {rota:#04x}) · "
          f"buffer {args.buffer} · enables {exemplo[4]:#04x}")
    print(f"os 16 primeiros bytes: {exemplo[:16].hex(' ')}")
    print(f"quadros Opus de {len(quadros[0])} B: {len(quadros)} "
          f"({args.segundos:g} s a 10,667 ms cada)")
    print(f"o primer: {'NÃO — a mordida 1' if args.sem_primer else 'sim, um 0x31 que pede a rota'}")

    if not args.tocar:
        print(resumo("leitura pura — nenhuma porta aberta, nenhum byte escrito."))
        return 0

    no = abrir_no_hidraw(alvo.caminho_hidraw, escrita=True)
    print(getattr(no, "linha_de_relatorio", "porta: broker"))
    seq = 0
    try:
        if args.desarmar:
            # A ROTA PERSISTE NO FIRMWARE ENTRE CORRIDAS, e isso furou a
            # mordida 1 em 10/09/2026: ela tocou SEM primer logo depois de uma
            # corrida COM primer, e ouviu — o aparelho continuava armado. Uma
            # mordida que não desarma antes não mede o primer, mede a memória do
            # aparelho. `SAIDA_ESTEREO_NO_FONE` é o valor de fábrica: `0x00`,
            # que manda L+R ao fone e deixa o alto-falante MUDO.
            seq = (seq + 1) & 0x0F
            os.write(no.fd, bytes(rep.build_bt_report(
                af.common_de_audio(volume=VOLUME_DO_PRIMER,
                                   rota=rep.SAIDA_ESTEREO_NO_FONE,
                                   preamp=rep.SP_PREAMP_GAIN_PADRAO), seq=seq)))
            print("DESARMADO: 0x31 pedindo rota=fone (o padrão de fábrica, "
                  "alto-falante mudo)")
            time.sleep(0.3)

        if not args.sem_primer:
            seq = (seq + 1) & 0x0F
            os.write(no.fd, primer_que_arma(seq))
            print("\nPRIMER mandado: 0x31 pedindo rota=alto-falante, volume "
                  f"{VOLUME_DO_PRIMER}, pré-amp {rep.SP_PREAMP_GAIN_PADRAO}")
            time.sleep(0.05)

        marca = " · CRC ERRADO (a mordida — tem de CALAR)" if args.crc_errado else ""
        print(f"\n  >>> OUÇA O ALTO-FALANTE DO CONTROLE DO RÁDIO — "
              f"{args.segundos:g} s{marca}", flush=True)
        # A CADÊNCIA É 512/48000, e não 10 ms: o erro não dá silêncio, dá
        # gagueira periódica de ~0,5 s. É o item 3 do `reverse_engineered` do
        # LinuxAudio4Dualsense5, achado por eles com `btmon`.
        intervalo = 512 / 48000
        recusas, enviados, contador = 0, 0, 0
        proximo = time.monotonic()
        for quadro in quadros:
            seq = (seq + 1) & 0x0F
            contador = (contador + 1) & 0xFF  # conta QUADROS, não reports
            pkt = report_035(quadro, seq=seq, contador=contador, rota=rota,
                             buffer=buffer, com_mic=args.com_mic,
                             crc_errado=args.crc_errado)
            try:
                os.write(no.fd, pkt)
                enviados += 1
            except OSError as erro:
                recusas += 1
                print(f"  RECUSA na escrita {enviados + 1}: "
                      f"{erro.__class__.__name__} {erro.errno} — {erro.strerror}")
                break
            proximo += intervalo
            espera = proximo - time.monotonic()
            if espera > 0:
                time.sleep(espera)
        print(f"  {enviados} report(s) enviados, {recusas} recusa(s)")
    finally:
        fechar = getattr(no, "fechar", None)
        if callable(fechar):
            fechar()

    print(resumo(
        "se ela OUVIU, o caminho é o 0x35 com o primer — e a ponte do alto-falante "
        "por rádio nasce daqui. Se calou, rode --sem-primer e --crc-errado para "
        "saber o que este ensaio ainda não sabe."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
