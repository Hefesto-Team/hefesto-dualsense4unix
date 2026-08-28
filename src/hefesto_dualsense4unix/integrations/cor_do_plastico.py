"""A cor do plástico de um DualSense, perguntada a ELE — no produto.

Até 22/08/2026 esta leitura vivia só em ``scripts/ensaios/cor_do_plastico.py``,
fora do aplicativo: ``grep -rn 'cor_do_plastico|plastic|nome_da_cor' src`` devolvia
ZERO, e o ``state_full`` só publica ``lightbar_rgb`` — que é a LUZ, não o plástico.
A decisão **T6** de ``docs/process/sprints/2026-08-21-ABA-CONFIGURACOES/DECISOES-DA-EXECUCAO.md``
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

DUAS TABELAS, DUAS PROCEDÊNCIAS DIFERENTES
------------------------------------------

* ``NOMES_DE_FABRICA`` — código → nome oficial. Três fontes independentes
  (``dualshock-tools`` confirmado pelo mantenedor na issue #210, ``nsfm/dualsense-ts``
  e ``TechAntohere/Senshi``). O ensaio guarda uma cópia própria para rodar num
  checkout sem o pacote instalado; ``tests/unit/test_config_06_declaracao_nasce_em_nao_sei.py``
  confronta as duas, para que a cópia não vire uma segunda verdade;
* ``TONS`` — código → hexa. Sai de ``docs/data/cores-do-plastico.md``, e **vinte
  das vinte e uma linhas são aproximadas**: só a ``05`` (Starlight Blue,
  ``#B5CED4``) foi medida, por ela, em 21/08/2026. É por isso que a escolha dela
  vence a tabela em toda parte desta aba.

Nada aqui toca a lightbar. Plástico é propriedade do aparelho, imutável, e serve
para saber qual controle é qual; a cor da lightbar continua sendo dela e mora em
``core/led_control.py``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: O comando de fábrica (escrita) e a resposta (leitura).
FEATURE_COMANDO = 0x80
FEATURE_RESPOSTA = 0x81

#: O par que pede o serial de fábrica — o ÚNICO par que este arquivo conhece.
BASE_DO_SERIAL = 1
NUM_DO_SERIAL = 19

#: 17 caracteres ASCII, o mesmo serial impresso na traseira do controle.
TAMANHO_DO_SERIAL = 17

#: Onde a cor mora dentro dele: caracteres 5 e 6 (base zero, 4 e 5).
FATIA_DA_COR = slice(4, 6)

#: O byte que o firmware devolve em ``buf[3]`` quando a resposta é boa.
MARCA_DE_RESPOSTA_BOA = 2

#: Tamanho do buffer do feature ``0x80`` nos quatro controles desta casa,
#: conferido pelo parser de descritor de ``scripts/ensaios/comum.py`` em
#: 15/08/2026. Report de feature tem comprimento fixo no HID: um ``SET_FEATURE``
#: curto pode voltar em stall, e o caminho provado envia o report inteiro.
TAMANHO_DO_FEATURE = 64

#: Os pares da MESMA família ``0x80`` que destroem o controle. Não estão aqui
#: para serem usados: estão para que a trava tenha o que reconhecer, e para que
#: quem ler este arquivo veja o tamanho do precipício ao lado da trilha.
PARES_QUE_DESTROEM: dict[tuple[int, int], str] = {
    (1, 1): "RESETA o controle",
    (3, 2): "destrava a NVS para escrita",
    (12, 1): "GRAVA calibração de stick na memória não-volátil",
}

#: A família por onde o FIRMWARE é atualizado. Decisão dela (D-32): ler tudo,
#: nunca escrever. Aqui ela nem chega perto de uma escrita — há trava.
FAMILIA_DO_FIRMWARE = range(0xF0, 0xF8)

#: Código → nome oficial de fábrica. Ver o cabeçalho para as três fontes.
NOMES_DE_FABRICA: dict[str, str] = {
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

#: Código → hexa do plástico, de ``docs/data/cores-do-plastico.md``. Vinte das
#: vinte e uma são aproximadas; só a ``05`` foi medida.
TONS: dict[str, str] = {
    "00": "#edeef0",
    "01": "#00040d",
    "02": "#da244b",
    "03": "#ee7ea6",
    "04": "#5f4b9b",
    "05": "#b5ced4",
    "06": "#7f8479",
    "07": "#8c2b2e",
    "08": "#a8adb3",
    "09": "#2b4c7e",
    "10": "#1e8e82",
    "11": "#3b3e8c",
    "12": "#e9dedc",
    "30": "#c6c2b6",
    "Z1": "#d9dee3",
    "Z2": "#a8232b",
    "Z3": "#e7eaee",
    "Z4": "#ddd8ec",
    "Z6": "#c3c6c2",
    "ZA": "#cfcac2",
    "ZB": "#1f4e9c",
}

#: O fundo sobre o qual a borda do card é vista: ``@bg`` do tema
#: (``gui/theme.css:21``), o nível que FLUTUA sobre a janela.
FUNDO_DO_CARD = (0x28, 0x2A, 0x36)

#: Contraste mínimo da borda contra o fundo do card. Menor que o ``RATIO_MINIMO``
#: de 3:1 dos traços e que os 4,5:1 de texto, e a diferença é de propósito: uma
#: borda de 2px não é uma frase para ler, é uma marca de identidade. Exigir 3:1
#: aqui empurraria todo plástico escuro para um pastel que não parece mais com o
#: aparelho.
RAZAO_DA_BORDA = 2.2

#: Em quantos degraus a mistura com branco é tentada. Vinte dá passos de 5 %, que
#: é abaixo do que o olho separa numa borda fina.
PASSOS_DA_MISTURA = 20

#: ``HID_ID`` é ``BARRAMENTO:VENDOR:PRODUCT`` em hexa; ``0003`` é USB. Topologia
#: de sysfs NÃO serve para decidir transporte — com BlueZ >= 5.73 os controles de
#: rádio moram sob ``/devices/virtual/misc/uhid/``, junto do nosso vpad, e essa
#: armadilha já foi paga em 11/08/2026.
_BUS_USB = 0x0003

#: VID e PID do DualSense. Um par errado aqui faria o módulo mandar o comando de
#: fábrica da Sony para o aparelho de outro fabricante.
_VID_SONY = 0x054C
_PID_DUALSENSE = 0x0CE6

#: Identidade do NOSSO vpad no HID (``core/backend_pydualsense.py:151-153``). Ele
#: forja VID/PID/bus de DualSense no cabo de propósito — é o que o faz o
#: ``hid_playstation`` fazer bind nele —, então sem este filtro o módulo pediria o
#: serial de fábrica à saída do próprio produto.
_VPAD_PHYS = "hefesto-vpad"
_VPAD_UNIQ_PREFIX = "02fe"


class PedidoRecusadoError(Exception):
    """O payload não é o que este arquivo autoriza. Nada foi ao aparelho."""


@dataclass(frozen=True)
class CorDoPlastico:
    """O que o aparelho respondeu, já traduzido. ``tom`` vazio = sem hexa."""

    codigo: str
    nome: str
    tom: str = ""


class _Pedidor(Protocol):
    """Assinatura do transporte: ``(caminho, pedido) -> resposta | None``."""

    def __call__(self, caminho: str, pedido: bytes) -> bytes | None: ...


# ---------------------------------------------------------------------------
# Tradução — pura, sem aparelho nenhum
# ---------------------------------------------------------------------------


def cor_do_codigo(codigo: str) -> CorDoPlastico | None:
    """A cor de um código de dois caracteres, ou ``None`` para código estranho.

    ``None`` é resposta legítima e frequente: a tabela tem vinte e uma entradas e
    a Sony fabrica edições novas sem avisar ninguém. Inventar um nome aqui poria
    na tela uma cor que ninguém mediu.
    """
    chave = (codigo or "").strip().upper()
    nome = NOMES_DE_FABRICA.get(chave)
    if nome is None:
        return None
    return CorDoPlastico(codigo=chave, nome=nome, tom=TONS.get(chave, ""))


def cor_do_nome(nome: str) -> CorDoPlastico | None:
    """A cor pelo nome oficial de fábrica — o caminho da escolha dela.

    A tela grava o NOME (``ControleDeclarado.cor`` é texto livre, decisão C2), e
    é por aqui que o nome gravado volta a ter hexa para pintar a borda.
    """
    procurado = (nome or "").strip().casefold()
    if not procurado:
        return None
    for codigo, oficial in NOMES_DE_FABRICA.items():
        if oficial.casefold() == procurado:
            return CorDoPlastico(codigo=codigo, nome=oficial, tom=TONS.get(codigo, ""))
    return None


def cor_do_serial(serial: str) -> CorDoPlastico | None:
    """A cor escondida nos caracteres 5 e 6 do serial de fábrica."""
    if len(serial or "") < FATIA_DA_COR.stop:
        return None
    return cor_do_codigo(serial[FATIA_DA_COR])


def tom_para_a_borda(tom: str, *, minimo: float = RAZAO_DA_BORDA) -> str:
    """O hexa que a borda do card pode usar de verdade.

    Midnight Black é ``#00040d`` — mais escuro que o fundo do card (``@bg``,
    ``#282a36``). Pintado cru, ele não é uma borda preta: é a AUSÊNCIA de borda,
    e o card perde a única marca que diz de quem ele é. O desenho já previa isto
    e a dica está escrita nele: *"Preto puro sumiria no fundo escuro da janela,
    então a borda usa um tom clareado do mesmo plástico."*

    **A clareada é uma MISTURA COM BRANCO, e não a subida de luminosidade em HLS
    do `ensure_min_contrast` da casa.** Medido em 22/08/2026, e é por isso que
    esta função existe em vez de uma chamada àquela: o ``#00040d`` tem saturação
    HLS de 100 % (o canal vermelho é zero), então subir só a luminosidade
    preservando matiz e saturação devolve ``#0a56ff`` — um AZUL ELÉTRICO no lugar
    do preto do plástico. O desenho aprovado pinta aquele card de ``#5a5c6b``, um
    cinza-azulado; misturar com branco a 30 % dá ``#4d4f56``, que é o mesmo
    lugar. Misturar não pode aumentar saturação; subir luminosidade pode, e
    justamente nas cores quase pretas, que são as que precisam da correção.

    O piso é 2,2:1 contra o fundo do card, e não os 3:1 de traço nem os 4,5:1 de
    texto: isto é uma borda de 2px, não uma frase para ler. Acima dele a cor
    passa INTACTA — Starlight Blue e White não são mexidos.

    Tom vazio ou malformado devolve ``""`` — a seção então usa a borda neutra do
    tema, que é o "não sei" desta linha.
    """
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


def conferir_pedido(buffer: bytes) -> None:
    """Confere byte a byte e levanta se qualquer um estiver fora do lugar.

    Chamada imediatamente antes do ``ioctl``, nunca antes disso.
    """
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
    sujos = [i for i, valor in enumerate(buffer[3:], start=3) if valor]
    if sujos:
        raise PedidoRecusadoError(
            f"bytes que tinham de estar zerados vieram sujos: {sujos[:8]}"
        )


def decodificar(dados: bytes) -> CorDoPlastico | None:
    """``buf[1]=1, buf[2]=19, buf[3]=2`` e então 17 caracteres ASCII.

    Os três primeiros bytes são o ECO do que se pediu, e qualquer divergência é
    erro — não é "veio outra coisa, vamos ler assim mesmo". Sem o eco certo, o
    que vem depois não é o serial, e decodificá-lo produziria uma cor inventada.
    """
    if len(dados) < 4 + TAMANHO_DO_SERIAL:
        return None
    if dados[1] != BASE_DO_SERIAL or dados[2] != NUM_DO_SERIAL:
        return None
    if dados[3] != MARCA_DE_RESPOSTA_BOA:
        return None
    serial = dados[4 : 4 + TAMANHO_DO_SERIAL].decode("ascii", errors="replace")
    return cor_do_serial(serial)


# ---------------------------------------------------------------------------
# A conversa com o aparelho
# ---------------------------------------------------------------------------


def _campos_do_uevent(texto: str) -> dict[str, str]:
    campos: dict[str, str] = {}
    for linha in texto.splitlines():
        chave, separador, valor = linha.partition("=")
        if separador:
            campos[chave.strip()] = valor.strip()
    return campos


def _e_dualsense_no_cabo(hid_id: str) -> bool:
    partes = hid_id.split(":")
    if len(partes) != 3:
        return False
    try:
        barramento, vendor, product = (int(parte, 16) for parte in partes)
    except ValueError:
        return False
    return (
        barramento == _BUS_USB and vendor == _VID_SONY and product == _PID_DUALSENSE
    )


def no_do_controle(
    uniq: str,
    *,
    raiz: str = "/sys/class/hidraw",
    listar: Any = os.listdir,
    ler: Any = None,
) -> str | None:
    """``/dev/hidrawN`` do DualSense cujo endereço é ``uniq`` — hoje, só no cabo.

    O "só no cabo" é o estado de HOJE, não uma propriedade do aparelho: ver o
    primeiro filtro abaixo, e a ``ONDA-CONEXOES-11``, que o tira.

    ``raiz``, ``listar`` e ``ler`` entram por argumento com o default do sistema
    real (regra F4 de ``DECISOES-DA-EXECUCAO.md``, e o ``CANARIO-FS-01`` pega
    constante de módulo): é o que permite ao teste montar uma bancada falsa sem
    encostar em ``/sys``.

    ``None`` — que é a resposta comum — quando não há aparelho com aquele
    endereço, quando ele está no rádio, ou quando o que casou é o nosso próprio
    vpad. Três filtros, e nenhum é zelo:

    * **cabo** — e este filtro é NOSSO, não do aparelho. **FATO ERRADO,
      SUBSTITUÍDO (27/08/2026).** Estas linhas diziam: *"por rádio o firmware do
      controle RECUSA o 0x80 (…) Não é o BlueZ, não é o uhid, não é o kernel,
      não é o daemon — é o aparelho."* **Não era o aparelho: era o nosso CRC.**
      As sementes desse CRC são o byte de cabeçalho da transação HIDP, e há uma
      por sentido; o ensaio de 23/08 assinou um ``SET_REPORT`` com a de
      ``DATA|FEATURE`` (``0xA3``), quando a que sai é ``SET_REPORT|FEATURE``
      (``0x53``). Medido em 27/08/2026 no mesmo controle e no mesmo comando,
      mudando só a semente: ``0xA3`` e ``0xA2`` devolvem ``errno 5``; ``0x53``
      é aceito, e os quatro DualSense desta bancada responderam pelo rádio.
      Ver ``docs/protocol/dualsense-referencia-canonica.md``, seção "O caminho
      da cor do plástico". **O filtro continua aqui porque ninguém o tirou
      ainda** — tirá-lo é a ``ONDA-CONEXOES-11``, junto com os outros dois
      portões que recusam o rádio (a trava de bytes zerados em
      ``conferir_pedido`` e o ``transporte != "usb"`` da janela). Não pare aqui
      achando que o aparelho recusa: ele não recusa;
    * **VID:PID de DualSense**: o comando é da família de fábrica da Sony, e
      mandá-lo para o aparelho de outro fabricante é escrever às cegas;
    * **vpad**: ele forja VID/PID/bus de DualSense no cabo, então sem o filtro o
      módulo pediria o serial à saída do próprio produto.
    """
    procurado = (uniq or "").replace(":", "").strip().lower()
    if not procurado:
        return None
    leitor = ler if ler is not None else _ler_texto
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
        if campos.get("HID_PHYS", "") == _VPAD_PHYS or endereco.startswith(
            _VPAD_UNIQ_PREFIX
        ):
            return None
        if not _e_dualsense_no_cabo(campos.get("HID_ID", "")):
            return None
        return f"/dev/{no}"
    return None


def _ler_texto(caminho: str) -> str:
    try:
        with open(caminho, encoding="utf-8", errors="replace") as arquivo:
            return arquivo.read()
    except OSError:
        return ""


def _perguntar_ao_hidraw(caminho: str, pedido: bytes) -> bytes | None:
    """Manda o pedido e devolve a resposta ``0x81``, ou ``None``.

    O ``ioctl`` de feature é síncrono e não disputa o fio com o daemon — o que
    disputa é o report de OUTPUT, que este módulo não sabe montar. A validação do
    id na volta não é zelo: em 15/08/2026 esta casa mediu um pedido de ``0x20``
    voltar com ``0x80`` no byte 0, e aceitar a resposta trocada decodificaria o
    serial a partir de outro report.
    """
    import array
    import fcntl

    conferir_pedido(pedido)
    tamanho = len(pedido)
    try:
        descritor = os.open(caminho, os.O_RDWR | os.O_NONBLOCK)
    except OSError as erro:
        logger.debug("cor_do_plastico_sem_acesso", caminho=caminho, erro=str(erro))
        return None
    try:
        saida = array.array("B", pedido)
        fcntl.ioctl(descritor, _hidiocsfeature(tamanho), saida, True)
        entrada = array.array("B", [0] * tamanho)
        entrada[0] = FEATURE_RESPOSTA
        lidos = fcntl.ioctl(descritor, _hidiocgfeature(tamanho), entrada, True)
    except OSError as erro:
        logger.debug("cor_do_plastico_ioctl_falhou", caminho=caminho, erro=str(erro))
        return None
    finally:
        os.close(descritor)
    if lidos <= 0:
        return None
    resposta = bytes(entrada[:lidos])
    if resposta[0] != FEATURE_RESPOSTA:
        return None
    return resposta


#: ``HIDIOCGFEATURE`` / ``HIDIOCSFEATURE``: ``_IOC(WRITE|READ, 'H', 0x07/0x06,
#: tamanho)``, montados à mão como em ``scripts/ensaios/`` — nenhuma dependência
#: nova, e o número mágico visível em vez de escondido atrás de uma biblioteca.
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


def ler_pelo_cabo(
    uniq: str,
    *,
    raiz: str = "/sys/class/hidraw",
    listar: Any = os.listdir,
    ler: Any = None,
    perguntar: _Pedidor | None = None,
) -> CorDoPlastico | None:
    """A cor do plástico do controle ``uniq``, lida dele. ``None`` = não sei.

    **Nunca levanta.** Sem aparelho, sem permissão, com firmware que não responde
    ou com código fora da tabela, o resultado é ``None`` — e ``None`` vira "Não
    sei" na tela, que é resposta válida em toda esta aba.

    ``perguntar`` é o ponto único de injeção do transporte. Sem ele a função fala
    com o ``hidraw`` de verdade; com ele, o teste exercita a decodificação inteira
    sem encostar em aparelho nenhum — e sem que uma suíte distraída mande comando
    de fábrica para os controles dela.
    """
    caminho = no_do_controle(uniq, raiz=raiz, listar=listar, ler=ler)
    if caminho is None:
        return None
    transporte = perguntar if perguntar is not None else _perguntar_ao_hidraw
    try:
        resposta = transporte(caminho, montar_pedido())
    except PedidoRecusadoError:
        # A trava mordeu. Isso é sucesso da trava, não da leitura: NENHUM byte
        # chegou ao aparelho, e é exatamente o que se quer de uma trava que erra.
        logger.warning("cor_do_plastico_pedido_recusado", caminho=caminho)
        return None
    except Exception as erro:  # defensivo — a leitura jamais derruba a janela
        logger.debug("cor_do_plastico_falhou", caminho=caminho, erro=str(erro))
        return None
    if not resposta:
        return None
    return decodificar(resposta)
