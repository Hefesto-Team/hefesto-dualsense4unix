#!/usr/bin/env python3
"""byte_no_fio.py — o byte SAI no fio? A escrita de cor, vista no ar, por MAC.

A PERGUNTA QUE ELE RESPONDE
----------------------------
*Quando alguém escreve em `multi_intensity`, o output report `0x31` chega a
sair pelo rádio para AQUELE controle — e, saindo, ele é igual ao que sai para
um controle são no mesmo instante?*

Ela existe por causa de um defeito perecível: em 15/08/2026 a casa teve, ao
vivo e ao mesmo tempo, um DualSense de rádio com a barra APAGADA que ignora as
escritas do kernel, e outro DualSense de rádio, também por rádio, que OBEDECE
ao mesmo comando. O `docs/data/mapa-controles.csv` registra o sintoma
("330 mil escritas ignoradas ao vivo") e registra também que *o que faz uma
conexão de rádio nascer travada continua SEM CAUSA ISOLADA* — porque ninguém
jamais comparou os bytes de um doente contra os de um são no mesmo instante.

Há exatamente três lugares onde o comando pode morrer, e este instrumento
existe para dizer em qual:

1. o kernel não monta nem envia para o doente (defeito do host);
2. o kernel envia igual para os dois, byte a byte (defeito do APARELHO);
3. o kernel envia DIFERENTE — `seq`, CRC, flags, tamanho (defeito nosso).

POR QUE `btmon`, E NÃO O `hidraw`
----------------------------------
O `hidraw` **não serve** para esta pergunta, e é importante dizer por quê antes
de alguém tentar: um `read()` em `/dev/hidrawN` devolve os relatórios de
ENTRADA. Os de saída que o kernel manda não voltam por ali. Ler o hidraw e não
ver a cor sair não prova nada — é o nó errado.

O `btmon` lê o socket `HCI_CHANNEL_MONITOR`, que é uma cópia de tudo que passa
entre o host e o controlador Bluetooth. É o último ponto do host antes do ar.
Se o quadro aparece ali com o `handle` daquele controle, o host fez a parte
dele; se não aparece, o comando morreu ANTES do ar.

O `btmon` é passivo: ele não fala com o adaptador, não abre conexão, não toca
em nenhum controle. Precisa de `CAP_NET_RAW`, e por isso este instrumento — e
só este trecho dele — roda `sudo -n btmon -w`.

A RÉGUA, DECLARADA
-------------------
**Um "byte no fio" = um pacote ACL, capturado no monitor HCI, cujo payload
L2CAP começa em `0xA2`** (HID-over-BT: `DATA` no sentido host->device) **e cujo
byte seguinte é `0x31`** (o output report do DualSense por rádio).

O sentido NÃO é lido do opcode do btsnoop — é lido do CONTEÚDO, do byte `0xA2`,
que só existe no sentido host->device. Isso é de propósito: o opcode é memória
minha sobre um formato, e o `0xA2` é o protocolo. A casa já pagou por um parser
de `btmon` que, em 12/08/2026, não venceu o formato.

O `handle` do ACL vira MAC pela tabela do kernel: cada conexão ACL é um device
`hciN:<handle>` em `/sys/class/bluetooth`, com o `address` ao lado. Onde essa
leitura não responder, o `hcitool con` (DEPRECIADO pelo BlueZ) é o plano B. O
mapa handle->MAC sai IMPRESSO no relatório, com a RÉGUA de onde saiu: sem ele,
dizer "o branco não recebeu" seria uma afirmação sem sujeito.

A MORDIDA (é isto que autoriza acreditar no número)
----------------------------------------------------
Este instrumento **não** acredita em si mesmo. Ele escreve, em cada controle,
uma cor MÁGICA — três bytes escolhidos a dedo, que ninguém mais na mesa usa — e
depois EXIGE reencontrar esses três bytes exatos, nos offsets 47/48/49 do
report `0x31` (`lightbar_red/green/blue`, conferidos em
`docs/protocol/driver-hid-playstation.md` §"off. abs. BT"), no `handle` daquele
controle.

Se a cor mágica do controle SÃO não for reencontrada, o instrumento se declara
QUEBRADO e não emite veredito: um parser que não acha o que ele mesmo acabou de
escrever não tem autoridade para dizer que o outro controle não recebeu nada. A
ausência só é evidência depois que a presença foi demonstrada no mesmo arquivo.

ELE ESCREVE — E SÓ NO SYSFS
----------------------------
Ele escreve em `/sys/class/leds/<inputN>:rgb:indicator/multi_intensity`, que é
exatamente o que o produto já faz o tempo todo. **Nenhum output report cru é
montado ou enviado por este arquivo** — quem monta o `0x31` é o kernel, e é
justamente o kernel que está sob observação. No fim ele devolve a cor anterior
de cada controle, lida antes de começar.

Ele **NÃO** desliga, reinicia nem faz power-off de controle nenhum: o power-off
CURA o defeito e destrói a evidência. Ele também não mexe em unit nenhuma.

O SEGUNDO OBSERVADOR (`--kprobe`)
----------------------------------
Opcional e independente do ar: um kprobe em `dualsense_send_output_report` do
`hid_playstation`, que conta quantas vezes o driver montou um report, por
JANELA DE TEMPO. Ele não sabe dizer para QUAL controle (o kprobe não carrega a
identidade do `hid_device`), então só serve para uma coisa — e é uma coisa que
importa: se o btmon vir zero quadros para um controle mas o kprobe contar
chamadas na janela em que só ele foi escrito, o comando morreu ENTRE o driver e
o ar. Sem isso, "não saiu" e "não foi montado" ficariam indistinguíveis.

USO
    sudo -v && .venv/bin/python scripts/ensaios/byte_no_fio.py
    .venv/bin/python scripts/ensaios/byte_no_fio.py --kprobe
    .venv/bin/python scripts/ensaios/byte_no_fio.py --bruto docs/data/ensaios-brutos/
"""

from __future__ import annotations

import argparse
import os
import re
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from comum import (
    RADIO,
    Aparelho,
    cabecalho_do_instrumento,
    descobrir_aparelhos,
    ler_texto,
    resumo,
    tabela,
)

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

#: As cores mágicas. Escolhidas para não colidir com nada que o produto use
#: (o Hefesto trabalha com cores de jogador, e nenhuma delas é um degradê de
#: nibble repetido) e para serem reconhecíveis a olho num despejo hexadecimal.
MAGICA_A = (0x11, 0x22, 0x33)
MAGICA_B = (0x44, 0x55, 0x66)
MAGICA_C = (0x77, 0x88, 0x99)
MAGICA_D = (0xAA, 0xBB, 0xCC)

_RE_MAC = re.compile(r"\b([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})\b")


def mascarar(texto: str) -> str:
    """A máscara da casa: octetos 4 e 5 zerados. Nada de MAC real em arquivo."""

    def _troca(m: re.Match[str]) -> str:
        p = m.group(1).split(":")
        return ":".join([p[0], p[1], p[2], "00", "00", p[5]])

    return _RE_MAC.sub(_troca, texto)


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


# ---------------------------------------------------------------------------
# A mesa: quem é quem, e qual handle é de quem
# ---------------------------------------------------------------------------


def _handles_do_sysfs(raiz: str = "/sys/class/bluetooth") -> dict[str, int]:
    """MAC -> handle ACL lido do sysfs: cada conexão vira `hciN:<handle>`.

    MIGRACAO-BLUEZ-DEPRECIADOS-01 (19/08/2026). O `hcitool` foi DEPRECIADO pela
    upstream do BlueZ e cada família de distro o mudou de pacote
    (`bluez-deprecated`, `bluez-deprecated-tools`). Onde ele não existe, este
    instrumento voltava um mapa VAZIO e o relatório saía com "SEM HANDLE" em
    todo mundo — sem dizer por quê.

    A fonte viva é o próprio kernel: o `hci_conn` registra um device
    `hciN:<handle>` (handle em decimal) sob /sys/class/bluetooth, com os
    atributos `address` e `type`. Nada de root, nada de pacote.

    NÃO CONFERIDO AO VIVO: em 19/08/2026 esta bancada não tinha adaptador BT
    ligado (`/sys/class/bluetooth` vazio), então a forma exata dos nomes e
    atributos veio do fonte do kernel, não de medição aqui. Por isso o
    `hcitool` continua como plano B e o relatório DECLARA de qual régua o mapa
    saiu — se a leitura do sysfs estiver errada, isso aparece impresso em vez
    de contaminar o veredito em silêncio.
    """
    mapa: dict[str, int] = {}
    try:
        nomes = os.listdir(raiz)
    except OSError:
        return mapa
    for nome in nomes:
        m = re.fullmatch(r"hci\d+:(\d+)", nome)
        if not m:
            continue
        try:
            with open(os.path.join(raiz, nome, "address"), encoding="utf-8") as fh:
                mac = fh.read().strip().lower()
        except OSError:
            continue
        if re.fullmatch(r"([0-9a-f]{2}:){5}[0-9a-f]{2}", mac):
            mapa[mac] = int(m.group(1))
    return mapa


def _handles_do_hcitool() -> dict[str, int]:
    """Plano B: o `hcitool con` depreciado, para não perder leitura em quem o tem."""
    try:
        saida = subprocess.run(
            ["sudo", "-n", "hcitool", "con"],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    mapa: dict[str, int] = {}
    for linha in saida.splitlines():
        m = re.search(r"([0-9A-Fa-f:]{17})\s+handle\s+(\d+)", linha)
        if m:
            mapa[m.group(1).lower()] = int(m.group(2))
    return mapa


def handles_por_mac() -> tuple[dict[str, int], str]:
    """O mapa MAC -> handle ACL, e a RÉGUA de onde ele saiu.

    Ferramenta viva primeiro (sysfs do kernel), depreciada como plano B. A régua
    volta junto porque este instrumento declara a régua — regra desta casa
    desde que uma medição contra a biblioteca errada produziu alarme
    convincente e falso.
    """
    mapa = _handles_do_sysfs()
    if mapa:
        return mapa, "sysfs /sys/class/bluetooth"
    mapa = _handles_do_hcitool()
    if mapa:
        return mapa, "hcitool con (depreciado)"
    return {}, "NENHUMA — nem sysfs nem hcitool responderam"


def led_do_aparelho(ap: Aparelho) -> str:
    """O diretório `<inputN>:rgb:indicator` deste hidraw, ou "" se não houver.

    Vai pelo `dir_device` do hid, que é o pai comum do `hidraw` e do `leds/` —
    e não por adivinhação de número de input, que já trocou de controle nesta
    casa quando um deles reconectou.
    """
    dir_leds = os.path.join(ap.dir_device, "leds")
    if not os.path.isdir(dir_leds):
        return ""
    for nome in sorted(os.listdir(dir_leds)):
        if nome.endswith(":rgb:indicator"):
            return os.path.join(dir_leds, nome)
    return ""


def cor_atual(dir_led: str) -> str:
    return ler_texto(os.path.join(dir_led, "multi_intensity")).strip()


def escrever_cor(dir_led: str, rgb: tuple[int, int, int]) -> str:
    """Escreve no sysfs. Devolve "" se deu certo, ou a queixa do sistema.

    Isto é uma escrita no SYSFS, não no aparelho: quem monta o `0x31` é o
    kernel. É a única forma de provocar a escrita para observá-la, e é
    literalmente o que o produto faz o tempo todo.
    """
    alvo = os.path.join(dir_led, "multi_intensity")
    texto = f"{rgb[0]} {rgb[1]} {rgb[2]}"
    try:
        with open(alvo, "w", encoding="ascii") as arq:
            arq.write(texto)
        return ""
    except OSError as erro:
        return str(erro)


# ---------------------------------------------------------------------------
# O segundo observador: o kprobe
# ---------------------------------------------------------------------------

TRACEFS = "/sys/kernel/tracing"
SIMBOLO_KPROBE = "dualsense_send_output_report.isra.0"


def _sudo_sh(comando: str, *, checar: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sudo", "-n", "sh", "-c", comando],
        capture_output=True,
        text=True,
        check=checar,
        timeout=20,
    )


def kprobe_armar() -> str:
    """Arma o kprobe. Devolve "" se armou, ou a razão de não ter armado."""
    simbolo = SIMBOLO_KPROBE
    if simbolo not in ler_kallsyms():
        simbolo = "dualsense_send_output_report"
    r = _sudo_sh(
        f"echo 'p:hefesto_dsout {simbolo}' > {TRACEFS}/kprobe_events && "
        f"echo 1 > {TRACEFS}/events/kprobes/hefesto_dsout/enable"
    )
    if r.returncode != 0:
        return (r.stderr or r.stdout).strip() or f"falha ao armar em `{simbolo}`"
    return ""


def ler_kallsyms() -> str:
    return _sudo_sh("cat /proc/kallsyms").stdout


def kprobe_contador() -> int:
    """Quantas linhas do kprobe estão no buffer AGORA.

    É contagem de buffer, não contador de hardware: se o buffer der a volta, o
    número mente para MENOS. Por isso ele é zerado a cada janela e as janelas
    são curtas — e por isso ele é o SEGUNDO observador, não o primeiro.
    """
    texto = _sudo_sh(f"grep -c hefesto_dsout {TRACEFS}/trace").stdout.strip()
    return int(texto) if texto.isdigit() else 0


def kprobe_zerar() -> None:
    _sudo_sh(f"echo > {TRACEFS}/trace")


def kprobe_desarmar() -> None:
    _sudo_sh(
        f"echo 0 > {TRACEFS}/events/kprobes/hefesto_dsout/enable; "
        f"echo '-:hefesto_dsout' >> {TRACEFS}/kprobe_events; "
        f"echo > {TRACEFS}/trace"
    )


# ---------------------------------------------------------------------------
# O ensaio
# ---------------------------------------------------------------------------


class Alvo:
    def __init__(self, ap: Aparelho, dir_led: str) -> None:
        self.ap = ap
        self.dir_led = dir_led
        self.cor_antes = cor_atual(dir_led)
        self.handle = -1
        self.magicas: list[tuple[int, int, int]] = []


def fatia(quadros: list[Quadro], t0: float, t1: float) -> list[Quadro]:
    return [q for q in quadros if t0 <= q.ts <= t1]


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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--segundos", type=float, default=1.2,
                    help="quanto tempo cada janela de escrita dura (padrão 1,2 s)")
    ap.add_argument("--kprobe", action="store_true",
                    help="arma o segundo observador, no kernel (precisa de sudo)")
    ap.add_argument("--bruto", default="",
                    help="diretório onde gravar o relatório bruto, com MAC mascarado")
    ap.add_argument("--mesma-cor", action="store_true",
                    help="o teste GÊMEO: a MESMA cor mágica nos dois, ao mesmo tempo. "
                         "É o que permite dizer 'os bytes são iguais' sem ressalva — "
                         "com cores diferentes, R/G/B diferem por desenho e a frase "
                         "ficaria mais fraca do que a medida permite.")
    args = ap.parse_args()

    print(
        cabecalho_do_instrumento(
            "byte_no_fio.py",
            "o output report 0x31 da cor SAI no ar para cada controle de rádio?",
            bibliotecas=["struct", "zlib"],
            escreve_no_aparelho=False,
        )
    )
    print("  ESCRITA ......... só no sysfs (`multi_intensity`), como o produto faz.")
    print("  NÃO faz .......... power-off, reconexão, restart de unit, report cru.")
    print("  privilégio ....... `sudo -n btmon -w` (passivo, CAP_NET_RAW)")
    print("=" * 78)

    aparelhos = [a for a in descobrir_aparelhos() if a.transporte == RADIO and not a.e_vpad]
    if len(aparelhos) < 1:
        print("\nNão há DualSense por rádio nesta mesa. Nada a medir.")
        return 2

    mapa, regua_do_mapa = handles_por_mac()
    alvos: list[Alvo] = []
    for a in aparelhos:
        dir_led = led_do_aparelho(a)
        if not dir_led:
            print(f"  !! {mascarar(a.apelido)} não tem `:rgb:indicator` no sysfs — fora")
            continue
        alvo = Alvo(a, dir_led)
        alvo.handle = mapa.get(a.mac.lower(), -1)
        alvos.append(alvo)

    print(f"\nA MESA DE RÁDIO, E O MAPA handle -> MAC (régua: {regua_do_mapa})")
    print(tabela(
        ["MAC", "hidraw", "handle ACL", "LED do sysfs", "cor agora"],
        [[mascarar(a.ap.mac), a.ap.hidraw, str(a.handle) if a.handle >= 0 else "SEM HANDLE",
          os.path.basename(a.dir_led), a.cor_antes] for a in alvos],
    ))
    if any(a.handle < 0 for a in alvos):
        print("\n  !! Sem handle não dá para atribuir quadro a controle. Veredito parcial.")

    # ---- captura ----------------------------------------------------------
    fd_tmp, caminho_captura = tempfile.mkstemp(prefix="byte-no-fio-", suffix=".btsnoop")
    os.close(fd_tmp)
    # O `btmon` roda como root e recria o arquivo; ele não sobrescreve um que
    # já exista com dono diferente. A captura NÃO é versionada: tem MAC real.
    _sudo_sh(f"rm -f {caminho_captura}")
    kprobe_erro = "não pedido"
    if args.kprobe:
        kprobe_erro = kprobe_armar()
        if not kprobe_erro:
            kprobe_zerar()

    captura = subprocess.Popen(
        ["sudo", "-n", "btmon", "-w", caminho_captura],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.0)  # o btmon precisa abrir o socket antes de a gente escrever

    janelas: list[tuple[str, Alvo, tuple[int, int, int], float, float, int]] = []
    magicas = [MAGICA_A, MAGICA_B, MAGICA_C, MAGICA_D]
    print("\nESCREVENDO (só sysfs), uma janela por controle, uma cor mágica por janela")
    for rodada in (0, 1):
        for i, alvo in enumerate(alvos):
            if args.mesma_cor:
                # No teste gêmeo a cor varia por RODADA, nunca por controle: os
                # dois recebem exatamente o mesmo valor na mesma janela.
                cor = magicas[rodada % len(magicas)]
            else:
                cor = magicas[(rodada * len(alvos) + i) % len(magicas)]
            if args.kprobe and not kprobe_erro:
                kprobe_zerar()
            k0 = 0
            t0 = time.time()
            # A escrita INSISTE durante a janela inteira. Não é redundância: o
            # daemon do Hefesto escreve cor nestes mesmos LEDs o tempo todo, e
            # uma escrita única pode ser sobrescrita antes de o `output_worker`
            # do driver rodar. Insistir garante que a cor mágica teve chance
            # real de sair — e se mesmo assim não sair, o silêncio é do rádio,
            # não da corrida com o daemon.
            erro = ""
            while time.time() - t0 < args.segundos:
                erro = escrever_cor(alvo.dir_led, cor) or erro
                time.sleep(0.05)
            t1 = time.time()
            k1 = kprobe_contador() if args.kprobe and not kprobe_erro else 0
            alvo.magicas.append(cor)
            janelas.append((
                f"r{rodada + 1}", alvo, cor, t0, t1, k1 - k0,
            ))
            print(f"  {mascarar(alvo.ap.mac)}  <- {cor[0]:3d} {cor[1]:3d} {cor[2]:3d}"
                  f"   ({'ok' if not erro else 'ERRO: ' + erro})")

    time.sleep(0.4)
    captura.terminate()
    try:
        captura.wait(timeout=5)
    except subprocess.TimeoutExpired:
        captura.kill()
    _sudo_sh(f"chmod 0644 {caminho_captura}")

    # ---- devolver a cor de antes -----------------------------------------
    print("\nDEVOLVENDO a cor que cada um tinha antes")
    for alvo in alvos:
        partes = alvo.cor_antes.split()
        if len(partes) == 3 and all(p.isdigit() for p in partes):
            escrever_cor(alvo.dir_led, (int(partes[0]), int(partes[1]), int(partes[2])))
            print(f"  {mascarar(alvo.ap.mac)}  <- {alvo.cor_antes}")

    if args.kprobe and not kprobe_erro:
        kprobe_desarmar()

    # ---- leitura ----------------------------------------------------------
    quadros, queixas = ler_btsnoop(caminho_captura)
    saidas = reports_de_saida(quadros)
    entradas = [q for q in quadros if q.sentido == HID_BT_ENTRADA]

    linhas_saida: list[str] = []
    linhas_saida.append("\nO QUE A CAPTURA VIU (arquivo do `btmon -w`, lido por parser próprio)")
    linhas_saida.append(f"  quadros ACL com payload L2CAP ...... {len(quadros)}")
    linhas_saida.append(f"  DATA host->device (0xA2) ........... "
                        f"{sum(1 for q in quadros if q.sentido == HID_BT_SAIDA)}")
    linhas_saida.append(f"  ... destes, output report 0x31 ..... {len(saidas)}")
    linhas_saida.append(f"  DATA device->host (0xA1) ........... {len(entradas)}")
    for q in queixas:
        linhas_saida.append(f"  queixa do parser ................... {q}")
    if args.kprobe:
        linhas_saida.append(f"  kprobe ............................. "
                            f"{kprobe_erro or 'armado em ' + SIMBOLO_KPROBE}")

    por_handle: dict[int, list[Quadro]] = {}
    for q in saidas:
        por_handle.setdefault(q.handle, []).append(q)
    linhas_saida.append("\nOUTPUT REPORTS 0x31 POR HANDLE, NA CAPTURA INTEIRA")
    linhas_saida.append(tabela(
        ["handle", "de quem", "quadros 0x31"],
        [[str(h),
          mascarar(next((mascarar(a.ap.mac) for a in alvos if a.handle == h), f"handle {h}")),
          str(len(v))]
         for h, v in sorted(por_handle.items())]
        + [[str(a.handle), mascarar(a.ap.mac), "0"] for a in alvos
           if a.handle not in por_handle],
    ))

    # ---- a mordida: reencontrar a cor mágica ------------------------------
    linhas_saida.append("\nA MORDIDA — a cor mágica que EU escrevi aparece no ar, "
                        "nos offsets 47/48/49?")
    achados: list[list[str]] = []
    mordeu: dict[str, bool] = {}
    exemplares: dict[str, bytes] = {}
    for rot, alvo, cor, _t0, _t1, dk in janelas:
        # De propósito, a busca é na CAPTURA INTEIRA e não na janela de tempo:
        # a cor mágica é única por janela, então ela mesma é o marcador. Assim
        # o veredito não depende de eu ter acertado a época do btsnoop.
        na_janela = [q for q in saidas if q.handle == alvo.handle]
        casados = [q for q in na_janela
                   if len(q.corpo) > OFF_B + 1
                   and (q.corpo[1 + OFF_R], q.corpo[1 + OFF_G], q.corpo[1 + OFF_B]) == cor]
        chave = alvo.ap.mac
        mordeu[chave] = mordeu.get(chave, False) or bool(casados)
        if casados and chave not in exemplares:
            exemplares[chave] = casados[0].corpo[1:]
        achados.append([
            rot, mascarar(alvo.ap.mac), str(alvo.handle),
            f"{cor[0]:02x} {cor[1]:02x} {cor[2]:02x}",
            str(len(na_janela)), str(len(casados)),
            str(dk) if args.kprobe and not kprobe_erro else "-",
        ])
    linhas_saida.append(tabela(
        ["rodada", "MAC", "handle", "cor mágica (hex)", "0x31 no handle",
         "com a cor mágica", "kprobe"],
        achados,
    ))

    # ---- os bytes, lado a lado -------------------------------------------
    if exemplares:
        linhas_saida.append("\nOS BYTES — um exemplar do 0x31 de cada controle "
                            "que a cor mágica identificou")
        linhas_saida.append(tabela(
            ["MAC", "seq_tag", "tag", "vflag0", "vflag1", "vflag2",
             "lb_setup", "brilho", "R G B", "tam", "CRC"],
            [[mascarar(mac), *descreve(rep)] for mac, rep in sorted(exemplares.items())],
        ))
        for mac, rep in sorted(exemplares.items()):
            linhas_saida.append(f"\n  {mascarar(mac)}  0x31 inteiro, {len(rep)} bytes:")
            for i in range(0, len(rep), 16):
                linhas_saida.append(f"    {i:3d}: " + " ".join(f"{c:02x}" for c in rep[i:i + 16]))

    # ---- o diff byte a byte ----------------------------------------------
    if len(exemplares) == 2:
        (mac_a, rep_a), (mac_b, rep_b) = sorted(exemplares.items())
        difs = [i for i in range(min(len(rep_a), len(rep_b))) if rep_a[i] != rep_b[i]]
        linhas_saida.append(
            f"\nO DIFF BYTE A BYTE — {mascarar(mac_a)} contra {mascarar(mac_b)}")
        linhas_saida.append(f"  tamanhos: {len(rep_a)} e {len(rep_b)}")
        if not difs:
            linhas_saida.append("  os 78 bytes são IDÊNTICOS. Nenhuma diferença.")
        else:
            linhas_saida.append(tabela(
                ["offset", "campo", mascarar(mac_a), mascarar(mac_b)],
                [[str(i),
                  NOME_DO_OFFSET.get(i, "crc32" if i >= OFF_CRC else "reservado"),
                  f"0x{rep_a[i]:02x}", f"0x{rep_b[i]:02x}"] for i in difs],
            ))

    # ---- veredito ---------------------------------------------------------
    sao = [a for a in alvos if mordeu.get(a.ap.mac)]
    mudo = [a for a in alvos if not mordeu.get(a.ap.mac)]
    if not sao:
        veredito = (
            "INSTRUMENTO QUEBRADO — não reencontrei a cor mágica de NENHUM controle. "
            "Sem demonstrar a presença, a ausência não é evidência. Sem veredito."
        )
    elif not mudo:
        veredito = (
            f"O BYTE SAI NO FIO PARA TODOS OS {len(alvos)}. Nenhum comando morreu no host: "
            "compare os bytes acima — se forem iguais, o réu é o aparelho."
        )
    else:
        quem = ", ".join(mascarar(a.ap.mac) for a in mudo)
        veredito = (
            f"O BYTE NÃO SAI NO FIO para {quem}, e SAI para "
            f"{', '.join(mascarar(a.ap.mac) for a in sao)} na mesma captura. "
            "O comando morre NO HOST, antes do ar."
        )

    texto = "\n".join(linhas_saida)
    print(texto)
    print(resumo(veredito))

    if args.bruto:
        os.makedirs(args.bruto, exist_ok=True)
        carimbo = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        destino = os.path.join(args.bruto, f"{carimbo}-byte-no-fio.txt")
        with open(destino, "w", encoding="utf-8") as arq:
            arq.write(mascarar(texto) + "\n\nRESUMO: " + mascarar(veredito) + "\n")
        print(f"bruto: {destino}")
    print(f"captura: {caminho_captura}  (NÃO versionar: contém MAC real)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
