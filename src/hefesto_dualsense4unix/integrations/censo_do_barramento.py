"""censo_do_barramento.py — o barramento USB inteiro, na palavra do kernel.

O PROBLEMA QUE ESTE MÓDULO RESOLVE
-----------------------------------

``mesa_de_radio.py`` responde três perguntas sobre RÁDIO e recusa todo o resto:
hub não entra, controle no cabo não entra, e o que não emite 2,4 GHz nunca foi
olhado. A decisão de 22/08/2026 pede o oposto — *"todo o rádio, hub de
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
from typing import NamedTuple

from hefesto_dualsense4unix.integrations import receptor_sem_fio as _receptor_sem_fio
from hefesto_dualsense4unix.utils.texto_do_sysfs import ler_texto

GRAU_LIDO = "lido"
GRAU_DESCONHECIDO = "desconhecido"

ESPECIE_DESCONHECIDA = "Não identificado"
ESPECIE_CAMERA = "Câmera"
_ESPECIES_QUE_NAO_USAM_A_VELOCIDADE = frozenset({ESPECIE_CAMERA})

LIGADO_COMO_WIFI = "wifi"
LIGADO_COMO_BLUETOOTH = "bluetooth"
LIGADO_COMO_CONTROLE = "controle"
LIGADO_COMO_CAMERA = "camera"
LIGADO_COMO_REDE = "rede"
_ESPECIE_DO_QUE_O_KERNEL_LIGOU = {
    LIGADO_COMO_WIFI: "Wi-Fi",
    LIGADO_COMO_BLUETOOTH: "Bluetooth",
    LIGADO_COMO_CONTROLE: "Controle",
    LIGADO_COMO_CAMERA: ESPECIE_CAMERA,
    LIGADO_COMO_REDE: "Rede",
}
_ORDEM_DO_QUE_O_KERNEL_LIGOU = tuple(_ESPECIE_DO_QUE_O_KERNEL_LIGOU)
_ESPECIES_QUE_O_RECEPTOR_JA_DIZ = frozenset({"Teclado", "Mouse"})
_O_QUE_O_KERNEL_PENDURA = {
    "ieee80211": LIGADO_COMO_WIFI,
    "bluetooth": LIGADO_COMO_BLUETOOTH,
    "video4linux": LIGADO_COMO_CAMERA,
}
_BTN_SOUTH = 0x130
_CLASSES_QUE_NAO_DIZEM = frozenset({"", "ef", "fe", "ff", "e0", "02", "0a"})

CLASSE_HUB = "09"

_CLASSE_ENTRADA = "03"
_CLASSE_SEM_FIO = "e0"

_DEVPATH_DO_RAIZ = "0"

_CARGA_UNITARIA_MA = 100

_BIT_AUTOALIMENTADO = 0x40

_CAPACIDADES_SUPERSPEED = frozenset({0x03, 0x0A})
_CAPACIDADE_CONTAINER_ID = 0x04
_TIPO_DO_BOS = 0x0F
_TIPO_DA_CAPACIDADE = 0x10
_ALTA_VELOCIDADE_MBPS = 480.0
_SUPERSPEED_MBPS = 5000.0

_PORTA = re.compile(r"^(.+)-port([0-9]+)$")

_CONTROLADOR_PCI = re.compile(r"0000:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9a-f]")

_CORRENTE = re.compile(r"^([0-9]+)")

_FILHO_HID = re.compile(r"^[0-9a-fA-F]{4}:[0-9a-fA-F]{4}:[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}$")
_EVENTO = re.compile(r"^event[0-9]+$")

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
    "0e": ESPECIE_CAMERA,
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
    """O que o ``/sys`` diz sobre energia sem root — e só isso."""

    corrente_pedida_ma: int | None = None
    controle: str = ""
    autoalimentado_declarado: bool | None = None
    excesso_de_corrente: int | None = None

    @property
    def declaracao_incoerente(self) -> bool:
        """Declara fonte própria E pede mais de uma carga unitária da porta."""
        if not self.autoalimentado_declarado:
            return False
        return (self.corrente_pedida_ma or 0) > _CARGA_UNITARIA_MA


@dataclass(frozen=True)
class Aparelho:
    """Um dispositivo USB, com tudo que o kernel publica sobre ele."""

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
    ligado_como: str = ""
    interfaces: tuple[str, ...] = ()
    eventos: tuple[str, ...] = ()
    receptor: bool = False
    especie: str = ESPECIE_DESCONHECIDA
    grau: str = GRAU_DESCONHECIDO
    e_hub: bool = False
    e_raiz: bool = False
    atras_de_hub: bool = False
    energia: Energia = field(default_factory=Energia)
    versao_usb: str = ""
    devnum: int = 0
    driver: str = ""
    fabricante_da_base: str = ""
    produto_da_base: str = ""
    sabe_superspeed: bool | None = None
    container_id: str = ""
    portas: int = 0
    pares: tuple[tuple[int, str, int], ...] = ()


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
        """Tudo menos os hubs-raiz — o que uma pessoa chamaria de aparelho."""
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
    ler_bytes: Callable[[str], bytes] | None = None,
    base: Callable[[str, str], str | None] | None = None,
) -> Censo:
    """Uma varredura de ``/sys``, e o barramento inteiro sai dela.

    ``ler_bytes`` lê o ``bos_descriptors`` (binário); ``base`` é a base do sistema,
    ``(syspath, propriedade) -> valor`` (a libudev por padrão).
    """
    leitor = ler_texto if ler is None else ler
    leitor_de_bytes = _ler_bytes if ler_bytes is None else ler_bytes
    da_base = _da_libudev if base is None else base
    try:
        nomes = sorted(listar(raiz_usb))
    except OSError:
        return Censo()

    nos = [nome for nome in nomes if ":" not in nome]
    interfaces = [nome for nome in nomes if ":" in nome]

    caminhos = {nome: real(os.path.join(raiz_usb, nome)) for nome in nos}
    nome_por_caminho = {caminho: nome for nome, caminho in caminhos.items()}

    brutos = {
        nome: _ler_um(
            nome, caminho, raiz_usb, interfaces, leitor=leitor, real=real, listar=listar,
            leitor_de_bytes=leitor_de_bytes, base=da_base,
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


@dataclass(frozen=True)
class HubFisico:
    """Um hub de plástico: os nós que o kernel enumera para ele, e as entradas que ele expõe."""

    representante: str
    nos: tuple[str, ...]
    container_id: str = ""
    entradas: int = 0


class EnlaceAbaixo(NamedTuple):
    """Um aparelho que sabe SuperSpeed e negociou menos; ``caminho_era_3x`` quando a porta acima
    tem o par SuperSpeed livre."""

    no: str
    velocidade_mbps: float
    caminho_era_3x: bool


def hubs_fisicos(censo: Censo) -> tuple[HubFisico, ...]:
    """Os nós de hub agrupados por aparelho: o mesmo Container ID, ou as portas amarradas pelo
    ``peer``; sem os dois, cada nó é um hub."""
    hubs = sorted((a for a in censo.aparelhos if a.e_hub and not a.e_raiz), key=_ordem)
    por_nome = {a.nome_do_kernel: a for a in hubs}
    grupo = {a.no: a.no for a in hubs}

    def raiz(no: str) -> str:
        while grupo[no] != no:
            grupo[no] = grupo[grupo[no]]
            no = grupo[no]
        return no

    def juntar(um: str, outro: str) -> None:
        a, b = raiz(um), raiz(outro)
        if a != b:
            grupo[max(a, b)] = min(a, b)

    por_container: dict[str, str] = {}
    for hub in hubs:
        if hub.container_id:
            juntar(hub.no, por_container.setdefault(hub.container_id, hub.no))
        for _porta, nome_do_par, _porta_do_par in hub.pares:
            par = por_nome.get(nome_do_par)
            if par is not None:
                juntar(hub.no, par.no)

    membros: dict[str, list[Aparelho]] = {}
    for hub in hubs:
        membros.setdefault(raiz(hub.no), []).append(hub)
    return tuple(
        HubFisico(
            representante=nos[0].no,
            nos=tuple(a.no for a in nos),
            container_id=next((a.container_id for a in nos if a.container_id), ""),
            entradas=_entradas(nos),
        )
        for nos in sorted(membros.values(), key=lambda lista: _ordem(lista[0]))
    )


def hub_fisico_de(censo: Censo, no: str) -> HubFisico | None:
    """O hub físico de que este nó faz parte, ou ``None`` quando ele não é hub."""
    return next((h for h in hubs_fisicos(censo) if no in h.nos), None)


def _entradas(nos: Sequence[Aparelho]) -> int:
    """As portas dos nós, menos as que alimentam outro nó do hub; um par de ``peer`` conta uma."""
    nomes = {a.nome_do_kernel for a in nos}
    proprios = {a.no for a in nos}
    alimentam = {
        (a.nome_do_kernel, porta)
        for a in nos
        for porta in range(1, a.portas + 1)
        if f"{a.no}/{_no_na_porta(a, porta)}" in proprios
    }
    portas = [
        (a.nome_do_kernel, porta)
        for a in nos
        for porta in range(1, a.portas + 1)
        if (a.nome_do_kernel, porta) not in alimentam
    ]
    pares = {
        frozenset({(a.nome_do_kernel, porta), (nome_do_par, porta_do_par)})
        for a in nos
        for porta, nome_do_par, porta_do_par in a.pares
        if nome_do_par in nomes
    }
    abertas = set(portas)
    contadas = len(portas) - sum(1 for par in pares if par <= abertas)
    if pares or len({a.busnum for a in nos}) < 2:
        return contadas
    por_lado: dict[int, int] = {}
    for nome, _porta in portas:
        lado = next(a.busnum for a in nos if a.nome_do_kernel == nome)
        por_lado[lado] = por_lado.get(lado, 0) + 1
    return max(por_lado.values(), default=0)


def enlace_abaixo(censo: Censo, aparelho: Aparelho) -> EnlaceAbaixo | None:
    """O aparelho sabe SuperSpeed (no BOS), usa essa velocidade e negociou 480M ou menos.

    Fato medido, sem causa. O lado 2.0 de um hub que tem o lado SuperSpeed no ar não conta: ele
    é 2.0 por construção. A espécie que não usa a velocidade (a câmera) não recebe o aviso.
    """
    if aparelho.e_raiz or not aparelho.sabe_superspeed:
        return None
    if aparelho.especie in _ESPECIES_QUE_NAO_USAM_A_VELOCIDADE:
        return None
    if not 0 < aparelho.velocidade_mbps <= _ALTA_VELOCIDADE_MBPS:
        return None
    hub = hub_fisico_de(censo, aparelho.no) if aparelho.e_hub else None
    if hub is not None and any(
        (outro := censo.aparelho(no)) is not None and outro.velocidade_mbps >= _SUPERSPEED_MBPS
        for no in hub.nos
    ):
        return None
    return EnlaceAbaixo(
        aparelho.no, aparelho.velocidade_mbps, _par_superspeed_livre(censo, aparelho))


def _par_superspeed_livre(censo: Censo, aparelho: Aparelho) -> bool:
    """A porta acima deste aparelho tem o par SuperSpeed, e nada enumerou nele."""
    pai = censo.aparelho(aparelho.pai) if aparelho.pai else None
    if pai is None or not aparelho.devpath:
        return False
    porta = _inteiro(aparelho.devpath.split(".")[-1])
    par = next(((nome, p) for q, nome, p in pai.pares if q == porta), None)
    if par is None:
        return False
    hub_do_par = next((a for a in censo.aparelhos if a.nome_do_kernel == par[0]), None)
    if hub_do_par is None or hub_do_par.velocidade_mbps < _SUPERSPEED_MBPS:
        return False
    ocupada = f"{hub_do_par.no}/{_no_na_porta(hub_do_par, par[1])}"
    return censo.aparelho(ocupada) is None


def _no_na_porta(hub: Aparelho, porta: int) -> str:
    """O nó que a porta enumeraria: sob o raiz ``usb4`` é ``4-1``; sob ``4-1`` é ``4-1.1``."""
    return f"{hub.busnum}-{porta}" if hub.e_raiz else f"{hub.nome_do_kernel}.{porta}"


def cadeia_de_hubs(censo: Censo, no: str) -> tuple[str, ...]:
    """Os hubs FÍSICOS acima deste aparelho, do mais perto ao mais longe.

    Cada hub vem pelo representante do hub físico (:func:`hubs_fisicos`): os dois lados e a
    cascata interna de um hub de plástico contam um, e dois aparelhos nos dois lados do mesmo
    hub dão o mesmo nó.
    """
    por_no = {a.no: a for a in censo.aparelhos}
    representante = {no: h.representante for h in hubs_fisicos(censo) for no in h.nos}
    atual = por_no.get(no)
    proprio = representante.get(no, "")
    cadeia: list[str] = []
    vistos: set[str] = set()
    while atual is not None and atual.pai and atual.pai not in vistos:
        vistos.add(atual.pai)
        pai = por_no.get(atual.pai)
        if pai is None:
            break
        if pai.e_hub and not pai.e_raiz:
            fisico = representante.get(pai.no, pai.no)
            if fisico != proprio and fisico not in cadeia:
                cadeia.append(fisico)
        atual = pai
    return tuple(cadeia)


def hub_em_comum(censo: Censo, nos: Sequence[str]) -> str:
    """O hub mais próximo que está acima de TODOS estes aparelhos — ou ``""``."""
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


def _barramentos(aparelhos: Sequence[Aparelho]) -> tuple[Barramento, ...]:
    """Um ``Barramento`` por hub-raiz, com tudo que pendura abaixo dele."""
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
    ligado_como: str = ""
    interfaces: tuple[str, ...] = ()
    eventos: tuple[str, ...] = ()
    drivers: tuple[str, ...] = ()
    bos: bytes = b""
    pares: tuple[tuple[int, str, int], ...] = ()
    fabricante_da_base: str = ""
    produto_da_base: str = ""


def _ler_um(
    nome: str,
    caminho: str,
    raiz_usb: str,
    interfaces: Iterable[str],
    *,
    leitor: Callable[[str], str],
    real: Callable[[str], str],
    listar: Callable[[str], list[str]],
    leitor_de_bytes: Callable[[str], bytes] = lambda _caminho: b"",
    base: Callable[[str, str], str | None] = lambda _syspath, _nome: None,
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
            "version",
            "devnum",
            "maxchild",
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
        classe = campos["bDeviceClass"].lower()
        origem = "descritor do aparelho" if classe else ""
    ligado = _o_que_o_kernel_ligou(
        nome, campos["busnum"], campos["devpath"], raiz_usb, interfaces,
        leitor=leitor, real=real, listar=listar)
    triplas, eventos = _interfaces_e_eventos(
        nome, campos["busnum"], campos["devpath"], raiz_usb, interfaces,
        leitor=leitor, real=real, listar=listar)
    proprias = _interfaces_do_no(nome, campos["busnum"], campos["devpath"], interfaces)
    pastas = [_real_sem_erro(real, os.path.join(raiz_usb, i)) for i in proprias]
    return _Bruto(
        nome=nome,
        caminho=caminho,
        campos=campos,
        classe=classe,
        subclasse=subclasse,
        protocolo=protocolo,
        origem=origem,
        controlador_pci=_controlador_pci(caminho),
        ligado_como=ligado,
        interfaces=triplas,
        eventos=eventos,
        drivers=_drivers(pastas, real),
        bos=_bytes_sem_erro(leitor_de_bytes, os.path.join(caminho, "bos_descriptors")),
        pares=_pares(pastas, real, listar) if classe == CLASSE_HUB else (),
        fabricante_da_base=_nome_da_base(base, caminho, "ID_VENDOR_FROM_DATABASE"),
        produto_da_base=_nome_da_base(base, caminho, "ID_MODEL_FROM_DATABASE"),
    )


def _interfaces_do_no(nome: str, busnum: str, devpath: str, interfaces: Iterable[str]) -> list[str]:
    """As interfaces deste nó (``3-1.4:1.0``…), em ordem."""
    prefixo = f"{busnum}-{devpath}:" if busnum and devpath else f"{nome}:"
    return sorted(alvo for alvo in interfaces if alvo.startswith(prefixo))


def _drivers(pastas: Sequence[str], real: Callable[[str], str]) -> tuple[str, ...]:
    """O driver ligado em cada interface (o alvo do link ``driver``), sem repetir."""
    achados: list[str] = []
    for pasta in pastas:
        alvo = _real_sem_erro(real, os.path.join(pasta, "driver"))
        nome = os.path.basename(alvo)
        if alvo and nome != "driver" and nome not in achados:
            achados.append(nome)
    return tuple(achados)


def _pares(
    pastas: Sequence[str], real: Callable[[str], str], listar: Callable[[str], list[str]]
) -> tuple[tuple[int, str, int], ...]:
    """As portas deste hub e a do outro lado a que o ``peer`` as amarra."""
    pares: list[tuple[int, str, int]] = []
    for pasta in pastas:
        for entrada in sorted(_listar_sem_erro(listar, pasta)):
            porta = _PORTA.match(entrada)
            if porta is None:
                continue
            alvo = _PORTA.match(os.path.basename(
                _real_sem_erro(real, os.path.join(pasta, entrada, "peer"))))
            if alvo is not None:
                pares.append((int(porta.group(2)), alvo.group(1), int(alvo.group(2))))
    return tuple(pares)


def ler_o_bos(dados: bytes) -> tuple[bool | None, str]:
    """``(sabe SuperSpeed, Container ID)`` do ``bos_descriptors``; ``(None, "")`` sem ele.

    Pelo tipo de cada capacidade, nunca pela marca: ``0x03``/``0x0a`` são SuperSpeed, ``0x04`` é
    o Container ID (16 bytes depois de quatro de cabeçalho).
    """
    if len(dados) < 5 or dados[1] != _TIPO_DO_BOS:
        return None, ""
    total = min(len(dados), int.from_bytes(dados[2:4], "little") or len(dados))
    posicao = dados[0] or 5
    sabe = False
    container = ""
    while posicao + 3 <= total:
        tamanho = dados[posicao]
        if tamanho < 3:
            break
        if dados[posicao + 1] == _TIPO_DA_CAPACIDADE:
            tipo = dados[posicao + 2]
            if tipo in _CAPACIDADES_SUPERSPEED:
                sabe = True
            elif tipo == _CAPACIDADE_CONTAINER_ID and tamanho >= 20 and posicao + 20 <= total:
                container = dados[posicao + 4:posicao + 20].hex()
        posicao += tamanho
    return sabe, container


def _ler_bytes(caminho: str) -> bytes:
    """Um atributo binário do ``/sys``; ``b""`` em qualquer erro."""
    try:
        with open(caminho, "rb") as arquivo:
            return arquivo.read()
    except OSError:
        return b""


def _da_libudev(syspath: str, nome: str) -> str | None:
    """A propriedade do dispositivo na base da libudev; ``None`` sem libudev ou sem a linha."""
    from hefesto_dualsense4unix.core.banco_do_udev import propriedade_do_syspath

    return propriedade_do_syspath(syspath, nome)


def _nome_da_base(base: Callable[[str, str], str | None], syspath: str, nome: str) -> str:
    """O nome na base do udev; o ``banco_do_udev`` devolve ``None`` e nunca levanta."""
    return (base(syspath, nome) or "").strip()


def _bytes_sem_erro(ler: Callable[[str], bytes], caminho: str) -> bytes:
    try:
        return ler(caminho)
    except (OSError, KeyError):
        return b""


def _real_sem_erro(real: Callable[[str], str], caminho: str) -> str:
    try:
        return real(caminho)
    except (OSError, KeyError):
        return ""


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
    if bruto.ligado_como and (grau != GRAU_LIDO or bruto.classe in _CLASSES_QUE_NAO_DIZEM):
        especie, grau = _ESPECIE_DO_QUE_O_KERNEL_LIGOU[bruto.ligado_como], GRAU_LIDO
        origem = "o que o kernel ligou"
    else:
        origem = bruto.origem
    receptor = _receptor_sem_fio.e_receptor(
        bruto.interfaces, _decimal(campos["speed"]),
        (campos["product"], campos["manufacturer"]))
    if receptor and especie not in _ESPECIES_QUE_O_RECEPTOR_JA_DIZ:
        especie, grau = _receptor_sem_fio.ESPECIE, GRAU_LIDO
        origem = "as interfaces de teclado e mouse"
    sabe_superspeed, container_id = ler_o_bos(bruto.bos)
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
        origem_da_classe=origem,
        ligado_como=bruto.ligado_como,
        interfaces=bruto.interfaces,
        eventos=bruto.eventos,
        receptor=receptor,
        especie=especie,
        grau=grau,
        versao_usb=campos["version"],
        devnum=_inteiro(campos["devnum"]),
        driver=", ".join(bruto.drivers),
        fabricante_da_base=bruto.fabricante_da_base,
        produto_da_base=bruto.produto_da_base,
        sabe_superspeed=sabe_superspeed,
        container_id=container_id,
        portas=_inteiro(campos["maxchild"]),
        pares=bruto.pares,
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
    """O pai é um hub DE VERDADE, e não o hub-raiz do controlador?"""
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
    """``(classe, subclasse, protocolo, origem)`` da interface 0 deste nó."""
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


def _o_que_o_kernel_ligou(
    nome: str,
    busnum: str,
    devpath: str,
    raiz_usb: str,
    interfaces: Iterable[str],
    *,
    leitor: Callable[[str], str],
    real: Callable[[str], str],
    listar: Callable[[str], list[str]],
) -> str:
    """Wi-Fi, Bluetooth, controle, câmera ou rede, pelo que o KERNEL ligou nas interfaces.

    Quem classifica é o driver que casou, não o fabricante nem o nome do produto: o ``ff`` do
    fabricante não diz nada, mas a interface em que o ``mac80211`` pendurou um ``ieee80211``
    (ou uma ``net/<if>/wireless``) é Wi-Fi, de qualquer chip. Só leitura de ``/sys``.
    """
    prefixo = f"{busnum}-{devpath}:" if busnum and devpath else f"{nome}:"
    achados: set[str] = set()
    for interface in sorted(alvo for alvo in interfaces if alvo.startswith(prefixo)):
        pasta = real(os.path.join(raiz_usb, interface))
        dentro = _listar_sem_erro(listar, pasta)
        achados |= {ligado for pasta_do_kernel, ligado in _O_QUE_O_KERNEL_PENDURA.items()
                    if pasta_do_kernel in dentro}
        for rede in _listar_sem_erro(listar, os.path.join(pasta, "net")):
            sinais = _listar_sem_erro(listar, os.path.join(pasta, "net", rede))
            achados.add(LIGADO_COMO_WIFI if {"wireless", "phy80211"} & set(sinais)
                        else LIGADO_COMO_REDE)
        for no_de_input in _nos_de_input(pasta, listar):
            teclas = _campo(os.path.join(no_de_input, "capabilities"), "key", leitor)
            if _tem_a_tecla(teclas, _BTN_SOUTH):
                achados.add(LIGADO_COMO_CONTROLE)
    return next((c for c in _ORDEM_DO_QUE_O_KERNEL_LIGOU if c in achados), "")


def _nos_de_input(pasta: str, listar: Callable[[str], list[str]]) -> list[str]:
    """Os ``inputN`` de uma interface USB: direto nela (``xpad``) ou sob o filho HID.

    Medido em 05/10/2026: num aparelho HID o kernel pendura o filho
    ``0003:VVVV:PPPP.NNNN`` na interface e o ``input/inputN`` mora DENTRO dele; só o driver que
    se liga direto à interface (``xpad``) cria ``input/`` na própria interface.
    """
    pais = [pasta]
    pais += [os.path.join(pasta, filho) for filho in _listar_sem_erro(listar, pasta)
             if _FILHO_HID.match(filho)]
    return [os.path.join(pai, "input", no)
            for pai in pais
            for no in sorted(_listar_sem_erro(listar, os.path.join(pai, "input")))]


def _interfaces_e_eventos(
    nome: str,
    busnum: str,
    devpath: str,
    raiz_usb: str,
    interfaces: Iterable[str],
    *,
    leitor: Callable[[str], str],
    real: Callable[[str], str],
    listar: Callable[[str], list[str]],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """``(triplas, eventos)``: a tripla de CADA interface e os ``eventN`` que elas criaram."""
    prefixo = f"{busnum}-{devpath}:" if busnum and devpath else f"{nome}:"
    triplas: list[str] = []
    eventos: list[str] = []
    for interface in sorted(alvo for alvo in interfaces if alvo.startswith(prefixo)):
        pasta = real(os.path.join(raiz_usb, interface))
        tripla = "".join(
            _campo(pasta, atributo, leitor).lower()
            for atributo in ("bInterfaceClass", "bInterfaceSubClass", "bInterfaceProtocol"))
        if len(tripla) == 6:
            triplas.append(tripla)
        for no_de_input in _nos_de_input(pasta, listar):
            eventos += [e for e in sorted(_listar_sem_erro(listar, no_de_input))
                        if _EVENTO.match(e)]
    return tuple(triplas), tuple(eventos)


def _listar_sem_erro(listar: Callable[[str], list[str]], pasta: str) -> list[str]:
    """O que há numa pasta do ``/sys``; vazio quando ela não existe (nem todo nó tem tudo)."""
    try:
        return list(listar(pasta))
    except (OSError, KeyError):
        return []


def _tem_a_tecla(mapa: str, bit: int) -> bool:
    """O ``bit`` do ``capabilities/key`` (palavras hex separadas por espaço)."""
    palavras = mapa.split()
    try:
        inteiro = int("".join(f"{int(p, 16):016x}" for p in palavras), 16) if palavras else 0
    except ValueError:
        return False
    return bool(inteiro >> bit & 1)


def _especie(classe: str, subclasse: str, protocolo: str) -> tuple[str, str]:
    """``(palavra de gente, grau)`` a partir da tripla que o kernel publica."""
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
    """O painel do gabinete, na palavra do kernel — ``""`` quando ele não sabe."""
    return "" if valor == "unknown" else valor


def _autoalimentado(bm_attributes: str) -> bool | None:
    """Bit ``0x40`` de ``bmAttributes``; ``None`` quando o campo não é legível."""
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
    """Um atributo do nó, já sem o ``\\n`` do sysfs — ``""`` se não houver."""
    return ler(os.path.join(no, atributo)).strip()


__all__ = [
    "CLASSE_HUB",
    "ESPECIE_DESCONHECIDA",
    "GRAU_DESCONHECIDO",
    "GRAU_LIDO",
    "LIGADO_COMO_BLUETOOTH",
    "LIGADO_COMO_CAMERA",
    "LIGADO_COMO_CONTROLE",
    "LIGADO_COMO_REDE",
    "LIGADO_COMO_WIFI",
    "Aparelho",
    "Barramento",
    "Censo",
    "Energia",
    "EnlaceAbaixo",
    "HubFisico",
    "cadeia_de_hubs",
    "enlace_abaixo",
    "hub_em_comum",
    "hub_fisico_de",
    "hubs_fisicos",
    "ler_o_barramento",
    "ler_o_bos",
]
