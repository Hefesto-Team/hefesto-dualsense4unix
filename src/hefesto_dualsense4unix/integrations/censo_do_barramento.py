"""censo_do_barramento.py — o barramento USB inteiro, na palavra do kernel.

O PROBLEMA QUE ESTE MÓDULO RESOLVE
-----------------------------------

``mesa_de_radio.py`` responde três perguntas sobre RÁDIO e recusa todo o resto:
hub não entra, controle no cabo não entra, e o que não emite 2,4 GHz nunca foi
olhado. A decisão dela de 22/08/2026 pede o oposto — *"todo o rádio, hub de
energia, todos os usb, todos os dongles tipo do mouse e teclado, e até webcam ou
microfones extras. tudo de verdade."*

Este módulo é esse censo: **todo dispositivo USB da máquina**, com o que o
``/sys`` dá de graça — sem root, sem subprocesso, sem IPC, sem abrir ``/dev``.
Ele não filtra nada; quem filtra é quem chama.

O QUE O KERNEL CLASSIFICA SOZINHO
----------------------------------

A espécie de cada aparelho não é palpite: ela sai de
``bInterfaceClass``/``SubClass``/``Protocol`` da **interface 0**, medido nesta
bancada em 22/08/2026::

    1-3        25a7:fa07   03/01/02   mouse
    1-4        3554:fa09   03/01/01   teclado
    3-3        05e3:0610   09/00/00   hub
    3-3.1.1    2357:0604   e0/01/01   Bluetooth
    3-3.3      258a:010c   03/01/01   teclado
    4-1        2357:012d   ff/ff/ff   do fabricante — o kernel NÃO nomeia
    4-3        05e3:0626   09/00/00   hub

Por isso o grau. ``GRAU_LIDO`` é *"o kernel disse, e temos palavra para isso"*;
``GRAU_DESCONHECIDO`` é *"ninguém disse"* — a classe ``ff``, em que o fabricante
declinou de classificar, e qualquer código que este módulo não saiba nomear. Os
dois casos guardam o código cru em ``classe`` para a tela mostrar, e nos dois a
tela deixa ela corrigir. **Não há heurística por nome de produto**: o ``4-1``
diz "802.11ac NIC" no ``product`` e isso não o torna Wi-Fi para o produto — a
palavra do fabricante não é classificação do kernel, e adivinhar por texto é
como se erra com confiança.

A CLASSE SAI DA INTERFACE, NÃO DO APARELHO
-------------------------------------------

``bDeviceClass`` vale ``00`` em todo aparelho composto — medido: o mouse, o
teclado e o Wi-Fi desta bancada são todos ``00`` no descritor do aparelho e só
dizem o que são na interface. Ler o descritor do aparelho classificaria a mesa
inteira como "não identificado", com exceção dos hubs.

A interface 0 de um nó ``3-3.1.1`` é ``3-3.1.1:C.0``; a do hub-raiz ``usb3`` é
``3-0:1.0``, porque o sysfs nomeia interface por ``barramento-porta`` e a porta
do raiz é ``0``. Uma regra só cobre os dois: o prefixo é
``f"{busnum}-{devpath}:"``.

TOPOLOGIA
----------

``pai`` é o nó imediatamente acima, e ele **não basta**. Medido em 22/08/2026:
os três adaptadores Bluetooth desta casa NÃO têm o mesmo pai — ``3-3.1.1`` e
``3-3.1.4`` penduram no hub interno ``3-3.1``, e ``3-3.2`` pendura no ``3-3``.
Comparar o pai responderia "estão em hubs diferentes", que é falso no metal: são
o mesmo aparelho de bancada, com um hub encadeado dentro. Quem responde é
``hub_em_comum()``, que sobe a cadeia inteira.

O hub-RAIZ é a exceção que torna a resposta útil: todo aparelho pendura sob um,
sempre, em qualquer PC. ``mesa_de_radio.py`` chegou nela pelo nome
(``^usb[0-9]+$``); aqui a régua é ``devpath == "0"``, que é a mesma medição por
outro lado — porta 0 não existe no barramento, e os quatro ``usbN`` desta
bancada são os únicos nós com ``devpath`` ``0``.

ENERGIA — E O QUE NÃO DÁ PARA SABER
------------------------------------

Sem root o ``/sys`` dá três números e nenhuma medição de corrente:

* ``bMaxPower`` — o que o descritor **pede** da porta, não o que o aparelho
  consome;
* ``power/control`` — ``on`` (autosuspend desligado) ou ``auto``;
* ``port/over_current_count`` — quantas vezes a porta acusou excesso. É o único
  número aqui que registra um evento real, e ``0`` em toda a mesa é uma
  resposta.

**Se o hub tem fonte própria, o sysfs NÃO diz.** Duas medições independentes,
22/08/2026:

1. ``bMaxPower`` não distingue — o hub USB 3.1 alimentado reporta ``0mA`` e o
   USB 2.1 alimentado reporta ``100mA`` (já era a nota de ``mesa_de_radio.py``);
2. o bit de autoalimentado de ``bmAttributes`` é **declaração, não medição** —
   os três adaptadores TP-Link desta bancada declaram ``e0`` (bit ``0x40``
   ligado) e no mesmo descritor pedem ``bMaxPower=500mA`` da porta. Um aparelho
   com fonte própria pode tirar do barramento no máximo uma carga unitária, 100
   mA; pedir 500 e dizer que não depende da porta é o descritor se contradizendo.

Por isso o campo se chama ``autoalimentado_declarado`` e vem acompanhado de
``declaracao_incoerente``. Quem desenhar a tela mostra a declaração como
declaração — nunca como "este hub é alimentado".

UNIVERSALIDADE
---------------

Nada aqui olha nome de máquina, quantidade de aparelhos ou ordem de conexão. A
raiz e os quatro leitores entram por argumento com default do sistema real —
nunca por constante de módulo, que o ``CANARIO-FS-01`` (``tests/conftest.py``)
pega e que impediria fotografar a aba com uma bancada de mentira.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field

#: O grau da classificação. ``lido`` = o kernel disse e temos palavra para
#: isso; ``desconhecido`` = ninguém disse (classe ``ff``, ou um código que este
#: módulo não sabe nomear). O código cru fica em ``Aparelho.classe`` nos dois
#: casos, e é ele que distingue "o fabricante declinou" de "falta mapa aqui".
GRAU_LIDO = "lido"
GRAU_DESCONHECIDO = "desconhecido"

#: A palavra de quando não há palavra. Vale para ``ff`` e para código sem mapa.
ESPECIE_DESCONHECIDA = "Não identificado"

#: Classe USB de hub, tanto no descritor do aparelho quanto na interface.
CLASSE_HUB = "09"

#: Classe de dispositivo de entrada (HID) e classe de controlador sem fio.
_CLASSE_ENTRADA = "03"
_CLASSE_SEM_FIO = "e0"

#: A porta ``0`` não existe num barramento USB: quem tem ``devpath`` ``0`` é o
#: hub-raiz do controlador xHCI. Medido em 22/08/2026 — os quatro ``usbN`` desta
#: bancada são os únicos nós assim.
_DEVPATH_DO_RAIZ = "0"

#: Uma carga unitária, em mA. É o teto que um aparelho com fonte própria pode
#: tirar da porta; pedir mais e ainda declarar autoalimentado é contradição do
#: descritor, e nesta bancada os três TP-Link fazem exatamente isso (500 mA).
_CARGA_UNITARIA_MA = 100

#: Bit 6 de ``bmAttributes`` — "autoalimentado", na declaração do descritor.
_BIT_AUTOALIMENTADO = 0x40

#: O último ``0000:xx:xx.x`` da cadeia sysfs é o controlador xHCI onde o
#: aparelho pendura. Mesmo algoritmo de ``mesa_de_radio.py``, repetido e não
#: importado: lá ele é privado, e um módulo de integração puxar o privado do
#: outro é acoplamento que ninguém pediu.
_CONTROLADOR_PCI = re.compile(r"0000:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9a-f]")

#: ``bMaxPower`` chega como ``500mA``; só o número interessa.
_CORRENTE = re.compile(r"^([0-9]+)")

#: Classe da interface -> palavra de gente. Fora deste mapa a resposta é
#: ``ESPECIE_DESCONHECIDA`` com grau ``desconhecido``: um código sem palavra na
#: tela é pior que dizer "não sei", porque parece informação.
_ESPECIE_POR_CLASSE: dict[str, str] = {
    "01": "Áudio",
    "02": "Rede",
    _CLASSE_ENTRADA: "Aparelho de entrada",
    "05": "Interface física",
    "06": "Imagem",
    "07": "Impressora",
    "08": "Armazenamento",
    CLASSE_HUB: "Hub",
    "0a": "Rede (dados)",
    "0b": "Cartão inteligente",
    "0d": "Segurança de conteúdo",
    "0e": "Câmera",
    "0f": "Saúde",
    "10": "Áudio e vídeo",
    "11": "Painel de vídeo",
    "12": "Ponte USB-C",
    "dc": "Diagnóstico",
    _CLASSE_SEM_FIO: "Sem fio",
    "ef": "Diversos",
    "fe": "Específico do programa",
}


@dataclass(frozen=True)
class Energia:
    """O que o ``/sys`` diz sobre energia sem root — e só isso.

    ``corrente_pedida_ma`` é o ``bMaxPower`` do descritor: o que o aparelho
    **pede**, não o que ele gasta. ``None`` quando o arquivo não existe ou vem
    ilegível, que é diferente de ``0``.

    ``autoalimentado_declarado`` é o bit ``0x40`` de ``bmAttributes``, e o nome
    é longo de propósito: é declaração do descritor, e nesta bancada ela mente.
    """

    corrente_pedida_ma: int | None = None
    controle: str = ""
    autoalimentado_declarado: bool | None = None
    excesso_de_corrente: int | None = None

    @property
    def declaracao_incoerente(self) -> bool:
        """Declara fonte própria E pede mais de uma carga unitária da porta.

        Medido em 22/08/2026 nos três TP-Link ``2357:0604``: ``bmAttributes=e0``
        com ``bMaxPower=500mA``. Quem consumir este módulo precisa ver a
        contradição junto com a declaração, senão vai desenhar "hub alimentado"
        em cima de um bit que não sustenta a afirmação.
        """
        if not self.autoalimentado_declarado:
            return False
        return (self.corrente_pedida_ma or 0) > _CARGA_UNITARIA_MA


@dataclass(frozen=True)
class Aparelho:
    """Um dispositivo USB, com tudo que o kernel publica sobre ele.

    ``no`` é o caminho real no sysfs — a mesma convenção de
    ``mesa_de_radio.Adaptador.no``, para que os dois módulos falem do mesmo
    aparelho com a mesma palavra. ``nome_do_kernel`` é o apelido curto
    (``3-3.1.1``), que é o que cabe na tela.

    ``fabricante`` e ``produto`` são texto do descritor e podem vir vazios: os
    TP-Link desta bancada publicam ``manufacturer`` com **um espaço** dentro.
    Espaço em branco é ausência, e ausência é resposta.
    """

    no: str
    nome_do_kernel: str
    vid: str = ""
    pid: str = ""
    fabricante: str = ""
    produto: str = ""
    velocidade_mbps: float = 0.0
    busnum: int = 0
    devpath: str = ""
    pai: str = ""
    painel: str = ""
    controlador_pci: str = ""
    classe: str = ""
    subclasse: str = ""
    protocolo: str = ""
    origem_da_classe: str = ""
    especie: str = ESPECIE_DESCONHECIDA
    grau: str = GRAU_DESCONHECIDO
    e_hub: bool = False
    e_raiz: bool = False
    atras_de_hub: bool = False
    energia: Energia = field(default_factory=Energia)


@dataclass(frozen=True)
class Barramento:
    """Um controlador USB inteiro — um ``usbN`` e tudo que pendura nele."""

    no: str
    nome_do_kernel: str
    controlador_pci: str = ""
    velocidade_mbps: float = 0.0
    aparelhos: tuple[str, ...] = ()


@dataclass(frozen=True)
class Censo:
    """A leitura inteira, de uma vez — um ponto de injeção, não seis."""

    aparelhos: tuple[Aparelho, ...] = ()
    barramentos: tuple[Barramento, ...] = ()

    def conectados(self) -> tuple[Aparelho, ...]:
        """Tudo menos os hubs-raiz — o que uma pessoa chamaria de aparelho.

        Existe para que ninguém precise lembrar do filtro. Foi por esquecê-lo
        que a primeira leitura de ``mesa_de_radio`` pôs ``1d6b:0002`` na tabela
        de antenas: o hub-raiz não é aparelho, é o próprio barramento.
        """
        return tuple(a for a in self.aparelhos if not a.e_raiz)

    def aparelho(self, no: str) -> Aparelho | None:
        """O aparelho de um caminho, ou ``None``. Busca linear: são dezenas."""
        for atual in self.aparelhos:
            if atual.no == no:
                return atual
        return None


def ler_o_barramento(
    *,
    raiz_usb: str = "/sys/bus/usb/devices",
    listar: Callable[[str], list[str]] = os.listdir,
    ler: Callable[[str], str] | None = None,
    real: Callable[[str], str] = os.path.realpath,
) -> Censo:
    """Uma varredura de ``/sys``, e o barramento inteiro sai dela.

    Chamada ao entrar na aba e no botão de reexame, nunca em tique: os tiques
    desta casa são de 100 ms, 500 ms e 2 s, e pendurar uma varredura de
    barramento em qualquer um deles é gastar CPU relendo o que não muda.

    ``/sys`` ausente ou ilegível (contêiner, sandbox) devolve censo vazio. Não
    pode derrubar a janela: a ausência do barramento é uma resposta sobre a
    máquina, não um defeito do produto.
    """
    leitor = _ler_texto if ler is None else ler
    try:
        nomes = sorted(listar(raiz_usb))
    except OSError:
        return Censo()

    #: `1-3:1.0` é INTERFACE, não dispositivo: ela não tem `idVendor` e
    #: multiplicaria o mesmo aparelho por quantas funções ele expuser.
    nos = [nome for nome in nomes if ":" not in nome]
    interfaces = [nome for nome in nomes if ":" in nome]

    caminhos = {nome: real(os.path.join(raiz_usb, nome)) for nome in nos}
    nome_por_caminho = {caminho: nome for nome, caminho in caminhos.items()}

    brutos = {
        nome: _ler_um(
            nome, caminho, raiz_usb, interfaces, leitor=leitor, real=real
        )
        for nome, caminho in caminhos.items()
    }
    aparelhos = tuple(
        sorted(
            (
                _montar(bruto, nome_por_caminho, brutos)
                for bruto in brutos.values()
            ),
            key=_ordem,
        )
    )
    return Censo(aparelhos=aparelhos, barramentos=_barramentos(aparelhos))


def cadeia_de_hubs(censo: Censo, no: str) -> tuple[str, ...]:
    """Os hubs acima deste aparelho, do mais perto ao mais longe.

    Sem os hubs-raiz: eles não são aparelho de bancada, e incluí-los faria dois
    dispositivos quaisquer do mesmo controlador parecerem "no mesmo hub".

    Medido: ``3-3.1.1`` devolve ``(3-3.1, 3-3)`` — dois hubs encadeados dentro
    do mesmo aparelho de bancada.
    """
    por_no = {a.no: a for a in censo.aparelhos}
    atual = por_no.get(no)
    cadeia: list[str] = []
    vistos: set[str] = set()
    while atual is not None and atual.pai and atual.pai not in vistos:
        vistos.add(atual.pai)
        pai = por_no.get(atual.pai)
        if pai is None:
            break
        if pai.e_hub and not pai.e_raiz:
            cadeia.append(pai.no)
        atual = pai
    return tuple(cadeia)


def hub_em_comum(censo: Censo, nos: Sequence[str]) -> str:
    """O hub mais próximo que está acima de TODOS estes aparelhos — ou ``""``.

    É a pergunta que a tela faz — *"os três rádios de controle estão no mesmo
    hub?"* — e ela **não** se responde comparando o pai. Medido em 22/08/2026:
    os três adaptadores desta casa têm dois pais diferentes (``3-3.1`` e
    ``3-3``) e um único hub em comum, o ``3-3``. Comparar o pai diria que não,
    e diria errado.
    """
    if not nos:
        return ""
    cadeias = [cadeia_de_hubs(censo, no) for no in nos]
    if any(not cadeia for cadeia in cadeias):
        return ""
    comuns = set(cadeias[0]).intersection(*(set(c) for c in cadeias[1:]))
    for candidato in cadeias[0]:
        if candidato in comuns:
            return candidato
    return ""


def filhos_de(censo: Censo, no: str) -> tuple[Aparelho, ...]:
    """Quem pendura DIRETAMENTE neste nó, em ordem de porta."""
    return tuple(sorted((a for a in censo.aparelhos if a.pai == no), key=_ordem))


def _barramentos(aparelhos: Sequence[Aparelho]) -> tuple[Barramento, ...]:
    """Um ``Barramento`` por hub-raiz, com tudo que pendura abaixo dele.

    O agrupamento é por ``busnum`` e não por controlador PCI: um controlador
    xHCI publica DOIS barramentos (o 2.0 e o 3.0). Medido nesta bancada —
    ``usb3`` e ``usb4`` são ambos ``0000:0c:00.3``, e juntá-los esconderia que
    o aparelho está no lado 2.0 ou no lado 3.0.
    """
    achados: list[Barramento] = []
    for raiz in sorted((a for a in aparelhos if a.e_raiz), key=_ordem):
        abaixo = tuple(
            a.no
            for a in sorted(aparelhos, key=_ordem)
            if a.busnum == raiz.busnum and not a.e_raiz
        )
        achados.append(
            Barramento(
                no=raiz.no,
                nome_do_kernel=raiz.nome_do_kernel,
                controlador_pci=raiz.controlador_pci,
                velocidade_mbps=raiz.velocidade_mbps,
                aparelhos=abaixo,
            )
        )
    return tuple(achados)


@dataclass(frozen=True)
class _Bruto:
    """O que se lê de um nó antes de saber quem é o pai dele."""

    nome: str
    caminho: str
    campos: dict[str, str]
    classe: str
    subclasse: str
    protocolo: str
    origem: str
    controlador_pci: str


def _ler_um(
    nome: str,
    caminho: str,
    raiz_usb: str,
    interfaces: Iterable[str],
    *,
    leitor: Callable[[str], str],
    real: Callable[[str], str],
) -> _Bruto:
    """Todos os atributos de um nó, mais a classe da interface 0."""
    campos = {
        atributo: _campo(caminho, atributo, leitor)
        for atributo in (
            "idVendor",
            "idProduct",
            "manufacturer",
            "product",
            "speed",
            "busnum",
            "devpath",
            "bDeviceClass",
            "bMaxPower",
            "bmAttributes",
            "physical_location/panel",
            "power/control",
            "port/over_current_count",
        )
    }
    classe, subclasse, protocolo, origem = _classe_da_interface(
        nome,
        campos["busnum"],
        campos["devpath"],
        raiz_usb,
        interfaces,
        leitor=leitor,
        real=real,
    )
    if not classe:
        # Sem interface 0 — aparelho ainda não configurado. O descritor do
        # APARELHO é o que sobra, e continua sendo o kernel falando; só a
        # origem muda, e ela vai para a tela junto.
        classe = campos["bDeviceClass"].lower()
        origem = "descritor do aparelho" if classe else ""
    return _Bruto(
        nome=nome,
        caminho=caminho,
        campos=campos,
        classe=classe,
        subclasse=subclasse,
        protocolo=protocolo,
        origem=origem,
        controlador_pci=_controlador_pci(caminho),
    )


def _montar(
    bruto: _Bruto,
    nome_por_caminho: dict[str, str],
    brutos: dict[str, _Bruto],
) -> Aparelho:
    """Um ``Aparelho`` completo — só aqui a topologia já é conhecida."""
    campos = bruto.campos
    devpath = campos["devpath"]
    e_raiz = devpath == _DEVPATH_DO_RAIZ
    pai_nome = nome_por_caminho.get(os.path.dirname(bruto.caminho), "")
    pai = brutos.get(pai_nome)
    especie, grau = _especie(bruto.classe, bruto.subclasse, bruto.protocolo)
    return Aparelho(
        no=bruto.caminho,
        nome_do_kernel=bruto.nome,
        vid=campos["idVendor"].lower(),
        pid=campos["idProduct"].lower(),
        fabricante=campos["manufacturer"],
        produto=campos["product"],
        velocidade_mbps=_decimal(campos["speed"]),
        busnum=_inteiro(campos["busnum"]),
        devpath=devpath,
        pai=pai.caminho if pai is not None else "",
        painel=_painel(campos["physical_location/panel"]),
        controlador_pci=bruto.controlador_pci,
        classe=bruto.classe,
        subclasse=bruto.subclasse,
        protocolo=bruto.protocolo,
        origem_da_classe=bruto.origem,
        especie=especie,
        grau=grau,
        e_hub=bruto.classe == CLASSE_HUB,
        e_raiz=e_raiz,
        atras_de_hub=_atras_de_hub(pai),
        energia=Energia(
            corrente_pedida_ma=_corrente(campos["bMaxPower"]),
            controle=campos["power/control"],
            autoalimentado_declarado=_autoalimentado(campos["bmAttributes"]),
            excesso_de_corrente=_talvez_inteiro(campos["port/over_current_count"]),
        ),
    )


def _atras_de_hub(pai: _Bruto | None) -> bool:
    """O pai é um hub DE VERDADE, e não o hub-raiz do controlador?

    Sem a exceção do raiz, a mesa INTEIRA sai rotulada "em hub", porque todo
    aparelho pendura sob um hub-raiz, sempre, em qualquer PC. É a mesma medição
    que ``mesa_de_radio._atras_de_hub`` já carregava; aqui a régua do raiz é o
    ``devpath`` em vez do nome.
    """
    if pai is None:
        return False
    if pai.campos["devpath"] == _DEVPATH_DO_RAIZ:
        return False
    return pai.classe == CLASSE_HUB


def _classe_da_interface(
    nome: str,
    busnum: str,
    devpath: str,
    raiz_usb: str,
    interfaces: Iterable[str],
    *,
    leitor: Callable[[str], str],
    real: Callable[[str], str],
) -> tuple[str, str, str, str]:
    """``(classe, subclasse, protocolo, origem)`` da interface 0 deste nó.

    O prefixo é ``f"{busnum}-{devpath}:"`` e cobre os dois formatos de uma vez:
    o nó ``3-3.1.1`` tem interfaces ``3-3.1.1:1.0``, e o hub-raiz ``usb3`` —
    cujo nome não parece com nada — tem ``3-0:1.0``. Medido em 22/08/2026: os
    quatro hubs-raiz desta bancada publicam ``N-0:1.0``, classe ``09/00/00``.
    """
    prefixo = f"{busnum}-{devpath}:" if busnum and devpath else f"{nome}:"
    candidatas = sorted(
        alvo
        for alvo in interfaces
        if alvo.startswith(prefixo) and alvo.endswith(".0")
    )
    if not candidatas:
        return "", "", "", ""
    caminho = real(os.path.join(raiz_usb, candidatas[0]))
    return (
        _campo(caminho, "bInterfaceClass", leitor).lower(),
        _campo(caminho, "bInterfaceSubClass", leitor).lower(),
        _campo(caminho, "bInterfaceProtocol", leitor).lower(),
        "interface 0",
    )


def _especie(classe: str, subclasse: str, protocolo: str) -> tuple[str, str]:
    """``(palavra de gente, grau)`` a partir da tripla que o kernel publica.

    Teclado e mouse só se distinguem no PROTOCOLO (``03/01/01`` e ``03/01/02``);
    Bluetooth só se distingue de "sem fio" na subclasse e no protocolo
    (``e0/01/01``). Parar na classe daria "aparelho de entrada" para os dois
    primeiros e "sem fio" para o terceiro — verdadeiro e inútil.
    """
    if classe == _CLASSE_ENTRADA and subclasse == "01":
        if protocolo == "01":
            return "Teclado", GRAU_LIDO
        if protocolo == "02":
            return "Mouse", GRAU_LIDO
    if classe == _CLASSE_SEM_FIO and subclasse == "01" and protocolo == "01":
        return "Bluetooth", GRAU_LIDO
    palavra = _ESPECIE_POR_CLASSE.get(classe, "")
    if palavra:
        return palavra, GRAU_LIDO
    return ESPECIE_DESCONHECIDA, GRAU_DESCONHECIDO


def _painel(valor: str) -> str:
    """O painel do gabinete, na palavra do kernel — ``""`` quando ele não sabe.

    São sete valores possíveis (``top``, ``bottom``, ``left``, ``right``,
    ``front``, ``back``, ``unknown``) e o arquivo simplesmente não existe na
    maioria dos aparelhos, inclusive em todos os que estão atrás de um hub.
    Quem traduz para palavra de tela é a janela.
    """
    return "" if valor == "unknown" else valor


def _autoalimentado(bm_attributes: str) -> bool | None:
    """Bit ``0x40`` de ``bmAttributes``; ``None`` quando o campo não é legível.

    ``None`` e ``False`` são respostas diferentes: uma é "não sei", a outra é
    "o descritor diz que depende da porta".
    """
    try:
        return bool(int(bm_attributes, 16) & _BIT_AUTOALIMENTADO)
    except ValueError:
        return None


def _corrente(valor: str) -> int | None:
    """``500mA`` -> ``500``. ``None`` quando não há campo, que não é ``0``."""
    achado = _CORRENTE.match(valor)
    return int(achado.group(1)) if achado else None


def _controlador_pci(caminho: str) -> str:
    """O último ``0000:xx:xx.x`` da cadeia — o controlador xHCI do aparelho."""
    achados = _CONTROLADOR_PCI.findall(caminho)
    return achados[-1] if achados else ""


def _ordem(alvo: Aparelho | _Bruto) -> tuple[int, tuple[int, ...], str]:
    """Barramento, depois porta a porta, numericamente — ``3.2`` antes de ``3.10``."""
    if isinstance(alvo, Aparelho):
        busnum, devpath, nome = alvo.busnum, alvo.devpath, alvo.nome_do_kernel
    else:
        busnum = _inteiro(alvo.campos["busnum"])
        devpath, nome = alvo.campos["devpath"], alvo.nome
    portas = tuple(_inteiro(parte) for parte in devpath.split(".") if parte)
    return (busnum, portas, nome)


def _decimal(valor: str) -> float:
    """Número do sysfs; ``0.0`` quando o campo não existe ou vem sujo."""
    try:
        return float(valor)
    except ValueError:
        return 0.0


def _inteiro(valor: str) -> int:
    """Inteiro do sysfs; ``0`` quando o campo não existe ou vem sujo."""
    try:
        return int(valor)
    except ValueError:
        return 0


def _talvez_inteiro(valor: str) -> int | None:
    """Inteiro do sysfs; ``None`` quando não há campo — ``0`` é outra coisa."""
    try:
        return int(valor)
    except ValueError:
        return None


def _campo(no: str, atributo: str, ler: Callable[[str], str]) -> str:
    """Um atributo do nó, já sem o ``\\n`` do sysfs — ``""`` se não houver.

    O ``strip()`` também é o que transforma o ``manufacturer`` de um espaço só
    dos TP-Link em ausência de verdade.
    """
    return ler(os.path.join(no, atributo)).strip()


def _ler_texto(caminho: str) -> str:
    """Lê um arquivo de ``/sys``; ``""`` em qualquer erro — sysfs some sob a mão."""
    try:
        with open(caminho, encoding="utf-8", errors="replace") as arquivo:
            return arquivo.read()
    except OSError:
        return ""


__all__ = [
    "CLASSE_HUB",
    "ESPECIE_DESCONHECIDA",
    "GRAU_DESCONHECIDO",
    "GRAU_LIDO",
    "Aparelho",
    "Barramento",
    "Censo",
    "Energia",
    "cadeia_de_hubs",
    "filhos_de",
    "hub_em_comum",
    "ler_o_barramento",
]
