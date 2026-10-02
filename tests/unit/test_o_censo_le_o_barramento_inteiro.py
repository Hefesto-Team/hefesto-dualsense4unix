"""O censo universal do barramento USB — sem encostar no `/sys` desta máquina."""
from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    ESPECIE_DESCONHECIDA,
    GRAU_DESCONHECIDO,
    GRAU_LIDO,
    Censo,
    cadeia_de_hubs,
    hub_em_comum,
    ler_o_barramento,
)

RAIZ_USB = "/mentira/bus/usb/devices"
USB1 = "/mentira/devices/pci0000:00/0000:aa:00.0/usb1"
USB2 = "/mentira/devices/pci0000:00/0000:aa:00.0/usb2"
USB3 = "/mentira/devices/pci0000:00/0000:bb:00.3/usb3"
USB4 = "/mentira/devices/pci0000:00/0000:bb:00.3/usb4"

HUB_DE_BANCADA = f"{USB3}/3-3"
HUB_ENCADEADO = f"{HUB_DE_BANCADA}/3-3.1"
BLUETOOTH = (
    f"{HUB_ENCADEADO}/3-3.1.1",
    f"{HUB_ENCADEADO}/3-3.1.4",
    f"{HUB_DE_BANCADA}/3-3.2",
)
CAMERA = f"{USB4}/4-3/4-3.1/4-3.1.10"

APARELHOS: dict[str, dict[str, str]] = {
    USB1: {
        "idVendor": "1d6b",
        "idProduct": "0002",
        "bDeviceClass": "09",
        "busnum": "1",
        "devpath": "0",
        "speed": "480",
        "bMaxPower": "0mA",
        "bmAttributes": "e0",
        "manufacturer": "Linux xhci-hcd",
        "product": "xHCI Host Controller",
        "power/control": "on",
    },
    f"{USB1}/1-3": {
        "idVendor": "25a7",
        "idProduct": "fa07",
        "bDeviceClass": "00",
        "busnum": "1",
        "devpath": "3",
        "speed": "12",
        "bMaxPower": "98mA",
        "bmAttributes": "a0",
        "manufacturer": "Compx",
        "product": "2.4G Wireless Receiver",
        "physical_location/panel": "right",
        "power/control": "on",
        "port/over_current_count": "0",
    },
    f"{USB1}/1-4": {
        "idVendor": "3554",
        "idProduct": "fa09",
        "bDeviceClass": "00",
        "busnum": "1",
        "devpath": "4",
        "speed": "12",
        "bMaxPower": "100mA",
        "bmAttributes": "a0",
        "manufacturer": "CX",
        "product": "2.4G Wireless Receiver",
        "physical_location/panel": "right",
        "power/control": "on",
        "port/over_current_count": "0",
    },
    USB2: {
        "idVendor": "1d6b",
        "idProduct": "0003",
        "bDeviceClass": "09",
        "busnum": "2",
        "devpath": "0",
        "speed": "10000",
        "bMaxPower": "0mA",
        "bmAttributes": "e0",
        "manufacturer": "Linux xhci-hcd",
        "product": "xHCI Host Controller",
        "power/control": "on",
    },
    f"{USB2}/2-1": {
        "idVendor": "0781",
        "idProduct": "5583",
        "bDeviceClass": "08",
        "busnum": "2",
        "devpath": "1",
        "speed": "5000",
        "manufacturer": "Fabricante",
        "product": "Pendrive",
        "power/control": "auto",
    },
    USB3: {
        "idVendor": "1d6b",
        "idProduct": "0002",
        "bDeviceClass": "09",
        "busnum": "3",
        "devpath": "0",
        "speed": "480",
        "bMaxPower": "0mA",
        "bmAttributes": "e0",
        "manufacturer": "Linux xhci-hcd",
        "product": "xHCI Host Controller",
        "power/control": "on",
    },
    HUB_DE_BANCADA: {
        "idVendor": "05e3",
        "idProduct": "0610",
        "bDeviceClass": "09",
        "busnum": "3",
        "devpath": "3",
        "speed": "480",
        "bMaxPower": "100mA",
        "bmAttributes": "e0",
        "manufacturer": "GenesysLogic",
        "product": "USB2.1 Hub",
        "power/control": "on",
        "port/over_current_count": "0",
    },
    HUB_ENCADEADO: {
        "idVendor": "05e3",
        "idProduct": "0610",
        "bDeviceClass": "09",
        "busnum": "3",
        "devpath": "3.1",
        "speed": "480",
        "bMaxPower": "100mA",
        "bmAttributes": "e0",
        "manufacturer": "GenesysLogic",
        "product": "USB2.1 Hub",
        "power/control": "on",
        "port/over_current_count": "0",
    },
    BLUETOOTH[0]: {
        "idVendor": "2357",
        "idProduct": "0604",
        "bDeviceClass": "e0",
        "busnum": "3",
        "devpath": "3.1.1",
        "speed": "12",
        "bMaxPower": "500mA",
        "bmAttributes": "e0",
        "manufacturer": " ",
        "product": "TP-Link UB500 Adapter",
        "power/control": "on",
        "port/over_current_count": "0",
    },
    BLUETOOTH[1]: {
        "idVendor": "2357",
        "idProduct": "0604",
        "bDeviceClass": "e0",
        "busnum": "3",
        "devpath": "3.1.4",
        "speed": "12",
        "bMaxPower": "500mA",
        "bmAttributes": "e0",
        "manufacturer": " ",
        "product": "TP-Link Bluetooth USB Adapter",
        "power/control": "on",
        "port/over_current_count": "0",
    },
    BLUETOOTH[2]: {
        "idVendor": "2357",
        "idProduct": "0604",
        "bDeviceClass": "e0",
        "busnum": "3",
        "devpath": "3.2",
        "speed": "12",
        "bMaxPower": "500mA",
        "bmAttributes": "e0",
        "manufacturer": " ",
        "product": "TP-Link UB500 Adapter",
        "power/control": "on",
        "port/over_current_count": "0",
    },
    f"{HUB_DE_BANCADA}/3-3.3": {
        "idVendor": "258a",
        "idProduct": "010c",
        "bDeviceClass": "00",
        "busnum": "3",
        "devpath": "3.3",
        "speed": "12",
        "bMaxPower": "500mA",
        "bmAttributes": "a0",
        "manufacturer": "BY Tech",
        "product": "Gaming Keyboard",
        "power/control": "on",
        "port/over_current_count": "0",
    },
    USB4: {
        "idVendor": "1d6b",
        "idProduct": "0003",
        "bDeviceClass": "09",
        "busnum": "4",
        "devpath": "0",
        "speed": "10000",
        "bMaxPower": "0mA",
        "bmAttributes": "e0",
        "manufacturer": "Linux xhci-hcd",
        "product": "xHCI Host Controller",
        "power/control": "on",
    },
    f"{USB4}/4-1": {
        "idVendor": "2357",
        "idProduct": "012d",
        "bDeviceClass": "00",
        "busnum": "4",
        "devpath": "1",
        "speed": "5000",
        "bMaxPower": "504mA",
        "bmAttributes": "80",
        "manufacturer": "Realtek",
        "product": "802.11ac NIC",
        "power/control": "on",
        "port/over_current_count": "0",
    },
    f"{USB4}/4-3": {
        "idVendor": "05e3",
        "idProduct": "0626",
        "bDeviceClass": "09",
        "busnum": "4",
        "devpath": "3",
        "speed": "5000",
        "bMaxPower": "0mA",
        "bmAttributes": "e0",
        "manufacturer": "GenesysLogic",
        "product": "USB3.1 Hub",
        "power/control": "on",
        "port/over_current_count": "0",
    },
    f"{USB4}/4-3/4-3.1": {
        "idVendor": "05e3",
        "idProduct": "0626",
        "bDeviceClass": "09",
        "busnum": "4",
        "devpath": "3.1",
        "speed": "5000",
        "bMaxPower": "0mA",
        "bmAttributes": "e0",
        "manufacturer": "GenesysLogic",
        "product": "USB3.1 Hub",
        "power/control": "on",
        "port/over_current_count": "0",
    },
    f"{USB4}/4-3/4-3.1/4-3.1.2": {
        "idVendor": "046d",
        "idProduct": "0a44",
        "bDeviceClass": "00",
        "busnum": "4",
        "devpath": "3.1.2",
        "speed": "12",
        "bMaxPower": "100mA",
        "bmAttributes": "80",
        "manufacturer": "Logitech",
        "product": "Microfone",
        "power/control": "on",
        "port/over_current_count": "0",
    },
    CAMERA: {
        "idVendor": "046d",
        "idProduct": "0892",
        "bDeviceClass": "ef",
        "busnum": "4",
        "devpath": "3.1.10",
        "speed": "480",
        "bMaxPower": "500mA",
        "bmAttributes": "a0",
        "manufacturer": "Logitech",
        "product": "HD Pro Webcam",
        "power/control": "on",
        "port/over_current_count": "3",
    },
}

INTERFACES: dict[str, dict[str, str]] = {
    f"{USB1}/1-0:1.0": {"classe": "09", "subclasse": "00", "protocolo": "00"},
    f"{USB1}/1-3/1-3:1.0": {"classe": "03", "subclasse": "01", "protocolo": "02"},
    f"{USB1}/1-3/1-3:1.1": {"classe": "03", "subclasse": "01", "protocolo": "01"},
    f"{USB1}/1-4/1-4:1.0": {"classe": "03", "subclasse": "01", "protocolo": "01"},
    f"{USB1}/1-4/1-4:1.1": {"classe": "03", "subclasse": "01", "protocolo": "02"},
    f"{USB2}/2-0:1.0": {"classe": "09", "subclasse": "00", "protocolo": "00"},
    f"{USB3}/3-0:1.0": {"classe": "09", "subclasse": "00", "protocolo": "00"},
    f"{HUB_DE_BANCADA}/3-3:1.0": {"classe": "09", "subclasse": "00", "protocolo": "00"},
    f"{HUB_ENCADEADO}/3-3.1:1.0": {
        "classe": "09",
        "subclasse": "00",
        "protocolo": "00",
    },
    f"{BLUETOOTH[0]}/3-3.1.1:1.0": {
        "classe": "e0",
        "subclasse": "01",
        "protocolo": "01",
    },
    f"{BLUETOOTH[1]}/3-3.1.4:1.0": {
        "classe": "e0",
        "subclasse": "01",
        "protocolo": "01",
    },
    f"{BLUETOOTH[2]}/3-3.2:1.0": {"classe": "e0", "subclasse": "01", "protocolo": "01"},
    f"{HUB_DE_BANCADA}/3-3.3/3-3.3:1.0": {
        "classe": "03",
        "subclasse": "01",
        "protocolo": "01",
    },
    f"{HUB_DE_BANCADA}/3-3.3/3-3.3:1.1": {
        "classe": "03",
        "subclasse": "00",
        "protocolo": "00",
    },
    f"{USB4}/4-0:1.0": {"classe": "09", "subclasse": "00", "protocolo": "00"},
    f"{USB4}/4-1/4-1:1.0": {"classe": "ff", "subclasse": "ff", "protocolo": "ff"},
    f"{USB4}/4-3/4-3:1.0": {"classe": "09", "subclasse": "00", "protocolo": "00"},
    f"{USB4}/4-3/4-3.1/4-3.1:1.0": {
        "classe": "09",
        "subclasse": "00",
        "protocolo": "00",
    },
    f"{USB4}/4-3/4-3.1/4-3.1.2/4-3.1.2:1.0": {
        "classe": "01",
        "subclasse": "01",
        "protocolo": "00",
    },
    f"{CAMERA}/4-3.1.10:1.0": {"classe": "0e", "subclasse": "01", "protocolo": "00"},
}

_ATRIBUTO_DA_INTERFACE = {
    "classe": "bInterfaceClass",
    "subclasse": "bInterfaceSubClass",
    "protocolo": "bInterfaceProtocol",
}


class Bancada:
    """Um sysfs inteiro em memória, mais o registro de tudo que foi tocado."""

    def __init__(
        self,
        *,
        aparelhos: dict[str, dict[str, str]] | None = None,
        interfaces: dict[str, dict[str, str]] | None = None,
        listar: Callable[[str], list[str]] | None = None,
    ) -> None:
        self.aparelhos = APARELHOS if aparelhos is None else aparelhos
        self.interfaces = INTERFACES if interfaces is None else interfaces
        self._listar_de_fora = listar
        self.tocados: list[str] = []

        self.conteudo = {
            os.path.join(no, atributo): f"{valor}\n"
            for no, atributos in self.aparelhos.items()
            for atributo, valor in atributos.items()
        }
        self.conteudo.update(
            {
                os.path.join(caminho, _ATRIBUTO_DA_INTERFACE[chave]): f"{valor}\n"
                for caminho, campos in self.interfaces.items()
                for chave, valor in campos.items()
            }
        )
        self.reais = {
            os.path.join(RAIZ_USB, os.path.basename(caminho)): caminho
            for caminho in [*self.aparelhos, *self.interfaces]
        }
        self.listagem = sorted(
            os.path.basename(caminho)
            for caminho in [*self.aparelhos, *self.interfaces]
        )

    def listar(self, raiz: str) -> list[str]:
        self.tocados.append(raiz)
        if self._listar_de_fora is not None:
            return self._listar_de_fora(raiz)
        if raiz != RAIZ_USB:
            raise OSError(2, "não existe", raiz)
        return list(self.listagem)

    def ler(self, caminho: str) -> str:
        self.tocados.append(caminho)
        return self.conteudo.get(caminho, "")

    def real(self, caminho: str) -> str:
        self.tocados.append(caminho)
        return self.reais.get(caminho, caminho)

    def fontes(self) -> dict[str, Any]:
        return {
            "raiz_usb": RAIZ_USB,
            "listar": self.listar,
            "ler": self.ler,
            "real": self.real,
        }


def _censo() -> Censo:
    return ler_o_barramento(**Bancada().fontes())


def _por_nome(censo: Censo) -> dict[str, Any]:
    return {a.nome_do_kernel: a for a in censo.aparelhos}


def test_o_kernel_classifica_e_o_censo_so_traduz() -> None:
    """Cada espécie sai da tripla da interface 0, e o grau diz que foi lida."""
    achados = _por_nome(_censo())

    esperado = {
        "1-3": "Mouse",
        "1-4": "Teclado",
        "3-3": "Hub",
        "3-3.1.1": "Bluetooth",
        "3-3.3": "Teclado",
        "4-3.1.2": "Áudio",
        "4-3.1.10": "Câmera",
    }
    for nome, especie in esperado.items():
        assert achados[nome].especie == especie, (nome, achados[nome])
        assert achados[nome].grau == GRAU_LIDO, nome
        assert achados[nome].origem_da_classe == "interface 0", nome


def test_a_classe_sai_da_interface_e_nao_do_descritor_do_aparelho() -> None:
    """`bDeviceClass` vale `00` em todo aparelho composto — e são quase todos."""
    achados = _por_nome(_censo())
    mouse = achados["1-3"]

    assert mouse.classe == "03" and mouse.subclasse == "01"
    assert mouse.protocolo == "02"
    assert mouse.especie == "Mouse"
    assert APARELHOS[f"{USB1}/1-3"]["bDeviceClass"] == "00"


def test_o_teclado_e_o_mouse_so_se_separam_no_protocolo_da_interface_zero() -> None:
    """`1-3` e `1-4` expõem as MESMAS duas interfaces, em ordem trocada."""
    achados = _por_nome(_censo())

    assert achados["1-3"].especie == "Mouse"
    assert achados["1-4"].especie == "Teclado"
    assert INTERFACES[f"{USB1}/1-3/1-3:1.1"]["protocolo"] == "01"
    assert INTERFACES[f"{USB1}/1-4/1-4:1.1"]["protocolo"] == "02"


def test_o_ff_do_fabricante_nao_vira_wifi_por_causa_do_nome_do_produto() -> None:
    """`ff` é `ff`. O `product` diz "802.11ac NIC" e isso não classifica nada."""
    achados = _por_nome(_censo())
    sem_nome = achados["4-1"]

    assert sem_nome.classe == "ff"
    assert sem_nome.especie == ESPECIE_DESCONHECIDA
    assert sem_nome.grau == GRAU_DESCONHECIDO
    assert sem_nome.produto == "802.11ac NIC"
    assert sem_nome.origem_da_classe == "interface 0"


def test_um_no_sem_interface_cai_no_descritor_e_diz_de_onde_veio() -> None:
    """Aparelho ainda não configurado não tem interface — e ainda assim existe."""
    achados = _por_nome(_censo())
    pendrive = achados["2-1"]

    assert pendrive.especie == "Armazenamento"
    assert pendrive.grau == GRAU_LIDO
    assert pendrive.origem_da_classe == "descritor do aparelho"


def test_o_hub_raiz_nao_conta_como_estar_em_hub() -> None:
    """Todo aparelho pendura sob um hub-raiz — inclusive num PC sem hub nenhum."""
    censo = _censo()
    achados = _por_nome(censo)

    assert achados["1-3"].atras_de_hub is False
    assert achados["1-3"].pai == USB1
    assert achados["usb1"].e_raiz is True
    assert achados["usb1"].atras_de_hub is False
    assert achados["3-3"].atras_de_hub is False
    assert achados["3-3.1"].atras_de_hub is True
    assert cadeia_de_hubs(censo, achados["1-3"].no) == ()


def test_os_tres_bluetooth_estao_no_mesmo_hub_apesar_de_terem_pais_diferentes() -> None:
    """A medição que derrubou a premissa do roteiro desta onda."""
    censo = _censo()
    pais = {censo.aparelho(no).pai for no in BLUETOOTH if censo.aparelho(no)}

    assert len(pais) == 2, pais
    assert hub_em_comum(censo, list(BLUETOOTH)) == HUB_DE_BANCADA
    assert cadeia_de_hubs(censo, BLUETOOTH[0]) == (HUB_ENCADEADO, HUB_DE_BANCADA)
    assert cadeia_de_hubs(censo, BLUETOOTH[2]) == (HUB_DE_BANCADA,)


def test_sem_hub_em_comum_a_resposta_e_vazia_e_nao_o_controlador() -> None:
    """Dois aparelhos direto no raiz não estão "no mesmo hub" — estão em nenhum."""
    censo = _censo()
    achados = _por_nome(censo)

    assert hub_em_comum(censo, [achados["1-3"].no, achados["1-4"].no]) == ""
    assert hub_em_comum(censo, [BLUETOOTH[0], CAMERA]) == ""
    assert hub_em_comum(censo, []) == ""


def test_um_aparelho_atras_de_dois_hubs_conhece_a_cadeia_inteira() -> None:
    """A câmera está a dois hubs de distância, e os dois têm de aparecer."""
    censo = _censo()
    camera = censo.aparelho(CAMERA)

    assert camera is not None
    assert camera.atras_de_hub is True
    assert cadeia_de_hubs(censo, CAMERA) == (f"{USB4}/4-3/4-3.1", f"{USB4}/4-3")
    assert camera.controlador_pci == "0000:bb:00.3"


def test_energia_entrega_os_tres_numeros_e_nao_afirma_fonte_propria() -> None:
    """O bit de autoalimentado é DECLARAÇÃO, e nesta bancada ele se contradiz."""
    achados = _por_nome(_censo())

    dongle = achados["3-3.1.1"].energia
    assert dongle.corrente_pedida_ma == 500
    assert dongle.controle == "on"
    assert dongle.autoalimentado_declarado is True
    assert dongle.declaracao_incoerente is True

    hub = achados["4-3"].energia
    assert hub.corrente_pedida_ma == 0
    assert hub.autoalimentado_declarado is True
    assert hub.declaracao_incoerente is False

    barramento = achados["4-1"].energia
    assert barramento.autoalimentado_declarado is False
    assert barramento.declaracao_incoerente is False


def test_zero_e_ausencia_sao_respostas_diferentes_em_energia() -> None:
    """`0mA` é o hub dizendo zero; campo ausente é ninguém dizendo nada."""
    achados = _por_nome(_censo())

    sem_dado = achados["2-1"].energia
    assert sem_dado.corrente_pedida_ma is None
    assert sem_dado.excesso_de_corrente is None
    assert sem_dado.autoalimentado_declarado is None
    assert sem_dado.controle == "auto"

    assert achados["4-3"].energia.corrente_pedida_ma == 0
    assert achados["1-3"].energia.excesso_de_corrente == 0
    assert achados["4-3.1.10"].energia.excesso_de_corrente == 3


def test_o_fabricante_de_um_espaco_so_e_ausencia() -> None:
    """Medido: os TP-Link publicam `manufacturer` com um espaço dentro."""
    achados = _por_nome(_censo())

    assert achados["3-3.1.1"].fabricante == ""
    assert achados["3-3.1.1"].produto == "TP-Link UB500 Adapter"
    assert achados["1-3"].fabricante == "Compx"


def test_a_ordem_e_por_porta_numerica_e_nao_alfabetica() -> None:
    """`3.1.2` vem antes de `3.1.10`. Em texto, `10` vem antes de `2`."""
    censo = _censo()
    no_hub = [a.nome_do_kernel for a in censo.aparelhos if a.pai == f"{USB4}/4-3/4-3.1"]

    assert no_hub == ["4-3.1.2", "4-3.1.10"], no_hub
    nomes = [a.nome_do_kernel for a in censo.aparelhos]
    assert nomes[0] == "usb1" and nomes[-1] == "4-3.1.10", nomes


def test_o_barramento_agrupa_por_busnum_e_nao_por_controlador_pci() -> None:
    """Um controlador xHCI publica DOIS barramentos: o 2.0 e o 3.0."""
    censo = _censo()
    barramentos = {b.nome_do_kernel: b for b in censo.barramentos}

    assert len(censo.barramentos) == 4
    assert barramentos["usb3"].controlador_pci == "0000:bb:00.3"
    assert barramentos["usb4"].controlador_pci == "0000:bb:00.3"
    assert barramentos["usb3"].velocidade_mbps == 480.0
    assert barramentos["usb4"].velocidade_mbps == 10000.0
    assert set(barramentos["usb3"].aparelhos) == {
        HUB_DE_BANCADA,
        HUB_ENCADEADO,
        *BLUETOOTH,
        f"{HUB_DE_BANCADA}/3-3.3",
    }
    assert BLUETOOTH[0] not in barramentos["usb4"].aparelhos


def test_conectados_deixa_os_quatro_hubs_raiz_de_fora() -> None:
    """O hub-raiz não é aparelho: é o próprio barramento."""
    censo = _censo()

    vistos = {f"{a.vid}:{a.pid}" for a in censo.conectados()}
    assert "1d6b:0002" not in vistos and "1d6b:0003" not in vistos, vistos
    assert len(censo.conectados()) == len(censo.aparelhos) - 4
    assert len([a for a in censo.aparelhos if a.e_raiz]) == 4


def test_o_painel_do_gabinete_so_existe_onde_o_kernel_o_publica() -> None:
    """Dois aparelhos sabem onde estão; o resto não, e `unknown` é não saber."""
    achados = _por_nome(
        ler_o_barramento(
            **Bancada(
                aparelhos={
                    **APARELHOS,
                    BLUETOOTH[0]: {
                        **APARELHOS[BLUETOOTH[0]],
                        "physical_location/panel": "unknown",
                    },
                }
            ).fontes()
        )
    )

    assert achados["1-3"].painel == "right"
    assert achados["3-3.1.1"].painel == ""
    assert achados["4-1"].painel == ""


def test_censo_vazio_ou_ilegivel_devolve_nada_sem_levantar() -> None:
    """`/sys` ausente (contêiner, sandbox) não pode derrubar a janela."""
    vazia = ler_o_barramento(**Bancada(aparelhos={}, interfaces={}).fontes())
    assert vazia.aparelhos == ()
    assert vazia.barramentos == ()

    def _explode(_raiz: str) -> list[str]:
        raise OSError(13, "acesso negado")

    quebrada = ler_o_barramento(**Bancada(listar=_explode).fontes())
    assert quebrada.aparelhos == ()
    assert quebrada.barramentos == ()


def test_nenhum_caminho_do_sys_real_e_tocado() -> None:
    """O teste que protege a FOTO — e o único que morde o vazamento."""
    bancada = Bancada()
    ler_o_barramento(**bancada.fontes())

    escapados = [c for c in bancada.tocados if not c.startswith("/mentira")]
    assert not escapados, (
        "a leitura tocou caminhos fora da bancada injetada — "
        f"o primeiro é {escapados[0]!r}"
    )
    assert bancada.tocados, "nenhum leitor foi chamado: a bancada não provou nada"
