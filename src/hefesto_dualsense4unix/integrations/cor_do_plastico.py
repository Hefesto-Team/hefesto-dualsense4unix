"""A cor do plástico de um DualSense, perguntada a ELE — no produto.

Até 22/08/2026 esta leitura vivia só em ``scripts/ensaios/cor_do_plastico.py``,
fora do aplicativo: ``grep -rn 'cor_do_plastico|plastic|nome_da_cor' src`` devolvia
ZERO, e o ``state_full`` só publica ``lightbar_rgb`` — que é a LUZ, não o plástico.
A decisão **T6** do registro «DECISOES-DA-EXECUCAO» da aba Configurações
trouxe a leitura para cá: sem ela, toda linha "Cor:" da aba Configurações nasceria
em "Não sei", inclusive nos controles no cabo, que o desenho mostra com a cor lida.

Isto é um PORTE, não uma reescrita. O ensaio segue sendo o instrumento (rodada
seca, transcrito, prova de vida antes e depois); aqui fica o mínimo de que a
janela precisa: montar o pedido, conferi-lo, mandar, decodificar e traduzir.

A ÚNICA ESCRITA QUE ESTE MÓDULO SABE FAZER
------------------------------------------

O serial de fábrica de 17 caracteres carrega a cor nos caracteres 5 e 6, e ele
não está em report nenhum de graça: é preciso PEDIR, e pedir é escrever. O
comando é a família ``SET_FEATURE 0x80``, a mesma em que ``[1, 1]`` RESETA o
controle e ``[12, 1, ...]`` grava calibração na memória não-volátil. Não há
desfazer, e ela tem quatro controles sem reposição.

Por isso o payload é montado por uma função **sem parâmetro** e conferido byte a
byte por outra imediatamente antes de sair. Uma função que aceitasse ``base`` e
``num`` seria uma função que aceita ``[1, 1]``. Entre :func:`conferir_pedido` e o
``ioctl`` não há linha que toque no buffer — mexer nisso é mexer na trava.

A procedência do par ``[1, 19]`` está no ensaio, conferida contra o fonte de
``dualshock-tools.github.io`` (``js/controllers/ds5-controller.js``,
``getSystemInfo(1, 19, 17)``), em 15/08/2026.

DOIS TRANSPORTES, DOIS ENVELOPES — E O COMANDO É O MESMO
--------------------------------------------------------

O par ``[1, 19]`` não muda com o transporte; o ENVELOPE muda. Pelo cabo o
``ioctl`` não leva assinatura nenhuma. Pelo rádio o feature report é assinado
com um CRC-32 nos quatro últimos bytes, e a semente é o **byte de cabeçalho da
transação HIDP** — há uma por sentido, e a de quem ESCREVE feature é
``SET_REPORT|FEATURE`` (``0x53``). Ver :data:`SEMENTE_SET_FEATURE_BT`.

**MEDIDO EM 02/09/2026, com o controle do usuário no rádio** (``hidraw5``, o mesmo
comando três vezes, mudando só o envelope):

===================  ==========  ============================================
envelope             resposta    o que voltou
===================  ==========  ============================================
CRC semente ``0x53``  13,6 ms    64 bytes, eco ``[1, 19, 2]``, código ``04``
``0xA3`` (o de 23/08)  7,0 ms    ``errno 5``
sem CRC nenhum         7,0 ms    ``errno 5``
===================  ==========  ============================================

Duas coisas que essa tabela fecha e estavam abertas: **o CRC não é opcional no
rádio** (a "dúvida honesta" que o ``--sem-crc`` do ensaio existia para responder
— sem assinatura o firmware recusa igual), e **a amostra por rádio passou de UMA
para DUAS unidades** (``hidraw8``, código ``02``, em 27/08/2026; ``hidraw5``,
código ``04``, hoje). Duas unidades não são universalidade, e este arquivo não
escreve que são.

UMA TABELA SÓ, E ELA É O MAPA DO USUÁRIO
----------------------------------

O-CONTROLE-NUNCA-VISTO-TEM-NOME-E-COR-01, 25/09/2026. A tradução código → nome
→ cor sai de ``docs/data/cores-do-dualsense.csv`` (os 28 modelos e as 10 zonas),
lida por :func:`ler_a_tabela`. ``NOMES_DE_FABRICA`` e ``TONS`` continuam
existindo com o mesmo nome e passam a ser LIDOS dali.

**FATO SUBSTITUÍDO.** Aqui estavam duas tabelas DIGITADAS, de 21 códigos cada:
os nomes e os tons, este aproximado de ``docs/data/cores-do-plastico.md``. O
mapa dela tem 28. Os sete que faltavam (``13``, ``14``, ``15``, ``ZC``, ``ZD``,
``ZE`` e ``ZF``, a linha HyperPop e as edições de jogo de 2025) saíam «Não sei»,
sem cor, no cabo e no rádio: a pessoa que plugasse um deles via o produto
dizer que não sabia que controle era. E três nomes divergiam do mapa
(``God of War Ragnarok``, ``Spider-Man 2``, ``Icon Blue Limited Edition``), o
que punha duas grafias do mesmo modelo na mesma tela, a do daemon e a da mesa.

**O CÓDIGO QUE NEM O MAPA CONHECE** (uma edição que sair amanhã) continua
saindo ``None`` em :func:`cor_do_codigo`, e o nome que a tela escreve é o do
MODELO, pelo PID (:data:`MODELOS`): «DualSense» ou «DualSense Edge». Ver
:func:`nome_do_aparelho`. Nada quebra por não achar o modelo.

A procedência dos códigos continua sendo a de três fontes independentes
(``dualshock-tools`` confirmado pelo mantenedor na issue #210,
``nsfm/dualsense-ts`` e ``TechAntohere/Senshi``), e o grau de cada hexa está na
coluna ``grau`` do CSV.

Nada aqui toca a lightbar. Plástico é propriedade do aparelho, imutável, e serve
para saber qual controle é qual; a cor da lightbar continua sendo dela e mora em
``core/led_control.py``.
"""
from __future__ import annotations

import colorsys
import csv
import os
import pathlib
import threading
import time
import unicodedata
from dataclasses import dataclass
from typing import Any, Protocol

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

FEATURE_COMANDO = 0x80
FEATURE_RESPOSTA = 0x81

BASE_DO_SERIAL = 1
NUM_DO_SERIAL = 19

TAMANHO_DO_SERIAL = 17

FATIA_DA_COR = slice(4, 6)

MARCA_DE_RESPOSTA_BOA = 2

TAMANHO_DO_CRC = 4

SEMENTE_SET_FEATURE_BT = 0x53

TAMANHO_DO_FEATURE = 64

#: Os pares da MESMA família ``0x80`` que destroem o controle. Não estão aqui
#: para serem usados: estão para que a trava tenha o que reconhecer, e para que
#: quem ler este arquivo veja o tamanho do precipício ao lado da trilha.
PARES_QUE_DESTROEM: dict[tuple[int, int], str] = {
    (1, 1): "RESETA o controle",
    (3, 2): "destrava a NVS para escrita",
    (12, 1): "GRAVA calibração de stick na memória não-volátil",
}

FAMILIA_DO_FIRMWARE = range(0xF0, 0xF8)

_RAIZ = pathlib.Path(__file__).resolve().parents[3]

#: cabeçalho, «UMA TABELA SÓ».
TABELA_DAS_CORES = _RAIZ / "docs" / "data" / "cores-do-dualsense.csv"

_ZONAS_DO_TOM = ("casca_esq", "casca_dir")

#: O produto não pode estar ajustado só para a máquina de quem desenvolve: outro usuário pluga o
#: controle dele e o app tem de funcionar.
MODELOS: dict[int, str] = {
    0x0CE6: "DualSense",
    0x0DF2: "DualSense Edge",
}

#: família DualSense (``core/evdev_reader.DUALSENSE_PIDS``).
MODELO_GENERICO = MODELOS[0x0CE6]

_GRAFIAS_DE_ANTES: dict[str, str] = {
    "spider-man 2": "Z2",
    "icon blue limited edition": "ZB",
}

FUNDO_DO_CARD = (0x28, 0x2A, 0x36)

RAZAO_DA_BORDA = 2.2

PASSOS_DA_MISTURA = 20

_BUS_USB = 0x0003
_BUS_BLUETOOTH = 0x0005

CABO = "cabo"
RADIO = "rádio"

#: O VID do DualSense. Os PIDs são as chaves de :data:`MODELOS`. Um par errado
_VID_SONY = 0x054C

# VID/PID/bus de DualSense Edge no cabo (``0003:054C:0DF2``) — o mesmo par do


class PedidoRecusadoError(Exception):
    """O payload não é o que este arquivo autoriza. Nada foi ao aparelho."""


@dataclass(frozen=True)
class CorDoPlastico:
    """O que o aparelho respondeu, já traduzido. ``tom`` vazio = sem hexa."""

    codigo: str
    nome: str
    tom: str = ""
    id: str = ""


@dataclass(frozen=True)
class IdentidadeDeFabrica:
    """O que o serial de fábrica diz deste aparelho. ``None`` = não sei.

    ROTA-A (02/09/2026). Até aqui o módulo devolvia só a COR e jogava o serial
    fora dentro de :func:`decodificar` — e o daemon, que é quem tem o fd, não
    publicava nem um nem outro. O resultado media-se na tela do usuário: ``Cosmic
    Red`` e ``Starlight Blue`` cravados no HTML, e o nome de um controle mudando
    quando o segundo entrava na mesa, porque ele vinha da POSIÇÃO.

    Os dois campos viajam juntos porque vêm da MESMA resposta e nascem no mesmo
    instante; separá-los faria duas leituras do aparelho onde uma basta.

    **OS DOIS ``None`` NÃO SÃO O MESMO «NÃO SEI»** — A-FITA-PERDEU-O-MODELO-E-A-COR-01,
    22/09/2026. ``cor=None`` saía igual quando o aparelho respondeu com um
    código fora da tabela (resposta: não muda nunca) e quando o descritor não
    chegou ou o ``ioctl`` estourou (falha: a próxima pode responder). Quem
    guardava tratava as duas como a primeira, e os dois controles do usuário ficaram
    sem modelo nem cor pelo resto da sessão. ``definitiva`` separa as duas AQUI,
    na fonte — quem guarda não adivinha:

    * ``respondeu`` — o aparelho devolveu o eco certo; o que veio vale para
      sempre, inclusive a cor ``None``;
    * ``nao_pode`` — a trava recusou o pedido: repetir mandaria os mesmos bytes
      à mesma trava;
    * o resto é FALHA DE AGORA, e ``motivo`` diz qual.

    ``modelo`` é o nome GENÉRICO do aparelho pelo PID do ``uevent``
    («DualSense», «DualSense Edge»), e ele chega MESMO QUANDO A PERGUNTA FALHA:
    o PID se lê do sysfs, sem mandar byte nenhum. ``None`` só quando nenhum nó
    daquele endereço foi achado. Quem escreve o nome na tela é
    :func:`nome_do_aparelho`.
    """

    serial: str | None = None
    cor: CorDoPlastico | None = None
    nao_pode: bool = False
    motivo: str = ""
    modelo: str | None = None

    @property
    def respondeu(self) -> bool:
        return self.serial is not None or self.cor is not None

    @property
    def definitiva(self) -> bool:
        return self.respondeu or self.nao_pode


@dataclass(frozen=True)
class AlvoDoControle:
    """O nó a que perguntar, por qual transporte a pergunta sai, e qual modelo."""

    caminho: str
    transporte: str = CABO
    modelo: str = MODELO_GENERICO


class _Pedidor(Protocol):
    """Assinatura do transporte: ``(caminho, pedido) -> resposta | None``."""

    def __call__(self, caminho: str, pedido: bytes) -> bytes | None: ...


def ler_a_tabela(caminho: str | os.PathLike[str] | None = None) -> dict[str, CorDoPlastico]:
    """``{código: CorDoPlastico}`` dos modelos do mapa, na ordem do arquivo.

    Uma entrada por CÓDIGO (o CSV tem uma linha por zona): o ``nome`` e o ``id``
    são os da primeira linha do código, e o ``tom`` é o hexa da casca
    (:data:`_ZONAS_DO_TOM`), minúsculo, ou ``""`` quando a casca é ``SEM-HEX``.

    **NUNCA LEVANTA.** Sem o arquivo (um pacote instalado sem o ``docs/``), a
    tabela sai VAZIA e todo aparelho cai no nome do modelo — «DualSense» —,
    que é verdade e não derruba o daemon nem a janela. O ``caminho`` resolve
    na CHAMADA, não no default: é o que deixa a régua medir a tabela vazia sem
    tocar no disco de ninguém.

    O arquivo que ABRE e não é UTF-8 cai no mesmo vazio que o que não abre: a
    tabela é lida na importação, pelo daemon e pela janela, e um
    ``UnicodeDecodeError`` ali seria o produto sem abrir, não uma cor a menos.
    """
    alvo = pathlib.Path(caminho) if caminho is not None else TABELA_DAS_CORES
    try:
        texto = alvo.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as erro:
        logger.warning("cor_do_plastico_sem_tabela", caminho=str(alvo), erro=str(erro))
        return {}
    linhas = [ln for ln in texto.splitlines() if ln.strip() and not ln.startswith("#")]
    nomes: dict[str, tuple[str, str]] = {}
    tons: dict[str, dict[str, str]] = {}
    for linha in csv.DictReader(linhas):
        codigo = (linha.get("codigo_da_cor") or "").strip().upper()
        if not codigo:
            continue
        nomes.setdefault(
            codigo, ((linha.get("id") or "").strip(), (linha.get("nome") or "").strip())
        )
        hexa = (linha.get("hex") or "").strip().lower()
        if hexa:
            tons.setdefault(codigo, {})[(linha.get("zona") or "").strip()] = hexa
    tabela: dict[str, CorDoPlastico] = {}
    for codigo, (ident, nome) in nomes.items():
        zonas = tons.get(codigo, {})
        tom = next((zonas[z] for z in _ZONAS_DO_TOM if zonas.get(z)), "")
        tabela[codigo] = CorDoPlastico(codigo=codigo, nome=nome, tom=tom, id=ident)
    return tabela


TABELA: dict[str, CorDoPlastico] = ler_a_tabela()

NOMES_DE_FABRICA: dict[str, str] = {codigo: cor.nome for codigo, cor in TABELA.items()}

TONS: dict[str, str] = {codigo: cor.tom for codigo, cor in TABELA.items() if cor.tom}


# Tradução — pura, sem aparelho nenhum
# ---------------------------------------------------------------------------


def cor_do_codigo(codigo: str) -> CorDoPlastico | None:
    """A cor de um código de dois caracteres, ou ``None`` para código estranho.

    ``None`` é resposta legítima: o mapa tem 28 modelos e a Sony fabrica edições
    novas sem avisar ninguém. Inventar uma COR aqui poria na tela uma cor que
    ninguém mediu — o NOME, quem dá é :func:`nome_do_aparelho`, pelo modelo.
    """
    return TABELA.get((codigo or "").strip().upper())


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c)).casefold()


def cor_do_nome(nome: str) -> CorDoPlastico | None:
    """A cor pelo nome oficial de fábrica — o caminho da escolha do usuário.

    A tela grava o NOME (``ControleDeclarado.cor`` é texto livre, decisão C2), e
    é por aqui que o nome gravado volta a ter hexa para pintar a borda. Compara
    sem caixa e sem acento, e aceita as grafias da tabela digitada de antes de
    25/09/2026 (:data:`_GRAFIAS_DE_ANTES`) — uma declaração daquela época não
    perde a borda porque o nome passou a vir do mapa.
    """
    procurado = _sem_acento((nome or "").strip())
    if not procurado:
        return None
    for cor in TABELA.values():
        if _sem_acento(cor.nome) == procurado:
            return cor
    antigo = _GRAFIAS_DE_ANTES.get(procurado)
    return TABELA.get(antigo) if antigo else None


def nome_do_aparelho(cor: CorDoPlastico | None, modelo: str | None = None) -> str:
    """O nome que a tela escreve para um controle: o do mapa, ou o do modelo.

    O-CONTROLE-NUNCA-VISTO-TEM-NOME-E-COR-01, 25/09/2026. Com a cor achada no
    mapa, o nome é o dela (``Cosmic Red``, ``Ghost of Yōtei Limited Edition``) —
    no DualSense e no Edge, que tem a cor perguntada do mesmo jeito. Sem ela
    (código fora do mapa, pergunta que ainda não voltou, aparelho que não pode
    responder), o nome é o do MODELO pelo PID, e sem PID o da família.

    **NUNCA «Não sei».** Todo controle da mesa é um DualSense que funciona; o
    que não se sabe é a edição, e o nome do modelo é verdade sem ela.
    """
    if cor is not None and cor.nome:
        return cor.nome
    return modelo or MODELO_GENERICO


def cor_do_serial(serial: str) -> CorDoPlastico | None:
    """A cor escondida nos caracteres 5 e 6 do serial de fábrica."""
    if len(serial or "") < FATIA_DA_COR.stop:
        return None
    return cor_do_codigo(serial[FATIA_DA_COR])


#: padrão de produto, sem a sessão com a luz na mão (ela dormia): a saturação de 15%
SATURACAO_NEUTRA = 0.15
VALOR_CLARO = 0.5

LUZ_BRANCA = (255, 255, 255)


def tom_da_luz(cor: CorDoPlastico | None) -> tuple[int, int, int] | None:
    """O tom de luz do plástico `cor` — ou `None` quando o plástico não tem tom."""
    if cor is None or not cor.tom:
        return None
    hexa = cor.tom.strip().lstrip("#")
    try:
        r, g, b = (int(hexa[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return None
    matiz, saturacao, valor = colorsys.rgb_to_hsv(r, g, b)
    if saturacao < SATURACAO_NEUTRA:
        return LUZ_BRANCA if valor >= VALOR_CLARO else None
    cheia = colorsys.hsv_to_rgb(matiz, 1.0, 1.0)
    return (round(cheia[0] * 255), round(cheia[1] * 255), round(cheia[2] * 255))


def tom_da_luz_do_nome(nome: str | None) -> tuple[int, int, int] | None:
    """O tom de luz pelo NOME de fábrica que o `state_full` publica (`modelo`)."""
    if not nome:
        return None
    return tom_da_luz(cor_do_nome(nome) or cor_do_codigo_por_id(nome))


def cor_do_codigo_por_id(ident: str) -> CorDoPlastico | None:
    """A cor pelo `id` da linha do mapa (`white`, `cosmic-red`) — o `data-colorway`."""
    procurado = (ident or "").strip().casefold()
    for cor in TABELA.values():
        if cor.id and cor.id.casefold() == procurado:
            return cor
    return None


def tom_para_a_borda(tom: str, *, minimo: float = RAZAO_DA_BORDA) -> str:
    """O hexa que a borda do card pode usar de verdade."""
    from hefesto_dualsense4unix.utils.color_contrast import razao_contraste, rgb_para_hex

    bruto = (tom or "").strip().lstrip("#")
    if len(bruto) != 6:
        return ""
    try:
        rgb = (int(bruto[0:2], 16), int(bruto[2:4], 16), int(bruto[4:6], 16))
    except ValueError:
        return ""
    if razao_contraste(rgb, FUNDO_DO_CARD) >= minimo:
        return rgb_para_hex(rgb)
    for passo in range(1, PASSOS_DA_MISTURA + 1):
        parte = passo / PASSOS_DA_MISTURA
        misto = (
            round(rgb[0] + (255 - rgb[0]) * parte),
            round(rgb[1] + (255 - rgb[1]) * parte),
            round(rgb[2] + (255 - rgb[2]) * parte),
        )
        if razao_contraste(misto, FUNDO_DO_CARD) >= minimo:
            return rgb_para_hex(misto)
    return rgb_para_hex((255, 255, 255))


# ---------------------------------------------------------------------------
# A trava — tudo que escreve passa por aqui
# ---------------------------------------------------------------------------


def montar_pedido(tamanho: int = TAMANHO_DO_FEATURE) -> bytes:
    """O ÚNICO pedido que este módulo sabe montar: ``80 01 13 00 ... 00``.

    Sem parâmetro de conteúdo, de propósito — ver o cabeçalho. O resto vai zerado
    até o tamanho que o descritor do aparelho declara para o ``0x80``.
    """
    buffer = bytearray(max(3, tamanho))
    buffer[0] = FEATURE_COMANDO
    buffer[1] = BASE_DO_SERIAL
    buffer[2] = NUM_DO_SERIAL
    return bytes(buffer)


def crc_do_pedido(comando: bytes) -> int:
    """A assinatura do rádio para ``comando``, no sentido de ESCRITA."""
    from hefesto_dualsense4unix.core.ds_output_report import bt_crc32

    return bt_crc32(comando, seed=SEMENTE_SET_FEATURE_BT)


def envelope_de_radio(pedido: bytes) -> bytes:
    """O MESMO pedido, assinado para sair pelo rádio."""
    if len(pedido) < 3 + TAMANHO_DO_CRC:
        raise PedidoRecusadoError(
            f"pedido curto demais para levar assinatura: {len(pedido)} bytes"
        )
    envelope = bytearray(pedido)
    corte = len(envelope) - TAMANHO_DO_CRC
    envelope[corte:] = crc_do_pedido(bytes(envelope[:corte])).to_bytes(4, "little")
    return bytes(envelope)


def conferir_pedido(buffer: bytes) -> None:
    """Confere byte a byte e levanta se qualquer um estiver fora do lugar."""
    if buffer and buffer[0] in FAMILIA_DO_FIRMWARE:
        raise PedidoRecusadoError(
            f"0x{buffer[0]:02x} está na família do FIRMWARE (0xf0-0xf7): ler, nunca escrever"
        )
    if len(buffer) < 3:
        raise PedidoRecusadoError(f"pedido curto demais: {len(buffer)} bytes")
    if buffer[0] != FEATURE_COMANDO:
        raise PedidoRecusadoError(
            f"byte 0 é 0x{buffer[0]:02x}, tinha de ser 0x{FEATURE_COMANDO:02x}"
        )
    if (buffer[1], buffer[2]) in PARES_QUE_DESTROEM:
        raise PedidoRecusadoError(
            f"o par ({buffer[1]}, {buffer[2]}) {PARES_QUE_DESTROEM[(buffer[1], buffer[2])]}"
        )
    if buffer[1] != BASE_DO_SERIAL or buffer[2] != NUM_DO_SERIAL:
        raise PedidoRecusadoError(
            f"o par ({buffer[1]}, {buffer[2]}) não é o do serial "
            f"({BASE_DO_SERIAL}, {NUM_DO_SERIAL})"
        )
    assinado = len(buffer) >= 3 + TAMANHO_DO_CRC and any(buffer[-TAMANHO_DO_CRC:])
    corte = len(buffer) - TAMANHO_DO_CRC if assinado else len(buffer)
    sujos = [i for i, valor in enumerate(buffer[3:corte], start=3) if valor]
    if sujos:
        raise PedidoRecusadoError(
            f"bytes que tinham de estar zerados vieram sujos: {sujos[:8]}"
        )
    if not assinado:
        return
    esperado = crc_do_pedido(bytes(buffer[:corte]))
    veio = int.from_bytes(buffer[corte:], "little")
    if veio != esperado:
        raise PedidoRecusadoError(
            f"a assinatura do rádio não confere: veio 0x{veio:08x}, "
            f"recalculada 0x{esperado:08x} (semente 0x{SEMENTE_SET_FEATURE_BT:02x})"
        )


def serial_de(dados: bytes) -> str | None:
    """``buf[1]=1, buf[2]=19, buf[3]=2`` e então 17 caracteres ASCII."""
    if len(dados) < 4 + TAMANHO_DO_SERIAL:
        return None
    if dados[1] != BASE_DO_SERIAL or dados[2] != NUM_DO_SERIAL:
        return None
    if dados[3] != MARCA_DE_RESPOSTA_BOA:
        return None
    return dados[4 : 4 + TAMANHO_DO_SERIAL].decode("ascii", errors="replace")


def decodificar(dados: bytes) -> CorDoPlastico | None:
    """A COR dentro da resposta ``0x81``, ou ``None``. Ver :func:`serial_de`."""
    serial = serial_de(dados)
    if serial is None:
        return None
    return cor_do_serial(serial)


def _campos_do_uevent(texto: str) -> dict[str, str]:
    campos: dict[str, str] = {}
    for linha in texto.splitlines():
        chave, separador, valor = linha.partition("=")
        if separador:
            campos[chave.strip()] = valor.strip()
    return campos


def _do_hid_id(hid_id: str) -> tuple[int, int] | None:
    """``(barramento, PID)`` de um DualSense adotado, ou ``None``.

    O filtro de VID:PID é o que FICA de pé desde 02/09/2026: o comando é da
    família de fábrica da Sony, e mandá-lo para o aparelho de outro fabricante é
    escrever às cegas. Os PIDs aceitos são os de :data:`MODELOS` — e o Edge
    (``0DF2``) ENTROU em 25/09/2026 (O-CONTROLE-NUNCA-VISTO-TEM-NOME-E-COR-01):
    até ali ele nunca tinha a cor perguntada, e a tela dizia «Não sei» sobre um
    controle que o daemon adota, numera e acende como qualquer outro.
    """
    partes = hid_id.split(":")
    if len(partes) != 3:
        return None
    try:
        barramento, vendor, product = (int(parte, 16) for parte in partes)
    except ValueError:
        return None
    if vendor != _VID_SONY or product not in MODELOS:
        return None
    return barramento, product


def _transporte_do_dualsense(hid_id: str) -> str | None:
    """``"cabo"``, ``"rádio"``, ou ``None`` se não é um DualSense (nem um Edge).

    Era ``_e_dualsense_no_cabo`` e devolvia ``bool``, com o barramento USB
    embutido na resposta — o primeiro dos três portões que recusavam o rádio.
    O filtro de VID:PID mora em :func:`_do_hid_id`.
    """
    achado = _do_hid_id(hid_id)
    if achado is None:
        return None
    if achado[0] == _BUS_USB:
        return CABO
    if achado[0] == _BUS_BLUETOOTH:
        return RADIO
    return None


def _e_o_nosso_vpad(campos: dict[str, str], pai: str, barramento: int) -> bool:
    """O nó é o NOSSO vpad? A pergunta é do broker, e ele é o dono dela."""
    from hefesto_dualsense4unix.broker.hidraw_broker import (
        _e_o_nosso_vpad as regra_do_broker,
    )

    return bool(regra_do_broker(campos, pai, barramento))


def alvo_do_controle(
    uniq: str,
    *,
    raiz: str = "/sys/class/hidraw",
    listar: Any = os.listdir,
    ler: Any = None,
    resolver: Any = None,
) -> AlvoDoControle | None:
    """O nó do DualSense cujo endereço é ``uniq``, **por qual transporte**, e qual modelo.

    ``raiz``, ``listar`` e ``ler`` entram por argumento com o default do sistema
    real (regra F4 de ``DECISOES-DA-EXECUCAO.md``, e o ``CANARIO-FS-01`` pega
    constante de módulo): é o que permite ao teste montar uma bancada falsa sem
    encostar em ``/sys``.

    ``resolver`` é o ``realpath`` do pai HID, de onde sai a TOPOLOGIA do filtro
    do vpad. **A árvore é uma só**: quem injeta o ``uevent`` (``ler``) injeta o
    sysfs inteiro, e o default dele passa a ser o caminho como veio — senão a
    régua de uma bancada falsa perguntaria a topologia ao ``/sys`` da máquina em
    que roda, e o resultado mudaria com o que estivesse plugado nela.

    ``None`` — que é a resposta comum — quando não há aparelho com aquele
    endereço, quando ele não é um DualSense, ou quando o que casou é o nosso
    próprio vpad. **DOIS filtros, e eram TRÊS até 02/09/2026:**

    * **VID:PID de DualSense ou de DualSense Edge** (:func:`_do_hid_id`): o
      comando é da família de fábrica da Sony, e mandá-lo para o aparelho de
      outro fabricante é escrever às cegas;
    * **vpad** (:func:`_e_o_nosso_vpad`, a regra do broker): ele forja
      VID/PID/bus de DualSense Edge no cabo, então sem o filtro o módulo
      pediria o serial à saída do próprio produto.

    **O FILTRO DE CABO SAIU — ``ONDA-CONEXOES-11``, 02/09/2026.** Ele exigia
    barramento USB e era NOSSO, não do aparelho. A razão dele já tinha caído em
    27/08/2026 (não era o firmware recusando o ``0x80``: era a semente do nosso
    CRC), e o que faltava era medir com o controle do usuário no rádio. Medido hoje,
    em ``hidraw5``: **64 bytes, eco ``[1, 19, 2]``, código ``04`` — Galactic
    Purple — em 13,6 ms**, com o mesmo comando que sai pelo cabo, só assinado
    com a semente ``0x53``. Ver a tabela no cabeçalho do módulo.

    A amostra por rádio é de **DUAS unidades** (``hidraw8`` em 27/08, ``hidraw5``
    hoje), e este arquivo não escreve que são quatro: duas provam que o APARELHO
    faz, não que toda unidade faz. Se um terceiro controle recusar por rádio, o
    achado é a ASSINATURA, não o filtro — e a leitura já devolve ``None`` sem
    levantar, que é o nome do modelo na tela (:func:`nome_do_aparelho`).
    """
    procurado = (uniq or "").replace(":", "").strip().lower()
    if not procurado:
        return None
    leitor = ler if ler is not None else _ler_texto
    if resolver is None:
        resolver = os.path.realpath if ler is None else (lambda caminho: caminho)
    try:
        nos = sorted(listar(raiz))
    except OSError:
        return None
    for no in nos:
        if not no.startswith("hidraw"):
            continue
        campos = _campos_do_uevent(leitor(os.path.join(raiz, no, "device", "uevent")))
        if not campos:
            continue
        endereco = campos.get("HID_UNIQ", "").replace(":", "").strip().lower()
        if endereco != procurado:
            continue
        achado = _do_hid_id(campos.get("HID_ID", ""))
        transporte = _transporte_do_dualsense(campos.get("HID_ID", ""))
        if achado is None or transporte is None:
            return None
        if _e_o_nosso_vpad(campos, str(resolver(os.path.join(raiz, no, "device"))), achado[0]):
            return None
        return AlvoDoControle(
            caminho=f"/dev/{no}", transporte=transporte, modelo=MODELOS[achado[1]]
        )
    return None


def _ler_texto(caminho: str) -> str:
    try:
        with open(caminho, encoding="utf-8", errors="replace") as arquivo:
            return arquivo.read()
    except OSError:
        return ""


def _perguntar_ao_hidraw(
    caminho: str,
    pedido: bytes,
    *,
    abrir: Any = None,
    ioctl: Any = None,
) -> bytes | None:
    """Manda o pedido pela PORTA DA CASA e devolve a resposta ``0x81``, ou ``None``.

    **A porta é o broker, e a queda para ``open()`` vem depois.** Esta função
    fazia ``os.open(caminho, O_RDWR)`` e nada mais, e por isso a cor não chegava
    à tela do usuário. Medido em 29/08/2026, com o daemon rodando e sem parar nada: os
    dois DualSense no cabo estão ``0600 root:root``, ``os.open`` direto colhe
    ``errno 13`` nos dois, ``ler_pelo_cabo`` devolve ``None`` nos dois — e
    ``None`` é o "Não sei" que o usuário viu nos dois cards.

    Os nós estão fechados porque **o Hefesto os esconde do JOGO**: é o BROKER-01
    funcionando (``broker/hidraw_broker.py``, ``setfacl -b`` + ``chmod 0600``).
    Não é udev, não é firmware, não é o rádio — é o produto batendo na porta que
    o próprio produto fechou. O broker é root e serve um fd ``O_RDWR`` do nó
    ESCONDIDO por ``SCM_RIGHTS``, e o ENSAIO já entra por ali
    (``scripts/ensaios/cor_do_plastico.py`` → ``comum.py`` → ``abrir_hidraw``).
    Era mais uma da classe "a casa sabe e o produto não faz".

    ``abrir_hidraw`` cai sozinho para ``open()`` onde não há broker (CI,
    checkout, install antigo) e DIZ por qual porta entrou — a queda não fica
    muda. ``PortaFechadaError`` É um ``OSError``, então o ``except`` de sempre
    já o cobre, e a mensagem dele carrega o que as DUAS portas responderam, que
    é o diagnóstico que faltava no log.

    ``abrir`` e ``ioctl`` são costura de teste, com o default do sistema real —
    o mesmo par que ``estado_do_grab`` (``hidraw_broker_client.py``) já tem.

    ``conferir_pedido`` CONTINUA SENDO A PRIMEIRA LINHA, antes de qualquer porta
    se abrir: o par que RESETA o controle não chega nem a pedir fd.

    O ``ioctl`` de feature é síncrono e não disputa o fio com o daemon — o que
    disputa é o report de OUTPUT, que este módulo não sabe montar. A validação do
    id na volta não é zelo: em 15/08/2026 esta casa mediu um pedido de ``0x20``
    voltar com ``0x80`` no byte 0, e aceitar a resposta trocada decodificaria o
    serial a partir de outro report.
    """
    import array
    import fcntl

    from hefesto_dualsense4unix.integrations.hidraw_broker_client import abrir_hidraw

    conferir_pedido(pedido)
    tamanho = len(pedido)
    porta = abrir if abrir is not None else abrir_hidraw
    disparar = ioctl if ioctl is not None else fcntl.ioctl
    try:
        no = porta(caminho, escrita=True)
    except OSError as erro:
        logger.info("cor_do_plastico_sem_acesso", caminho=caminho, erro=str(erro))
        return None
    try:
        saida = array.array("B", pedido)
        disparar(no.fd, _hidiocsfeature(tamanho), saida, True)
        entrada = array.array("B", [0] * tamanho)
        entrada[0] = FEATURE_RESPOSTA
        lidos = disparar(no.fd, _hidiocgfeature(tamanho), entrada, True)
    except OSError as erro:
        logger.info(
            "cor_do_plastico_ioctl_falhou",
            caminho=caminho,
            porta=no.porta,
            erro=str(erro),
        )
        return None
    finally:
        no.fechar()
    if lidos <= 0:
        return None
    resposta = bytes(entrada[:lidos])
    if resposta[0] != FEATURE_RESPOSTA:
        return None
    return resposta


_IOC_ESCRITA_E_LEITURA = 3
_IOC_TIPO_HID = ord("H")
_IOC_NR_GETFEATURE = 0x07
_IOC_NR_SETFEATURE = 0x06


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


def ler_identidade_pelo_cabo(
    uniq: str,
    *,
    raiz: str = "/sys/class/hidraw",
    listar: Any = os.listdir,
    ler: Any = None,
    perguntar: _Pedidor | None = None,
    resolver: Any = None,
) -> IdentidadeDeFabrica:
    """Serial E cor do controle ``uniq``, lidos dele. Campos ``None`` = não sei."""
    alvo = alvo_do_controle(uniq, raiz=raiz, listar=listar, ler=ler, resolver=resolver)
    if alvo is None:
        return IdentidadeDeFabrica(motivo="nenhum DualSense físico com este endereço")
    pedido = montar_pedido()
    if alvo.transporte == RADIO:
        pedido = envelope_de_radio(pedido)
    conversa = perguntar if perguntar is not None else _perguntar_ao_hidraw
    try:
        resposta = conversa(alvo.caminho, pedido)
    except PedidoRecusadoError:
        logger.warning(
            "cor_do_plastico_pedido_recusado",
            caminho=alvo.caminho,
            transporte=alvo.transporte,
        )
        return IdentidadeDeFabrica(
            nao_pode=True, motivo="a trava recusou o pedido", modelo=alvo.modelo
        )
    except Exception as erro:
        logger.debug(
            "cor_do_plastico_falhou",
            caminho=alvo.caminho,
            transporte=alvo.transporte,
            erro=str(erro),
        )
        return IdentidadeDeFabrica(
            motivo=f"a conversa levantou {type(erro).__name__}", modelo=alvo.modelo
        )
    if not resposta:
        return IdentidadeDeFabrica(motivo="o aparelho não respondeu", modelo=alvo.modelo)
    serial = serial_de(resposta)
    if serial is None:
        return IdentidadeDeFabrica(
            motivo="a resposta veio sem o eco do pedido", modelo=alvo.modelo
        )
    return IdentidadeDeFabrica(serial=serial, cor=cor_do_serial(serial), modelo=alvo.modelo)


def ler_pelo_cabo(
    uniq: str,
    *,
    raiz: str = "/sys/class/hidraw",
    listar: Any = os.listdir,
    ler: Any = None,
    perguntar: _Pedidor | None = None,
    resolver: Any = None,
) -> CorDoPlastico | None:
    """A cor do plástico do controle ``uniq``, lida dele. ``None`` = não sei."""
    return ler_identidade_pelo_cabo(
        uniq, raiz=raiz, listar=listar, ler=ler, perguntar=perguntar, resolver=resolver
    ).cor


RECUO_DA_NOVA_TENTATIVA: tuple[float, ...] = (5.0, 30.0, 120.0)


class AgendaDaPergunta:
    """Quando se pode perguntar a identidade de um ``uniq`` — e quando não.

    A-FITA-PERDEU-O-MODELO-E-A-COR-01, 22/09/2026. A janela
    (``interface/mesa_viva.LeitorDeCor``) e o daemon
    (``daemon/ipc_handlers._identidade_de_fabrica``) guardavam a primeira
    resposta PARA SEMPRE, e a falha de um instante virava «este controle não
    tem cor». Medido no ``interface.log`` e no journal da bancada: a janela das 23:36
    abriu 28 s depois do segundo controle entrar pelo rádio, no meio de um
    engasgo de 5 s em que o daemon perdia um terceiro nó (``ENODEV``). O broker
    serviu um descritor na hora, e a pergunta por ele não trouxe cor; serviu o
    outro 5 s depois, quando o cliente já tinha desistido (prazo de 2 s). As
    duas falhas eram de um instante — a janela das 23:43, sem uma linha de
    código mudada, leu os dois.

    As regras, e cada uma tem razão:

    * **resposta definitiva fecha** o ``uniq`` (ver ``IdentidadeDeFabrica.definitiva``);
    * **falha reabre com recuo** (:data:`RECUO_DA_NOVA_TENTATIVA`) e depois
      desiste — o pedido é um ``SET_FEATURE`` da família ``0x80``, e ele não
      entra no tique de 10 Hz de ninguém;
    * **nunca duas em voo** para o mesmo ``uniq``, nem se o controle sair e
      voltar no meio da pergunta — por isso :meth:`esquecer_ausentes` não
      solta quem está em voo;
    * **nunca duas no mesmo intervalo**: entre o começo de uma pergunta e o da
      seguinte passa ao menos o primeiro degrau do recuo, mesmo que a lista de
      controles pisque e o esquecimento zere a conta a cada tique;
    * **o leitor é o mesmo**: a agenda só decide QUANDO. Quem pergunta chama o
      :func:`ler_identidade_pelo_cabo` de sempre, com a trava de sempre.

    Os três métodos são seguros entre fios: quem reserva é o laço (da janela ou
    do daemon), quem registra é a thread que perguntou.
    """

    def __init__(
        self,
        *,
        recuo: tuple[float, ...] = RECUO_DA_NOVA_TENTATIVA,
        relogio: Any = time.monotonic,
    ) -> None:
        self._recuo = tuple(recuo)
        self._relogio = relogio
        self._trava = threading.Lock()
        self._em_voo: set[str] = set()
        self._fechados: set[str] = set()
        self._falhas: dict[str, int] = {}
        self._proxima: dict[str, float] = {}
        self._ultima: dict[str, float] = {}

    def reservar(self, uniq: str) -> bool:
        """``True`` = pergunte AGORA; o ``uniq`` fica em voo até :meth:`registrar`."""
        if not uniq:
            return False
        with self._trava:
            if uniq in self._em_voo or uniq in self._fechados:
                return False
            agora = self._relogio()
            quando = self._proxima.get(uniq)
            if quando is not None and agora < quando:
                return False
            ultima = self._ultima.get(uniq)
            if ultima is not None and self._recuo and agora - ultima < self._recuo[0]:
                return False
            self._em_voo.add(uniq)
            self._ultima[uniq] = agora
            return True

    def registrar(self, uniq: str, achado: IdentidadeDeFabrica) -> None:
        """O que a pergunta devolveu. Solta o voo e decide se volta a perguntar."""
        with self._trava:
            self._em_voo.discard(uniq)
            if achado.definitiva:
                self._fechar_travado(uniq)
                return
            falhas = self._falhas.get(uniq, 0) + 1
            self._falhas[uniq] = falhas
            if falhas > len(self._recuo):
                self._fechar_travado(uniq)
                desistiu, espera = True, None
            else:
                espera = self._recuo[falhas - 1]
                self._proxima[uniq] = self._relogio() + espera
                desistiu = False
        logger.info(
            "identidade_de_fabrica_falhou",
            uniq=uniq,
            motivo=achado.motivo,
            falhas=falhas,
            desistiu=desistiu,
            proxima_em_s=espera,
        )

    def fechar(self, uniq: str) -> None:
        """Quem não pode responder — o mapa de canais diz que o transporte não entrega."""
        with self._trava:
            self._fechar_travado(uniq)

    def esquecer_ausentes(self, vivos: set[str]) -> None:
        """Quem saiu da mesa volta do zero — é o «até reconectar» da desistência."""
        with self._trava:
            for uniq in list(self._fechados | set(self._falhas)):
                if uniq not in vivos:
                    self._fechados.discard(uniq)
                    self._falhas.pop(uniq, None)
                    self._proxima.pop(uniq, None)

    def _fechar_travado(self, uniq: str) -> None:
        self._fechados.add(uniq)
        self._falhas.pop(uniq, None)
        self._proxima.pop(uniq, None)
