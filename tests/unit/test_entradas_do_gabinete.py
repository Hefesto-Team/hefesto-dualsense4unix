"""As entradas USB — inclusive as vazias — sem encostar no `/sys` desta máquina.

`integrations/entradas_do_gabinete.py` lê os NÓS de entrada (que existem mesmo
com a entrada vazia) e os agrupa em BURACOS pelo symlink `peer`. Estes testes
provam as duas coisas que a `CALIBRAR-AS-ENTRADAS-01` chama de fatais: um buraco
3.x tem dois nós e é UM buraco, e a entrada vazia aparece na lista.

POR QUE NÃO HÁ UMA ÁRVORE DE ARQUIVOS AQUI
-------------------------------------------

Nenhum teste deste arquivo cria diretório. O sysfs inteiro é um dicionário em
memória, entregue pelos argumentos injetáveis que o produto expõe (`listar`,
`ler`, `real`) — o molde é `test_o_censo_le_o_barramento_inteiro.py`. Duas
razões, e a segunda é a que importa:

1. a bancada de quem roda não é a bancada de quem escreveu. Um teste contra o
   `/sys` real passaria aqui e mediria outra coisa na máquina seguinte;
2. o mesmo ponto de injeção é o que protege a FOTO da janela de calibração.
   `test_nenhum_caminho_do_sys_real_e_tocado` é o que segura essa porta.

A BANCADA DE MENTIRA
---------------------

Copiada da medição desta casa em 25/08/2026, com caminhos `/mentira`. Sem o hub
externo (que ela desplugou às 02h36) são **22 nós** e **15 buracos**, que é o
número real da mesa dela::

    usb1  480 Mbps   10 nós   usb1-port1 .. usb1-port10
        port3   configured  device=1-3   panel=right  h=left  v=lower   teclado
        port4   configured  device=1-4                                  DualSense
        port5   not attached             peer=usb2-port1
        port6   configured  device=1-6   panel=right  h=left  v=lower   mouse
                                         peer=usb2-port2
        port7   not attached             peer=usb2-port3
    usb2  10000 Mbps  4 nós   port1..port3 pareados com usb1; port4 sozinho
    usb3  480 Mbps    4 nós   pareados um a um com usb4; connect_type=unknown
    usb4  10000 Mbps  4 nós   port4 configured device=4-4 (Wi-Fi)

`usb1-port3` e `usb1-port6` são **byte a byte iguais** nos três campos que o
kernel decodifica: é a prova medida de que a frente do gabinete não é dedutível,
e por isso o lugar tem de ser declarado.

Com o hub (`Bancada(com_hub=True)`) entram `3-1` em `usb3-port1` e mais quatro
nós `3-1-port1..4`, um deles com `3-1.2` dentro — 26 nós e 19 buracos. O hub
**não publica `speed`**, e é assim que a bancada exercita o terceiro estado de
`Furo.rapido`: "não sei".
"""
from __future__ import annotations

import os
from collections.abc import Callable

import pytest

from hefesto_dualsense4unix.integrations.entradas_do_gabinete import (
    ESTADO_VAZIO,
    Furo,
    NoDeEntrada,
    entrada_de,
    furo_declarado,
    furos,
    listar_entradas,
    vazias,
)

RAIZ = "/mentira/bus/usb/devices"
PCI_A = "/mentira/devices/pci0000:00/0000:aa:00.0"
PCI_B = "/mentira/devices/pci0000:00/0000:bb:00.3"
USB1 = f"{PCI_A}/usb1"
USB2 = f"{PCI_A}/usb2"
USB3 = f"{PCI_B}/usb3"
USB4 = f"{PCI_B}/usb4"
HUB = f"{USB3}/3-1"

#: `nome do hub -> (caminho real, interface, velocidade, quantas entradas)`.
#: `""` na velocidade = o atributo não é legível, que é o caso "não sei".
_HUBS: dict[str, tuple[str, str, str, int]] = {
    "usb1": (USB1, "1-0:1.0", "480", 10),
    "usb2": (USB2, "2-0:1.0", "10000", 4),
    "usb3": (USB3, "3-0:1.0", "480", 4),
    "usb4": (USB4, "4-0:1.0", "10000", 4),
    "3-1": (HUB, "3-1:1.0", "", 4),
}

#: `nó -> atributos`. Atributo que falta falta de verdade: é assim que "não sei"
#: chega ao produto pelo mesmo caminho de uma máquina real.
_ATRIBUTOS: dict[str, dict[str, str]] = {
    "usb1-port3": {
        "state": "configured",
        "connect_type": "hotplug",
        "physical_location/panel": "right",
        "physical_location/horizontal_position": "left",
        "physical_location/vertical_position": "lower",
        "over_current_count": "0",
    },
    "usb1-port4": {
        "state": "configured",
        "connect_type": "hotplug",
        "physical_location/panel": "right",
        "over_current_count": "0",
    },
    "usb1-port6": {
        "state": "configured",
        "connect_type": "hotplug",
        "physical_location/panel": "right",
        "physical_location/horizontal_position": "left",
        "physical_location/vertical_position": "lower",
        "over_current_count": "0",
    },
    "usb4-port4": {"state": "configured", "connect_type": "unknown"},
}

#: Os dois nós que só respondem `configured` COM o hub plugado. Sem ele, o
#: `usb3-port1` volta a dizer `not attached`, que é o estado real dela desde as
#: 02h36 — e é o que faz a conta da caminhada subir de 10 para 11.
_ATRIBUTOS_COM_HUB: dict[str, dict[str, str]] = {
    "usb3-port1": {"state": "configured", "connect_type": "unknown"},
    "3-1-port2": {"state": "configured", "connect_type": "hotplug"},
}

#: O padrão de todo nó que a tabela acima não nomeia — a entrada VAZIA, que é a
#: maioria e a razão desta tela existir.
_VAZIO_DE_RAIZ = {"state": ESTADO_VAZIO, "connect_type": "hotplug"}
_VAZIO_INTERNO = {"state": ESTADO_VAZIO, "connect_type": "unknown"}

#: Painel dos nós de `usb1` que a tabela não nomeia. As entradas 1, 2 e 7 a 10
#: dizem `left`; as 3 a 6 dizem `right`.
_PAINEL_DE_USB1 = {
    numero: "right" if 3 <= numero <= 6 else "left" for numero in range(1, 11)
}

#: `peer`, nos dois sentidos — o kernel publica sempre os dois lados.
_PARES: dict[str, str] = {
    "usb1-port5": "usb2-port1",
    "usb1-port6": "usb2-port2",
    "usb1-port7": "usb2-port3",
    "usb3-port1": "usb4-port1",
    "usb3-port2": "usb4-port2",
    "usb3-port3": "usb4-port3",
    "usb3-port4": "usb4-port4",
}
_PARES.update({destino: origem for origem, destino in _PARES.items()})

#: `nó de entrada -> aparelho encaixado`, e o caminho real de cada aparelho.
_APARELHOS: dict[str, str] = {
    "usb1-port3": "1-3",
    "usb1-port4": "1-4",
    "usb1-port6": "1-6",
    "usb4-port4": "4-4",
}
_APARELHOS_COM_HUB: dict[str, str] = {"usb3-port1": "3-1", "3-1-port2": "3-1.2"}
_CAMINHO_DO_APARELHO: dict[str, str] = {
    "1-3": f"{USB1}/1-3",
    "1-4": f"{USB1}/1-4",
    "1-6": f"{USB1}/1-6",
    "4-4": f"{USB4}/4-4",
    "3-1": HUB,
    "3-1.2": f"{HUB}/3-1.2",
}

#: A interface de um aparelho existe na raiz e **não** hospeda entrada nenhuma.
#: Ela está aqui para provar que a varredura filtra por FORMA do nome, e não por
#: sorte de o diretório estar vazio.
_INTERFACE_DE_APARELHO = "1-3:1.0"

#: Interface que some entre o `listdir` da raiz e o dela — o hub desplugado no
#: meio da leitura. A varredura tem de seguir, não cair.
_INTERFACE_QUE_SUMIU = "1-4:1.0"


class Bancada:
    """O `/sys` inteiro em memória, atrás dos três leitores injetáveis."""

    def __init__(self, *, com_hub: bool = False) -> None:
        self.com_hub = com_hub
        #: Todo caminho que passou por qualquer um dos três leitores.
        self.tocados: list[str] = []

        self.hubs = dict(_HUBS) if com_hub else {
            nome: dados for nome, dados in _HUBS.items() if nome != "3-1"
        }
        self.aparelhos = dict(_APARELHOS)
        if com_hub:
            self.aparelhos.update(_APARELHOS_COM_HUB)
        else:
            self.aparelhos.pop("usb3-port1", None)

        self.nos: dict[str, str] = {}
        for hub, (caminho, interface, _, quantas) in self.hubs.items():
            for numero in range(1, quantas + 1):
                nome = f"{hub}-port{numero}"
                self.nos[nome] = f"{caminho}/{interface}/{nome}"

    # -- os três leitores ---------------------------------------------------

    def listar(self, raiz: str) -> list[str]:
        self.tocados.append(raiz)
        if raiz == RAIZ:
            nomes = [*self.hubs, _INTERFACE_DE_APARELHO, _INTERFACE_QUE_SUMIU]
            nomes += [interface for _, interface, _, _ in self.hubs.values()]
            nomes += [
                aparelho
                for no, aparelho in self.aparelhos.items()
                if no in self.nos
            ]
            return nomes
        for hub, (caminho, interface, _, quantas) in self.hubs.items():
            if raiz == f"{caminho}/{interface}":
                return [f"{hub}-port{numero}" for numero in range(1, quantas + 1)]
        if raiz.endswith(_INTERFACE_DE_APARELHO):
            return []
        raise OSError(2, "não existe", raiz)

    def ler(self, caminho: str) -> str:
        self.tocados.append(caminho)
        no, _, atributo = caminho.partition("/physical_location/")
        if atributo:
            return self._atributo(no, f"physical_location/{atributo}")
        no, atributo = os.path.split(caminho)
        if atributo == "speed":
            return self._velocidade(no)
        return self._atributo(no, atributo)

    def real(self, caminho: str) -> str:
        self.tocados.append(caminho)
        pai, folha = os.path.split(caminho)
        if folha in ("peer", "device", "port"):
            alvo = self._alvo(pai, folha)
            if alvo:
                return alvo
            return caminho
        if pai == RAIZ:
            return self._caminho_de(folha)
        return caminho

    # -- interno ------------------------------------------------------------

    def _caminho_de(self, nome: str) -> str:
        if nome in self.hubs:
            return self.hubs[nome][0]
        if nome in _CAMINHO_DO_APARELHO:
            return _CAMINHO_DO_APARELHO[nome]
        for caminho, interface, _, _ in self.hubs.values():
            if nome == interface:
                return f"{caminho}/{interface}"
        return f"{RAIZ}/{nome}"

    def _velocidade(self, caminho: str) -> str:
        for real, _, velocidade, _ in self.hubs.values():
            if caminho == real:
                return f"{velocidade}\n" if velocidade else ""
        return "480\n"

    def _atributo(self, caminho: str, atributo: str) -> str:
        nome = os.path.basename(caminho)
        if self.nos.get(nome) != caminho:
            return ""
        tabela = dict(_ATRIBUTOS)
        if self.com_hub:
            tabela.update(_ATRIBUTOS_COM_HUB)
        valores = dict(tabela.get(nome, self._vazio(nome)))
        if nome.startswith("usb1-") and "physical_location/panel" not in valores:
            valores["physical_location/panel"] = _PAINEL_DE_USB1[
                int(nome.rsplit("port", 1)[1])
            ]
        valor = valores.get(atributo, "")
        return f"{valor}\n" if valor else ""

    def _vazio(self, nome: str) -> dict[str, str]:
        interno = nome.startswith(("usb3-", "usb4-"))
        return _VAZIO_INTERNO if interno else _VAZIO_DE_RAIZ

    def _alvo(self, caminho: str, folha: str) -> str:
        nome = os.path.basename(caminho)
        if folha == "peer":
            par = _PARES.get(nome, "")
            return self.nos.get(par, "") if par else ""
        if folha == "device":
            return _CAMINHO_DO_APARELHO.get(self.aparelhos.get(nome, ""), "")
        # `port`: o symlink que o APARELHO publica de volta para o nó.
        aparelho = os.path.basename(caminho)
        for no, encaixado in self.aparelhos.items():
            if encaixado == aparelho:
                return self.nos.get(no, "")
        return ""

    def fontes(self) -> dict[str, Callable[[str], object] | str]:
        return {
            "raiz_usb": RAIZ,
            "listar": self.listar,
            "ler": self.ler,
            "real": self.real,
        }


def _entradas(*, com_hub: bool = False) -> tuple[NoDeEntrada, ...]:
    bancada = Bancada(com_hub=com_hub)
    return listar_entradas(
        raiz_usb=RAIZ,
        listar=bancada.listar,
        ler=bancada.ler,
        real=bancada.real,
    )


def _furo_com(lista: tuple[Furo, ...], no: str) -> Furo | None:
    return next((furo for furo in lista if no in furo.nos), None)


# ---------------------------------------------------------------------------
# As duas mordidas nomeadas na sprint
# ---------------------------------------------------------------------------


def test_o_par_2_0_e_3_0_e_um_furo_so() -> None:
    """`usb1-port5` e `usb2-port1` são o MESMO buraco do gabinete.

    Um buraco USB 3.x aparece duas vezes no `/sys`, e o DualSense (que é 2.0)
    sempre enumera do lado 2.0. Contar nós daria 22 buracos onde existem 15.

    Mordida: arranquei o `peer` do agrupamento (`furos` devolvendo um `Furo` por
    nó). Os dois nós viraram dois buracos, a conta foi de 15 para 22, e o teste
    reprovou nomeando o par que era um só.
    """
    lista = furos(_entradas())
    furo = _furo_com(lista, "usb1-port5")

    assert furo is not None, "o nó `usb1-port5` sumiu da leitura"
    assert furo.nos == ("usb1-port5", "usb2-port1"), (
        "`usb1-port5` e `usb2-port1` são o mesmo buraco (peer), e sairam "
        f"separados: {furo.nos}"
    )
    assert len(lista) == 15, (
        f"a mesa dela tem 15 buracos e 22 nós; contei {len(lista)} — "
        "sinal de que o `peer` não agrupou"
    )


def test_entrada_vazia_aparece_com_state_not_attached() -> None:
    """A entrada SEM aparelho existe na lista, e é a razão desta tela existir.

    O nó da entrada responde `state` sempre: `configured` com aparelho,
    `not attached` sem. É o único jeito de o produto saber que a entrada existe.

    Mordida: arranquei listando só quem tem `device` (filtro `if aparelho`). A
    lista caiu de 22 para 4 nós, `usb1-port5` sumiu, e o teste reprovou.
    """
    entradas = _entradas()
    por_nome = {entrada.no: entrada for entrada in entradas}

    assert "usb1-port5" in por_nome, (
        "a entrada vazia sumiu da lista — sem ela a calibração não tem o que "
        f"mostrar; sobraram {len(entradas)} nós"
    )
    vazia = por_nome["usb1-port5"]
    assert vazia.estado == ESTADO_VAZIO
    assert vazia.aparelho == ""
    assert vazia.vazio is True
    assert len(entradas) == 22, (
        f"a mesa dela publica 22 nós de raiz; contei {len(entradas)}"
    )


# ---------------------------------------------------------------------------
# O buraco ocupado, o hub que sumiu, e o resto do contrato
# ---------------------------------------------------------------------------


def test_a_caminhada_nao_visita_o_buraco_onde_o_mouse_dela_esta() -> None:
    """`usb2-port2` diz `not attached` e o buraco dele tem o mouse dentro.

    O mouse é 2.0 e ocupa `usb1-port6`; o lado 3.x do MESMO buraco continua
    respondendo `not attached`. Perguntar por nó mandaria ela se ajoelhar para
    encaixar um cabo onde já tem aparelho — o F-2 da sprint.

    Mordida: arranquei o `all()` de `Furo.vazio` para `any()`. O buraco do mouse
    entrou na caminhada, a lista foi de 11 para 12, e o teste reprovou.
    """
    entradas = _entradas()
    caminhada = vazias(entradas)
    nos_da_caminhada = {no for furo in caminhada for no in furo.nos}

    assert "usb2-port2" not in nos_da_caminhada, (
        "`usb2-port2` é o lado 3.x do buraco onde o mouse `1-6` está — "
        "a caminhada não pode mandar ninguém lá"
    )
    assert all(not furo.aparelho for furo in caminhada)
    assert len(caminhada) == 11, (
        f"4 buracos ocupados de 15 deixam 11 para a caminhada; contei "
        f"{len(caminhada)}"
    )


def test_o_hub_que_sumiu_nao_vira_entrada_inexistente() -> None:
    """Desplugar o hub apaga os nós dele — e o LUGAR continua no mapa.

    `furo_declarado` devolve `None`, e `None` quer dizer "o barramento não
    mostra isso agora", nunca "essa entrada não existe". É o estado real dela
    desde as 02h36 de 25/08/2026.
    """
    com_hub = _entradas(com_hub=True)
    sem_hub = _entradas()

    assert len(com_hub) == 26 and len(sem_hub) == 22
    presente = furo_declarado(["3-1-port2"], com_hub)
    assert presente is not None and presente.aparelho == "3-1.2"
    assert furo_declarado(["3-1-port2"], sem_hub) is None
    # E o que continua plugado não é afetado pela ausência do hub.
    assert furo_declarado(["usb1-port3"], sem_hub) is not None


def test_entrada_de_atravessa_o_symlink_do_aparelho() -> None:
    """Entrada OCUPADA não precisa de caminhada: o aparelho diz onde está.

    `<dispositivo>/port` é o symlink que `censo_do_barramento.py:447` já
    atravessa. A busca final é pela lista de nós do buraco, nunca por uma chave
    montada — o F-5 mostrou que chave sem `busnum` colide os dois lados do mesmo
    controlador.
    """
    entradas = _entradas()
    bancada = Bancada()

    furo = entrada_de("1-6", entradas, raiz_usb=RAIZ, real=bancada.real)
    assert furo is not None
    assert furo.nos == ("usb1-port6", "usb2-port2")
    assert furo.aparelho == "1-6"
    assert entrada_de("9-9", entradas, raiz_usb=RAIZ, real=bancada.real) is None


def test_a_frente_do_gabinete_nao_e_dedutivel() -> None:
    """As duas entradas da frente dela são IGUAIS nos três campos decodificados.

    Medido em 25/08/2026: `usb1-port3` (teclado) e `usb1-port6` (mouse) dizem
    `panel=right`, `horizontal_position=left`, `vertical_position=lower` — byte
    a byte o mesmo. É a prova de que o lugar tem de ser DECLARADO, e este teste
    existe para que ninguém volte a tentar deduzi-lo.
    """
    por_nome = {entrada.no: entrada for entrada in _entradas()}
    tres_campos = [
        (
            por_nome[nome].painel,
            por_nome[nome].posicao_horizontal,
            por_nome[nome].posicao_vertical,
        )
        for nome in ("usb1-port3", "usb1-port6")
    ]

    assert tres_campos[0] == tres_campos[1] == ("right", "left", "lower")


def test_rapido_tem_tres_estados_e_o_terceiro_e_nao_sei() -> None:
    """"Esta entrada é azul" não sai do `peer` — sai da velocidade do hub.

    Buraco com um nó em hub de 10 Gbps é rápido; buraco só em hub de 480 não é;
    e hub cujo `speed` não é legível responde `None`, que é o produto dizendo
    "não sei" em vez de chutar.
    """
    lista = furos(_entradas(com_hub=True))

    par = _furo_com(lista, "usb1-port5")
    sozinho = _furo_com(lista, "usb1-port3")
    no_hub = _furo_com(lista, "3-1-port1")

    assert par is not None and par.rapido is True
    assert sozinho is not None and sozinho.rapido is False
    assert no_hub is not None and no_hub.rapido is None


def test_a_ordem_poe_port10_depois_de_port2() -> None:
    """Ordem alfabética poria `usb1-port10` entre a 1 e a 2.

    A tela conta "entrada 4 de 15": com a ordem errada, o número aponta para o
    buraco errado, e a pessoa é mandada ao lugar errado do gabinete.
    """
    nomes = [entrada.no for entrada in _entradas() if entrada.hub == "usb1"]

    assert nomes == [f"usb1-port{numero}" for numero in range(1, 11)]


def test_sys_ausente_devolve_lista_vazia_e_nao_levanta() -> None:
    """Contêiner e sandbox não têm `/sys/bus/usb` — e isso é uma resposta."""

    def sem_sys(_: str) -> list[str]:
        raise OSError(2, "não existe")

    assert listar_entradas(raiz_usb=RAIZ, listar=sem_sys) == ()


def test_nenhum_caminho_do_sys_real_e_tocado() -> None:
    """O portão que protege a foto da janela: a bancada de mentira é total.

    Sem ele, um caminho real que sobrasse no módulo faria o PNG versionado
    carregar o barramento DELA — e o teste passaria na máquina de quem escreveu.
    """
    bancada = Bancada(com_hub=True)
    listar_entradas(
        raiz_usb=RAIZ, listar=bancada.listar, ler=bancada.ler, real=bancada.real
    )

    reais = [caminho for caminho in bancada.tocados if not caminho.startswith("/mentira")]
    assert reais == [], f"o módulo tocou caminho de verdade: {reais}"


@pytest.mark.parametrize("com_hub", [False, True])
def test_a_leitura_nao_inventa_buraco_a_partir_de_interface_qualquer(
    com_hub: bool,
) -> None:
    """Interface de aparelho está na raiz e não hospeda entrada nenhuma.

    A varredura filtra por FORMA do nome (`<hub>-port<N>`), não por sorte de o
    diretório estar vazio — e uma interface que some no meio da leitura (hub
    desplugado) não derruba nada.
    """
    entradas = _entradas(com_hub=com_hub)

    assert all(entrada.no.startswith(entrada.hub + "-port") for entrada in entradas)
    assert len(entradas) == (26 if com_hub else 22)
