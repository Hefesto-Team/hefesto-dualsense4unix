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
(``broker/hidraw_broker.py:165``) devolve ``set()`` sobre ``/sys``. O endereço
existe pelo BlueZ no D-Bus de sistema, que hoje o produto não abre em lugar
nenhum e que o manifesto Flatpak não permite
(``flatpak/br.andrefarias.Hefesto.yml``: sem ``--socket=system-bus``). Por isso
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
máquina sem Bluetooth nenhum, e o Flatpak, que não monta o barramento.

Esta bancada NÃO é esse caso — ela tem TRÊS (``hci0``, ``hci1``, ``hci2``,
medido em 22/08/2026). A frase anterior aqui dizia o contrário, e um fato
errado sobre a bancada é justamente o tipo de linha que a próxima pessoa cita
como prova (UMA-FAIXA-NÃO-É-UM-FABRICANTE-01, A6).

Todas as raízes e todos os leitores entram por argumento com default do sistema
real — nunca por constante de módulo, que o ``CANARIO-FS-01``
(``tests/conftest.py:338``) pega e que impediria o retrato de fotografar a aba
com uma bancada de mentira.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from hefesto_dualsense4unix.integrations.usb_pai import dispositivo_usb_pai

#: Nome de interface Bluetooth do kernel. O ``/sys/class/bluetooth`` também
#: hospeda nós de canal (``hci0:12``), que não são adaptadores — casar o nome
#: inteiro é o que os deixa de fora.
_INTERFACE_BT = re.compile(r"^hci[0-9]+$")

#: Hub-RAIZ do controlador xHCI. Ele é classe ``09`` como qualquer hub, e TODO
#: aparelho pendura sob um deles: sem esta exceção a mesa inteira sairia
#: marcada como "em hub". Medido nesta bancada em 22/08/2026 — as quatro
#: entradas ``usb1``..``usb4`` são ``1d6b:0002``/``1d6b:0003``, classe ``09``.
_HUB_RAIZ = re.compile(r"^usb[0-9]+$")

#: Classe USB de hub, do descritor de dispositivo (``bDeviceClass``).
_CLASSE_HUB = "09"

#: O último ``0000:xx:xx.x`` da cadeia sysfs é o controlador xHCI onde o
#: aparelho pendura. É o algoritmo de ``scripts/doctor.sh:4817``
#: (``usb_pci_controller``), portado. O que NÃO se porta é o ``pci_label``
#: (``doctor.sh:4823-4830``): ele traduz dois endereços PCI de uma máquina
#: específica, e endereço PCI de máquina é o oposto de universal.
_CONTROLADOR_PCI = re.compile(r"0000:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9a-f]")

#: Velocidade negociada, em Mbit/s, a partir da qual o aparelho é USB 3.x.
#: É a fonte real do "USB 3.0" que a dica da tela promete: o ``speed`` do
#: sysfs vale ``5000`` para SuperSpeed e ``10000`` para SuperSpeed+.
_VELOCIDADE_USB3 = 5000.0

#: VIDs de fabricante de CONTROLE. Um controle no cabo NÃO é "outro rádio que
#: divide a faixa" — listá-lo faria o produto acusar os próprios controles de
#: interferência, e nesta bancada seriam DOIS (``054c:0ce6`` em ``3-1`` e
#: ``3-4``). É a decisão M4 de ``DECISOES-DA-EXECUCAO.md``.
#:
#: O conjunto é o mesmo de ``app/actions/external_controllers.py:40``
#: (``_VENDOR_BY_VID``), repetido e não importado: aquele é privado e mora na
#: camada de JANELA, e ``integrations/`` não pode depender de ``app/``. Quando
#: um VID novo entrar lá, entra aqui — as duas listas respondem à mesma
#: pergunta.
_VIDS_DE_CONTROLE = frozenset(
    {
        "054c",  # Sony
        "057e",  # Nintendo
        "045e",  # Xbox
        "2dc8",  # 8BitDo
        "0f0d",  # HORI
        "20d6",  # PowerA
        "28de",  # Valve
    }
)


@dataclass(frozen=True)
class Adaptador:
    """Um adaptador Bluetooth e ONDE ele está, fisicamente.

    ``interface`` é o ``hciN`` e existe só para o registro e para a depuração:
    ele inverte entre boots, e por isso NUNCA vai para a tela (M1).

    ``no`` é o caminho do nó do dispositivo USB, ou ``""`` quando o adaptador
    não pendura em USB nenhum — o caso do rádio embutido na placa-mãe. Nesse
    caso ``vid``, ``pid``, ``busnum`` e ``devpath`` vêm vazios, e isso é uma
    resposta, não uma falha.
    """

    interface: str
    no: str = ""
    vid: str = ""
    pid: str = ""
    busnum: int = 0
    devpath: str = ""
    painel: str = ""
    atras_de_hub: bool = False
    controlador_pci: str = ""


@dataclass(frozen=True)
class RadioUsb:
    """Um aparelho USB que divide a faixa de 2,4 GHz com os controles.

    ``usb3`` sai de ``speed >= 5000`` e não é enfeite: USB 3.x emite ruído de
    banda larga bem em cima dos 2,4 GHz, e é essa medição — não um palpite —
    que autoriza a tela a dizê-lo.
    """

    no: str
    vid: str
    pid: str
    busnum: int = 0
    devpath: str = ""
    painel: str = ""
    atras_de_hub: bool = False
    controlador_pci: str = ""
    usb3: bool = False


@dataclass(frozen=True)
class Mesa:
    """A leitura inteira, de uma vez — o que a seção "A mesa" desenha.

    Existe para que haja UM ponto de injeção em vez de seis: quem fotografa a
    aba (``scripts/gui-captura/retratar_abas.py``) troca esta chamada por uma
    com raízes de mentira, e nenhum caminho de ``/sys`` real é tocado. A foto
    entra em ``docs/usage/assets`` sem revisão humana, e um endereço de rádio
    dela num PNG versionado não tem portão que pegue.
    """

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
    """As três leituras de uma vez — adaptadores, rádios e quem está colado.

    Uma varredura de ``/sys`` por chamada, sem subprocesso e sem abrir ``/dev``:
    nada aqui disputa o hidraw com o daemon. Chamada ao ENTRAR na aba e no
    botão "Reexaminar a mesa", nunca em tique — os tiques desta casa são de
    100 ms, 500 ms e 2 s (``status_actions.py:507``), e pendurar uma varredura
    de barramento em qualquer um deles é gastar CPU para reler o que não muda.

    A vizinhança é calculada sobre adaptadores E rádios juntos, de propósito: os
    dois avisos que a tela dá — "colado no vizinho" e "vizinho do adaptador" —
    são o MESMO cálculo com participantes diferentes.
    """
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
    """Os adaptadores Bluetooth da máquina, em ordem estável de interface.

    Lista VAZIA é a resposta mais comum e não é erro: é o estado desta bancada
    em 22/08/2026, e é também o de qualquer PC de mesa sem dongle. Quem chama
    tem de dizer isso na tela em vez de mostrar uma tabela em branco (M5).

    O nó do adaptador NÃO sai de ``raiz_bt/hciN`` direto: o ``realpath`` de lá
    aponta para a INTERFACE USB (medido: termina em ``.../3-3/3-3:1.0``), e é
    ``dispositivo_usb_pai`` (``usb_pai.py:68``) quem sobe até o dispositivo. Sem
    a subida, ``idVendor`` e ``physical_location`` não existem no caminho.
    """
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
            # Adaptador que não pendura em USB — embutido na placa-mãe, por
            # PCIe, UART ou SDIO. Ele EXISTE e a tela tem de dizer que existe;
            # o que ela não pode é inventar uma porta para ele.
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
      à pessoa que os controles dela atrapalham os controles dela (M4).

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
            # `1-3:1.0` é INTERFACE, não dispositivo: ela não tem `idVendor` e
            # multiplicaria o mesmo aparelho por quantas funções ele expuser.
            continue
        no = real(os.path.join(raiz_usb, nome))
        if no in nos_dos_adaptadores:
            continue
        vid = _campo(no, "idVendor", leitor).lower()
        pid = _campo(no, "idProduct", leitor).lower()
        if not vid or not pid:
            continue
        if _e_hub(_campo(no, "bDeviceClass", leitor)):
            # Hub NENHUM entra, nem o de raiz: um hub não é aparelho de rádio,
            # é o próprio barramento. Medido antes de existir esta linha — os
            # quatro `usbN` desta bancada entraram na tabela como se fossem
            # antenas, com `1d6b:0002` no lugar do nome.
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
    """Os pares de aparelhos COLADOS, como ``(nó, nó)`` — um par, um aviso.

    "Colado" é a conjunção de três leituras, e ela é conservadora de propósito:
    mesmo controlador PCI, mesmo barramento, e ``devpath`` numericamente
    vizinho dentro do mesmo hub (``3`` e ``4``; ``1.2`` e ``1.3``). Portas
    vizinhas no sysfs são, na esmagadora maioria dos gabinetes, portas vizinhas
    no metal — que é o que importa para dois rádios se atrapalharem.

    Cada par aparece UMA vez, na ordem dos nós. Devolver ``(a, b)`` e ``(b, a)``
    faria a tela mostrar dois avisos para um problema só.
    """
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


def _portas_vizinhas(uma: str, outra: str) -> bool:
    """``devpath`` numericamente adjacente NO MESMO hub — ``1.2`` e ``1.3``.

    O prefixo tem de bater: ``1.2`` e ``2.3`` são portas de hubs diferentes, e
    o número final vizinho ali é coincidência de numeração, não proximidade
    física.
    """
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
    """O PAI deste nó é um hub DE VERDADE, e não o hub-raiz do controlador?

    A exceção do hub-raiz é o que torna a resposta útil, e ela nasceu de uma
    medição: sem ela TODO aparelho da mesa sairia rotulado "em hub", porque
    todo aparelho pendura sob um hub-raiz, sempre, em qualquer PC.

    Nada de ``bMaxPower`` para saber se o hub tem fonte própria: MEDIDO, ele
    diz o contrário do palpite — o hub USB 3.1 alimentado reporta ``0mA`` e o
    USB 2.1 sem fonte reporta ``100mA``. Sem fonte de verdade, a tela não
    afirma.
    """
    pai = os.path.dirname(no)
    if not pai:
        return False
    if _HUB_RAIZ.match(os.path.basename(pai)):
        return False
    return _e_hub(_campo(pai, "bDeviceClass", ler))


def _painel(no: str, ler: Callable[[str], str]) -> str:
    """O painel do gabinete, na palavra do kernel — ``""`` quando ele não sabe.

    São SETE valores possíveis (``top``, ``bottom``, ``left``, ``right``,
    ``front``, ``back``, ``unknown``), e não os três que o desenho previa: esta
    bancada mede ``right`` em ``/sys/bus/usb/devices/1-3/physical_location/panel``.
    O arquivo simplesmente não existe em boa parte dos aparelhos — inclusive em
    todos os que estão atrás de um hub —, e ausência é ausência: quem traduz
    para palavra de tela é a janela, e ela diz "Não sei", nunca chuta.
    """
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
    """Lê um arquivo de ``/sys``; "" em qualquer erro — sysfs some sob a mão.

    Mesmas três linhas de ``usb_pai.py:212``, repetidas e não importadas: lá
    ela é privada, e um módulo de integração puxar o privado do outro é
    acoplamento que ninguém pediu.
    """
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
    "ler_a_mesa",
    "radios_do_barramento",
    "vizinhancas_apertadas",
]
