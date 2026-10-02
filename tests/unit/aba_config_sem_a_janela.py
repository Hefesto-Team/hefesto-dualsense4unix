"""A aba Configurações montada SEM a janela GTK — o berço que sobrou.

POR QUE ELE EXISTE — 06/09/2026, sprint `GTK-3`
-----------------------------------------------

A aba Configurações **nunca morou no `gui/main.glade`**: o XML reservava o
container (`tab_config_box`) e as cinco seções nasciam em código, em
`app/actions/config/`, que é MOTOR e a sprint manda ficar. Três réguas de
redação e de saúde montavam a aba de verdade para medir o texto e os selos, e
todas as três abriam o glade **só para pegar a caixa vazia**.

Com o XML apagado (`D-0609-GTK-LEVA-INTEIRA`), o berço passa a ser feito em
código. O que se mede continua sendo o mesmo: o que o MOTOR escreve dentro da
caixa.

O DUBLÊ NASCEU FROUXO, E A MEDIÇÃO PEGOU — a razão de ele ter DOIS widgets
--------------------------------------------------------------------------

A primeira versão devolvia só a caixa. Medido no mesmo dia, contra o
`main.glade` de `98f2a6a4` restaurado do git e montado no MESMO processo:

    com o glade   5 seções · 196 textos
    com a caixa   5 seções · 193 textos      ← TRÊS A MENOS, em silêncio

As três eram *"Ligar junto com o computador"*, *"Desligado"* e *"Este valor é
um espelho. Quem liga e desliga é o interruptor da aba Sistema."* —
`secao_janela._linha_do_espelho` (`:440`) devolve `None` quando
`daemon_autostart_switch` não existe, e a linha inteira some sem levantar. Uma
régua de redação que não vê três frases é uma régua que passa com a frase
errada dentro.

**É a cicatriz desta casa, e ela é literal:** *"três dublês eram mais frouxos
que o daemon vivo"* (05/09/2026). Por isso o berço declara o interruptor, e por
isso `FRASES_DO_ESPELHO` existe: a régua
`test_o_berco_nao_e_mais_frouxo_que_o_glade` cobra as três pelo NOME.

O PISO CONTAVA A MÁQUINA — 13/09/2026, sprint `BERCO-SEM-A-BANCADA-01`
----------------------------------------------------------------------

Em 08/09/2026 a mesma aba colhia 189 textos num processo solto e 186 sob a
suíte — as três frases do censo do gabinete saem de um arquivo que o
`install.sh` grava sob o `HOME`, e o `conftest` desvia o `HOME` —, e por isso a
régua cobrava um PISO com folga de três, e não a igualdade.

A suíte do fecho de 13/09 reprovou 172 contra 186, igual em `9639f1df` e em
`e7d1dac2`, e o `e7d1dac2` tinha fechado verde às 05:40 do mesmo dia: mesmo
código, outra máquina. A queda inteira estava em "Conexões", que lia o
barramento USB DE VERDADE — o hospedeiro não injetava leitor nenhum, e
`secao_mesa._PainelDaMesa` cai em `ler_a_mesa()`, `ler_o_barramento()` e
`listar_entradas()` quando o hospedeiro não traz os seus. Catorze textos a
menos sobre o mesmo código, e a régua de redação reprovava o produto.

Desde então `HospedeiroDaAbaConfig` injeta uma bancada de mentira FIXA
(`APARELHOS_DA_BANCADA`) e fixa também o gabinete, e a diferença entre os
ambientes acabou: **190 textos** num processo solto sob um lar vazio, 190 sob
um lar com o produto instalado e declarado, e 190 sob a suíte. Ver
`FOLGA_DO_AMBIENTE` e `PISO_DA_COLHEITA`.

**E UM EFEITO QUE VEM JUNTO, declarado.** Com `_mesa_leitor` de pé, "Os
controles" e "Desempenho" também deixam de pedir o `daemon.state_full` na
montagem — é a guarda do retrato em `secao_controles._e_bancada_de_retrato` e
em `secao_orcamento._ContaDeSlots.pedir_o_estado`. O texto colhido não muda (a
colheita já era tomada antes de a resposta chegar); o que some são os dois
pedidos, contados num processo solto sem a injeção.

`ConfigActionsMixin._get` é o único caminho pelo qual as seções pedem widget, e
`daemon_autostart_switch` é o ÚNICO id que elas pedem — conferido com

    grep -rn '_get("' src/hefesto_dualsense4unix/app/actions/config/
"""
from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config import ABA_CONFIG
from hefesto_dualsense4unix.app.actions.config.mixin import (
    ConfigActionsMixin,
)
from hefesto_dualsense4unix.integrations import (
    censo_do_barramento,
    entradas_do_gabinete,
    mesa_de_radio,
)

SECOES_NO_GLADE = 5

FRASES_DO_ESPELHO = (
    "Ligar junto com o computador",
    "Este valor é um espelho. Quem liga e desliga é o interruptor da aba Sistema.",
)

FOLGA_DO_AMBIENTE = 0

#: "Os controles" por não haver controle ligado. Medido com QUATRO DualSense
PISO_DA_COLHEITA = 194

PISO_POR_SECAO = 6


_PCI_A = "0000:aa:00.0"
_PCI_B = "0000:bb:00.0"
_RAIZ_BT = "/bancada/class/bluetooth"
_RAIZ_USB = "/bancada/bus/usb/devices"
_USB_A = f"/bancada/devices/pci0000:00/{_PCI_A}/usb61"
_USB_B = f"/bancada/devices/pci0000:00/{_PCI_B}/usb62"

APARELHOS_DA_BANCADA: dict[str, dict[str, str]] = {
    f"{_USB_A}/61-1": {
        "idVendor": "0fab",
        "idProduct": "0001",
        "bDeviceClass": "e0",
        "busnum": "61",
        "devnum": "2",
        "devpath": "1",
        "speed": "12",
        "physical_location/panel": "back",
    },
    f"{_USB_A}/61-2": {
        "idVendor": "0bad",
        "idProduct": "0002",
        "bDeviceClass": "09",
        "busnum": "61",
        "devnum": "3",
        "devpath": "2",
        "speed": "480",
    },
    f"{_USB_A}/61-2/61-2.1": {
        "idVendor": "0fab",
        "idProduct": "0001",
        "bDeviceClass": "e0",
        "busnum": "61",
        "devnum": "4",
        "devpath": "2.1",
        "speed": "12",
    },
    f"{_USB_A}/61-2/61-2.2": {
        "idVendor": "0cab",
        "idProduct": "0003",
        "bDeviceClass": "00",
        "busnum": "61",
        "devnum": "5",
        "devpath": "2.2",
        "speed": "5000",
    },
    f"{_USB_A}/61-3": {
        "idVendor": "0abc",
        "idProduct": "0004",
        "bDeviceClass": "00",
        "busnum": "61",
        "devnum": "6",
        "devpath": "3",
        "speed": "12",
        "physical_location/panel": "front",
    },
    f"{_USB_A}/61-4": {
        "idVendor": "0a0a",
        "idProduct": "0005",
        "bDeviceClass": "00",
        "busnum": "61",
        "devnum": "7",
        "devpath": "4",
        "speed": "12",
        "physical_location/panel": "front",
    },
    f"{_USB_B}/62-1": {
        "idVendor": "0e0e",
        "idProduct": "0006",
        "bDeviceClass": "00",
        "busnum": "62",
        "devnum": "2",
        "devpath": "1",
        "speed": "480",
        "physical_location/panel": "right",
    },
}

INTERFACES_DA_BANCADA: dict[str, tuple[str, str, str]] = {
    f"{_USB_A}/61-1/61-1:1.0": ("e0", "01", "01"),
    f"{_USB_A}/61-2/61-2:1.0": ("09", "00", "00"),
    f"{_USB_A}/61-2/61-2.1/61-2.1:1.0": ("e0", "01", "01"),
    f"{_USB_A}/61-2/61-2.2/61-2.2:1.0": ("ff", "ff", "ff"),
    f"{_USB_A}/61-3/61-3:1.0": ("03", "01", "01"),
    f"{_USB_A}/61-4/61-4:1.0": ("03", "01", "02"),
    f"{_USB_B}/62-1/62-1:1.0": ("e0", "01", "01"),
}

_INTERFACES_BT: dict[str, str] = {
    "hci0": f"{_USB_A}/61-1/61-1:1.0",
    "hci1": f"{_USB_A}/61-2/61-2.1/61-2.1:1.0",
}

Listar = Callable[[str], list[str]]
Ler = Callable[[str], str]
Existe = Callable[[str], bool]
Real = Callable[[str], str]


def sysfs_da_bancada() -> tuple[Listar, Ler, Existe, Real]:
    """`(listar, ler, existe, real)` — o sysfs de mentira, e nada além dele."""
    conteudo = {
        os.path.join(no, atributo): f"{valor}\n"
        for no, atributos in APARELHOS_DA_BANCADA.items()
        for atributo, valor in atributos.items()
    }
    conteudo.update(
        {
            os.path.join(no, atributo): f"{valor}\n"
            for no, tripla in INTERFACES_DA_BANCADA.items()
            for atributo, valor in zip(
                ("bInterfaceClass", "bInterfaceSubClass", "bInterfaceProtocol"),
                tripla,
                strict=True,
            )
        }
    )
    presentes = set(conteudo)
    reais = {
        os.path.join(_RAIZ_BT, nome): destino for nome, destino in _INTERFACES_BT.items()
    }
    reais.update(
        {
            os.path.join(_RAIZ_USB, os.path.basename(no)): no
            for no in (*APARELHOS_DA_BANCADA, *INTERFACES_DA_BANCADA)
        }
    )
    listagens = {
        _RAIZ_BT: sorted(_INTERFACES_BT),
        _RAIZ_USB: sorted(
            os.path.basename(no)
            for no in (*APARELHOS_DA_BANCADA, *INTERFACES_DA_BANCADA)
        ),
    }
    return (
        lambda raiz: list(listagens.get(raiz, [])),
        lambda caminho: conteudo.get(caminho, ""),
        lambda caminho: caminho in presentes,
        lambda caminho: reais.get(caminho, caminho),
    )


def mesa_da_bancada() -> mesa_de_radio.Mesa:
    """Adaptadores, rádios e quem está colado — `ler_a_mesa` sobre a bancada."""
    listar, ler, existe, real = sysfs_da_bancada()
    return mesa_de_radio.ler_a_mesa(
        raiz_bt=_RAIZ_BT,
        raiz_usb=_RAIZ_USB,
        listar=listar,
        ler=ler,
        existe=existe,
        real=real,
    )


def censo_da_bancada() -> censo_do_barramento.Censo:
    """O barramento inteiro da bancada — `ler_o_barramento` com a raiz trocada."""
    listar, ler, _existe, real = sysfs_da_bancada()
    return censo_do_barramento.ler_o_barramento(
        raiz_usb=_RAIZ_USB, listar=listar, ler=ler, real=real
    )


def entradas_da_bancada() -> tuple[entradas_do_gabinete.NoDeEntrada, ...]:
    """Os nós de entrada da bancada — `listar_entradas` com a raiz trocada."""
    listar, ler, _existe, real = sysfs_da_bancada()
    return entradas_do_gabinete.listar_entradas(
        raiz_usb=_RAIZ_USB, listar=listar, ler=ler, real=real
    )


def _cor_nenhuma(_uniq: str) -> None:
    """A cor do plástico que nenhum aparelho respondeu."""
    return None


class BercoDaAbaConfig:
    """O que o `Gtk.Builder` do glade entregava às seções, e nada mais."""

    def __init__(self) -> None:
        self.caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.caixa.set_name(ABA_CONFIG)
        self.interruptor_do_arranque = Gtk.Switch()

    def get_object(self, nome: str) -> Any:
        if nome == ABA_CONFIG:
            return self.caixa
        if nome == "daemon_autostart_switch":
            return self.interruptor_do_arranque
        return None


class HospedeiroDaAbaConfig(ConfigActionsMixin):
    """O mínimo que o mixin precisa para montar a aba: um `builder` e a bancada."""

    def __init__(self, builder: BercoDaAbaConfig | None = None) -> None:
        self.builder = builder or BercoDaAbaConfig()
        self._mesa_leitor = mesa_da_bancada
        self._censo_leitor = censo_da_bancada
        self._entradas_leitor = entradas_da_bancada
        self._gabinete_leitor = dict
        self._cor_do_plastico_leitor = _cor_nenhuma


def aba_config_montada() -> Any:
    """Monta as cinco seções em código e devolve a caixa da aba."""
    hospedeiro = HospedeiroDaAbaConfig()
    hospedeiro.install_config_tab()
    return hospedeiro.builder.get_object(ABA_CONFIG)


def textos_da_arvore(raiz: Any) -> list[str]:
    """Todo texto visível da árvore — rótulo, rótulo de botão e dica."""
    achados: list[str] = []
    pilha = [raiz]
    while pilha:
        widget = pilha.pop()
        if isinstance(widget, Gtk.Label):
            texto = widget.get_text()
            if texto:
                achados.append(texto)
        obter_rotulo = getattr(widget, "get_label", None)
        if obter_rotulo is not None and not isinstance(widget, Gtk.Label):
            texto = obter_rotulo()
            if texto:
                achados.append(texto)
        dica = widget.get_tooltip_text()
        if dica:
            achados.append(dica)
        if isinstance(widget, Gtk.Frame):
            rotulo = widget.get_label_widget()
            if rotulo is not None:
                pilha.append(rotulo)
        obter_filhos = getattr(widget, "get_children", None)
        if obter_filhos is not None:
            pilha.extend(obter_filhos())
    return achados
