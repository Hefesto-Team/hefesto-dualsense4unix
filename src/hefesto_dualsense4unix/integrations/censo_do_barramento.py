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

GRAU_LIDO = "lido"
GRAU_DESCONHECIDO = "desconhecido"

ESPECIE_DESCONHECIDA = "Não identificado"

#: O que o KERNEL ligou nas interfaces do aparelho (``ligado_como``), na ordem em que a palavra
#: vale quando há mais de uma: Wi-Fi vence Bluetooth (um combo é as duas coisas, e o que
#: atrapalha o rádio dela é o Wi-Fi), e o resto vem depois.
LIGADO_COMO_WIFI = "wifi"
LIGADO_COMO_BLUETOOTH = "bluetooth"
LIGADO_COMO_CONTROLE = "controle"
LIGADO_COMO_CAMERA = "camera"
LIGADO_COMO_REDE = "rede"
_ESPECIE_DO_QUE_O_KERNEL_LIGOU = {
    LIGADO_COMO_WIFI: "Wi-Fi",
    LIGADO_COMO_BLUETOOTH: "Bluetooth",
    LIGADO_COMO_CONTROLE: "Controle",
    LIGADO_COMO_CAMERA: "Câmera",
    LIGADO_COMO_REDE: "Rede",
}
_ORDEM_DO_QUE_O_KERNEL_LIGOU = tuple(_ESPECIE_DO_QUE_O_KERNEL_LIGOU)
#: A pasta que o driver pendura na interface → o que ele ligou.
_O_QUE_O_KERNEL_PENDURA = {
    "ieee80211": LIGADO_COMO_WIFI,
    "bluetooth": LIGADO_COMO_BLUETOOTH,
    "video4linux": LIGADO_COMO_CAMERA,
}
#: ``BTN_SOUTH`` (0x130): o botão que todo controle de jogo tem e nenhum teclado tem.
_BTN_SOUTH = 0x130
#: As classes em que a tripla da interface NÃO diz o que o aparelho é (fabricante, «diversos»,
#: específico do programa, sem fio sem a tripla do Bluetooth): ali a palavra é a do kernel.
_CLASSES_QUE_NAO_DIZEM = frozenset({"", "ef", "fe", "ff", "e0", "02", "0a"})

CLASSE_HUB = "09"

_CLASSE_ENTRADA = "03"
_CLASSE_SEM_FIO = "e0"

_DEVPATH_DO_RAIZ = "0"

_CARGA_UNITARIA_MA = 100

_BIT_AUTOALIMENTADO = 0x40

_CONTROLADOR_PCI = re.compile(r"0000:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9a-f]")

_CORRENTE = re.compile(r"^([0-9]+)")

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
    #: o que o kernel ligou nas interfaces dele (:data:`LIGADO_COMO_WIFI`…), ou ``""``
    ligado_como: str = ""
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
) -> Censo:
    """Uma varredura de ``/sys``, e o barramento inteiro sai dela."""
    leitor = _ler_texto if ler is None else ler
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
            nome, caminho, raiz_usb, interfaces, leitor=leitor, real=real, listar=listar
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
    """Os hubs acima deste aparelho, do mais perto ao mais longe."""
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


def _ler_um(
    nome: str,
    caminho: str,
    raiz_usb: str,
    interfaces: Iterable[str],
    *,
    leitor: Callable[[str], str],
    real: Callable[[str], str],
    listar: Callable[[str], list[str]],
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
        classe = campos["bDeviceClass"].lower()
        origem = "descritor do aparelho" if classe else ""
    ligado = _o_que_o_kernel_ligou(
        nome, campos["busnum"], campos["devpath"], raiz_usb, interfaces,
        leitor=leitor, real=real, listar=listar)
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
    if bruto.ligado_como and (grau != GRAU_LIDO or bruto.classe in _CLASSES_QUE_NAO_DIZEM):
        especie, grau = _ESPECIE_DO_QUE_O_KERNEL_LIGOU[bruto.ligado_como], GRAU_LIDO
        origem = "o que o kernel ligou"
    else:
        origem = bruto.origem
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
        for entrada in _listar_sem_erro(listar, os.path.join(pasta, "input")):
            teclas = _campo(os.path.join(pasta, "input", entrada, "capabilities"), "key", leitor)
            if _tem_a_tecla(teclas, _BTN_SOUTH):
                achados.add(LIGADO_COMO_CONTROLE)
    return next((c for c in _ORDEM_DO_QUE_O_KERNEL_LIGOU if c in achados), "")


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
    "LIGADO_COMO_BLUETOOTH",
    "LIGADO_COMO_CAMERA",
    "LIGADO_COMO_CONTROLE",
    "LIGADO_COMO_REDE",
    "LIGADO_COMO_WIFI",
    "Aparelho",
    "Barramento",
    "Censo",
    "Energia",
    "cadeia_de_hubs",
    "hub_em_comum",
    "ler_o_barramento",
]
