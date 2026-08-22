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
`test_a_placa_e_o_controle_pelo_usb_pai.py:271-345`. Duas razões, e a segunda é
a que importa:

1. a bancada de quem roda não é a bancada de quem escreveu. Esta máquina, em
   22/08/2026, tem ZERO adaptadores Bluetooth (`/sys/class/bluetooth` vazio) e
   nenhum hub — um teste contra o `/sys` real aqui não testaria nada e, na
   máquina seguinte, testaria outra coisa;
2. **o mesmo ponto de injeção é o que protege a foto.** `retratar_abas.py`
   monta a aba de verdade para fotografá-la, e a foto entra em
   `docs/usage/assets` sem revisão humana. Sem raízes injetáveis, o PNG
   versionado carregaria o barramento dela. O teste
   `test_nenhum_caminho_do_sys_real_e_tocado` é o que segura essa porta.

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

from hefesto_dualsense4unix.app.actions.config.secao_mesa import (
    _avisos_de_vizinhanca,
    _nome_do_adaptador,
    _onde_esta_o_adaptador,
    _onde_esta_o_radio,
    _painel_em_portugues,
)
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

#: `nó -> {atributo: valor}`. Atributo que falta falta de verdade: é assim que
#: "não sei" chega ao produto pelo mesmo caminho de uma máquina real.
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

#: Onde cada `hciN` aterrissa. No sysfs de verdade o link vai para a INTERFACE
#: (`1-1:1.0`), não para o dispositivo — quem sobe é o produto.
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
        #: Todo caminho que passou por qualquer um dos quatro leitores.
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
    """O aceite escrito da sprint, na única forma em que esta bancada o prova.

    A máquina de quem implementou tem ZERO adaptadores — `/sys/class/bluetooth`
    vazio, medido em 22/08/2026 —, então "numa máquina com um adaptador, lista
    um" só existe aqui dentro.

    Mordida: troquei o `_INTERFACE_BT.match(nome)` de `mesa_de_radio.py` por
    `nome.startswith("hci")`; com um nó de canal `hci0:12` na raiz, a lista
    passou a ter DOIS adaptadores e o teste reprovou em `len(achados) == 1`.
    """
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


def test_uma_mesa_de_dois_lista_dois_com_nomes_distintos_e_sem_hci() -> None:
    """Dois adaptadores, dois nomes diferentes, e `hciN` em nenhum deles.

    `hci0` e `hci1` invertem entre boots: um nome que troca de dono manda a
    pessoa mexer na porta errada. É a decisão M1, e é o aceite literal da
    sprint ("nomeia cada um pelo endereço, nunca por `hciN`").

    Mordida: fiz `_nome_do_adaptador` devolver `adaptador.interface`; o teste
    reprovou na asserção de que nenhum nome contém "hci".
    """
    bancada = Bancada()
    achados = adaptadores_bluetooth(
        raiz_bt=RAIZ_BT,
        listar=bancada.listar,
        ler=bancada.ler,
        existe=bancada.existe,
        real=bancada.real,
    )

    nomes = [_nome_do_adaptador(a) for a in achados]
    assert len(achados) == 2
    assert len(set(nomes)) == 2, f"os dois adaptadores têm o mesmo nome: {nomes}"
    assert not any("hci" in nome.lower() for nome in nomes), nomes
    # E a linha inteira também não pode carregá-lo: o "onde está" é a outra
    # metade da identidade física.
    onde = [_onde_esta_o_adaptador(a)[0] for a in achados]
    assert not any("hci" in texto.lower() for texto in onde), onde


def test_o_hub_raiz_nao_conta_como_estar_em_hub() -> None:
    """Todo aparelho pendura sob um hub-raiz — inclusive num PC sem hub nenhum.

    Sem a exceção do `^usb[0-9]+$`, a mesa INTEIRA sairia marcada "Em hub", que
    é o defeito mais fácil de acreditar desta sprint: a afirmação está errada e
    parece medida.

    Mordida: apaguei a guarda `_HUB_RAIZ.match(...)` de `_atras_de_hub`; o
    adaptador da porta 1, que está direto no hub-raiz, passou a sair como
    "Em hub" e o teste reprovou.
    """
    bancada = Bancada()
    achados = adaptadores_bluetooth(
        raiz_bt=RAIZ_BT,
        listar=bancada.listar,
        ler=bancada.ler,
        existe=bancada.existe,
        real=bancada.real,
    )
    direto = next(a for a in achados if a.devpath == "1")

    assert direto.atras_de_hub is False
    assert "hub" not in _onde_esta_o_adaptador(direto)[0].lower()


def test_o_hub_nao_entra_na_lista_de_radios() -> None:
    """Hub não é aparelho de rádio: é o próprio barramento.

    Mordida: tirei o `if _e_hub(...): continue` de `radios_do_barramento`; os
    dois hubs-raiz e o hub de porta entraram na tabela como se fossem antenas
    (`1d6b:0002`, `1d6b:0003`, `05e3:0608`) e o teste reprovou. Foi ASSIM que o
    defeito apareceu de verdade, na primeira leitura da bancada real.
    """
    bancada = Bancada()
    achados = radios_do_barramento(
        raiz_usb=RAIZ_USB, listar=bancada.listar, ler=bancada.ler, real=bancada.real
    )

    vistos = {f"{r.vid}:{r.pid}" for r in achados}
    assert "1d6b:0002" not in vistos and "1d6b:0003" not in vistos, vistos
    assert "05e3:0608" not in vistos, vistos


def test_atras_de_hub_e_sem_painel_sai_como_nao_sei() -> None:
    """O painel some atrás de um hub, e ausência não vira chute.

    O adaptador `1-2.1` está numa porta de hub e não tem
    `physical_location/panel`. "Frente" ali seria a tela afirmando o que
    ninguém mediu.

    Mordida: pus `_PAINEL_DESCONHECIDO = "Frente"` em `secao_mesa.py` — o
    palpite mais provável, que é o que torna o defeito perigoso; o teste
    reprovou nas duas asserções de baixo.
    """
    bancada = Bancada()
    achados = adaptadores_bluetooth(
        raiz_bt=RAIZ_BT,
        listar=bancada.listar,
        ler=bancada.ler,
        existe=bancada.existe,
        real=bancada.real,
    )
    no_hub = next(a for a in achados if a.devpath == "2.1")

    assert no_hub.atras_de_hub is True
    assert no_hub.painel == ""
    texto, dica = _onde_esta_o_adaptador(no_hub)
    assert "Não sei" in texto
    assert "Frente" not in texto and "Trás" not in texto
    assert texto.endswith("Em hub")
    # A dica do desenho prometia "e se ele tem fonte própria". `bMaxPower` NÃO
    # distingue hub alimentado — a promessa saiu e não pode voltar sem medição.
    assert dica is not None and "fonte" not in dica.lower()


def test_o_painel_direita_nao_vira_frente_nem_tras() -> None:
    """O kernel tem SETE palavras de painel, e esta bancada mede uma das cinco
    que o desenho não previa.

    Medido em 22/08/2026 na máquina de quem implementou:
    `/sys/bus/usb/devices/1-3/physical_location/panel` = `right`. Com um mapa
    de três valores (`front`/`back`/`unknown`), o único aparelho da casa que
    SABE onde está cairia em "Não sei".

    Mordida: tirei `right`, `left`, `top` e `bottom` do
    `_PAINEL_EM_PORTUGUES`; o rádio `2-1` passou a sair "Não sei" e o teste
    reprovou.
    """
    bancada = Bancada()
    achados = radios_do_barramento(
        raiz_usb=RAIZ_USB, listar=bancada.listar, ler=bancada.ler, real=bancada.real
    )
    lateral = next(r for r in achados if r.painel == "right")

    assert _onde_esta_o_radio(lateral, None) == "Direita"
    assert _painel_em_portugues("left") == "Esquerda"
    assert _painel_em_portugues("top") == "Cima"
    assert _painel_em_portugues("bottom") == "Baixo"
    assert _painel_em_portugues("unknown") == "Não sei"
    assert _painel_em_portugues("") == "Não sei"


def test_um_dualsense_no_cabo_nao_e_outro_radio_que_divide_a_faixa() -> None:
    """A regra crua do roteiro faz o produto acusar os próprios controles.

    "Dispositivo USB que não é hub e não é o adaptador" inclui, nesta bancada
    real, os DOIS DualSense do cabo (`054c:0ce6` em `3-1` e `3-4`). A tela diria
    que os controles dela atrapalham os controles dela. Decisão M4.

    Mordida: apaguei o `if vid in _VIDS_DE_CONTROLE: continue`; o `054c:0ce6`
    entrou na lista e o teste reprovou.
    """
    bancada = Bancada()
    mesa = ler_a_mesa(**bancada.fontes())

    vistos = {f"{r.vid}:{r.pid}" for r in mesa.radios}
    assert "054c:0ce6" not in vistos, vistos
    assert vistos == {"0bda:b812", "1d57:fa20", "046d:c52b", "0cf3:3005"}


def test_o_adaptador_nao_aparece_tambem_na_lista_de_radios() -> None:
    """A mesma antena não pode contar duas vezes.

    Mordida: apaguei o `if no in nos_dos_adaptadores: continue`; `0a12:0001` e
    `0bda:8771` apareceram na tabela de rádios e o teste reprovou.
    """
    bancada = Bancada()
    mesa = ler_a_mesa(**bancada.fontes())

    nos_de_radio = {r.no for r in mesa.radios}
    for adaptador in mesa.adaptadores:
        assert adaptador.no not in nos_de_radio, adaptador


def test_dois_aparelhos_colados_geram_um_aviso_e_nao_dois() -> None:
    """Dois aparelhos, um problema — e a tela mostra um aviso.

    "Colado" exige as três leituras juntas: mesmo controlador PCI, mesmo
    barramento e `devpath` vizinho DENTRO do mesmo hub. `1-3` e `1-4` casam;
    `1-2.2` e `1-3` não, porque `2.2` e `3` são portas de hubs diferentes.

    Mordida: fiz `vizinhancas_apertadas` devolver também o par invertido
    (`(b, a)`); os dois rádios do par passaram a carregar o aviso e o teste
    reprovou em `len(pares) == 2`.
    """
    bancada = Bancada()
    mesa = ler_a_mesa(**bancada.fontes())
    curtos = [
        (os.path.basename(um), os.path.basename(outro)) for um, outro in mesa.apertadas
    ]

    assert curtos == [("1-2.1", "1-2.2"), ("1-3", "1-4")], curtos


def test_portas_vizinhas_em_hubs_diferentes_nao_estao_coladas() -> None:
    """`1.2` e `2.3` têm número final vizinho e estão em hubs diferentes.

    Sem a comparação de prefixo, a coincidência de numeração viraria aviso de
    proximidade física — e um aviso falso ensina a ignorar os verdadeiros.

    Mordida: fiz `_portas_vizinhas` comparar só a cauda numérica; o par
    `1-2.2`/`1-3` (portas `2.2` e `3`) passou a ser "colado" e o teste reprovou.
    """
    bancada = Bancada()
    mesa = ler_a_mesa(**bancada.fontes())
    colados = {
        os.path.basename(um) for par in mesa.apertadas for um in par
    }

    assert "2-1" not in colados
    pares = {tuple(sorted(os.path.basename(x) for x in par)) for par in mesa.apertadas}
    assert ("1-2.2", "1-3") not in pares, pares


def test_controladores_pci_diferentes_nunca_estao_colados() -> None:
    """Dois barramentos distintos não têm porta vizinha um do outro.

    Mordida: apaguei a comparação de `controlador_pci` em
    `vizinhancas_apertadas`; os dois rádios abaixo, que só compartilham o
    número do barramento, viraram um par "colado" e o teste reprovou.
    """
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
    # E com o MESMO controlador o par existe — senão a asserção de cima
    # passaria por qualquer motivo, inclusive pelo errado.
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
    """O estado REAL desta bancada, e o de qualquer PC sem dongle.

    `/sys/class/bluetooth` vazio não é erro: é a resposta. E `/sys` inteiro
    ilegível (contêiner, sandbox) também não pode derrubar a janela.

    Mordida: tirei o `except OSError: return []` das duas varreduras; a leitura
    passou a propagar `FileNotFoundError` e o teste reprovou com a exceção
    subindo até aqui.
    """
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
    """O teste que protege a FOTO — e o único que morde o vazamento.

    `retratar_abas.py` monta esta aba para fotografá-la, e o PNG entra em
    `docs/usage/assets` sem revisão humana. Nenhum portão desta casa varre
    imagem: `test_retrato_das_abas_nao_vaza_dado_real` inspeciona o SCRIPT, e
    `check_test_data.sh` só olha `tests/`. Se a leitura escapar para `/sys`
    quando as raízes foram injetadas, o barramento dela vai para a
    documentação.

    Mordida: pus de volta um `os.listdir("/sys/bus/usb/devices")` dentro de
    `radios_do_barramento`, ignorando a raiz recebida — exatamente o deslize
    que uma constante de módulo produz; o teste reprovou listando o caminho
    absoluto tocado.
    """
    bancada = Bancada()
    ler_a_mesa(**bancada.fontes())

    escapados = [c for c in bancada.tocados if not c.startswith("/mentira")]
    assert not escapados, (
        "a leitura tocou caminhos fora da bancada injetada — "
        f"o primeiro é {escapados[0]!r}"
    )
    assert bancada.tocados, "nenhum leitor foi chamado: a bancada não provou nada"


def test_um_adaptador_sem_no_usb_ainda_aparece_e_nao_inventa_porta() -> None:
    """Rádio Bluetooth embutido na placa não pendura em USB — e existe.

    Uma lista que o esconda faria a pessoa procurar um dongle que ela não tem;
    uma linha com "Barramento 0, porta " seria pior ainda.

    Mordida: fiz o ramo sem nó USB dar `continue` em vez de registrar o
    adaptador; a mesa passou a listar UM em vez de dois e o teste reprovou.
    """
    bancada = Bancada(interfaces_bt={"hci0": "/mentira/devices/platform/serial0/hci0"})
    achados = adaptadores_bluetooth(
        raiz_bt=RAIZ_BT,
        listar=bancada.listar,
        ler=bancada.ler,
        existe=bancada.existe,
        real=bancada.real,
    )

    assert len(achados) == 1
    assert achados[0].no == ""
    assert _nome_do_adaptador(achados[0]) == "Adaptador embutido"
    assert _onde_esta_o_adaptador(achados[0]) == ("Dentro da máquina", None)


def test_o_radio_ao_lado_de_um_adaptador_ganha_o_aviso_do_adaptador() -> None:
    """Os dois avisos saem do MESMO par de nós colados, e não são o mesmo aviso.

    "Colado no vizinho" fala de dois rádios se atrapalhando; "vizinho do
    adaptador N" fala de ruído em cima da antena que serve os controles — que é
    o problema caro. O aviso vai sempre no RÁDIO, porque é ele que tem coluna de
    aviso e é ele que a pessoa vai mudar de porta.

    A dica do USB 3.0 só aparece onde `speed >= 5000` foi MEDIDO: ela afirma
    "USB 3.0 emite ruído de banda larga", e mostrá-la sobre um receptor USB 2.0
    seria explicar o problema errado.

    Mordida: fiz `ler_a_mesa` calcular a vizinhança só sobre os rádios; o par
    `1-2.1`/`1-2.2` sumiu, o rádio ficou sem aviso e o teste reprovou.
    """
    bancada = Bancada()
    mesa = ler_a_mesa(**bancada.fontes())
    avisos = _avisos_de_vizinhanca(mesa)

    vizinho = next(r for r in mesa.radios if os.path.basename(r.no) == "1-2.2")
    sufixo, dica = avisos[vizinho.no]
    assert sufixo == "vizinho do adaptador 2"
    assert vizinho.usb3 is True
    assert dica.startswith("USB 3.0")
    assert _onde_esta_o_radio(vizinho, avisos[vizinho.no]) == (
        "Não sei · vizinho do adaptador 2"
    )

    # E o par de dois rádios recebe o OUTRO aviso, uma vez só.
    colados = [no for no, (texto, _d) in avisos.items() if texto == "colado no vizinho"]
    assert [os.path.basename(no) for no in colados] == ["1-4"]


def test_sem_o_segundo_adaptador_o_mesmo_par_vira_dois_radios_colados() -> None:
    """A mesma porta muda de aviso quando muda o que está nela.

    Com `hci1` fora, `1-2.1` deixa de ser adaptador e passa a ser mais um rádio:
    o par continua colado, e o texto passa a ser o de dois rádios — não o do
    adaptador, que já não existe naquela porta.

    Mordida: fiz `_avisos_de_vizinhanca` sempre escrever "vizinho do adaptador
    1"; sem adaptador nenhum naquele par, o teste reprovou no texto.
    """
    bancada = _so_um_adaptador()
    mesa = ler_a_mesa(**bancada.fontes())
    avisos = _avisos_de_vizinhanca(mesa)

    assert len(mesa.adaptadores) == 1
    assert len(mesa.radios) == 5, [f"{r.vid}:{r.pid}" for r in mesa.radios]
    textos = {os.path.basename(no): texto for no, (texto, _d) in avisos.items()}
    assert textos == {"1-2.2": "colado no vizinho", "1-4": "colado no vizinho"}
