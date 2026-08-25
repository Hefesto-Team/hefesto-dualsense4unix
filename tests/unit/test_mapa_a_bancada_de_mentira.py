"""A bancada de mentira do mapa 2D — e a régua que confere a própria régua.

CONEXÕES · MAPA 2D 01 (25/08/2026). Todos os testes desta frente medem contra
UM sysfs em memória, e ele mora aqui. Nenhum arquivo é criado, nenhum caminho
de ``/sys`` desta máquina é tocado: os leitores entram por argumento, que é o
mesmo ponto de injeção que protege a foto da aba de publicar o barramento dela
num PNG versionado.

DE ONDE SAI ESTA BANCADA
-------------------------

Da leitura de **25/08/2026 às 02h30**, uid 1000, sem root, feita por quem
coordena a leva. Ela substitui a tabela de 24/08 às 21h que a sprint carrega:
entre as duas, a mantenedora moveu três aparelhos, tirou a webcam e tirou o
Wi-Fi do hub. Um teste escrito contra a tabela velha mediria uma mesa que não
existe mais::

    1-3      3554:fa09   receptor 2,4 GHz (teclado)   frente do gabinete
    1-6      25a7:fa07   receptor 2,4 GHz (mouse)     frente do gabinete
    3-1      05e3:0610   hub USB 2.1, lado 2.0
    3-1.1    05e3:0610   segundo chip do MESMO hub
    3-1.1.1  2357:0604   TP-Link UB500 (Bluetooth)
    3-1.1.4  2357:0604   TP-Link UB500 (Bluetooth), na ponta de uma extensão
    3-1.2    054c:0ce6   DualSense, por cabo
    4-1      05e3:0626   hub USB 3.1 — o MESMO plástico, lado 3.0
    4-1.1    05e3:0626   segundo chip, lado 3.0
    4-4      2357:012d   Archer T3U (Wi-Fi), numa traseira 3.0

O QUE AQUI É MEDIDO E O QUE É DA BANCADA
-----------------------------------------

**Medido:** os dez caminhos acima, os ``vid:pid``, as classes que o kernel
publica, o ``bMaxPower`` de cada um, o controlador ``0000:0c:00.3`` dos
barramentos 3 e 4, e o serial ``123456`` do Archer T3U — o contraexemplo que
prova que serial-é-endereço **não** é regra universal.

**Da bancada, não medido:** o endereço PCI do controlador dos barramentos 1 e
2 (aqui ``0000:0a:00.0``, um segundo controlador qualquer), e os dois seriais
dos adaptadores Bluetooth, forjados na faixa ``aa:bb:cc`` que esta casa usa
para dado de teste. Serial de verdade identifica a unidade dela tão bem quanto
o MAC, e não entra em arquivo versionado.

O DOIS ESTADOS, E OS DOIS SÃO REAIS
------------------------------------

:func:`bancada_de_agora` é a leitura de 25/08 às 02h30.
:func:`bancada_com_o_wifi_no_hub` é a MESMA mesa com o Archer T3U de volta em
``4-1.1.2``, que é onde ele estava às 21h de 24/08 — a leitura "antes" de um
ensaio real. Ele existe porque é o único estado em que o **hub de dois
barramentos** aparece: com o Wi-Fi na traseira, o lado 3.0 do hub está vazio e
a incoerência que a ``MAPA-6`` cura não tem como acontecer.
"""
from __future__ import annotations

import os
from typing import Any

from hefesto_dualsense4unix.integrations.censo_do_barramento import Censo
from hefesto_dualsense4unix.integrations.mesa_de_radio import Mesa
from hefesto_dualsense4unix.utils.maquina import MapaDaMesa

RAIZ_BT = "/mentira/class/bluetooth"
RAIZ_USB = "/mentira/bus/usb/devices"

#: Os quatro hubs-raiz. Os barramentos 3 e 4 são os dois lados do MESMO
#: controlador (medido: `0000:0c:00.3`), e é isso que faz o hub de dois chips
#: dela enumerar em dois barramentos.
_PCI_DE_1_E_2 = "0000:0a:00.0"
_PCI_DE_3_E_4 = "0000:0c:00.3"

USB1 = f"/mentira/devices/pci0000:00/{_PCI_DE_1_E_2}/usb1"
USB2 = f"/mentira/devices/pci0000:00/{_PCI_DE_1_E_2}/usb2"
USB3 = f"/mentira/devices/pci0000:00/{_PCI_DE_3_E_4}/usb3"
USB4 = f"/mentira/devices/pci0000:00/{_PCI_DE_3_E_4}/usb4"

#: O nó de cada aparelho, pelo nome do kernel. Escrito uma vez para que teste
#: nenhum precise montar caminho à mão.
NOS: dict[str, str] = {
    "usb1": USB1,
    "usb2": USB2,
    "usb3": USB3,
    "usb4": USB4,
    "1-3": f"{USB1}/1-3",
    "1-6": f"{USB1}/1-6",
    "3-1": f"{USB3}/3-1",
    "3-1.1": f"{USB3}/3-1/3-1.1",
    "3-1.1.1": f"{USB3}/3-1/3-1.1/3-1.1.1",
    "3-1.1.4": f"{USB3}/3-1/3-1.1/3-1.1.4",
    "3-1.2": f"{USB3}/3-1/3-1.2",
    "4-1": f"{USB4}/4-1",
    "4-1.1": f"{USB4}/4-1/4-1.1",
    "4-1.1.2": f"{USB4}/4-1/4-1.1/4-1.1.2",
    "4-4": f"{USB4}/4-4",
}

#: Os dois seriais forjados dos adaptadores Bluetooth. Doze hex, que é a forma
#: em que o TP-Link UB500 publica o próprio endereço — a coincidência que casa
#: as duas leituras. Faixa `aa:bb:cc`, que é dado de teste desta casa.
SERIAL_DO_BT_DO_HUB = "aabbcc0000a1"
SERIAL_DO_BT_DA_EXTENSAO = "aabbcc0000c4"

#: Como o BlueZ reporta os mesmos dois endereços: maiúsculas, com dois-pontos.
ENDERECO_DO_BT_DO_HUB = "AA:BB:CC:00:00:A1"
ENDERECO_DO_BT_DA_EXTENSAO = "AA:BB:CC:00:00:C4"

#: O serial do Archer T3U — MEDIDO, e é o contraexemplo inteiro: seis dígitos
#: decimais, que não são endereço de coisa nenhuma.
SERIAL_DO_WIFI = "123456"


def _raiz(busnum: str, velocidade: str) -> dict[str, str]:
    return {
        "idVendor": "1d6b",
        "idProduct": "0002" if velocidade == "480" else "0003",
        "bDeviceClass": "09",
        "busnum": busnum,
        "devnum": "1",
        "devpath": "0",
        "speed": velocidade,
        "bMaxPower": "0mA",
        "power/control": "on",
    }


#: `nó -> {atributo: valor}`. Atributo que falta falta de verdade: é assim que
#: "não sei" chega ao produto pelo mesmo caminho de uma máquina real.
_APARELHOS: dict[str, dict[str, str]] = {
    USB1: _raiz("1", "480"),
    USB2: _raiz("2", "10000"),
    USB3: _raiz("3", "480"),
    USB4: _raiz("4", "10000"),
    NOS["1-3"]: {
        "idVendor": "3554",
        "idProduct": "fa09",
        "bDeviceClass": "00",
        "busnum": "1",
        "devnum": "4",
        "devpath": "3",
        "speed": "12",
        "bMaxPower": "98mA",
        "power/control": "on",
        # MEDIDO, e é a prova de que o mapa não se deduz: as DUAS entradas da
        # frente respondem exatamente isto, iguais uma à outra.
        "physical_location/panel": "right",
    },
    NOS["1-6"]: {
        "idVendor": "25a7",
        "idProduct": "fa07",
        "bDeviceClass": "00",
        "busnum": "1",
        "devnum": "5",
        "devpath": "6",
        "speed": "12",
        "bMaxPower": "100mA",
        "power/control": "on",
        "physical_location/panel": "right",
    },
    NOS["3-1"]: {
        "idVendor": "05e3",
        "idProduct": "0610",
        "bDeviceClass": "09",
        "busnum": "3",
        "devnum": "2",
        "devpath": "1",
        "speed": "480",
        "bMaxPower": "100mA",
        "power/control": "on",
    },
    NOS["3-1.1"]: {
        "idVendor": "05e3",
        "idProduct": "0610",
        "bDeviceClass": "09",
        "busnum": "3",
        "devnum": "3",
        "devpath": "1.1",
        "speed": "480",
        "bMaxPower": "100mA",
        "power/control": "on",
    },
    NOS["3-1.1.1"]: {
        "idVendor": "2357",
        "idProduct": "0604",
        "bDeviceClass": "e0",
        "busnum": "3",
        "devnum": "6",
        "devpath": "1.1.1",
        "speed": "12",
        "bMaxPower": "500mA",
        "bmAttributes": "e0",
        "power/control": "on",
        "serial": SERIAL_DO_BT_DO_HUB,
    },
    NOS["3-1.1.4"]: {
        "idVendor": "2357",
        "idProduct": "0604",
        "bDeviceClass": "e0",
        "busnum": "3",
        "devnum": "7",
        "devpath": "1.1.4",
        "speed": "12",
        "bMaxPower": "500mA",
        "bmAttributes": "e0",
        "power/control": "on",
        "serial": SERIAL_DO_BT_DA_EXTENSAO,
    },
    NOS["3-1.2"]: {
        "idVendor": "054c",
        "idProduct": "0ce6",
        "bDeviceClass": "00",
        "busnum": "3",
        "devnum": "8",
        "devpath": "1.2",
        "speed": "12",
        "bMaxPower": "500mA",
        "power/control": "on",
    },
    NOS["4-1"]: {
        "idVendor": "05e3",
        "idProduct": "0626",
        "bDeviceClass": "09",
        "busnum": "4",
        "devnum": "2",
        "devpath": "1",
        "speed": "5000",
        "bMaxPower": "0mA",
        "power/control": "on",
    },
    NOS["4-1.1"]: {
        "idVendor": "05e3",
        "idProduct": "0626",
        "bDeviceClass": "09",
        "busnum": "4",
        "devnum": "3",
        "devpath": "1.1",
        "speed": "5000",
        "bMaxPower": "0mA",
        "power/control": "on",
    },
}

#: O Archer T3U. O nó muda de lugar entre os dois estados da mesa e o resto do
#: descritor é o mesmo — é literalmente o mesmo aparelho noutro buraco.
_WIFI = {
    "idVendor": "2357",
    "idProduct": "012d",
    "bDeviceClass": "00",
    "speed": "5000",
    "bMaxPower": "504mA",
    "power/control": "on",
    "serial": SERIAL_DO_WIFI,
}

#: `nó -> (classe, subclasse, protocolo)` da interface 0, que é de onde o censo
#: tira a espécie. O descritor do APARELHO vale `00` em todo aparelho composto.
_INTERFACES: dict[str, tuple[str, str, str]] = {
    USB1: ("09", "00", "00"),
    USB2: ("09", "00", "00"),
    USB3: ("09", "00", "00"),
    USB4: ("09", "00", "00"),
    NOS["1-3"]: ("03", "01", "01"),
    NOS["1-6"]: ("03", "01", "02"),
    NOS["3-1"]: ("09", "00", "00"),
    NOS["3-1.1"]: ("09", "00", "00"),
    NOS["3-1.1.1"]: ("e0", "01", "01"),
    NOS["3-1.1.4"]: ("e0", "01", "01"),
    NOS["3-1.2"]: ("03", "00", "00"),
    NOS["4-1"]: ("09", "00", "00"),
    NOS["4-1.1"]: ("09", "00", "00"),
}

#: Onde cada `hciN` aterrissa. No sysfs de verdade o link vai para a INTERFACE
#: (`3-1.1.1:1.0`), não para o dispositivo — quem sobe é o produto.
_INTERFACES_BT: dict[str, str] = {
    "hci0": f"{NOS['3-1.1.1']}/3-1.1.1:1.0",
    "hci1": f"{NOS['3-1.1.4']}/3-1.1.4:1.0",
}


class Bancada:
    """Um sysfs inteiro em memória, mais o registro de tudo que foi tocado."""

    def __init__(
        self,
        *,
        aparelhos: dict[str, dict[str, str]],
        interfaces: dict[str, tuple[str, str, str]],
        interfaces_bt: dict[str, str],
    ) -> None:
        self.aparelhos = aparelhos
        self.interfaces_bt = interfaces_bt
        #: Todo caminho que passou por qualquer um dos quatro leitores.
        self.tocados: list[str] = []

        self.conteudo = {
            os.path.join(no, atributo): f"{valor}\n"
            for no, atributos in aparelhos.items()
            for atributo, valor in atributos.items()
        }
        self.reais = {
            os.path.join(RAIZ_BT, nome): destino
            for nome, destino in interfaces_bt.items()
        }
        self.reais.update(
            {os.path.join(RAIZ_USB, os.path.basename(no)): no for no in aparelhos}
        )

        nomes_de_interface: list[str] = []
        for no, (classe, subclasse, protocolo) in interfaces.items():
            if no not in aparelhos:
                continue
            busnum = aparelhos[no]["busnum"]
            devpath = aparelhos[no]["devpath"]
            nome = f"{busnum}-{devpath}:1.0"
            alvo = f"{no}/{nome}"
            nomes_de_interface.append(nome)
            self.reais[os.path.join(RAIZ_USB, nome)] = alvo
            self.conteudo[os.path.join(alvo, "bInterfaceClass")] = f"{classe}\n"
            self.conteudo[os.path.join(alvo, "bInterfaceSubClass")] = f"{subclasse}\n"
            self.conteudo[os.path.join(alvo, "bInterfaceProtocol")] = f"{protocolo}\n"

        self.listagens = {
            RAIZ_BT: sorted(interfaces_bt),
            RAIZ_USB: sorted(
                [os.path.basename(no) for no in aparelhos] + nomes_de_interface
            ),
        }

    def listar(self, raiz: str) -> list[str]:
        self.tocados.append(raiz)
        if raiz not in self.listagens:
            raise OSError(2, "não existe", raiz)
        return list(self.listagens[raiz])

    def ler(self, caminho: str) -> str:
        self.tocados.append(caminho)
        return self.conteudo.get(caminho, "")

    def existe(self, caminho: str) -> bool:
        self.tocados.append(caminho)
        return caminho in self.conteudo

    def real(self, caminho: str) -> str:
        self.tocados.append(caminho)
        return self.reais.get(caminho, caminho)

    def serial(self, no: str) -> str:
        """O leitor de serial que :func:`porta_do_adaptador` recebe."""
        return self.ler(os.path.join(no, "serial"))

    def fontes(self) -> dict[str, Any]:
        return {
            "raiz_bt": RAIZ_BT,
            "raiz_usb": RAIZ_USB,
            "listar": self.listar,
            "ler": self.ler,
            "existe": self.existe,
            "real": self.real,
        }

    def censo(self) -> Censo:
        from hefesto_dualsense4unix.integrations.censo_do_barramento import (
            ler_o_barramento,
        )

        return ler_o_barramento(
            raiz_usb=RAIZ_USB, listar=self.listar, ler=self.ler, real=self.real
        )

    def mesa(self) -> Mesa:
        from hefesto_dualsense4unix.integrations.mesa_de_radio import ler_a_mesa

        return ler_a_mesa(**self.fontes())

    def adaptadores(self) -> list[Any]:
        from hefesto_dualsense4unix.integrations.mesa_de_radio import (
            adaptadores_bluetooth,
        )

        fontes = self.fontes()
        fontes.pop("raiz_usb")
        return adaptadores_bluetooth(**fontes)


def _com_o_wifi_em(nome: str) -> dict[str, dict[str, str]]:
    """A mesa inteira com o Archer T3U num nó ou noutro."""
    busnum, _, devpath = nome.partition("-")
    aparelhos = {no: dict(atributos) for no, atributos in _APARELHOS.items()}
    aparelhos[NOS[nome]] = {
        **_WIFI,
        "busnum": busnum,
        "devnum": "9",
        "devpath": devpath,
    }
    return aparelhos


def _interfaces_com_o_wifi_em(nome: str) -> dict[str, tuple[str, str, str]]:
    """O Archer declina de se classificar — classe `ff`, medida."""
    return {**_INTERFACES, NOS[nome]: ("ff", "ff", "ff")}


def bancada_de_agora() -> Bancada:
    """A leitura de 25/08/2026 às 02h30 — o Wi-Fi numa traseira 3.0."""
    return Bancada(
        aparelhos=_com_o_wifi_em("4-4"),
        interfaces=_interfaces_com_o_wifi_em("4-4"),
        interfaces_bt=dict(_INTERFACES_BT),
    )


def bancada_com_o_wifi_no_hub() -> Bancada:
    """A MESMA mesa às 21h de 24/08 — o Wi-Fi no lado 3.0 do hub.

    É o único estado em que o hub de dois barramentos aparece, e por isso é a
    bancada da ``MAPA-6``. Não é hipótese: é a leitura "antes" do ensaio que a
    mantenedora executou naquela noite.
    """
    return Bancada(
        aparelhos=_com_o_wifi_em("4-1.1.2"),
        interfaces=_interfaces_com_o_wifi_em("4-1.1.2"),
        interfaces_bt=dict(_INTERFACES_BT),
    )


def mapa_dela() -> MapaDaMesa:
    """O gabinete dela: três faces, quinze entradas, e uma por extensão.

    Os números são os que ela escreveu na foto do gabinete. As duas entradas da
    frente são as que a máquina não distingue (`1-3` e `1-6`); a entrada 4 é o
    cabo do hub; a 15a é o dongle na ponta da extensão que sai da 15.

    As entradas 7 e 11 declaram os DOIS lugares por onde o Archer T3U já
    passou. Só uma delas está ocupada de cada vez, e é assim que uma mesa
    declarada uma vez continua valendo quando ela troca um cabo de buraco.
    """
    return MapaDaMesa.model_validate(
        {
            "faces": [
                {"nome": "Frente", "portas": ["1", "2"]},
                {"nome": "Traseira", "portas": ["3", "4", "5", "6", "7", "8"]},
                {
                    "nome": "Hub",
                    "portas": ["9", "10", "11", "12", "13", "14", "15"],
                },
            ],
            "portas": {
                "1": {"caminho": "1-3"},
                "2": {"caminho": "1-6"},
                "4": {"caminho": "3-1"},
                "7": {"caminho": "4-4"},
                "9": {"caminho": "3-1.2"},
                "11": {"caminho": "4-1.1.2"},
                "13": {"caminho": "3-1.1.1"},
                "15a": {"caminho": "3-1.1.4", "filha_de": "15"},
            },
        }
    )


# --- A régua conferindo a própria régua -------------------------------------


def test_a_bancada_devolve_os_dez_aparelhos_da_leitura_de_agora() -> None:
    """O censo desta bancada é a leitura de 02h30, aparelho por aparelho.

    Instrumento não se usa sem calibrar. Se esta lista deixar de bater, todo
    teste desta frente passou a medir outra mesa — que é o defeito
    "medir contra a biblioteca errada produz alarme convincente e falso".
    """
    censo = bancada_de_agora().censo()
    nomes = sorted(a.nome_do_kernel for a in censo.conectados())

    assert nomes == [
        "1-3",
        "1-6",
        "3-1",
        "3-1.1",
        "3-1.1.1",
        "3-1.1.4",
        "3-1.2",
        "4-1",
        "4-1.1",
        "4-4",
    ], f"a bancada deixou de ser a leitura de 25/08 às 02h30: {nomes}"


def test_as_duas_entradas_da_frente_sao_indistinguiveis_para_a_maquina() -> None:
    """O fato que obriga o mapa a ser declarado, na bancada.

    Medido em 25/08/2026: `1-3` e `1-6` respondem `panel=right` os dois, e a
    ACPI desta placa nunca diz "front" nem "back". São faces diferentes do
    metal com a mesma resposta do kernel — deduzir aqui é errar.
    """
    censo = bancada_de_agora().censo()
    paineis = {
        a.nome_do_kernel: a.painel
        for a in censo.conectados()
        if a.nome_do_kernel in {"1-3", "1-6"}
    }

    assert paineis == {"1-3": "right", "1-6": "right"}, (
        "as duas entradas da frente deixaram de responder a mesma coisa; sem "
        f"isso a bancada não exercita o motivo do mapa existir: {paineis}"
    )


def test_o_hub_de_dois_chips_enumera_em_dois_barramentos() -> None:
    """`3-1` e `4-1` são o mesmo plástico — mesmo controlador, `devpath` igual."""
    censo = bancada_com_o_wifi_no_hub().censo()
    lados = {
        a.nome_do_kernel: (a.busnum, a.devpath, a.controlador_pci)
        for a in censo.conectados()
        if a.nome_do_kernel in {"3-1", "4-1"}
    }

    assert lados["3-1"][1] == lados["4-1"][1], "os dois lados perderam o devpath igual"
    assert lados["3-1"][0] != lados["4-1"][0], "os dois lados caíram no mesmo barramento"
    assert lados["3-1"][2] == lados["4-1"][2] == _PCI_DE_3_E_4, (
        f"os dois lados deixaram de pender do mesmo controlador PCI: {lados}"
    )


def test_a_bancada_nao_toca_um_caminho_do_sys_real() -> None:
    """Nenhum leitor desta bancada chega perto do `/sys` desta máquina."""
    bancada = bancada_de_agora()
    bancada.censo()
    bancada.mesa()

    vazados = [caminho for caminho in bancada.tocados if caminho.startswith("/sys")]
    assert not vazados, f"a bancada tocou o /sys real: {vazados[:5]}"
