"""O que a mesa já sabe dizer — a leitura do barramento, sem tocar em `/sys`.

CONFIG-02 (22/08/2026). `integrations/mesa_de_radio.py` responde três perguntas
que a janela nunca soube fazer: quais adaptadores Bluetooth existem e ONDE
estão, quais outros rádios dividem a faixa de 2,4 GHz, e quais aparelhos estão
colados um no outro.

POR QUE NÃO HÁ UMA ÁRVORE DE ARQUIVOS AQUI
-------------------------------------------

Nenhum teste deste arquivo cria diretório. O sysfs inteiro é um dicionário em
memória, entregue pelos mesmos argumentos injetáveis que o produto expõe
(`listar`, `ler`, `existe`, `real`) — o molde é
`test_a_placa_e_o_controle_pelo_usb_pai.py:212-286`. Duas razões, e a segunda é
a que importa:

1. a bancada de quem roda não é a bancada de quem escreveu. Esta máquina, em
   22/08/2026, tem ZERO adaptadores Bluetooth (`/sys/class/bluetooth` vazio) e
   nenhum hub — um teste contra o `/sys` real aqui não testaria nada e, na
   máquina seguinte, testaria outra coisa;
2. **o mesmo ponto de injeção é o que protege a foto.** O retratista da JANELA
   montava a aba de verdade para fotografá-la, e a foto entra em
   `docs/usage/assets` sem revisão humana. Sem raízes injetáveis, o PNG
   versionado carregaria o barramento dela. O teste
   `test_nenhum_caminho_do_sys_real_e_tocado` é o que segura essa porta.
   (Aquele retratista — `scripts/gui-captura/retratar_abas.py` — saiu com a
   janela em 06/09/2026. **A razão não caducou, e a injeção fica**: ela é
   também como a suíte lê uma mesa de mentira. Ver a nota gêmea em
   `integrations/mesa_de_radio.py`, na classe `Mesa`.)

A BANCADA DE MENTIRA
---------------------

Sete aparelhos, escolhidos para cobrir cada estado que a seção sabe desenhar::

    usb1 (PCI 0000:aa:00.0)   hub-raiz, classe 09
      1-1     adaptador   0a12:0001   porta 1     painel back
      1-2     hub         05e3:0608   porta 2     classe 09
        1-2.1 adaptador   0bda:8771   porta 2.1   sem painel, atrás de hub
        1-2.2 rádio       0bda:b812   porta 2.2   sem painel, USB 3.0
      1-3     rádio       1d57:fa20   porta 3     painel front
      1-4     rádio       046d:c52b   porta 4     painel front
      1-5     controle    054c:0ce6   porta 5     um DualSense no cabo
    usb2 (PCI 0000:bb:00.0)   hub-raiz, classe 09
      2-1     rádio       0cf3:3005   porta 1     painel right
"""
from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `app.actions.config`, que carrega o GTK")

from hefesto_dualsense4unix.integrations.mesa_de_radio import (
    RadioUsb,
    adaptadores_bluetooth,
    ler_a_mesa,
    radios_do_barramento,
    vizinhancas_apertadas,
)

RAIZ_BT = "/mentira/class/bluetooth"
RAIZ_USB = "/mentira/bus/usb/devices"
USB1 = "/mentira/devices/pci0000:00/0000:aa:00.0/usb1"
USB2 = "/mentira/devices/pci0000:00/0000:bb:00.0/usb2"

APARELHOS: dict[str, dict[str, str]] = {
    USB1: {
        "idVendor": "1d6b",
        "idProduct": "0002",
        "bDeviceClass": "09",
        "busnum": "1",
        "devnum": "1",
        "devpath": "0",
        "speed": "480",
    },
    f"{USB1}/1-1": {
        "idVendor": "0a12",
        "idProduct": "0001",
        "bDeviceClass": "e0",
        "busnum": "1",
        "devnum": "4",
        "devpath": "1",
        "speed": "12",
        "physical_location/panel": "back",
    },
    f"{USB1}/1-2": {
        "idVendor": "05e3",
        "idProduct": "0608",
        "bDeviceClass": "09",
        "busnum": "1",
        "devnum": "5",
        "devpath": "2",
        "speed": "480",
    },
    f"{USB1}/1-2/1-2.1": {
        "idVendor": "0bda",
        "idProduct": "8771",
        "bDeviceClass": "e0",
        "busnum": "1",
        "devnum": "6",
        "devpath": "2.1",
        "speed": "12",
    },
    f"{USB1}/1-2/1-2.2": {
        "idVendor": "0bda",
        "idProduct": "b812",
        "bDeviceClass": "00",
        "busnum": "1",
        "devnum": "7",
        "devpath": "2.2",
        "speed": "5000",
    },
    f"{USB1}/1-3": {
        "idVendor": "1d57",
        "idProduct": "fa20",
        "bDeviceClass": "00",
        "busnum": "1",
        "devnum": "8",
        "devpath": "3",
        "speed": "12",
        "physical_location/panel": "front",
    },
    f"{USB1}/1-4": {
        "idVendor": "046d",
        "idProduct": "c52b",
        "bDeviceClass": "00",
        "busnum": "1",
        "devnum": "9",
        "devpath": "4",
        "speed": "12",
        "physical_location/panel": "front",
    },
    f"{USB1}/1-5": {
        "idVendor": "054c",
        "idProduct": "0ce6",
        "bDeviceClass": "00",
        "busnum": "1",
        "devnum": "10",
        "devpath": "5",
        "speed": "480",
    },
    USB2: {
        "idVendor": "1d6b",
        "idProduct": "0003",
        "bDeviceClass": "09",
        "busnum": "2",
        "devnum": "1",
        "devpath": "0",
        "speed": "10000",
    },
    f"{USB2}/2-1": {
        "idVendor": "0cf3",
        "idProduct": "3005",
        "bDeviceClass": "00",
        "busnum": "2",
        "devnum": "3",
        "devpath": "1",
        "speed": "480",
        "physical_location/panel": "right",
    },
}

INTERFACES_BT: dict[str, str] = {
    "hci0": f"{USB1}/1-1/1-1:1.0",
    "hci1": f"{USB1}/1-2/1-2.1/1-2.1:1.0",
}


class Bancada:
    """Um sysfs inteiro em memória, mais o registro de tudo que foi tocado."""

    def __init__(
        self,
        *,
        aparelhos: dict[str, dict[str, str]] | None = None,
        interfaces_bt: dict[str, str] | None = None,
        listar: Callable[[str], list[str]] | None = None,
    ) -> None:
        self.aparelhos = APARELHOS if aparelhos is None else aparelhos
        self.interfaces_bt = INTERFACES_BT if interfaces_bt is None else interfaces_bt
        self._listar_de_fora = listar
        self.tocados: list[str] = []

        self.conteudo = {
            os.path.join(no, atributo): f"{valor}\n"
            for no, atributos in self.aparelhos.items()
            for atributo, valor in atributos.items()
        }
        self.reais = {
            os.path.join(RAIZ_BT, nome): destino
            for nome, destino in self.interfaces_bt.items()
        }
        self.reais.update(
            {
                os.path.join(RAIZ_USB, os.path.basename(no)): no
                for no in self.aparelhos
            }
        )
        self.listagens = {
            RAIZ_BT: sorted(self.interfaces_bt),
            RAIZ_USB: sorted(os.path.basename(no) for no in self.aparelhos),
        }

    def listar(self, raiz: str) -> list[str]:
        self.tocados.append(raiz)
        if self._listar_de_fora is not None:
            return self._listar_de_fora(raiz)
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

    def fontes(self) -> dict[str, Any]:
        return {
            "raiz_bt": RAIZ_BT,
            "raiz_usb": RAIZ_USB,
            "listar": self.listar,
            "ler": self.ler,
            "existe": self.existe,
            "real": self.real,
        }


def _so_um_adaptador() -> Bancada:
    """A mesma bancada, com `hci1` fora — uma mesa de UM adaptador."""
    return Bancada(interfaces_bt={"hci0": INTERFACES_BT["hci0"]})


def test_uma_mesa_de_um_adaptador_lista_um() -> None:
    """O aceite escrito da sprint, na única forma em que esta bancada o prova."""
    bancada = Bancada(
        interfaces_bt={
            "hci0": INTERFACES_BT["hci0"],
            "hci0:12": INTERFACES_BT["hci0"],
        }
    )
    achados = adaptadores_bluetooth(
        raiz_bt=RAIZ_BT,
        listar=bancada.listar,
        ler=bancada.ler,
        existe=bancada.existe,
        real=bancada.real,
    )

    assert len(achados) == 1
    assert achados[0].vid == "0a12"
    assert achados[0].pid == "0001"
    assert achados[0].busnum == 1
    assert achados[0].devpath == "1"


def test_o_hub_nao_entra_na_lista_de_radios() -> None:
    """Hub não é aparelho de rádio: é o próprio barramento."""
    bancada = Bancada()
    achados = radios_do_barramento(
        raiz_usb=RAIZ_USB, listar=bancada.listar, ler=bancada.ler, real=bancada.real
    )

    vistos = {f"{r.vid}:{r.pid}" for r in achados}
    assert "1d6b:0002" not in vistos and "1d6b:0003" not in vistos, vistos
    assert "05e3:0608" not in vistos, vistos


def test_um_dualsense_no_cabo_nao_e_outro_radio_que_divide_a_faixa() -> None:
    """A regra crua do roteiro faz o produto acusar os próprios controles.

    "Dispositivo USB que não é hub e não é o adaptador" inclui, nesta bancada
    real, os DOIS DualSense do cabo (`054c:0ce6` em `3-1` e `3-4`). A tela diria
    que os controles do usuário atrapalham os controles do usuário. Decisão M4.

    Mordida: apagar o `if vid in _VIDS_DE_CONTROLE: continue` o `054c:0ce6`
    entrou na lista e o teste reprovou.
    """
    bancada = Bancada()
    mesa = ler_a_mesa(**bancada.fontes())

    vistos = {f"{r.vid}:{r.pid}" for r in mesa.radios}
    assert "054c:0ce6" not in vistos, vistos
    assert vistos == {"0bda:b812", "1d57:fa20", "046d:c52b", "0cf3:3005"}


def test_o_adaptador_nao_aparece_tambem_na_lista_de_radios() -> None:
    """A mesma antena não pode contar duas vezes."""
    bancada = Bancada()
    mesa = ler_a_mesa(**bancada.fontes())

    nos_de_radio = {r.no for r in mesa.radios}
    for adaptador in mesa.adaptadores:
        assert adaptador.no not in nos_de_radio, adaptador


def test_dois_aparelhos_colados_geram_um_aviso_e_nao_dois() -> None:
    """Dois aparelhos, um problema — e a tela mostra um aviso."""
    bancada = Bancada()
    mesa = ler_a_mesa(**bancada.fontes())
    curtos = [
        (os.path.basename(um), os.path.basename(outro)) for um, outro in mesa.apertadas
    ]

    assert curtos == [("1-2.1", "1-2.2"), ("1-3", "1-4")], curtos


def test_portas_vizinhas_em_hubs_diferentes_nao_estao_coladas() -> None:
    """`1.2` e `2.3` têm número final vizinho e estão em hubs diferentes."""
    bancada = Bancada()
    mesa = ler_a_mesa(**bancada.fontes())
    colados = {
        os.path.basename(um) for par in mesa.apertadas for um in par
    }

    assert "2-1" not in colados
    pares = {tuple(sorted(os.path.basename(x) for x in par)) for par in mesa.apertadas}
    assert ("1-2.2", "1-3") not in pares, pares


def test_controladores_pci_diferentes_nunca_estao_colados() -> None:
    """Dois barramentos distintos não têm porta vizinha um do outro."""
    um = RadioUsb(
        no="/mentira/a",
        vid="1d57",
        pid="fa20",
        busnum=1,
        devpath="1",
        controlador_pci="0000:aa:00.0",
    )
    outro = RadioUsb(
        no="/mentira/b",
        vid="046d",
        pid="c52b",
        busnum=1,
        devpath="2",
        controlador_pci="0000:bb:00.0",
    )

    assert vizinhancas_apertadas([um, outro]) == []
    vizinho = RadioUsb(
        no="/mentira/b",
        vid="046d",
        pid="c52b",
        busnum=1,
        devpath="2",
        controlador_pci="0000:aa:00.0",
    )
    assert vizinhancas_apertadas([um, vizinho]) == [("/mentira/a", "/mentira/b")]


def test_sysfs_vazio_ou_ilegivel_devolve_lista_vazia_sem_levantar() -> None:
    """O estado REAL desta bancada, e o de qualquer PC sem dongle."""
    vazia = Bancada(aparelhos={}, interfaces_bt={})
    mesa = ler_a_mesa(**vazia.fontes())
    assert mesa.adaptadores == ()
    assert mesa.radios == ()
    assert mesa.apertadas == ()

    def _explode(_raiz: str) -> list[str]:
        raise OSError(13, "acesso negado")

    ilegivel = Bancada(listar=_explode)
    quebrada = ler_a_mesa(**ilegivel.fontes())
    assert quebrada.adaptadores == ()
    assert quebrada.radios == ()


def test_nenhum_caminho_do_sys_real_e_tocado() -> None:
    """O teste que protege a FOTO — e o único que morde o vazamento."""
    bancada = Bancada()
    ler_a_mesa(**bancada.fontes())

    escapados = [c for c in bancada.tocados if not c.startswith("/mentira")]
    assert not escapados, (
        "a leitura tocou caminhos fora da bancada injetada — "
        f"o primeiro é {escapados[0]!r}"
    )
    assert bancada.tocados, "nenhum leitor foi chamado: a bancada não provou nada"


