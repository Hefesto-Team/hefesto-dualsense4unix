#!/usr/bin/env python3
"""cor_do_plastico.py — de que cor é o plástico deste controle, perguntado a ELE.

A PERGUNTA
----------
A D-15 foi respondida por ela em 15/08/2026: *a cor física é a cor do
PLÁSTICO, lida do aparelho, por cabo E por rádio*. E a D-16: *a cor mora no
APARELHO* — sem arquivo por endereço, sem ela escolher numa lista.

O serial de fábrica de 17 caracteres carrega a cor nos caracteres 5 e 6. Ele
não está em report nenhum de graça: é preciso PEDIR, e pedir é escrever.

O QUE ESTE INSTRUMENTO TEM DE DIFERENTE DE TODOS OS OUTROS DESTA PASTA
----------------------------------------------------------------------
Os outros não escrevem no aparelho. **Este escreve.** É o único, e por isso
ele carrega o dobro de trava.

`SET_FEATURE 0x80` é a família de comandos de FÁBRICA do DualSense. Na mesma
família, mudando DOIS bytes do payload:

    [1, 1]      RESETA o controle
    [3, 2, ...] destrava a NVS
    [12, 1, ...] GRAVA calibração de stick na memória NÃO-VOLÁTIL

O nosso `[1, 19]` é leitura pura — ele pede um bloco de informação de sistema e
o firmware responde no `0x81`. Mas um byte errado no payload escreve onde não
devia, **e não há desfazer**. Ela tem quatro controles e nenhum deles é
reposição.

As travas, todas exercidas em código e não em recomendação:

1. O payload é montado UMA VEZ, por uma função sem parâmetro
   (`montar_payload`), e conferido byte a byte por outra (`conferir_payload`)
   imediatamente antes de sair. Byte fora do lugar levanta e o programa morre
   sem tocar no aparelho.
2. O payload é IMPRESSO em hexadecimal antes de qualquer escrita, sempre —
   inclusive na rodada seca.
3. A rodada é SECA por omissão. Sem `--escrever` nada sai no fio: o
   instrumento mostra o comando exato e para. Escrever é decisão explícita de
   quem roda.
4. UM alvo por execução, obrigatoriamente (`--alvo hidrawN`). Não existe modo
   "todos": a disciplina de um de cada vez é estrutural, não é lembrete.
5. A família `0xF0`-`0xF7` — por onde o firmware é atualizado — é recusada por
   uma trava própria, que nem sabe escrever. A D-32 dela foi explícita: *ler a
   família inteira, só leitura, NUNCA escrever*.
6. Antes e depois de cada escrita o instrumento PROVA que o controle continua
   são: o feature `0x20` sai igual byte a byte, o `hardware_version` do sysfs
   não mudou, e o aparelho continua entregando reports de entrada. A prova
   aparece na tela — não é uma frase minha, é uma medida.

A PROCEDÊNCIA DO PAYLOAD (é isto que autoriza a escrita)
--------------------------------------------------------
Conferido contra o fonte de `dualshock-tools.github.io`,
`js/controllers/ds5-controller.js`, em 15/08/2026, literalmente:

    async getSystemInfo(base, num, length, decode = true) {
      await this.sendFeatureReport(128, [base, num])
      const pcba_id = await this.receiveFeatureReport(129);
      if (pcba_id.getUint8(1) != base || pcba_id.getUint8(2) != num ||
          pcba_id.getUint8(3) != 2) { return l("error"); }
      ...
      return new TextDecoder().decode(pcba_id.buffer.slice(4, 4 + length));
    }

    // o serial: getSystemInfo(1, 19, 17)
    // a cor:    serialNumber.slice(4, 6)

`128` e `129` são `0x80` e `0x81`; `[base, num]` é `[1, 19]`, que em hexadecimal
é `01 13`. No WebHID o id do report NÃO entra no vetor de dados; no `hidraw`
ele é o byte 0 do buffer. Daí o nosso buffer começar em `80 01 13`.

O QUE ESTE INSTRUMENTO NÃO SABE FAZER, E DIZ
---------------------------------------------
Por rádio, ninguém demonstrou. O canal existe (o `0x80`/`0x81` está no
descritor destes controles, conferido pelo parser de `comum.py`), e o envelope
de Bluetooth desta casa já é conhecido — CRC-32 de semente `0xA3` nos quatro
últimos bytes, `ps_check_crc32` do `hid-playstation`. O caminho está escrito
aqui (`envelope_de_radio`), atrás de `--radio-a-serio`, e **não foi exercido**:
está marcado como DESENHO, não como medida, e a tela diz isso.
"""

from __future__ import annotations

import argparse
import array
import errno
import fcntl
import os
import select
import sys
import time
import zlib
from dataclasses import dataclass, field

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)

from comum import (  # noqa: E402
    RADIO,
    Aparelho,
    PortaFechadaError,
    abrir_no_hidraw,
    cabecalho_do_instrumento,
    censo_da_mesa,
    descobrir_aparelhos,
    diagnostico_de_acesso,
    fisicos,
    ler_texto,
    resumo,
    tabela,
    tamanhos_do_descritor,
)

# ---------------------------------------------------------------------------
# Os números, todos com procedência, nenhum chutado
# ---------------------------------------------------------------------------

#: O comando de fábrica (escrita) e a resposta (leitura). `dualshock-tools`,
#: `ds5-controller.js`: `sendFeatureReport(128, ...)` / `receiveFeatureReport(129)`.
FEATURE_COMANDO = 0x80
FEATURE_RESPOSTA = 0x81

#: A âncora de sanidade: informação de firmware, constante por unidade. Lida
#: antes e depois de toda escrita, e comparada byte a byte.
FEATURE_FIRMWARE = 0x20

#: O par que pede o serial de fábrica. É O ÚNICO par que este arquivo conhece,
#: e a trava de `conferir_payload` existe para que continue sendo.
BASE_DO_SERIAL = 1
NUM_DO_SERIAL = 19

#: 17 caracteres ASCII, o mesmo serial impresso na traseira do controle.
TAMANHO_DO_SERIAL = 17

#: Onde a cor mora dentro dele: caracteres 5 e 6 (base zero: 4 e 5).
FATIA_DA_COR = slice(4, 6)

#: O byte que o firmware devolve em `buf[3]` quando a resposta é boa.
MARCA_DE_RESPOSTA_BOA = 2

#: A família por onde o FIRMWARE é atualizado. Decisão dela na D-32: ler tudo,
#: nunca escrever. Aqui ela nem chega perto de uma escrita — há trava.
FAMILIA_DO_FIRMWARE = range(0xF0, 0xF8)

#: Os pares da MESMA família `0x80` que destroem o controle. Não estão aqui
#: para serem usados: estão para que a trava tenha o que reconhecer, e para
#: que quem ler este arquivo veja o tamanho do precipício ao lado da trilha.
PARES_QUE_DESTROEM = {
    (1, 1): "RESETA o controle",
    (3, 2): "destrava a NVS para escrita",
    (12, 1): "GRAVA calibração de stick na memória não-volátil",
}

#: A tabela de cores. `dualshock-tools`, `ds5-controller.js`, confirmada pelo
#: mantenedor na issue #210; concorda com `nsfm/dualsense-ts` e com
#: `TechAntohere/Senshi`. Três fontes independentes.
CORES = {
    "00": "White",
    "01": "Midnight Black",
    "02": "Cosmic Red",
    "03": "Nova Pink",
    "04": "Galactic Purple",
    "05": "Starlight Blue",
    "06": "Grey Camouflage",
    "07": "Volcanic Red",
    "08": "Sterling Silver",
    "09": "Cobalt Blue",
    "10": "Chroma Teal",
    "11": "Chroma Indigo",
    "12": "Chroma Pearl",
    "30": "30th Anniversary",
    "Z1": "God of War Ragnarok",
    "Z2": "Spider-Man 2",
    "Z3": "Astro Bot",
    "Z4": "Fortnite",
    "Z6": "The Last of Us",
    "ZA": "God of War 20th Anniversary",
    "ZB": "Icon Blue Limited Edition",
}

#: Semente do CRC-32 dos feature reports por Bluetooth. `PS_FEATURE_CRC32_SEED`
#: do `hid-playstation`, e `core/ds_output_report.py::BT_FEATURE_CRC_SEED`.
#: Escrita aqui, e não importada, para que este instrumento rode num checkout
#: sem o pacote instalado.
SEMENTE_FEATURE_BT = 0xA3


def conferir_a_semente() -> str:
    """A semente daqui é a MESMA do pacote? Confere, e diz de onde.

    Duas cópias do mesmo número são duas réguas, e esta casa já pagou três
    vezes por medir contra a régua errada. A cópia existe por um motivo bom
    (rodar sem o pacote instalado), então o preço dela é este confronto — que
    roda antes de o número ser usado, e não numa suíte que ninguém executou.
    """
    try:
        from hefesto_dualsense4unix.core.ds_output_report import BT_FEATURE_CRC_SEED
    except ImportError as erro:
        return f"NÃO CONFERIDA — o pacote não é importável ({erro})"
    if BT_FEATURE_CRC_SEED != SEMENTE_FEATURE_BT:
        raise SystemExit(
            f"ERRO: a semente daqui (0x{SEMENTE_FEATURE_BT:02x}) diverge da do "
            f"pacote (0x{BT_FEATURE_CRC_SEED:02x}). Uma das duas está velha, e "
            "medir com a errada produz alarme convincente e falso."
        )
    return (
        f"0x{SEMENTE_FEATURE_BT:02x}, IGUAL à de "
        "core/ds_output_report.py::BT_FEATURE_CRC_SEED"
    )

# HIDIOCGFEATURE / HIDIOCSFEATURE: _IOC(WRITE|READ, 'H', 0x07/0x06, tamanho).
# Montados à mão, como em `censo_features.py`: nenhuma dependência nova, e o
# número mágico visível em vez de escondido atrás de uma biblioteca.
_IOC_ESCRITA_E_LEITURA = 3
_IOC_TIPO_HID = ord("H")
_IOC_NR_GETFEATURE = 0x07
_IOC_NR_SETFEATURE = 0x06

#: Quanto se espera por um report de entrada na prova de vida. O DualSense no
#: cabo emite a ~250 Hz; um segundo é folga de trinta vezes.
SEGUNDOS_DE_ESPERA = 1.0

#: Quantos reports de entrada bastam para dizer "está vivo". Três, e não um,
#: porque um report pode ser o que já estava no buffer do `hidraw`.
REPORTS_QUE_PROVAM_VIDA = 3


def _hidiocgfeature(tamanho: int) -> int:
    return (
        (_IOC_ESCRITA_E_LEITURA << 30)
        | (tamanho << 16)
        | (_IOC_TIPO_HID << 8)
        | _IOC_NR_GETFEATURE
    )


def _hidiocsfeature(tamanho: int) -> int:
    return (
        (_IOC_ESCRITA_E_LEITURA << 30)
        | (tamanho << 16)
        | (_IOC_TIPO_HID << 8)
        | _IOC_NR_SETFEATURE
    )


# ---------------------------------------------------------------------------
# A TRAVA. Tudo que escreve passa por aqui, e nada passa por aqui duas vezes
# ---------------------------------------------------------------------------


class PayloadRecusadoError(Exception):
    """O payload não é o que este arquivo autoriza. Nada foi ao aparelho."""


def montar_payload(tamanho: int) -> bytearray:
    """O ÚNICO payload que este instrumento sabe montar: `80 01 13 00 ... 00`.

    Sem parâmetro de propósito. Uma função que aceitasse `base` e `num` seria
    uma função que aceita `[1, 1]` — o reset — e a distância entre "aceita" e
    "recebeu por engano" é um dedo. Aqui não há como pedir outra coisa.

    O resto do buffer vai zerado até o tamanho que o DESCRITOR DO APARELHO
    declara para o `0x80` (64 bytes nestes quatro controles, conferido pelo
    parser de `comum.py`). Report de feature tem comprimento fixo no HID; um
    `SET_FEATURE` curto pode voltar em stall, e o caminho provado no navegador
    envia o report inteiro.
    """
    buffer = bytearray(tamanho)
    buffer[0] = FEATURE_COMANDO
    buffer[1] = BASE_DO_SERIAL
    buffer[2] = NUM_DO_SERIAL
    return buffer


def conferir_payload(buffer: bytes | bytearray) -> None:
    """Confere byte a byte, e levanta se qualquer um estiver fora do lugar.

    Chamada imediatamente antes do `ioctl`, nunca antes disso — entre a
    conferência e a escrita não pode caber linha nenhuma que toque no buffer.
    """
    if len(buffer) < 3:
        raise PayloadRecusadoError(f"payload curto demais: {len(buffer)} bytes")
    if buffer[0] != FEATURE_COMANDO:
        raise PayloadRecusadoError(
            f"byte 0 e 0x{buffer[0]:02x}, tinha de ser 0x{FEATURE_COMANDO:02x}"
        )
    if buffer[1] != BASE_DO_SERIAL:
        raise PayloadRecusadoError(
            f"byte 1 (base) é {buffer[1]}, tinha de ser {BASE_DO_SERIAL}"
        )
    if buffer[2] != NUM_DO_SERIAL:
        raise PayloadRecusadoError(
            f"byte 2 (num) é {buffer[2]}, tinha de ser {NUM_DO_SERIAL}"
        )
    if (buffer[1], buffer[2]) in PARES_QUE_DESTROEM:
        raise PayloadRecusadoError(
            f"o par ({buffer[1]}, {buffer[2]}) "
            f"{PARES_QUE_DESTROEM[(buffer[1], buffer[2])]}"
        )
    sujos = [i for i, b in enumerate(buffer[3:], start=3) if b]
    if sujos:
        raise PayloadRecusadoError(
            f"bytes que tinham de estar zerados vieram sujos: {sujos[:8]}"
        )


def recusar_familia_do_firmware(report_id: int) -> None:
    """Trava da D-32: nada da família `0xF0`-`0xF7` sai daqui, nunca.

    Não é uma trava contra engano meu — é contra engano de quem editar este
    arquivo depois. A família por onde o firmware é atualizado não pode virar
    alvo de escrita por uma linha distraída.
    """
    if report_id in FAMILIA_DO_FIRMWARE:
        raise PayloadRecusadoError(
            f"0x{report_id:02x} está na família do FIRMWARE (0xf0-0xf7). "
            "A decisão dela (D-32) é explícita: ler, nunca escrever."
        )


def sem_o_serial(dados: bytes | bytearray) -> bytes:
    """A resposta `0x81` com o número de série trocado por `#`, para o hex dump.

    O que o dump precisa mostrar é o ENQUADRAMENTO — `81 01 13 02` e então
    ASCII —, não o número da unidade dela. Mascarar aqui, e não só no texto
    decodificado, é o que impede o serial de vazar em hexadecimal num arquivo
    versionado: `4d 36 35 ...` é o serial tanto quanto `M65...`.
    """
    saida = bytearray(dados)
    inicio = 4 + CARACTERES_PUBLICOS_DO_SERIAL
    fim = 4 + TAMANHO_DO_SERIAL
    if len(saida) >= fim and saida[0] == FEATURE_RESPOSTA:
        saida[inicio:fim] = b"#" * (fim - inicio)
    return bytes(saida)


def em_hexadecimal(dados: bytes | bytearray, *, por_linha: int = 16) -> str:
    """O buffer em hexadecimal, para o olho conferir antes de o fio levar."""
    linhas = []
    for inicio in range(0, len(dados), por_linha):
        pedaco = dados[inicio : inicio + por_linha]
        linhas.append(f"    {inicio:04x}  " + " ".join(f"{b:02x}" for b in pedaco))
    return "\n".join(linhas)


def mascarar(mac: str) -> str:
    """`aa:bb:cc:dd:ee:ff` -> `aa:bb:cc:00:00:ff` — a máscara da casa.

    Octetos 4 e 5 zerados: preserva o fabricante e apaga o aparelho dela. Há
    portão que reprova MAC real em arquivo versionado, e a saída bruta deste
    ensaio É versionada.

    O exemplo acima é forjado de propósito. Ele já foi escrito com o endereço
    REAL de um dos controles da bancada — a docstring da função que mascara era,
    ela mesma, o vazamento, e passou verde porque o portão não conhecia aquele
    OUI (15/08/2026; ver a nota datada em `tests/unit/test_docs_mac_anonimato.py`).
    """
    partes = mac.split(":")
    if len(partes) != 6:
        return mac
    return ":".join([*partes[:3], "00", "00", partes[5]])


#: Quantos caracteres do serial sobrevivem no arquivo. Seis: os quatro de
#: modelo/planta, que são compartilhados por lote e não identificam unidade
#: nenhuma, MAIS os dois da cor, que são o objeto inteiro deste ensaio. Os onze
#: restantes são o número de série da unidade dela.
CARACTERES_PUBLICOS_DO_SERIAL = 6


def mascarar_serial(serial: str) -> str:
    """`AB1C05D1234567890` -> `AB1C05###########` — a mesma lógica da do MAC.

    O exemplo é forjado; os dois caracteres da cor (`05`) estão na posição real.
    Ele já foi escrito com o serial VERDADEIRO de um dos controles da bancada —
    a docstring da função que mascara serial era, ela mesma, o vazamento, e o
    `check_anonymity.sh` passava verde porque varre a forma de um MAC, não a de
    um serial (15/08/2026).

    O serial de fábrica identifica a unidade dela tão bem quanto o MAC, e a
    regra desta casa é sobre arquivo versionado, não sobre a palavra "MAC". A
    máscara preserva exatamente o que o ensaio quer provar — os caracteres 5 e
    6, onde a cor mora — e apaga o resto.

    Na TELA o serial sai inteiro (é dela, é a máquina dela). No ARQUIVO, nunca:
    é o mesmo desenho de `imu_no_cabo.py`, onde o CSV mascara sempre, mesmo com
    `--sem-mascara` pedido para a tela.
    """
    if len(serial) <= CARACTERES_PUBLICOS_DO_SERIAL:
        return serial
    resto = len(serial) - CARACTERES_PUBLICOS_DO_SERIAL
    return serial[:CARACTERES_PUBLICOS_DO_SERIAL] + "#" * resto


# ---------------------------------------------------------------------------
# A conversa com o aparelho
# ---------------------------------------------------------------------------


@dataclass
class Resposta:
    """O que voltou de um `GET_FEATURE` — com a falha como campo, não exceção."""

    report_id: int
    dados: bytes = b""
    erro: str = ""
    segundos: float = 0.0

    @property
    def ok(self) -> bool:
        return bool(self.dados) and not self.erro


@dataclass
class Prova:
    """A prova de que o controle continua são, medida e não afirmada."""

    firmware: bytes = b""
    hardware_version: str = ""
    reports_lidos: int = 0
    ids_vistos: dict[int, int] = field(default_factory=dict)
    lightbar: str = ""
    erro: str = ""

    @property
    def vivo(self) -> bool:
        return bool(self.firmware) and self.reports_lidos > 0


def estado_da_lightbar(aparelho: Aparelho) -> str:
    """`brightness` e `multi_intensity` da lightbar, lidos do sysfs — só leitura.

    Entrou aqui em 15/08/2026 por causa de OUTRA investigação: um dos controles
    de rádio está com a lightbar travada (apagada, ignorando escrita do
    kernel), e três frentes a medem ao vivo. Um ensaio que escreve na família
    de fábrica ao lado disso tem de poder dizer *"não fui eu"* — ou, se for,
    dizer que foi. Sem medida antes e depois, essa frase não teria valor
    nenhum.

    Nada aqui ESCREVE no LED, e nada aqui desliga controle: o power-off cura a
    lightbar travada e destruiria a evidência das outras frentes.
    """
    raiz = os.path.join(aparelho.dir_device, "leds")
    if not os.path.isdir(raiz):
        return "sem nó de led no sysfs"
    for entrada in sorted(os.listdir(raiz)):
        if not entrada.endswith(":rgb:indicator"):
            continue
        dono = os.path.join(raiz, entrada)
        brilho = ler_texto(os.path.join(dono, "brightness")).strip()
        cores = ler_texto(os.path.join(dono, "multi_intensity")).strip()
        return f"{entrada}: brightness={brilho or '?'} multi_intensity=[{cores or '?'}]"
    return "sem indicador rgb"


def pedir_feature(fd: int, report_id: int, tamanho: int, *, tentativas: int = 4) -> Resposta:
    """`GET_FEATURE` com validação de id e retry — leitura pura, sempre.

    A validação de id não é zelo: em 15/08/2026 esta casa mediu um pedido de
    `0x20` voltar com `0x80` no byte 0. Resposta TROCADA não é erro do ioctl, e
    aceitá-la aqui seria decodificar o serial a partir de outro report.
    """
    resposta = Resposta(report_id)
    inicio = time.monotonic()
    for _ in range(tentativas):
        buffer = array.array("B", [0] * tamanho)
        buffer[0] = report_id
        try:
            escritos = fcntl.ioctl(fd, _hidiocgfeature(tamanho), buffer, True)
        except OSError as erro:
            if erro.errno == errno.EPIPE:
                resposta.erro = "não implementado (EPIPE)"
                break
            if erro.errno in (errno.ENODEV, errno.ENOENT):
                resposta.erro = "o controle DESCONECTOU (ENODEV)"
                break
            resposta.erro = f"ioctl: {erro.strerror or erro}"
            continue
        if escritos <= 0:
            resposta.erro = f"ioctl devolveu {escritos}"
            continue
        recebido = bytes(buffer[:escritos])
        if recebido[0] != report_id:
            resposta.erro = f"veio id 0x{recebido[0]:02x} no lugar de 0x{report_id:02x}"
            continue
        resposta.dados = recebido
        resposta.erro = ""
        break
    resposta.segundos = time.monotonic() - inicio
    return resposta


def mandar_o_comando(fd: int, payload: bytearray, *, bytes_de_crc: int = 0) -> str:
    """A ÚNICA escrita deste arquivo. Confere, e só então solta.

    Devolve "" no sucesso, ou a frase da falha. Entre a conferência e o `ioctl`
    não há linha que toque no buffer — é de propósito, e mexer nisso é mexer na
    trava.

    `bytes_de_crc` diz quantos bytes do FIM são CRC, e não comando. Nasceu em
    15/08/2026 de a trava ter mordido o próprio envelope de rádio: os quatro
    bytes de CRC caíram no teste de "tem de estar zerado" e a escrita foi
    recusada — corretamente, porque a trava não sabia deles. **Nenhum byte
    chegou ao aparelho**, que é exatamente o que se quer de uma trava que erra.

    A correção não afrouxa nada: o miolo continua conferido byte a byte, e o
    rabo de CRC passa a ser conferido TAMBÉM — recalculado aqui e comparado.
    Um rabo corrompido agora reprova, coisa que antes desta linha nem existia.
    """
    recusar_familia_do_firmware(payload[0])
    if bytes_de_crc:
        miolo = payload[: len(payload) - bytes_de_crc]
        conferir_payload(miolo)
        esperado = zlib.crc32(bytes([SEMENTE_FEATURE_BT]) + bytes(miolo)) & 0xFFFFFFFF
        veio = int.from_bytes(payload[len(payload) - bytes_de_crc :], "little")
        if veio != esperado:
            raise PayloadRecusadoError(
                f"o CRC do envelope não confere: veio 0x{veio:08x}, "
                f"recalculado 0x{esperado:08x}"
            )
    else:
        conferir_payload(payload)
    try:
        escritos = fcntl.ioctl(fd, _hidiocsfeature(len(payload)), payload, True)
    except OSError as erro:
        return f"ioctl SET_FEATURE: {erro.strerror or erro} (errno {erro.errno})"
    if escritos < 0:
        return f"ioctl SET_FEATURE devolveu {escritos}"
    return ""


def provar_que_vive(fd: int, aparelho: Aparelho, tamanho_do_firmware: int) -> Prova:
    """Três perguntas ao aparelho, e nenhuma opinião: ele responde, ou não.

    1. O feature `0x20` (informação de firmware) volta? Ele é constante por
       unidade, então serve de impressão digital antes e depois.
    2. O `hardware_version` que o `hid_playstation` publica no sysfs continua o
       mesmo? É de graça, não disputa nada com o daemon.
    3. Ele ainda EMITE? Um controle que responde a feature e não emite report
       de entrada não está são — e a diferença entre "não emitiu" e "não pude
       ler" é a armadilha que `comum.py` documenta.
    """
    prova = Prova()
    resposta = pedir_feature(fd, FEATURE_FIRMWARE, tamanho_do_firmware)
    if resposta.ok:
        prova.firmware = resposta.dados
    else:
        prova.erro = f"feature 0x20: {resposta.erro}"

    prova.hardware_version = ler_texto(
        os.path.join(aparelho.dir_device, "hardware_version")
    ).strip()
    prova.lightbar = estado_da_lightbar(aparelho)

    limite = time.monotonic() + SEGUNDOS_DE_ESPERA
    while time.monotonic() < limite and prova.reports_lidos < REPORTS_QUE_PROVAM_VIDA:
        prontos, _, _ = select.select([fd], [], [], max(0.0, limite - time.monotonic()))
        if not prontos:
            break
        try:
            bruto = os.read(fd, 256)
        except BlockingIOError:
            continue
        except OSError as erro:
            prova.erro = (prova.erro + " | " if prova.erro else "") + f"read: {erro}"
            break
        if not bruto:
            continue
        prova.reports_lidos += 1
        prova.ids_vistos[bruto[0]] = prova.ids_vistos.get(bruto[0], 0) + 1
    return prova


# ---------------------------------------------------------------------------
# A decodificação do serial
# ---------------------------------------------------------------------------


@dataclass
class Serial:
    """O que se conseguiu tirar do `0x81`, e o que faltou."""

    bruto: bytes = b""
    texto: str = ""
    codigo_da_cor: str = ""
    nome_da_cor: str = ""
    erro: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.texto) and not self.erro


def decodificar(dados: bytes) -> Serial:
    """`buf[1]=1, buf[2]=19, buf[3]=2` e então 17 caracteres ASCII.

    Os três primeiros bytes são o eco do que se pediu, e o `dualshock-tools`
    trata qualquer divergência como erro — não como "veio outra coisa, vamos
    tentar ler assim mesmo". Aqui é igual: sem o eco certo, o que vem depois
    não é o serial, e decodificá-lo produziria uma cor inventada.
    """
    serial = Serial(bruto=dados)
    if len(dados) < 4 + TAMANHO_DO_SERIAL:
        serial.erro = f"resposta curta: {len(dados)} bytes"
        return serial
    if dados[1] != BASE_DO_SERIAL or dados[2] != NUM_DO_SERIAL:
        serial.erro = (
            f"eco errado: base={dados[1]} num={dados[2]}, "
            f"esperava {BASE_DO_SERIAL}/{NUM_DO_SERIAL}"
        )
        return serial
    if dados[3] != MARCA_DE_RESPOSTA_BOA:
        serial.erro = f"buf[3]={dados[3]}, esperava {MARCA_DE_RESPOSTA_BOA}"
        return serial
    cru = dados[4 : 4 + TAMANHO_DO_SERIAL]
    serial.texto = cru.decode("ascii", errors="replace")
    codigo = serial.texto[FATIA_DA_COR]
    serial.codigo_da_cor = codigo
    serial.nome_da_cor = CORES.get(codigo, "")
    if not serial.nome_da_cor:
        serial.nome_da_cor = f"DESCONHECIDA (código {codigo!r})"
    return serial


# ---------------------------------------------------------------------------
# O DESENHO DO RÁDIO — escrito, conferível, e NÃO exercido
# ---------------------------------------------------------------------------


def envelope_de_radio(payload: bytes | bytearray) -> bytearray:
    """O mesmo comando com o envelope de Bluetooth: CRC-32 nos 4 últimos bytes.

    **GRAU: DESENHO. Não medido.** O que se sabe, e de onde:

    - O canal EXISTE: `0x80` e `0x81` estão no `report_descriptor` destes
      controles também no rádio, com os mesmos 64 bytes. Conferido pelo parser
      de `comum.py` em 15/08/2026, nos quatro.
    - Por Bluetooth os feature reports do DualSense levam CRC-32 nos quatro
      últimos bytes, com a semente `0xA3` prefixada ao buffer — é o
      `ps_check_crc32` do `hid-playstation`, e é o que esta casa já usa para
      VALIDAR o `0x05`, o `0x09`, o `0x20` e o `0x22` lidos de um físico BT.
    - O `seq` e o tag `0x10` do envelope de OUTPUT (report `0x31`) **não se
      aplicam aqui**: aquele envelope é do canal de interrupção, e o feature
      report sai pelo canal de CONTROLE, com o id no byte 0 e mais nada de
      cabeçalho. Confundir os dois envelopes é o defeito que a BTREPORT-02
      fechou — a `pydualsense` montava um `0x31` malformado e o firmware o
      descartava calado.

    O QUE FALTA PARA RODAR, e é curto:

    1. Ela reconectar os dois controles de rádio (botão PS).
    2. Rodar SECO primeiro, com `--alvo <hidraw do rádio> --radio-a-serio`, e
       conferir na tela o buffer com o CRC.
    3. Rodar com `--escrever`. Se o firmware recusar, a assinatura importa e
       tem de ser lida antes de tentar variação: `EPIPE` na hora é "não tenho
       esse report neste transporte"; ~3 s e timeout é o `REPORT_REQ_TIMEOUT`
       do BlueZ, que é o rádio se perdendo; eco errado no `0x81` é o firmware
       respondendo outra coisa.
    4. A DÚVIDA HONESTA, que só a medição resolve: não se sabe se o firmware
       exige o CRC num `SET_REPORT` de feature ou se ele só o EMITE nas
       respostas. Por isso `--sem-crc` existe — é a segunda tentativa, e ela
       tem de ser feita depois da primeira, não em vez dela. Nenhuma das duas
       muda os bytes do COMANDO: `01 13` continua sendo `01 13`, e a trava de
       `conferir_payload` roda igual nos dois casos.
    """
    print(f"    semente do CRC ... {conferir_a_semente()}")
    envelope = bytearray(payload)
    crc = zlib.crc32(
        bytes([SEMENTE_FEATURE_BT]) + bytes(envelope[: len(envelope) - 4])
    ) & 0xFFFFFFFF
    envelope[len(envelope) - 4 :] = crc.to_bytes(4, "little")
    return envelope


# ---------------------------------------------------------------------------
# A execução
# ---------------------------------------------------------------------------


@dataclass
class Medida:
    """Tudo que uma execução apurou sobre UM controle."""

    aparelho: Aparelho
    porta: str = ""
    motivo_da_porta: str = ""
    payload: bytes = b""
    escreveu: bool = False
    erro_da_escrita: str = ""
    antes: Prova = field(default_factory=Prova)
    depois: Prova = field(default_factory=Prova)
    resposta: Resposta = field(default_factory=lambda: Resposta(FEATURE_RESPOSTA))
    serial: Serial = field(default_factory=Serial)

    @property
    def continua_sao(self) -> bool:
        """São = respondia antes, responde depois, e responde a MESMA coisa."""
        if not self.antes.vivo or not self.depois.vivo:
            return False
        if self.antes.firmware != self.depois.firmware:
            return False
        return self.antes.hardware_version == self.depois.hardware_version


def escolher_alvo(alvos: list[Aparelho], pedido: str, *, exigir_mac: str = "") -> Aparelho:
    """UM alvo, nomeado. Não existe modo "todos", e isso é a trava número 4.

    `exigir_mac` é a trava número 7, e nasceu em 15/08/2026 de uma ordem dela
    repassada pela coordenação: *confirme pelo `HID_UNIQ`, não pela cor do LED
    — isso já apontou o aparelho errado hoje*.

    O número do nó **não identifica controle**: `descobrir_aparelhos()` avisa
    que os nós renumeram, e nesta casa já houve controle que sumiu e voltou com
    outro `eventN` entre duas chamadas com segundos de diferença. Entre eu
    conferir `hidraw8` na tela e a escrita sair, o `hidraw8` pode ser outro
    aparelho. O MAC não muda, então é por ele que se tranca.

    Isso importa MAIS que o normal agora: um dos controles de rádio está com a
    lightbar travada e é objeto de outra investigação ao vivo. Escrever no
    aparelho errado não estragaria só este ensaio.
    """
    nome = pedido.strip().removeprefix("/dev/")
    for aparelho in alvos:
        if aparelho.hidraw != nome:
            continue
        esperado = exigir_mac.strip().lower()
        if esperado and aparelho.mac.lower() != esperado:
            raise SystemExit(
                f"ERRO: {nome} NÃO é o controle que você pediu.\n"
                f"  HID_UNIQ exigido .. {mascarar(esperado)}\n"
                f"  HID_UNIQ do nó .... {mascarar(aparelho.mac)}\n"
                "Os nós renumeram; o MAC não. NADA foi ao aparelho."
            )
        return aparelho
    disponiveis = ", ".join(a.hidraw for a in alvos) or "nenhum"
    raise SystemExit(
        f"ERRO: não encontrei '{pedido}' entre os DualSense fisicos.\n"
        f"Na mesa agora: {disponiveis}.\n"
        "Rode com --listar para ver a mesa com transporte e MAC mascarado."
    )


def medir(aparelho: Aparelho, *, escrever: bool, radio_a_serio: bool, com_crc: bool) -> Medida:
    """A rodada inteira num controle: prova, comando, resposta, prova de novo."""
    medida = Medida(aparelho=aparelho)
    tamanhos = tamanhos_do_descritor(aparelho.dir_device)["feature"]
    tamanho_comando = tamanhos.get(FEATURE_COMANDO, 64)
    tamanho_resposta = tamanhos.get(FEATURE_RESPOSTA, 64)
    tamanho_firmware = tamanhos.get(FEATURE_FIRMWARE, 64)

    leva_crc = aparelho.transporte == RADIO and com_crc
    payload = montar_payload(tamanho_comando)
    if leva_crc:
        payload = envelope_de_radio(payload)
    medida.payload = bytes(payload)

    print()
    print(f"  ALVO ............. {aparelho.hidraw} ({aparelho.transporte})")
    print(f"  MAC (mascarado) .. {mascarar(aparelho.mac)}")
    print(f"  tamanho do 0x{FEATURE_COMANDO:02x} .. {tamanho_comando} bytes (do descritor)")
    print(f"  tamanho do 0x{FEATURE_RESPOSTA:02x} .. {tamanho_resposta} bytes (do descritor)")
    print()
    print("  O PAYLOAD QUE VAI (ou iria) NO FIO, em hexadecimal:")
    print(em_hexadecimal(payload))
    print()
    print(f"    byte 0 = 0x{payload[0]:02x}   report id (SET_FEATURE de fábrica)")
    print(f"    byte 1 = {payload[1]:<6} base  — tinha de ser {BASE_DO_SERIAL}")
    print(f"    byte 2 = {payload[2]:<6} num   — tinha de ser {NUM_DO_SERIAL}")
    if leva_crc:
        print(
            f"    últimos 4 = CRC-32 semente 0x{SEMENTE_FEATURE_BT:02x} "
            "(envelope BT, DESENHO)"
        )

    # No rádio os 4 últimos bytes são o CRC, e conferi-los contra "tem de estar
    # zerado" acusaria o próprio envelope. O que a trava confere é o COMANDO —
    # e o comando é o mesmo nos dois transportes.
    comando = payload[: len(payload) - 4] if leva_crc else payload
    try:
        conferir_payload(comando)
        recusar_familia_do_firmware(payload[0])
    except PayloadRecusadoError as erro:
        medida.erro_da_escrita = f"PAYLOAD RECUSADO: {erro}"
        print(f"\n  >> {medida.erro_da_escrita} — NADA foi ao aparelho.")
        return medida
    print("    conferido byte a byte: É LEITURA PURA (base 1, num 19).")

    if aparelho.transporte == RADIO and not radio_a_serio:
        medida.erro_da_escrita = (
            "alvo de RÁDIO sem --radio-a-serio: o envelope BT é DESENHO, "
            "não medida, e não se estreia caminho novo por omissao"
        )
        print(f"\n  >> RECUSADO: {medida.erro_da_escrita}.")
        return medida

    try:
        no = abrir_no_hidraw(aparelho.caminho_hidraw, escrita=True)
    except PortaFechadaError as erro:
        medida.erro_da_escrita = f"{diagnostico_de_acesso(aparelho.caminho_hidraw)} | {erro}"
        print(f"\n  >> PORTA FECHADA: {medida.erro_da_escrita}")
        return medida
    medida.porta = no.porta
    medida.motivo_da_porta = no.motivo

    try:
        print(f"\n  porta usada ...... {no.porta} — {no.motivo}")
        print("\n  [1/3] PROVA DE VIDA, ANTES de escrever")
        medida.antes = provar_que_vive(no.fd, aparelho, tamanho_firmware)
        _imprimir_prova(medida.antes)
        if not medida.antes.vivo:
            print("  >> O controle não respondeu ANTES da escrita. PARANDO aqui:")
            print("  >> escrever num aparelho que ja não responde e cegueira, não ensaio.")
            medida.erro_da_escrita = "o controle não provou vida ANTES"
            return medida

        if not escrever:
            print("\n  [2/3] RODADA SECA — nada foi ao fio.")
            print("        Para valer, repita com --escrever.")
            return medida

        print(f"\n  [2/3] ESCREVENDO SET_FEATURE 0x{FEATURE_COMANDO:02x} ...")
        falha = mandar_o_comando(
            no.fd, bytearray(payload), bytes_de_crc=4 if leva_crc else 0
        )
        if falha:
            medida.erro_da_escrita = falha
            print(f"        FALHOU: {falha}")
        else:
            medida.escreveu = True
            print("        aceito pelo aparelho (o ioctl voltou sem erro).")
            medida.resposta = pedir_feature(no.fd, FEATURE_RESPOSTA, tamanho_resposta)
            if medida.resposta.ok:
                print(
                    f"        resposta 0x{FEATURE_RESPOSTA:02x}, "
                    f"{len(medida.resposta.dados)} bytes:"
                )
                print(em_hexadecimal(sem_o_serial(medida.resposta.dados)[:32]))
                print("        (os '#' são o número de série da unidade, mascarado)")
                medida.serial = decodificar(medida.resposta.dados)
            else:
                print(f"        o 0x{FEATURE_RESPOSTA:02x} não voltou: {medida.resposta.erro}")

        print("\n  [3/3] PROVA DE VIDA, DEPOIS de escrever")
        medida.depois = provar_que_vive(no.fd, aparelho, tamanho_firmware)
        _imprimir_prova(medida.depois)
    finally:
        no.fechar()
    return medida


def _imprimir_prova(prova: Prova) -> None:
    digital = prova.firmware[:8].hex(" ") if prova.firmware else "NÃO VEIO"
    ids = ", ".join(f"0x{i:02x}x{n}" for i, n in sorted(prova.ids_vistos.items())) or "nenhum"
    print(f"        feature 0x20 (8 primeiros) . {digital}")
    print(f"        hardware_version ........... {prova.hardware_version or '?'}")
    print(f"        reports de entrada lidos ... {prova.reports_lidos} ({ids})")
    print(f"        lightbar (sysfs, só leitura) {prova.lightbar or '?'}")
    if prova.erro:
        print(f"        erro ....................... {prova.erro}")


def imprimir_veredito(medida: Medida) -> None:
    print()
    print("-" * 78)
    if medida.serial.ok:
        print(f"  SERIAL ........... {medida.serial.texto}")
        print(f"  código da cor .... {medida.serial.codigo_da_cor}")
        print(f"  COR DO PLÁSTICO .. {medida.serial.nome_da_cor}")
    elif medida.serial.erro:
        print(f"  SERIAL ........... NÃO SAIU: {medida.serial.erro}")
    elif not medida.escreveu:
        print("  SERIAL ........... não pedido (rodada seca ou recusada)")

    if medida.antes.vivo and medida.depois.vivo:
        igual = "IGUAL" if medida.antes.firmware == medida.depois.firmware else "MUDOU"
        print(
            f"  CONTINUA SÃO? .... {'SIM' if medida.continua_sao else 'NÃO'} "
            f"— firmware 0x20 {igual}, "
            f"{medida.depois.reports_lidos} reports depois da escrita"
        )
    elif medida.escreveu:
        print("  CONTINUA SÃO? .... NÃO PROVADO — o controle não respondeu depois")
    print("-" * 78)


def nos_de_evdev(aparelho: Aparelho) -> list[str]:
    """Os `/dev/input/eventN` deste controle — só para DECLARAR o grab.

    Este instrumento não lê evdev: ele fala `hidraw` por ioctl, e o
    `EVIOCGRAB` do co-op não atrapalha nem ajuda o que ele mede. A declaração
    entra no cabeçalho mesmo assim, porque a regra da casa é que o relatório
    diga o estado do grab — e "não me afeta" só é uma afirmação verificável se
    o estado estiver escrito ao lado dela.

    Resolvido a cada chamada: os números de nó NÃO são estáveis.
    """
    raiz = os.path.join(aparelho.dir_device, "input")
    achados: list[str] = []
    if not os.path.isdir(raiz):
        return achados
    for entrada in sorted(os.listdir(raiz)):
        if not entrada.startswith("input"):
            continue
        for sub in sorted(os.listdir(os.path.join(raiz, entrada))):
            if sub.startswith("event"):
                achados.append(f"/dev/input/{sub}")
    return achados


def listar(alvos: list[Aparelho], *, sem_mascara: bool) -> None:
    linhas = []
    for aparelho in alvos:
        hw = ler_texto(os.path.join(aparelho.dir_device, "hardware_version")).strip()
        linhas.append(
            [
                aparelho.hidraw,
                aparelho.transporte,
                aparelho.mac if sem_mascara else mascarar(aparelho.mac),
                hw or "?",
                diagnostico_de_acesso(aparelho.caminho_hidraw),
            ]
        )
    print(tabela(["no", "transporte", "MAC", "hardware_version", "acesso pelo fs"], linhas))


class Transcrito:
    """Copia para a tela e guarda, para que o arquivo saia MASCARADO.

    O precedente é o CSV de `imu_no_cabo.py`: a tela é dela e pode ver o
    aparelho dela inteiro; o arquivo é versionado e nunca vê. Guardar o texto e
    mascarar na hora de gravar é o que garante que as duas coisas não se
    confundam — e a gravação acontece no fim, com a lista de seriais já
    completa.
    """

    def __init__(self, saida: object) -> None:
        self.saida = saida
        self.pedacos: list[str] = []
        self.seriais: list[str] = []

    def write(self, texto: str) -> int:
        self.pedacos.append(texto)
        return self.saida.write(texto)  # type: ignore[attr-defined,no-any-return]

    def flush(self) -> None:
        self.saida.flush()  # type: ignore[attr-defined]

    def gravar(self, caminho: str) -> None:
        texto = "".join(self.pedacos)
        for serial in self.seriais:
            texto = texto.replace(serial, mascarar_serial(serial))
        os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as arquivo:
            arquivo.write(texto)
            arquivo.write(
                "\n\nMASCARAS APLICADAS NESTE ARQUIVO (a tela mostrou o valor inteiro):\n"
                "  MAC ..... octetos 4 e 5 zerados (máscara da casa)\n"
                f"  serial .. so os {CARACTERES_PUBLICOS_DO_SERIAL} primeiros "
                "caracteres; os demais viram '#', em texto E em hexadecimal.\n"
                "            Os caracteres 5 e 6 — a COR, que e o objeto do ensaio — "
                "estao entre os preservados.\n"
            )


def main() -> int:
    analisador = argparse.ArgumentParser(
        description="Le do APARELHO a cor do plástico dele (serial de fábrica).",
        epilog=(
            "SECO por omissao. Sem --escrever, nada sai no fio: o instrumento "
            "mostra o comando exato e para."
        ),
    )
    analisador.add_argument("--listar", action="store_true", help="mostra a mesa e sai")
    analisador.add_argument("--alvo", default="", help="UM no: hidraw4, hidraw5, ...")
    analisador.add_argument(
        "--escrever",
        action="store_true",
        help="manda o SET_FEATURE de verdade (sem isto, a rodada e seca)",
    )
    analisador.add_argument(
        "--radio-a-serio",
        action="store_true",
        help="autoriza alvo de RÁDIO, cujo envelope BT é DESENHO, e não medida",
    )
    analisador.add_argument(
        "--sem-crc",
        action="store_true",
        help="no radio, manda SEM o CRC-32 no fim (a segunda tentativa, não a primeira)",
    )
    analisador.add_argument(
        "--sem-mascara",
        action="store_true",
        help="mostra o MAC inteiro na TELA (arquivo nenhum sai sem máscara)",
    )
    analisador.add_argument(
        "--exigir-mac",
        default="",
        help="só escreve se o HID_UNIQ do nó for este (o nó renumera; o MAC não)",
    )
    analisador.add_argument(
        "--bruto",
        default="",
        help="grava a saída desta execução, ja mascarada, neste caminho",
    )
    argumentos = analisador.parse_args()

    transcrito = Transcrito(sys.stdout)
    if argumentos.bruto:
        sys.stdout = transcrito  # type: ignore[assignment]
    try:
        codigo = _corpo(argumentos, transcrito)
    finally:
        sys.stdout = transcrito.saida  # type: ignore[assignment]
        if argumentos.bruto:
            transcrito.gravar(argumentos.bruto)
            print(f"\nsaida bruta gravada em {argumentos.bruto}")
    return codigo


def _corpo(argumentos: argparse.Namespace, transcrito: Transcrito) -> int:
    aparelhos = descobrir_aparelhos()
    alvos = fisicos(aparelhos)
    escolhido = [a for a in alvos if a.hidraw == argumentos.alvo.strip().removeprefix("/dev/")]

    print(
        cabecalho_do_instrumento(
            "cor_do_plastico.py",
            "de que cor é o plástico deste controle, perguntado a ELE?",
            bibliotecas=["fcntl", "array", "select", "zlib"],
            escreve_no_aparelho=argumentos.escrever,
            daemon_precisa_parar=False,
            nos_evdev=nos_de_evdev(escolhido[0]) if escolhido else None,
        )
    )
    if escolhido:
        print(
            "  (o grab acima é informativo: este instrumento fala hidraw por "
            "ioctl,\n   não evdev, e o EVIOCGRAB do co-op não afeta o que ele mede.)"
        )
    print(f"\n{censo_da_mesa(aparelhos)}\n")
    listar(alvos, sem_mascara=argumentos.sem_mascara)

    if argumentos.listar:
        print(resumo("so listei a mesa. Escolha UM alvo com --alvo hidrawN."))
        return 0
    if not argumentos.alvo:
        print(
            resumo(
                "nenhum alvo. UM por execução, obrigatoriamente: --alvo hidrawN. "
                "Não existe modo 'todos', e isso e trava, não esquecimento."
            )
        )
        return 2

    aparelho = escolher_alvo(alvos, argumentos.alvo, exigir_mac=argumentos.exigir_mac)
    if argumentos.escrever:
        print()
        print("  " + "!" * 74)
        print("  !! ESCRITA AUTORIZADA nesta execução. A família 0x80 e a de FABRICA:")
        for (base, num), o_que in sorted(PARES_QUE_DESTROEM.items()):
            print(f"  !!   [{base},{num}] {o_que}")
        print(f"  !! O nosso e [{BASE_DO_SERIAL},{NUM_DO_SERIAL}], e a trava confere byte a byte.")
        print("  " + "!" * 74)

    medida = medir(
        aparelho,
        escrever=argumentos.escrever,
        radio_a_serio=argumentos.radio_a_serio,
        com_crc=not argumentos.sem_crc,
    )
    if medida.serial.texto:
        transcrito.seriais.append(medida.serial.texto)
    imprimir_veredito(medida)

    if medida.serial.ok and medida.continua_sao:
        print(
            resumo(
                f"{aparelho.hidraw} ({aparelho.transporte}) é "
                f"{medida.serial.nome_da_cor}, lido do próprio aparelho, "
                "e continua respondendo depois da escrita."
            )
        )
        return 0
    if not argumentos.escrever:
        print(resumo("rodada SECA: o payload está na tela, o fio ficou calado."))
        return 0
    print(
        resumo(
            f"a cor NÃO saiu de {aparelho.hidraw}. "
            f"escrita: {medida.erro_da_escrita or 'aceita'}; "
            f"resposta: {medida.resposta.erro or 'ok'}; "
            f"serial: {medida.serial.erro or 'ok'}. "
            "PARE e leia antes de tentar variação."
        )
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
