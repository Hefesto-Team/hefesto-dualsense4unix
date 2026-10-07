"""mesa_de_radio.py — o que o barramento já sabe dizer sobre a mesa.

O PROBLEMA QUE ESTE MÓDULO RESOLVE
-----------------------------------

A janela sabe quais controles estão conectados e não sabe **nada** sobre o
caminho físico até eles. Quantos adaptadores Bluetooth há na mesa, em que porta
cada um está, se há um hub no meio, e o que mais divide a faixa de 2,4 GHz com
os controles — tudo isso o kernel publica em ``/sys``, de graça, sem root, sem
subprocesso e sem IPC. Ninguém lia.

As três perguntas que ele responde, e nada além delas:

1. **quais adaptadores Bluetooth existem e ONDE estão** (VID:PID, barramento,
   porta, painel do gabinete, atrás-de-hub);
2. **quais outros rádios USB dividem a faixa** — receptor de 2,4 GHz, Wi-Fi,
   dongle de teclado;
3. **quais aparelhos estão colados**: mesmo controlador PCI, mesmo barramento e
   portas numericamente vizinhas.

O QUE ELE NÃO É
----------------

Não entrega o **endereço** (MAC) do adaptador. Medido nesta bancada em
22/08/2026, kernel 7.0.11-76070011-generic: ``/sys/class/bluetooth/hci0/`` não
tem arquivo ``address`` — o ``_adapter_addresses`` do próprio projeto
(``broker/hidraw_broker.py:181``) devolve ``set()`` sobre ``/sys``. O endereço
existe pelo BlueZ no D-Bus de sistema, que este módulo não abre: quem fala
com o BlueZ é o ``bluez_dbus``, o dono único do barramento de sistema
(BLUEZ-UM-DONO-01), e este módulo fica no que o kernel diz pelo
``/sys``. Por isso
o nome de um adaptador aqui é a **identidade física**, que é estável entre
boots — ao contrário de ``hciN``, que inverte — e ainda responde "onde está" de
quebra. É a decisão M1 de ``DECISOES-DA-EXECUCAO.md``.

Não mede força de sinal: o RSSI do BlueZ só existe durante *discovery*, e
manter discovery ligado rouba banda do rádio dos controles — medir pioraria
exatamente o que a aba quer melhorar.

Não diz qual controle está em qual adaptador: o que amarra os dois é o *bond*,
em ``/var/lib/bluetooth``, árvore ``700``, e a janela é sudo-zero por doutrina.

UNIVERSALIDADE
---------------

Nada aqui olha nome de máquina, ordem de conexão ou quantidade de aparelhos. A
mesma pergunta se responde igual numa mesa de zero, de um ou de quatro
adaptadores — quem responde é o sysfs do kernel. Lista vazia e ``""`` são
respostas legítimas, e **zero adaptadores é o caso mais comum lá fora**: a
máquina sem Bluetooth nenhum.

Esta bancada NÃO é esse caso — ela tem TRÊS (``hci0``, ``hci1``, ``hci2``,
medido em 22/08/2026). A frase anterior aqui dizia o contrário, e um fato
errado sobre a bancada é justamente o tipo de linha que a próxima pessoa cita
como prova (UMA-FAIXA-NÃO-É-UM-FABRICANTE-01, A6).

Todas as raízes e todos os leitores entram por argumento com default do sistema
real — nunca por constante de módulo, que o ``CANARIO-FS-01``
(``tests/conftest.py:332``) pega e que impediria o retrato de fotografar a aba
com uma bancada de mentira.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from hefesto_dualsense4unix.integrations.usb_pai import dispositivo_usb_pai

_INTERFACE_BT = re.compile(r"^hci[0-9]+$")

_HUB_RAIZ = re.compile(r"^usb[0-9]+$")

_CLASSE_HUB = "09"

_CONTROLADOR_PCI = re.compile(r"0000:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9a-f]")

_VELOCIDADE_USB3 = 5000.0

_VIDS_DE_CONTROLE = frozenset(
    {
        "054c",
        "057e",
        "045e",
        "2dc8",
        "0f0d",
        "20d6",
        "28de",
    }
)


@dataclass(frozen=True)
class Adaptador:
    """Um adaptador Bluetooth e ONDE ele está, fisicamente."""

    interface: str
    no: str = ""
    vid: str = ""
    pid: str = ""
    busnum: int = 0
    devpath: str = ""
    painel: str = ""
    atras_de_hub: bool = False
    controlador_pci: str = ""

    @property
    def caminho(self) -> str:
        """``3-1.1.4`` — a palavra COMUM com ``censo_do_barramento``."""
        return _caminho_de_barramento(self.busnum, self.devpath)

    @property
    def lugar(self) -> str:
        """O LUGAR (D3): ``pci-0000:0c:00.3-usb-0:4.1.4`` — a chave do dono."""
        return _lugar(self.controlador_pci, self.devpath)


@dataclass(frozen=True)
class RadioUsb:
    """Um aparelho USB que divide a faixa de 2,4 GHz com os controles."""

    no: str
    vid: str
    pid: str
    busnum: int = 0
    devpath: str = ""
    painel: str = ""
    atras_de_hub: bool = False
    controlador_pci: str = ""
    usb3: bool = False

    @property
    def caminho(self) -> str:
        """``3-1.1.4`` — o mesmo de :attr:`Adaptador.caminho`, pelo mesmo motivo."""
        return _caminho_de_barramento(self.busnum, self.devpath)

    @property
    def lugar(self) -> str:
        """O LUGAR (D3) — o mesmo de :attr:`Adaptador.lugar`, pelo mesmo motivo."""
        return _lugar(self.controlador_pci, self.devpath)


@dataclass(frozen=True)
class Mesa:
    """A leitura inteira, de uma vez — o que a seção "A mesa" desenha."""

    adaptadores: tuple[Adaptador, ...] = ()
    radios: tuple[RadioUsb, ...] = ()
    apertadas: tuple[tuple[str, str], ...] = ()


def ler_a_mesa(
    *,
    raiz_bt: str = "/sys/class/bluetooth",
    raiz_usb: str = "/sys/bus/usb/devices",
    listar: Callable[[str], list[str]] = os.listdir,
    ler: Callable[[str], str] | None = None,
    existe: Callable[[str], bool] = os.path.exists,
    real: Callable[[str], str] = os.path.realpath,
) -> Mesa:
    """As três leituras de uma vez — adaptadores, rádios e quem está colado."""
    leitor = _ler_texto if ler is None else ler
    adaptadores = adaptadores_bluetooth(
        raiz_bt=raiz_bt, listar=listar, ler=leitor, existe=existe, real=real
    )
    radios = radios_do_barramento(
        adaptadores, raiz_usb=raiz_usb, listar=listar, ler=leitor, real=real
    )
    return Mesa(
        adaptadores=tuple(adaptadores),
        radios=tuple(radios),
        apertadas=tuple(vizinhancas_apertadas([*adaptadores, *radios])),
    )


def adaptadores_bluetooth(
    *,
    raiz_bt: str = "/sys/class/bluetooth",
    listar: Callable[[str], list[str]] = os.listdir,
    ler: Callable[[str], str] | None = None,
    existe: Callable[[str], bool] = os.path.exists,
    real: Callable[[str], str] = os.path.realpath,
) -> list[Adaptador]:
    """Os adaptadores Bluetooth da máquina, em ordem estável de interface."""
    leitor = _ler_texto if ler is None else ler
    try:
        nomes = sorted(listar(raiz_bt))
    except OSError:
        return []

    achados: list[Adaptador] = []
    for nome in nomes:
        if not _INTERFACE_BT.match(nome):
            continue
        no = dispositivo_usb_pai(
            os.path.join(raiz_bt, nome), existe=existe, real=real
        )
        if not no:
            achados.append(Adaptador(interface=nome))
            continue
        achados.append(
            Adaptador(
                interface=nome,
                no=no,
                vid=_campo(no, "idVendor", leitor),
                pid=_campo(no, "idProduct", leitor),
                busnum=_inteiro(_campo(no, "busnum", leitor)),
                devpath=_campo(no, "devpath", leitor),
                painel=_painel(no, leitor),
                atras_de_hub=_atras_de_hub(no, leitor),
                controlador_pci=_controlador_pci(no, real),
            )
        )
    return achados


def radios_do_barramento(
    adaptadores: Sequence[Adaptador] = (),
    *,
    raiz_usb: str = "/sys/bus/usb/devices",
    listar: Callable[[str], list[str]] = os.listdir,
    ler: Callable[[str], str] | None = None,
    real: Callable[[str], str] = os.path.realpath,
) -> list[RadioUsb]:
    """Os aparelhos USB que dividem a faixa — sem hubs, sem os controles.

    Três exclusões, cada uma com o motivo medido:

    * **hubs** — inclusive os de raiz, que são classe ``09`` e não são aparelho
      nenhum: são o próprio barramento;
    * **os adaptadores Bluetooth** — eles têm tabela própria, e aparecer nas
      duas faria a mesma antena contar duas vezes;
    * **os controles** — ``054c:0ce6`` é um DualSense no cabo, e listá-lo diria
      à pessoa que os controles do usuário atrapalham os controles do usuário (M4).

    Não pede ``existe``: aqui a varredura é do próprio diretório de raiz, e não
    uma subida pela árvore — quem precisa de ``existe`` é o
    ``dispositivo_usb_pai`` do lado dos adaptadores.
    """
    leitor = _ler_texto if ler is None else ler
    try:
        nomes = sorted(listar(raiz_usb))
    except OSError:
        return []

    nos_dos_adaptadores = {a.no for a in adaptadores if a.no}
    achados: list[RadioUsb] = []
    for nome in nomes:
        if ":" in nome:
            continue
        no = real(os.path.join(raiz_usb, nome))
        if no in nos_dos_adaptadores:
            continue
        vid = _campo(no, "idVendor", leitor).lower()
        pid = _campo(no, "idProduct", leitor).lower()
        if not vid or not pid:
            continue
        if _e_hub(_campo(no, "bDeviceClass", leitor)):
            continue
        if vid in _VIDS_DE_CONTROLE:
            continue
        achados.append(
            RadioUsb(
                no=no,
                vid=vid,
                pid=pid,
                busnum=_inteiro(_campo(no, "busnum", leitor)),
                devpath=_campo(no, "devpath", leitor),
                painel=_painel(no, leitor),
                atras_de_hub=_atras_de_hub(no, leitor),
                controlador_pci=_controlador_pci(no, real),
                usb3=_usb3(_campo(no, "speed", leitor)),
            )
        )
    return achados


def vizinhancas_apertadas(
    aparelhos: Sequence[Adaptador | RadioUsb],
) -> list[tuple[str, str]]:
    """Os pares de aparelhos COLADOS, como ``(nó, nó)`` — um par, um aviso."""
    ordenados = sorted(
        (a for a in aparelhos if a.no and a.devpath), key=lambda a: a.no
    )
    pares: list[tuple[str, str]] = []
    for indice, primeiro in enumerate(ordenados):
        for segundo in ordenados[indice + 1 :]:
            if primeiro.busnum != segundo.busnum:
                continue
            if primeiro.controlador_pci != segundo.controlador_pci:
                continue
            if not _portas_vizinhas(primeiro.devpath, segundo.devpath):
                continue
            pares.append((primeiro.no, segundo.no))
    return pares


def controladores_dos_barramentos(
    *,
    raiz_usb: str = "/sys/bus/usb/devices",
    listar: Callable[[str], list[str]] = os.listdir,
    real: Callable[[str], str] = os.path.realpath,
) -> dict[int, str]:
    """``{busnum: controlador PCI}`` DESTE boot — o que traduz caminho em lugar."""
    try:
        nomes = listar(raiz_usb)
    except OSError:
        return {}
    achados: dict[int, str] = {}
    for nome in nomes:
        raiz = _HUB_RAIZ.match(nome)
        if raiz is None:
            continue
        controlador = _controlador_pci(os.path.join(raiz_usb, nome), real)
        if controlador:
            achados[int(nome[3:])] = controlador
    return achados


def _lugar(controlador_pci: str, devpath: str) -> str:
    """A grafia do lugar, perguntada ao dono dela (``utils/lugar``)."""
    from hefesto_dualsense4unix.utils.lugar import lugar_de

    return lugar_de(controlador_pci, devpath)


def _caminho_de_barramento(busnum: int, devpath: str) -> str:
    """``busnum-devpath``, ou ``""`` quando falta metade."""
    if not busnum or not devpath:
        return ""
    return f"{busnum}-{devpath}"


def _portas_vizinhas(uma: str, outra: str) -> bool:
    """``devpath`` numericamente adjacente NO MESMO hub — ``1.2`` e ``1.3``."""
    prefixo_uma, _, cauda_uma = uma.rpartition(".")
    prefixo_outra, _, cauda_outra = outra.rpartition(".")
    if prefixo_uma != prefixo_outra:
        return False
    try:
        return abs(int(cauda_uma) - int(cauda_outra)) == 1
    except ValueError:
        return False


def _e_hub(classe: str) -> bool:
    """Classe ``09`` no descritor de dispositivo — hub, de qualquer espécie."""
    return classe == _CLASSE_HUB


def _atras_de_hub(no: str, ler: Callable[[str], str]) -> bool:
    """O PAI deste nó é um hub DE VERDADE, e não o hub-raiz do controlador?"""
    pai = os.path.dirname(no)
    if not pai:
        return False
    if _HUB_RAIZ.match(os.path.basename(pai)):
        return False
    return _e_hub(_campo(pai, "bDeviceClass", ler))


def _painel(no: str, ler: Callable[[str], str]) -> str:
    """O painel do gabinete, na palavra do kernel — ``""`` quando ele não sabe."""
    valor = _campo(no, "physical_location/panel", ler)
    return "" if valor == "unknown" else valor


def _controlador_pci(no: str, real: Callable[[str], str]) -> str:
    """O último ``0000:xx:xx.x`` da cadeia — o controlador xHCI do aparelho."""
    achados = _CONTROLADOR_PCI.findall(real(no))
    return achados[-1] if achados else ""


def _usb3(velocidade: str) -> bool:
    """``speed >= 5000`` Mbit/s. Texto ilegível é "não sei", que é ``False``."""
    try:
        return float(velocidade) >= _VELOCIDADE_USB3
    except ValueError:
        return False


def _inteiro(valor: str) -> int:
    """Inteiro do sysfs; ``0`` quando o campo não existe ou vem sujo."""
    try:
        return int(valor)
    except ValueError:
        return 0


def _campo(no: str, atributo: str, ler: Callable[[str], str]) -> str:
    """Um atributo do nó, já sem o ``\\n`` do sysfs — ``""`` se não houver."""
    return ler(os.path.join(no, atributo)).strip()


def _ler_texto(caminho: str) -> str:
    """Lê um arquivo de ``/sys``; "" em qualquer erro — sysfs some sob a mão."""
    try:
        with open(caminho, encoding="utf-8", errors="replace") as arquivo:
            return arquivo.read()
    except OSError:
        return ""


__all__ = [
    "Adaptador",
    "Mesa",
    "RadioUsb",
    "adaptadores_bluetooth",
    "controladores_dos_barramentos",
    "ler_a_mesa",
    "radios_do_barramento",
    "vizinhancas_apertadas",
]
