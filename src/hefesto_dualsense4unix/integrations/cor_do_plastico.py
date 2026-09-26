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

DOIS TRANSPORTES, DOIS ENVELOPES — E O COMANDO É O MESMO
--------------------------------------------------------

O par ``[1, 19]`` não muda com o transporte; o ENVELOPE muda. Pelo cabo o
``ioctl`` não leva assinatura nenhuma. Pelo rádio o feature report é assinado
com um CRC-32 nos quatro últimos bytes, e a semente é o **byte de cabeçalho da
transação HIDP** — há uma por sentido, e a de quem ESCREVE feature é
``SET_REPORT|FEATURE`` (``0x53``). Ver :data:`SEMENTE_SET_FEATURE_BT`.

**MEDIDO EM 02/09/2026, com o controle dela no rádio** (``hidraw5``, o mesmo
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

UMA TABELA SÓ, E ELA É O MAPA DELA
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

#: Quantos bytes do FIM do pedido são assinatura, e não comando, no rádio.
TAMANHO_DO_CRC = 4

#: A semente do CRC-32 no sentido de ESCRITA de feature por Bluetooth.
#:
#: As sementes deste CRC são o **byte de cabeçalho da transação HIDP**, e há uma
#: por sentido::
#:
#:     0xA1 = HIDP_TRANS_DATA       (0xA0) | RTYPE_INPUT   (0x01)
#:     0xA2 = HIDP_TRANS_DATA       (0xA0) | RTYPE_OUTPUT  (0x02)
#:     0xA3 = HIDP_TRANS_DATA       (0xA0) | RTYPE_FEATURE (0x03)
#:     0x53 = HIDP_TRANS_SET_REPORT (0x50) | RTYPE_FEATURE (0x03)   <-- esta
#:
#: As TRÊS primeiras têm dono em ``core/ds_output_report.py``
#: (``BT_CRC_SEED``, ``BT_INPUT_CRC_SEED``, ``BT_FEATURE_CRC_SEED``) e a conta é
#: reusada dali (``bt_crc32``). A quarta mora aqui porque este é o ÚNICO lugar
#: do produto que ESCREVE feature report — e o lugar certo dela é ao lado das
#: outras três, o que é mudança em arquivo de outra frente.
SEMENTE_SET_FEATURE_BT = 0x53

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

#: A raiz da árvore, a partir DESTE arquivo — o mesmo cálculo de
#: ``interface/mesa_viva.RAIZ`` e ``integrations/canal_sem_imu._RAIZ``, e pela
#: mesma razão medida em 30/08/2026: um literal apontaria para a árvore DELA, e
#: um agente leria o mapa dela em vez do seu.
_RAIZ = pathlib.Path(__file__).resolve().parents[3]

#: O DONO DA TRADUÇÃO: o mapa dela das cores, 28 modelos e 10 zonas. Ver o
#: cabeçalho, «UMA TABELA SÓ».
TABELA_DAS_CORES = _RAIZ / "docs" / "data" / "cores-do-dualsense.csv"

#: As zonas cujo hexa vira o ``tom`` do modelo, na ordem: a casca é o plástico
#: que a pessoa vê de longe. Modelo com a casca ``SEM-HEX`` (camuflado,
#: iridescente, arte) fica sem tom — e sem tom a borda é a neutra, nunca uma
#: cor inventada.
_ZONAS_DO_TOM = ("casca_esq", "casca_dir")

#: Os modelos que o produto adota, pelo PID — e o nome GENÉRICO de cada um.
#:
#: É o nome que a tela escreve quando o código de fábrica não está no mapa (uma
#: edição que a Sony lançar amanhã), quando o aparelho ainda não respondeu, ou
#: quando não pode responder. A cena dela de 25/09/2026 é o aceite:
#: *«aí ele pluga o controle dele e o app não funciona pq ele tá todo setado  (noqa-acento): dela
#: pra funcionar só no meu pc»*.  (noqa-acento): citação literal dela
#: «Não sei» não é nome de um controle que funciona.
#:
#: Os dois PIDs são os mesmos de ``core/evdev_reader.DUALSENSE_PIDS`` e do
#: ``broker/hidraw_broker.PHYS_PRODUCTS``; a régua
#: ``tests/unit/test_o_controle_nunca_visto_tem_nome_e_cor.py`` reprova quem
#: divergir.
MODELOS: dict[int, str] = {
    0x0CE6: "DualSense",
    0x0DF2: "DualSense Edge",
}

#: O nome de quem ainda não se sabe o PID: todo controle adotado pela mesa é da
#: família DualSense (``core/evdev_reader.DUALSENSE_PIDS``).
MODELO_GENERICO = MODELOS[0x0CE6]

#: As GRAFIAS DE ANTES de 25/09/2026, quando a tabela era digitada. Elas só
#: servem para achar a cor de uma DECLARAÇÃO gravada naquela época
#: (``ControleDeclarado.cor`` é texto livre) — o nome que se escreve é o do
#: mapa. A ``Z1`` não precisa estar aqui: :func:`cor_do_nome` compara sem
#: acento.
_GRAFIAS_DE_ANTES: dict[str, str] = {
    "spider-man 2": "Z2",
    "icon blue limited edition": "ZB",
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

#: ``HID_ID`` é ``BARRAMENTO:VENDOR:PRODUCT`` em hexa; ``0003`` é USB e ``0005``
#: é Bluetooth. Topologia de sysfs NÃO serve para decidir transporte — com BlueZ
#: >= 5.73 os controles de rádio moram sob ``/devices/virtual/misc/uhid/``, junto
#: do nosso vpad, e essa armadilha já foi paga em 11/08/2026.
_BUS_USB = 0x0003
_BUS_BLUETOOTH = 0x0005

#: As duas palavras de transporte deste módulo, iguais às de
#: ``scripts/ensaios/comum.py``. Não são as da mesa (``usb``/``bt``): aqui o
#: transporte sai do ``HID_ID`` do ``uevent``, não do daemon.
CABO = "cabo"
RADIO = "rádio"

#: O VID do DualSense. Os PIDs são as chaves de :data:`MODELOS`. Um par errado
#: aqui faria o módulo mandar o comando de fábrica da Sony para o aparelho de
#: outro fabricante.
_VID_SONY = 0x054C

# O NOSSO VPAD NÃO SE RECUSA MAIS AQUI POR UMA CÓPIA DA REGRA. Ele forja
# VID/PID/bus de DualSense Edge no cabo (``0003:054C:0DF2``) — o mesmo par do
# Edge físico, que entrou em 25/09/2026 —, e quem sabe separar os dois é o
# broker, pela topologia e pelas marcas do vpad
# (``broker/hidraw_broker._e_o_nosso_vpad``). Esta é a mesma pergunta, e ela
# tem um dono só: ver :func:`_e_o_nosso_vpad`.


class PedidoRecusadoError(Exception):
    """O payload não é o que este arquivo autoriza. Nada foi ao aparelho."""


@dataclass(frozen=True)
class CorDoPlastico:
    """O que o aparelho respondeu, já traduzido. ``tom`` vazio = sem hexa.

    ``id`` é o ``id`` da linha do mapa (``white``, ``ghost-of-yotei``) — o
    ``data-colorway`` com que o desenho se pinta. Vazio num dublê antigo, que
    constrói só os três primeiros campos: quem pinta cai para a tradução por
    código (``interface/mesa_viva.CORES``), que lê esta mesma tabela.
    """

    codigo: str
    nome: str
    tom: str = ""
    id: str = ""


@dataclass(frozen=True)
class IdentidadeDeFabrica:
    """O que o serial de fábrica diz deste aparelho. ``None`` = não sei.

    ROTA-A (02/09/2026). Até aqui o módulo devolvia só a COR e jogava o serial
    fora dentro de :func:`decodificar` — e o daemon, que é quem tem o fd, não
    publicava nem um nem outro. O resultado media-se na tela dela: ``Cosmic
    Red`` e ``Starlight Blue`` cravados no HTML, e o nome de um controle mudando
    quando o segundo entrava na mesa, porque ele vinha da POSIÇÃO.

    Os dois campos viajam juntos porque vêm da MESMA resposta e nascem no mesmo
    instante; separá-los faria duas leituras do aparelho onde uma basta.

    **OS DOIS ``None`` NÃO SÃO O MESMO «NÃO SEI»** — A-FITA-PERDEU-O-MODELO-E-A-COR-01,
    22/09/2026. ``cor=None`` saía igual quando o aparelho respondeu com um
    código fora da tabela (resposta: não muda nunca) e quando o descritor não
    chegou ou o ``ioctl`` estourou (falha: a próxima pode responder). Quem
    guardava tratava as duas como a primeira, e os dois controles dela ficaram
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
    """O nó a que perguntar, por qual transporte a pergunta sai, e qual modelo.

    Os dois viajam juntos porque o ENVELOPE do pedido depende do transporte: no
    cabo o ``ioctl`` não leva assinatura, no rádio leva CRC-32. Devolver só o
    caminho obrigava quem manda a redescobrir o transporte lendo o ``uevent``
    outra vez — duas leituras da mesma verdade é como elas se afastam. O
    ``modelo`` vem do MESMO ``HID_ID``, pela mesma razão.
    """

    caminho: str
    transporte: str = CABO
    modelo: str = MODELO_GENERICO


class _Pedidor(Protocol):
    """Assinatura do transporte: ``(caminho, pedido) -> resposta | None``."""

    def __call__(self, caminho: str, pedido: bytes) -> bytes | None: ...


# ---------------------------------------------------------------------------
# A tabela — o mapa dela, lido
# ---------------------------------------------------------------------------


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
    """
    alvo = pathlib.Path(caminho) if caminho is not None else TABELA_DAS_CORES
    try:
        texto = alvo.read_text(encoding="utf-8")
    except OSError as erro:
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


#: A tabela lida UMA vez, na importação. O arquivo é versionado e só muda com o
#: produto; relê-lo a cada controle seria disco a cada tique sem ganho nenhum.
TABELA: dict[str, CorDoPlastico] = ler_a_tabela()

#: Código → nome de fábrica, LIDO do mapa. O nome e a ordem ficam — quem lista
#: as cores (``app/actions/external_controllers.cores_para_busca``) e o ensaio
#: continuam lendo daqui.
NOMES_DE_FABRICA: dict[str, str] = {codigo: cor.nome for codigo, cor in TABELA.items()}

#: Código → hexa da casca, LIDO do mapa. Só entra quem tem hexa: modelo de casca
#: ``SEM-HEX`` não tem tom, e a borda dele é a neutra.
TONS: dict[str, str] = {codigo: cor.tom for codigo, cor in TABELA.items() if cor.tom}


# ---------------------------------------------------------------------------
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
    """A cor pelo nome oficial de fábrica — o caminho da escolha dela.

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


def crc_do_pedido(comando: bytes) -> int:
    """A assinatura do rádio para ``comando``, no sentido de ESCRITA.

    A conta é a do ``hid-playstation`` e o dono dela é ``core/ds_output_report``
    (``bt_crc32``): uma casa, uma conta. O que muda aqui é só a semente —
    :data:`SEMENTE_SET_FEATURE_BT`, e não a ``BT_FEATURE_CRC_SEED``, que é a do
    feature que CHEGA.
    """
    from hefesto_dualsense4unix.core.ds_output_report import bt_crc32

    return bt_crc32(comando, seed=SEMENTE_SET_FEATURE_BT)


def envelope_de_radio(pedido: bytes) -> bytes:
    """O MESMO pedido, assinado para sair pelo rádio.

    Não toca no comando: escreve o CRC-32 nos quatro últimos bytes, que
    :func:`montar_pedido` já deixou zerados. Sem parâmetro de conteúdo pela
    mesma razão do :func:`montar_pedido` — o que se escolhe aqui é o envelope,
    nunca o que vai dentro dele.
    """
    if len(pedido) < 3 + TAMANHO_DO_CRC:
        raise PedidoRecusadoError(
            f"pedido curto demais para levar assinatura: {len(pedido)} bytes"
        )
    envelope = bytearray(pedido)
    corte = len(envelope) - TAMANHO_DO_CRC
    envelope[corte:] = crc_do_pedido(bytes(envelope[:corte])).to_bytes(4, "little")
    return bytes(envelope)


def conferir_pedido(buffer: bytes) -> None:
    """Confere byte a byte e levanta se qualquer um estiver fora do lugar.

    Chamada imediatamente antes do ``ioctl``, nunca antes disso.

    **DUAS FORMAS SÃO AUTORIZADAS, e nenhuma delas afrouxa a trava** — o comando
    é conferido byte a byte nas duas, e o que muda é o que se exige do RABO:

    * o pedido nu (cabo): tudo depois do byte 2 tem de estar ZERADO;
    * o pedido assinado (rádio): tudo depois do byte 2 zerado **exceto** os
      quatro últimos, que têm de ser exatamente o CRC recalculado aqui.

    A segunda forma é mais APERTADA que a primeira, não menos: o rabo deixou de
    ser "quatro bytes que ninguém olha" e passou a ter um único valor admitido —
    a assinatura de um comando todo zerado, que não carrega parâmetro nenhum.
    Cada tamanho de buffer tem, portanto, exatamente DOIS pedidos aceitáveis.

    A trava mordeu o próprio envelope antes disto existir (15/08/2026, no
    ensaio): os quatro bytes de assinatura caíram no teste de "tem de estar
    zerado" e a escrita foi recusada — corretamente, porque a trava não sabia
    deles. **Nenhum byte chegou ao aparelho**, que é o que se quer de uma trava
    que erra.
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
    """``buf[1]=1, buf[2]=19, buf[3]=2`` e então 17 caracteres ASCII.

    Os três primeiros bytes são o ECO do que se pediu, e qualquer divergência é
    erro — não é "veio outra coisa, vamos ler assim mesmo". Sem o eco certo, o
    que vem depois não é o serial, e decodificá-lo produziria uma cor inventada.

    ELA SAIU DE DENTRO DO :func:`decodificar` em 02/09/2026 (ROTA-A) e não é
    função nova: são as MESMAS quatro conferências, com o serial devolvido em
    vez de descartado. O ``decodificar`` passou a chamá-la, para que a régua do
    eco tenha um dono só — duas cópias dela se afastariam na primeira mudança de
    firmware.
    """
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
    """O nó é o NOSSO vpad? A pergunta é do broker, e ele é o dono dela.

    Até 25/09/2026 este módulo tinha uma CÓPIA da metade D2 (o ``phys`` exato e
    o prefixo do ``uniq``) e recusava o Edge pelo PID, que é o que o tornava
    seguro. Com o Edge aceito, o ``0003:054C:0DF2`` do vpad e o do Edge físico
    no cabo são o MESMO par, e quem os separa é a regra inteira do broker: a
    topologia (USB sob ``/misc/uhid/`` é forjado — D1) e as marcas do vpad (D2).
    ``broker/hidraw_broker.py`` é stdlib pura e o pacote já o importa
    (``profiles/manager.py``), então importar a regra custa nada e mata a cópia.
    """
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
    CRC), e o que faltava era medir com o controle DELA no rádio. Medido hoje,
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


# `no_do_controle` MORREU em 02/09/2026, e quem a matou foi o portão
# `casa-sabe`. Ela sobreviveu meia hora como embrulho de `alvo_do_controle` que
# devolvia só o caminho — e o portão a acusou de promessa pública sem chamador
# em produção, que é exatamente o que ela era: todo caminho do produto passou a
# precisar do TRANSPORTE junto, porque é ele que decide o envelope. Dois nomes
# para a mesma pergunta é como eles se afastam.


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
    à tela dela. Medido em 29/08/2026, com o daemon rodando e sem parar nada: os
    dois DualSense no cabo estão ``0600 root:root``, ``os.open`` direto colhe
    ``errno 13`` nos dois, ``ler_pelo_cabo`` devolve ``None`` nos dois — e
    ``None`` é o "Não sei" que ela viu nos dois cards.

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

    conferir_pedido(pedido)  # A TRAVA, ANTES DE QUALQUER PORTA SE ABRIR.
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


def ler_identidade_pelo_cabo(
    uniq: str,
    *,
    raiz: str = "/sys/class/hidraw",
    listar: Any = os.listdir,
    ler: Any = None,
    perguntar: _Pedidor | None = None,
    resolver: Any = None,
) -> IdentidadeDeFabrica:
    """Serial E cor do controle ``uniq``, lidos dele. Campos ``None`` = não sei.

    **Nunca levanta.** Sem aparelho, sem permissão, com firmware que não responde
    ou com código fora do mapa, os dois campos saem ``None`` — e a tela escreve o
    nome do MODELO no lugar (:func:`nome_do_aparelho`), que o ``modelo`` desta
    resposta carrega sempre que o nó foi achado, até quando a pergunta falhou.
    Se perguntar de novo adianta, quem diz é ``definitiva`` (ver
    :class:`IdentidadeDeFabrica`).

    **É O MESMO CAMINHO DE SEMPRE, com o serial deixando de ser descartado.** O
    :func:`ler_pelo_cabo` passou a delegar aqui: um transporte só, uma trava só,
    um lugar só onde o ``ioctl`` acontece. Duas rotas para o mesmo report seriam
    duas chances de uma delas passar sem a trava.

    ``perguntar`` é o ponto único de injeção do transporte. Sem ele a função fala
    com o ``hidraw`` de verdade; com ele, o teste exercita a decodificação inteira
    sem encostar em aparelho nenhum — e sem que uma suíte distraída mande comando
    de fábrica para os controles dela.

    **O serial vem CRU, e é de propósito**: quem o publica decide se ele cabe na
    tela. Ele identifica o aparelho de forma única, como um MAC — a régua de
    anonimato desta casa vale para ele do mesmo jeito.

    **O NOME DIZ "PELO CABO" E ELA LÊ PELOS DOIS** desde 02/09/2026
    (``ONDA-CONEXOES-11``): o comando é o mesmo, só o envelope muda. Renomeá-la
    mexeria em ``interface/mesa_viva.py``, ``daemon/ipc_handlers.py`` e
    ``app/actions/config/secao_controles.py``, que são de outras frentes.
    """
    alvo = alvo_do_controle(uniq, raiz=raiz, listar=listar, ler=ler, resolver=resolver)
    if alvo is None:
        # FALHA, e não «não pode», de propósito: o nó que ainda não nasceu e o
        # aparelho de outro fabricante chegam aqui iguais. Nenhum byte sai sem
        # alvo, e a agenda desiste sozinha depois do último degrau do recuo.
        return IdentidadeDeFabrica(motivo="nenhum DualSense físico com este endereço")
    pedido = montar_pedido()
    if alvo.transporte == RADIO:
        # Pelo rádio o feature report vai assinado, e o CRC NÃO É OPCIONAL:
        # medido em 02/09/2026, sem assinatura o firmware devolve `errno 5`, o
        # mesmo que a semente errada de 23/08 devolvia.
        pedido = envelope_de_radio(pedido)
    conversa = perguntar if perguntar is not None else _perguntar_ao_hidraw
    try:
        resposta = conversa(alvo.caminho, pedido)
    except PedidoRecusadoError:
        # A trava mordeu. Isso é sucesso da trava, não da leitura: NENHUM byte
        # chegou ao aparelho, e é exatamente o que se quer de uma trava que erra.
        logger.warning(
            "cor_do_plastico_pedido_recusado",
            caminho=alvo.caminho,
            transporte=alvo.transporte,
        )
        return IdentidadeDeFabrica(
            nao_pode=True, motivo="a trava recusou o pedido", modelo=alvo.modelo
        )
    except Exception as erro:  # defensivo — a leitura jamais derruba a janela
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
        # A porta que não abriu e o `ioctl` que estourou chegam aqui iguais; o
        # log de `_perguntar_ao_hidraw` diz qual dos dois.
        return IdentidadeDeFabrica(motivo="o aparelho não respondeu", modelo=alvo.modelo)
    serial = serial_de(resposta)
    if serial is None:
        return IdentidadeDeFabrica(
            motivo="a resposta veio sem o eco do pedido", modelo=alvo.modelo
        )
    # A COR PODE SER `None` COM O SERIAL PRESENTE, e isso não é defeito: o
    # mapa tem 28 modelos e a Sony fabrica edições novas sem avisar. Um serial
    # legível com código fora do mapa é "sei qual aparelho é, não sei a cor
    # dele" — e a tela escreve o nome do modelo, nunca «Não sei».
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
    """A cor do plástico do controle ``uniq``, lida dele. ``None`` = não sei.

    Embrulho de :func:`ler_identidade_pelo_cabo` — mesmo contrato de sempre, e
    é por isso que ele fica: a aba Configurações e o `mesa_viva.LeitorDeCor`
    pedem a COR, não o serial, e obrigá-los a desembrulhar seria espalhar a
    estrutura nova por quem não precisa dela.
    """
    return ler_identidade_pelo_cabo(
        uniq, raiz=raiz, listar=listar, ler=ler, perguntar=perguntar, resolver=resolver
    ).cor


# ---------------------------------------------------------------------------
# A nova tentativa — UM dono, chamado pela janela e pelo daemon
# ---------------------------------------------------------------------------

#: O recuo entre uma leitura que FALHOU e a seguinte: três novas tentativas, e
#: depois desiste até o controle sair da mesa e voltar.
RECUO_DA_NOVA_TENTATIVA: tuple[float, ...] = (5.0, 30.0, 120.0)


class AgendaDaPergunta:
    """Quando se pode perguntar a identidade de um ``uniq`` — e quando não.

    A-FITA-PERDEU-O-MODELO-E-A-COR-01, 22/09/2026. A janela
    (``interface/mesa_viva.LeitorDeCor``) e o daemon
    (``daemon/ipc_handlers._identidade_de_fabrica``) guardavam a primeira
    resposta PARA SEMPRE, e a falha de um instante virava «este controle não
    tem cor». Medido no ``interface.log`` e no journal dela: a janela das 23:36
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
