"""As ENTRADAS USB da máquina — inclusive as que estão VAZIAS.

O PROBLEMA QUE ESTE MÓDULO RESOLVE
-----------------------------------

``censo_do_barramento.py`` enxerga **aparelho**. Uma entrada sem nada encaixada
não tem aparelho, logo não existe para ele — e é exatamente a entrada que a
calibração precisa mostrar, porque é a única que nenhuma leitura alcança
sozinha (``CALIBRAR-AS-ENTRADAS-01`` §1).

O que torna a tela possível é uma medição de 25/08/2026: **o nó da entrada
existe com a entrada vazia**. ``state`` responde em todos eles — ``configured``
quando há aparelho, ``not attached`` quando não há. Nesta bancada são 22 nós de
raiz, e a leitura custa 6,87 ms.

O NÓ NÃO É O BURACO — E ESSA É A ARMADILHA CENTRAL
---------------------------------------------------

Um buraco USB 3.x do gabinete aparece no ``/sys`` como **dois** nós de entrada:
um no hub-raiz 2.0 e outro no 3.x, amarrados pelo symlink ``peer``. Medido nesta
bancada em 25/08/2026::

    usb1-port5  peer -> usb2-port1     (nenhum dos dois com aparelho)
    usb1-port6  peer -> usb2-port2     (o mouse, do lado 2.0)
    usb3-portN  peer -> usb4-portN     (as quatro internas)

O DualSense é 2.0 e **sempre** enumera no lado 2.0. Contar nós daria 22 buracos
onde existem 15; e chamar ``usb2-port2`` de "vazia" mandaria ela encaixar o cabo
num buraco que já tem o mouse dela dentro. Por isso:

* :func:`listar_entradas` devolve **nós**, que é o que o kernel publica;
* :func:`furos` agrupa os nós pelo ``peer`` e devolve **buracos**;
* :func:`vazias` devolve buraco, nunca nó — e um buraco só está vazio quando
  **todos** os seus nós estão.

O QUE NÃO SE DERIVA DAQUI
--------------------------

**A frente do gabinete não é dedutível.** Medido em 25/08/2026: ``usb1-port3``
(teclado) e ``usb1-port6`` (mouse) são byte a byte iguais nos três campos que o
kernel decodifica — ``panel=right``, ``horizontal_position=left``,
``vertical_position=lower`` — e a tabela ACPI desta placa nunca diz ``front``
nem ``back``. O lugar é DECLARADO pela pessoa; este módulo só lê o que existe.

**"Esta entrada é azul" também não sai do ``peer``.** Há porta de raiz
SuperSpeed sem ``peer`` nesta máquina, e onde o ``peer`` aparece em quantidade
ele é o pareamento posicional padrão do kernel, não um fato do firmware. O que
este módulo responde é :attr:`Furo.rapido`, e ele é **três estados**: um buraco
é rápido se qualquer nó dele mora num hub SuperSpeed, e ``None`` quando o
``speed`` do hub não pôde ser lido — na dúvida, "não sei".

O HUB QUE SUMIU É ESTADO DE PRIMEIRA CLASSE
--------------------------------------------

Quando o hub externo é desplugado (aconteceu às 02h36 de 25/08/2026), os 16 nós
dele **deixam de existir** no ``/sys``. Este módulo não inventa: eles somem da
leitura. Quem guarda o LUGAR é o mapa declarado; quem diz o que está lá agora é
esta leitura. :func:`furo_declarado` é a ponte entre os dois, e ela devolve
``None`` — que significa *"o lugar existe e o barramento não o mostra agora"*, e
nunca *"a entrada não existe"*.

UNIVERSALIDADE E ISOLAMENTO
----------------------------

Funções puras: sem GTK, sem IPC, sem ``/dev``, sem subprocesso, sem root. A raiz
do ``/sys`` e os três leitores entram por argumento, **nunca por constante de
módulo** — constante é avaliada na importação, antes de qualquer isolamento de
bateria, e é a cicatriz que o ``CANARIO-FS-01`` (``tests/conftest.py``) guarda.
É o mesmo contrato de ``censo_do_barramento.ler_o_barramento``.
"""
from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field

#: Onde o kernel publica o barramento. Default de ARGUMENTO, nunca constante
#: usada direto — ver o cabeçalho.
RAIZ_USB_PADRAO = "/sys/bus/usb/devices"

#: O ``state`` de uma entrada sem nada encaixado. É a palavra do kernel, e é o
#: pilar da tela inteira: sem ela, entrada vazia seria invisível.
ESTADO_VAZIO = "not attached"

#: O ``state`` de uma entrada com aparelho já configurado. Existe para a tela
#: ter palavra; o código NUNCA testa por ele para decidir se está vazio — um nó
#: em ``powered`` (no meio da enumeração) não está vazio e também não é este.
ESTADO_OCUPADO = "configured"

#: SuperSpeed começa em 5 Gbps. Abaixo disso o hub é 2.0 e o buraco não é azul.
VELOCIDADE_SUPERSPEED_MBPS = 5000.0

#: ``usb1-port3`` (entrada de hub-raiz) e ``3-1-port2`` (entrada de hub comum).
#: Os dois grupos são o hub que hospeda e o número da entrada nele.
_NO_DE_ENTRADA = re.compile(r"^(usb[0-9]+|[0-9]+-[0-9]+(?:\.[0-9]+)*)-port([0-9]+)$")

#: ``1-3``, ``3-1.2`` — o nome de kernel de um APARELHO. Serve para não
#: confundir o alvo de um symlink com o nome do próprio arquivo quando ele não
#: existe (ver :func:`_alvo_do_link`).
_NOME_DE_APARELHO = re.compile(r"^[0-9]+-[0-9]+(?:\.[0-9]+)*$")

#: ``usb1`` -> ``1``. O hub-raiz é o único cujo nome não é ``busnum-devpath``.
_HUB_RAIZ = re.compile(r"^usb([0-9]+)$")


@dataclass(frozen=True)
class NoDeEntrada:
    """Um **nó** de entrada do ``/sys`` — não necessariamente um buraco.

    ``no`` é o nome do kernel (``usb1-port5``), que é a chave estável: ele não
    muda entre boots e é o que o ``peer`` de outro nó aponta.

    ``aparelho`` é o nome de kernel do que está encaixado (``1-3``), lido do
    symlink ``device`` — ``""`` quando não há nada. ``par`` é o outro lado do
    mesmo buraco, lido do symlink ``peer``, e ``""`` quando o buraco tem um nó
    só.

    ``painel`` segue a regra de ``censo_do_barramento._painel``: ``""`` quando o
    kernel responde ``unknown`` ou quando o arquivo não existe. ``ausência é
    resposta``, e ela é a maior parte das respostas aqui — nesta bancada os oito
    nós de ``usb3``/``usb4`` não publicam painel nenhum.

    ``tipo_de_encaixe`` é o ``connect_type`` CRU, ``unknown`` incluído: ali a
    palavra "desconhecido" é informação (nesta bancada é o que separa as
    entradas internas das de gabinete), e apagá-la seria jogar fora medição.
    """

    no: str
    caminho_sysfs: str
    hub: str
    numero: int
    estado: str = ""
    tipo_de_encaixe: str = ""
    painel: str = ""
    posicao_horizontal: str = ""
    posicao_vertical: str = ""
    par: str = ""
    aparelho: str = ""
    velocidade_mbps: float = 0.0
    excesso_de_corrente: int | None = None

    @property
    def vazio(self) -> bool:
        """``True`` só quando o kernel DIZ ``not attached``.

        Estado ausente ou que este módulo não conhece **não** é vazio. A
        assimetria é de propósito: dizer "vazia" errado manda uma pessoa se
        ajoelhar atrás do gabinete para encaixar um cabo onde já tem aparelho.
        """
        return self.estado == ESTADO_VAZIO


@dataclass(frozen=True)
class Furo:
    """Um buraco do gabinete — **um ou dois** nós de entrada.

    É o que a pessoa enxerga e o que a caminhada visita. ``nos`` tem dois
    elementos exatamente quando o buraco é 3.x e o kernel publicou o ``peer``.
    """

    nos: tuple[str, ...] = ()
    entradas: tuple[NoDeEntrada, ...] = field(default_factory=tuple)
    aparelho: str = ""
    painel: str = ""
    tipo_de_encaixe: str = ""

    @property
    def vazio(self) -> bool:
        """``True`` quando **todos** os nós deste buraco dizem ``not attached``.

        O DualSense é 2.0 e enumera no lado 2.0: com o mouse dela em
        ``usb1-port6``, o par ``usb2-port2`` responde ``not attached`` e o
        buraco NÃO está vazio. Perguntar por nó em vez de por buraco é o defeito
        que esta propriedade existe para não deixar acontecer.
        """
        return bool(self.entradas) and all(e.vazio for e in self.entradas)

    @property
    def rapido(self) -> bool | None:
        """O buraco alcança SuperSpeed? ``None`` = não deu para saber.

        ``True`` quando QUALQUER nó mora num hub de 5 Gbps ou mais. ``None``
        quando nenhum nó teve a velocidade do hub lida — e aí o produto diz
        "não sei", que é a regra do §5 da sprint.
        """
        if any(e.velocidade_mbps >= VELOCIDADE_SUPERSPEED_MBPS for e in self.entradas):
            return True
        if all(e.velocidade_mbps <= 0 for e in self.entradas):
            return None
        return False


def listar_entradas(
    *,
    raiz_usb: str = RAIZ_USB_PADRAO,
    listar: Callable[[str], list[str]] = os.listdir,
    ler: Callable[[str], str] | None = None,
    real: Callable[[str], str] = os.path.realpath,
) -> tuple[NoDeEntrada, ...]:
    """Todos os nós de entrada da máquina, ordenados por hub e número.

    Uma varredura, um ponto de injeção — o mesmo contrato de
    ``ler_o_barramento``. Chamada ao abrir a janela de calibração e no tique de
    2 Hz DENTRO dela (custo medido: 6,87 ms, ~1,4% de um núcleo). A regra
    "nunca em tique" vale para a aba montada, não para uma janela modal que a
    pessoa abriu de propósito.

    Os nós de entrada não moram no diretório do hub: eles são filhos da
    INTERFACE dele (``usb1/1-0:1.0/usb1-port3``). Por isso a varredura entra
    pelas interfaces, que ``/sys/bus/usb/devices`` já lista — as mesmas que o
    censo descarta por não terem ``idVendor``.

    ``/sys`` ausente ou ilegível devolve tupla vazia. A ausência do barramento é
    uma resposta sobre a máquina, não um defeito do produto — e é o que
    acontece em contêiner e sob sandbox.
    """
    leitor = _ler_texto if ler is None else ler
    try:
        nomes = sorted(listar(raiz_usb))
    except OSError:
        return ()

    velocidades = _velocidade_por_hub(nomes, raiz_usb, leitor=leitor, real=real)
    achados: dict[str, NoDeEntrada] = {}
    for interface in (nome for nome in nomes if ":" in nome):
        caminho_da_interface = real(os.path.join(raiz_usb, interface))
        try:
            filhos = listar(caminho_da_interface)
        except OSError:
            # Interface que sumiu entre o `listdir` da raiz e este — o hub foi
            # desplugado no meio da leitura. Não é erro: é a mesa mudando.
            continue
        for filho in filhos:
            casado = _NO_DE_ENTRADA.match(filho)
            if casado is None or filho in achados:
                continue
            achados[filho] = _ler_um_no(
                filho,
                os.path.join(caminho_da_interface, filho),
                hub=casado.group(1),
                numero=int(casado.group(2)),
                velocidades=velocidades,
                leitor=leitor,
                real=real,
            )
    return tuple(sorted(achados.values(), key=lambda no: _ordem_do_no(no.no)))


def furos(entradas: Sequence[NoDeEntrada]) -> tuple[Furo, ...]:
    """Os nós agrupados em BURACOS, pelo symlink ``peer``.

    Nesta bancada em 25/08/2026: 22 nós, 7 pares, **15 buracos**.

    O ``peer`` do kernel é sempre recíproco e sempre de dois. Um ``peer`` que
    aponta para nó que não está na leitura (o outro lado num hub que acabou de
    sumir) não junta nada: o nó fica sozinho, que é a verdade do momento.
    """
    por_no = {entrada.no: entrada for entrada in entradas}
    juntados: set[str] = set()
    saida: list[Furo] = []
    for entrada in sorted(entradas, key=lambda no: _ordem_do_no(no.no)):
        if entrada.no in juntados:
            continue
        grupo = [entrada]
        juntados.add(entrada.no)
        par = por_no.get(entrada.par)
        if par is not None and par.no not in juntados:
            grupo.append(par)
            juntados.add(par.no)
        saida.append(_montar_furo(grupo))
    return tuple(saida)


def vazias(entradas: Sequence[NoDeEntrada]) -> tuple[Furo, ...]:
    """Os BURACOS sem nada encaixado — a caminhada da fase em pé, e só ela.

    Devolve buraco, nunca nó: mandar a pessoa a ``usb2-port2`` porque aquele nó
    diz ``not attached`` seria mandá-la ao buraco onde o mouse dela está.

    Entrada ocupada não precisa de caminhada nenhuma — o aparelho que está nela
    já diz qual entrada é (§2.3 e F-2). Numa mesa toda ocupada esta lista é
    vazia, e a fase em pé simplesmente não acontece.
    """
    return tuple(furo for furo in furos(entradas) if furo.vazio)


def entrada_de(
    caminho: str,
    entradas: Sequence[NoDeEntrada],
    *,
    raiz_usb: str = RAIZ_USB_PADRAO,
    real: Callable[[str], str] = os.path.realpath,
) -> Furo | None:
    """O buraco onde um aparelho está — ``None`` quando não dá para dizer.

    ``caminho`` é o nome de kernel do aparelho (``1-3``, ``3-1.2``), a mesma
    palavra de ``censo_do_barramento.Aparelho.nome_do_kernel``.

    Dois caminhos, e a ordem importa. O primeiro é o symlink
    ``<dispositivo>/port``, que é o próprio aparelho dizendo em que nó ele está
    — é o que ``censo_do_barramento.py:447`` já atravessa hoje para ler
    ``port/over_current_count``, e custa um ``realpath``. O segundo é o índice
    invertido da leitura que já está na mão, para quando o ``port`` não existe.

    A busca final é pela LISTA DE NÓS do buraco, nunca por uma chave montada: o
    F-5 da sprint mostrou que uma chave sem o ``busnum`` colide o lado 2.0 com o
    lado 3.0 do mesmo controlador, que são dois nós fisicamente diferentes.
    """
    alvo = _alvo_do_link(
        os.path.join(raiz_usb, caminho), "port", _NO_DE_ENTRADA, real=real
    )
    if not alvo:
        alvo = next((e.no for e in entradas if e.aparelho == caminho), "")
    if not alvo:
        return None
    return next((furo for furo in furos(entradas) if alvo in furo.nos), None)


def furo_declarado(
    nos: Sequence[str], entradas: Sequence[NoDeEntrada]
) -> Furo | None:
    """O buraco que o MAPA declarou, resolvido contra a leitura de AGORA.

    ``None`` não quer dizer "essa entrada não existe": quer dizer **"o lugar
    está no mapa e o barramento não o mostra agora"** — o hub foi desplugado, e
    esse é o estado real dela desde as 02h36 de 25/08/2026. O mapa guarda o
    LUGAR; quem deriva o que está lá é esta leitura, a cada abertura.

    A comparação é por INTERSEÇÃO de nós, não por igualdade: um buraco 3.x
    declarado com dois nós continua sendo o mesmo buraco quando o kernel de hoje
    publica um só (``peer`` ausente é comum em porta de raiz SuperSpeed).
    """
    procurados = set(nos)
    if not procurados:
        return None
    return next(
        (furo for furo in furos(entradas) if procurados & set(furo.nos)), None
    )


# ---------------------------------------------------------------------------
# Interno
# ---------------------------------------------------------------------------


def _ler_um_no(
    nome: str,
    caminho: str,
    *,
    hub: str,
    numero: int,
    velocidades: dict[str, float],
    leitor: Callable[[str], str],
    real: Callable[[str], str],
) -> NoDeEntrada:
    """Os atributos de um nó de entrada, mais os dois symlinks que o amarram."""
    return NoDeEntrada(
        no=nome,
        caminho_sysfs=caminho,
        hub=hub,
        numero=numero,
        estado=_campo(caminho, "state", leitor),
        tipo_de_encaixe=_campo(caminho, "connect_type", leitor),
        painel=_painel(_campo(caminho, "physical_location/panel", leitor)),
        posicao_horizontal=_campo(
            caminho, "physical_location/horizontal_position", leitor
        ),
        posicao_vertical=_campo(
            caminho, "physical_location/vertical_position", leitor
        ),
        par=_alvo_do_link(caminho, "peer", _NO_DE_ENTRADA, real=real),
        aparelho=_alvo_do_link(caminho, "device", _NOME_DE_APARELHO, real=real),
        velocidade_mbps=velocidades.get(hub, 0.0),
        excesso_de_corrente=_talvez_inteiro(
            _campo(caminho, "over_current_count", leitor)
        ),
    )


def _velocidade_por_hub(
    nomes: Sequence[str],
    raiz_usb: str,
    *,
    leitor: Callable[[str], str],
    real: Callable[[str], str],
) -> dict[str, float]:
    """``{"usb1": 480.0, "usb2": 10000.0, ...}`` — uma leitura por hub.

    É o único jeito honesto de responder :attr:`Furo.rapido`: a velocidade mora
    no hub, não na entrada. Hub cujo ``speed`` não é legível fica de fora, e o
    buraco dele responde ``None``.
    """
    saida: dict[str, float] = {}
    for nome in nomes:
        if ":" in nome:
            continue
        bruto = _campo(real(os.path.join(raiz_usb, nome)), "speed", leitor)
        try:
            saida[nome] = float(bruto)
        except ValueError:
            continue
    return saida


def _montar_furo(grupo: Sequence[NoDeEntrada]) -> Furo:
    """Um buraco a partir dos seus nós — o que eles concordam, e só isso."""
    entradas = tuple(sorted(grupo, key=lambda no: _ordem_do_no(no.no)))
    return Furo(
        nos=tuple(entrada.no for entrada in entradas),
        entradas=entradas,
        aparelho=next((e.aparelho for e in entradas if e.aparelho), ""),
        painel=_concordam(entrada.painel for entrada in entradas),
        tipo_de_encaixe=_concordam(
            entrada.tipo_de_encaixe for entrada in entradas
        ),
    )


def _concordam(valores: Iterable[str]) -> str:
    """O único valor não vazio em que os nós concordam — ``""`` se discordam.

    Ausência não é desacordo: um nó que não publica painel e outro que publica
    ``right`` concordam em ``right``. Dois valores diferentes viram ``""``,
    porque inventar um dos dois seria escolher no escuro.
    """
    distintos = {valor for valor in valores if valor}
    return distintos.pop() if len(distintos) == 1 else ""


def _alvo_do_link(
    no: str, atributo: str, forma: re.Pattern[str], *, real: Callable[[str], str]
) -> str:
    """O nome apontado por um symlink de ``/sys`` — ``""`` quando não há link.

    ``os.path.realpath`` de um caminho que não existe devolve o próprio caminho;
    o ``basename`` viraria ``peer`` ou ``device``, que não é nome de nada. Por
    isso o resultado só vale se casar com a FORMA esperada — e assim a ausência
    do symlink e um alvo inesperado dão a mesma resposta honesta: ``""``.
    """
    alvo = os.path.basename(real(os.path.join(no, atributo)))
    return alvo if forma.match(alvo) else ""


def _painel(valor: str) -> str:
    """O painel na palavra do kernel — ``""`` quando ele responde ``unknown``.

    Mesma regra de ``censo_do_barramento._painel``, repetida e não importada:
    lá ela é privada, e um módulo de integração puxar o privado do outro é
    acoplamento que ninguém pediu (o próprio censo diz isso do ``mesa_de_radio``).
    """
    return "" if valor == "unknown" else valor


def _ordem_do_no(nome: str) -> tuple[int, tuple[int, ...], int]:
    """Hubs-raiz primeiro, depois os pendurados; e ``port10`` DEPOIS de ``port2``.

    Ordem alfabética poria ``usb1-port10`` entre a 1 e a 2, e a tela contaria
    "entrada 4 de 15" apontando para o buraco errado.
    """
    casado = _NO_DE_ENTRADA.match(nome)
    if casado is None:  # defensivo — só entra aqui nome que já casou
        return (2, (), 0)
    hub, numero = casado.group(1), int(casado.group(2))
    raiz = _HUB_RAIZ.match(hub)
    if raiz is not None:
        return (0, (int(raiz.group(1)),), numero)
    barramento, _, caminho = hub.partition("-")
    return (
        1,
        (int(barramento), *(int(parte) for parte in caminho.split("."))),
        numero,
    )


def _campo(no: str, atributo: str, ler: Callable[[str], str]) -> str:
    """Um atributo do nó, já sem o ``\\n`` do sysfs — ``""`` se não houver."""
    return ler(os.path.join(no, atributo)).strip()


def _talvez_inteiro(valor: str) -> int | None:
    try:
        return int(valor)
    except ValueError:
        return None


def _ler_texto(caminho: str) -> str:
    """Lê um arquivo de ``/sys``; ``""`` em qualquer erro — sysfs some sob a mão."""
    try:
        with open(caminho, encoding="utf-8", errors="replace") as arquivo:
            return arquivo.read()
    except OSError:
        return ""


__all__ = [
    "ESTADO_OCUPADO",
    "ESTADO_VAZIO",
    "RAIZ_USB_PADRAO",
    "VELOCIDADE_SUPERSPEED_MBPS",
    "Furo",
    "NoDeEntrada",
    "entrada_de",
    "furo_declarado",
    "furos",
    "listar_entradas",
    "vazias",
]
