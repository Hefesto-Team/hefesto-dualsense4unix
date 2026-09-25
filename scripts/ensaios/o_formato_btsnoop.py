#!/usr/bin/env python3
"""o_formato_btsnoop.py — o arquivo do ``btmon -w``, lido por um dono só.

Nasceu dentro do ``byte_no_fio.py`` e saiu dele em 25/09/2026
(AS-CAPTURAS-DE-RADIO-NASCEM-FECHADAS-01), por duas razões:

1. **A lightbar lia a captura com um parser que não lê.** O
   ``scripts/capturar_a_probe_da_lightbar.sh`` passava o ``btmon -r`` num
   ``awk`` que exige um deslocamento de oito dígitos no começo da linha, e o
   ``packet_hexdump`` do BlueZ não imprime deslocamento: é o parser que, em
   12/08/2026, "não venceu o formato". Enquanto a captura crua ficava no
   ``/tmp``, isso só atrasava a leitura; agora que ela sai depois de lida, ler
   nada e apagar seria destruir a prova. A leitura passou a ser esta, a mesma
   que o ``byte_no_fio`` confere pela cor mágica.
2. **A lightbar lê como root**, logo depois de gravar, para a captura crua
   nunca sair das mãos do root. O ``byte_no_fio`` importa o ``comum``, que põe
   o ``src/`` no caminho e tenta o pacote da casa — nada disso deve rodar como
   root. Este arquivo é só biblioteca padrão, e roda com ``python3 -I -B``.

Uso (o que a lightbar chama)::

    python3 -I -B scripts/ensaios/o_formato_btsnoop.py --reports-de-saida <captura>
"""

from __future__ import annotations

import argparse
import struct
import sys
import zlib

# ---------------------------------------------------------------------------
# Constantes do protocolo — cada uma com a procedência que a autoriza
# ---------------------------------------------------------------------------

#: HID-over-BT, cabeçalho de transação: `(HANDSHAKE<<4)`... o que interessa é
#: que `0xA2` é `DATA` no sentido host->device e `0xA1` é `DATA` no sentido
#: device->host. É por este byte, e não pelo opcode do btsnoop, que este
#: instrumento decide o SENTIDO de cada quadro.
HID_BT_SAIDA = 0xA2
HID_BT_ENTRADA = 0xA1

#: `DS_OUTPUT_REPORT_BT` / `_SIZE` = `0x31` / 78, de
#: `docs/protocol/driver-hid-playstation.md`, lido no fonte C em 11/08/2026.
DS_OUTPUT_BT_ID = 0x31
DS_OUTPUT_BT_TAM = 78

#: Offsets ABSOLUTOS dentro do report `0x31` de saída. A mesma página da casa:
#: "BT, report `0x31`: o corpo começa em `data[2]`. Somar 2."
OFF_SEQ_TAG = 1
OFF_TAG = 2
OFF_VALID_FLAG0 = 3
OFF_VALID_FLAG1 = 4
OFF_VALID_FLAG2 = 41
OFF_LIGHTBAR_SETUP = 44
OFF_LED_BRIGHTNESS = 45
OFF_PLAYER_LEDS = 46
OFF_R, OFF_G, OFF_B = 47, 48, 49
OFF_CRC = 74

#: `PS_OUTPUT_CRC32_SEED` do `hid-playstation`. O CRC-32 é semeado com este
#: byte e calculado sobre os `len - 4` primeiros bytes do report.
CRC32_SEED_SAIDA = 0xA2

#: Só os offsets que TÊM nome no driver. O resto é reservado, e o diff diz
#: isso em vez de inventar um rótulo — um campo com nome errado num relatório
#: de protocolo custa mais caro que um campo sem nome.
NOME_DO_OFFSET = {
    OFF_SEQ_TAG: "seq_tag (contador rotativo do driver)",
    OFF_TAG: "tag",
    OFF_VALID_FLAG0: "valid_flag0",
    OFF_VALID_FLAG1: "valid_flag1",
    OFF_VALID_FLAG2: "valid_flag2",
    OFF_LIGHTBAR_SETUP: "lightbar_setup",
    OFF_LED_BRIGHTNESS: "led_brightness",
    OFF_PLAYER_LEDS: "player_leds",
    OFF_R: "lightbar_red",
    OFF_G: "lightbar_green",
    OFF_B: "lightbar_blue",
}

# ---------------------------------------------------------------------------
# O parser de btsnoop/monitor — pequeno, e conferido pela mordida
# ---------------------------------------------------------------------------


class Quadro:
    """Um pacote ACL do monitor HCI, já com o payload L2CAP separado."""

    __slots__ = ("corpo", "handle", "sentido", "ts")

    def __init__(self, ts: float, handle: int, sentido: int, corpo: bytes) -> None:
        self.ts = ts
        self.handle = handle
        self.sentido = sentido
        self.corpo = corpo


def ler_btsnoop(caminho: str) -> tuple[list[Quadro], list[str]]:
    """Os quadros ACL de um arquivo do `btmon -w`, e as queixas do caminho.

    Formato: cabeçalho de 16 bytes (`btsnoop\\0` + versão + datalink), depois
    registros big-endian de 24 bytes de cabeçalho + payload. Para o datalink
    2001 (o "monitor" do BlueZ) o campo `flags` é `(índice << 16) | opcode`.

    Este parser NÃO usa o opcode para decidir sentido — ele o ignora de
    propósito e lê o `0xA1`/`0xA2` do próprio HID. O opcode entraria como uma
    lembrança minha sobre um formato; o byte do HID é o protocolo.
    """
    queixas: list[str] = []
    with open(caminho, "rb") as arq:
        dados = arq.read()

    if len(dados) < 16 or not dados.startswith(b"btsnoop\x00"):
        return [], ["arquivo não começa com a assinatura `btsnoop\\0`"]

    datalink = struct.unpack_from(">I", dados, 12)[0]
    if datalink != 2001:
        queixas.append(f"datalink {datalink} não é 2001 (monitor do BlueZ)")

    quadros: list[Quadro] = []
    pos, incompletos, fragmentos = 16, 0, 0
    while pos + 24 <= len(dados):
        _orig, incl, _flags, _drops, ts = struct.unpack_from(">IIIIq", dados, pos)
        pos += 24
        if pos + incl > len(dados):
            incompletos += 1
            break
        pacote = dados[pos : pos + incl]
        pos += incl

        # Um pacote ACL tem, no mínimo, 4 bytes de cabeçalho + 4 de L2CAP.
        if len(pacote) < 9:
            continue
        hf, dlen = struct.unpack_from("<HH", pacote, 0)
        handle, pb = hf & 0x0FFF, (hf >> 12) & 0x03
        if dlen != len(pacote) - 4:
            # Não é ACL (é comando, evento, nota de sistema...). Silencioso: o
            # monitor multiplexa tudo no mesmo arquivo, e a maioria não é ACL.
            continue
        if pb == 0x01:
            # Continuação de um L2CAP fragmentado. O `0x31` tem 79 bytes com o
            # cabeçalho HID e nunca fragmenta num ACL de MTU normal; se
            # aparecer, é para sair na queixa e não em silêncio.
            fragmentos += 1
            continue
        l2_len, _cid = struct.unpack_from("<HH", pacote, 4)
        corpo = pacote[8 : 8 + l2_len]
        if not corpo:
            continue
        # O `ts` do btsnoop é microssegundo desde uma época que NÃO é a do
        # Unix, e o deslocamento é uma constante mágica do BlueZ. Este parser
        # se recusa a depender de uma constante que eu teria de lembrar: ele
        # guarda o carimbo CRU e, mais adiante, normaliza pelo primeiro
        # quadro. O veredito não usa tempo nenhum — usa a cor mágica.
        quadros.append(Quadro(ts / 1e6, handle, corpo[0], corpo))

    if incompletos:
        queixas.append(f"{incompletos} registro(s) truncado(s) no fim do arquivo")
    if fragmentos:
        queixas.append(f"{fragmentos} continuação(ões) L2CAP ignorada(s)")
    return quadros, queixas


def reports_de_saida(quadros: list[Quadro]) -> list[Quadro]:
    """Só o que é output report `0x31` do DualSense, no sentido host->device."""
    return [
        q
        for q in quadros
        if q.sentido == HID_BT_SAIDA
        and len(q.corpo) >= 2
        and q.corpo[1] == DS_OUTPUT_BT_ID
    ]


def crc_confere(report: bytes) -> bool | None:
    """O CRC-32 dos quatro últimos bytes bate? `None` se o tamanho não permite.

    `crc32_le(0xFFFFFFFF, &seed, 1)` seguido de `~crc32_le(crc, data, len-4)`,
    que é exatamente o `zlib.crc32` do Python com a semente encadeada.
    """
    if len(report) != DS_OUTPUT_BT_TAM:
        return None
    calc = zlib.crc32(bytes([CRC32_SEED_SAIDA]))
    calc = zlib.crc32(report[: DS_OUTPUT_BT_TAM - 4], calc)
    return struct.unpack_from("<I", report, OFF_CRC)[0] == calc


def descreve(report: bytes) -> list[str]:
    """Os campos que decidem a cor, de um report `0x31`, em texto de tabela."""
    def b(i: int) -> str:
        return f"0x{report[i]:02x}" if i < len(report) else "--"

    crc = crc_confere(report)
    return [
        b(OFF_SEQ_TAG),
        b(OFF_TAG),
        b(OFF_VALID_FLAG0),
        b(OFF_VALID_FLAG1),
        b(OFF_VALID_FLAG2),
        b(OFF_LIGHTBAR_SETUP),
        b(OFF_LED_BRIGHTNESS),
        f"{b(OFF_R)} {b(OFF_G)} {b(OFF_B)}",
        str(len(report)),
        {True: "ok", False: "RUIM", None: "?"}[crc],
    ]


def assinaturas_de_saida(quadros: list[Quadro]) -> list[tuple[int, int, bytes]]:
    """``(handle, quantos, report)`` de cada 0x31 de saída DISTINTO, na ordem.

    Distinto pelo que decide a barra — ``valid_flag1``, ``valid_flag2``,
    ``lightbar_setup`` e R/G/B —, e não pelo report inteiro, que muda o
    ``seq_tag`` e o CRC a cada quadro. É a pergunta da lightbar: *um report
    presente no braço sujo e ausente no limpo é o que apaga a barra.*
    """
    ordem: list[tuple[int, bytes]] = []
    contas: dict[tuple[int, bytes], int] = {}
    exemplar: dict[tuple[int, bytes], bytes] = {}
    for q in reports_de_saida(quadros):
        report = q.corpo[1:]
        chave = (q.handle, bytes(
            report[i] if i < len(report) else 0
            for i in (OFF_VALID_FLAG1, OFF_VALID_FLAG2, OFF_LIGHTBAR_SETUP,
                      OFF_R, OFF_G, OFF_B)
        ))
        if chave not in contas:
            ordem.append(chave)
            contas[chave] = 0
            exemplar[chave] = report
        contas[chave] += 1
    return [(h, contas[(h, a)], exemplar[(h, a)]) for h, a in ordem]


def texto_dos_reports_de_saida(caminho: str) -> str:
    """O que a lightbar grava como leitura de um braço: só os 0x31 de saída."""
    quadros, queixas = ler_btsnoop(caminho)
    assinaturas = assinaturas_de_saida(quadros)
    total = sum(n for _, n, _ in assinaturas)
    linhas = [f"    {total} report(s) 0x31 de saída, {len(assinaturas)} distinto(s)"]
    linhas.extend(f"    queixa do arquivo: {queixa}" for queixa in queixas)
    if not assinaturas:
        return "\n".join(linhas)
    cabecalho = ("handle", "quadros", "valid_flag1", "valid_flag2", "lightbar_setup", "R G B")
    larguras = [len(c) for c in cabecalho]

    def linha(valores: tuple[str, ...]) -> str:
        return "    " + "  ".join(v.ljust(w) for v, w in zip(valores, larguras, strict=True)).rstrip()

    linhas.append(linha(cabecalho))
    for handle, n, report in assinaturas:
        def b(i: int, rep: bytes = report) -> str:
            return f"{rep[i]:02x}" if i < len(rep) else "--"

        linhas.append(linha((
            str(handle), str(n), f"0x{b(OFF_VALID_FLAG1)}", f"0x{b(OFF_VALID_FLAG2)}",
            f"0x{b(OFF_LIGHTBAR_SETUP)}", f"{b(OFF_R)} {b(OFF_G)} {b(OFF_B)}",
        )))
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--reports-de-saida", metavar="CAPTURA", required=True,
                    help="imprime os 0x31 de saída distintos de uma captura do btmon -w")
    argumentos = ap.parse_args(argv)
    try:
        print(texto_dos_reports_de_saida(argumentos.reports_de_saida))
    except OSError as erro:
        print(f"    (captura ilegível: {erro})")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
