"""A topologia FÍSICA das entradas — o que o ``busnum`` esconde.

O PROBLEMA QUE ESTE MÓDULO RESOLVE
-----------------------------------

Um hub USB 3.x é **um plástico com dois chips**, e o kernel os enumera em dois
barramentos diferentes. Medido nesta bancada em 24/08/2026::

    readlink /sys/bus/usb/devices/3-1.1:1.0/3-1.1-port4/peer
    ../../../../usb4/4-1/4-1:1.0/4-1.1-port4

O ``peer`` costura, buraco a buraco, o lado 2.0 e o lado 3.0 do MESMO soquete.
Sem ele, o aparelho de 5 Gbps encaixado no buraco interno 2 (``4-1.1.2``) e o
adaptador Bluetooth do buraco interno 4 (``3-1.1.4``) parecem morar em máquinas
diferentes: ``mesa_de_radio.vizinhancas_apertadas`` recusa o par no
``if primeiro.busnum != segundo.busnum: continue``, e a única vizinhança que
sobra para a tela acusar é a webcam.

ESTE MÓDULO NÃO LÊ ``/sys``. NEM UMA LINHA.
--------------------------------------------

A leitura é toda de :mod:`~hefesto_dualsense4unix.integrations.entradas_do_gabinete`,
que já lê ``state``, ``connect_type``, ``peer``, ``device`` e
``over_current_count`` de cada nó de entrada — inclusive dos VAZIOS, que é o
caso que nenhuma outra leitura alcança. Aqui só mora a DERIVAÇÃO que ela não
faz: agrupar os hubs que são o mesmo plástico, e responder às três perguntas de
topologia que o catálogo de ordens precisa fazer.

**Duas réguas independentes para "buraco livre" seriam
`PORTÕES-EM-SÉRIE-ENGANAM` esperando acontecer** — é o C5 da própria sprint que
pediu este arquivo. Por isso :func:`livres` delega a ``vazias()`` e só
acrescenta um filtro; ela não conta buraco nenhum por conta própria.

O QUE UM HUB-RAIZ NÃO É
------------------------

``usb1``/``usb3`` são hubs-raiz do controlador xHCI, não aparelho de bancada.
:func:`mesmo_hub_fisico` os ignora de propósito: dois aparelhos encaixados
direto na placa-mãe não estão "no mesmo hub" em nenhum sentido que interesse a
uma ordem de serviço — e a ordem que R1 dá é justamente *mova para uma entrada
do próprio computador*. Contá-los faria a regra acusar o destino que ela
recomenda.
"""
from __future__ import annotations

import os
import re
from collections.abc import Callable, Sequence

from hefesto_dualsense4unix.integrations.entradas_do_gabinete import (
    RAIZ_USB_PADRAO,
    Furo,
    NoDeEntrada,
    entrada_de,
    furos,
    vazias,
)

#: O ``connect_type`` de um buraco que uma pessoa alcança com a mão. Medido em
#: 24/08/2026: os dez buracos de ``usb1`` respondem ``hotplug``, e é o que
#: separa a entrada do gabinete do conector interno soldado na placa. Mandar
#: alguém encaixar um dongle num conector que não existe do lado de fora é pior
#: que não mandar nada.
ENCAIXE_ALCANCAVEL = "hotplug"

#: ``usb1`` — o hub-raiz do controlador. Ver o cabeçalho.
_HUB_RAIZ = re.compile(r"^usb[0-9]+$")


def hubs_do_mesmo_plastico(
    entradas: Sequence[NoDeEntrada],
) -> dict[str, frozenset[str]]:
    """``{nome do hub: todos os hubs que são o mesmo plástico}``.

    A prova de que ``3-1.1`` e ``4-1.1`` são um aparelho só não está em nenhum
    atributo dos dois: está no ``peer`` dos BURACOS deles. Um buraco com dois
    nós é um soquete físico visto pelos dois chips, e os hubs desses dois nós
    são, por construção, o mesmo pedaço de plástico.

    Basta UM buraco com ``peer`` publicado para o par inteiro de hubs ficar
    costurado — e é por isso que a resposta é uma classe de equivalência e não
    uma comparação nó a nó: o buraco onde o aparelho está pode ser justamente o
    que não publicou ``peer``.

    Hub-raiz não entra (ver o cabeçalho).
    """
    classes: dict[str, set[str]] = {}
    for furo in furos(entradas):
        hubs = {
            entrada.hub
            for entrada in furo.entradas
            if entrada.hub and not _HUB_RAIZ.match(entrada.hub)
        }
        if not hubs:
            continue
        juntos = set(hubs)
        for hub in hubs:
            juntos |= classes.get(hub, set())
        for hub in juntos:
            classes[hub] = juntos
    return {hub: frozenset(juntos) for hub, juntos in classes.items()}


def hubs_de(
    caminho: str,
    entradas: Sequence[NoDeEntrada],
    *,
    raiz_usb: str = RAIZ_USB_PADRAO,
    real: Callable[[str], str] = os.path.realpath,
) -> frozenset[str]:
    """Os hubs que hospedam o buraco onde este aparelho está — ``frozenset()``.

    ``caminho`` é o nome de kernel do aparelho (``3-1.1.4``), a mesma palavra de
    ``censo_do_barramento.Aparelho.nome_do_kernel``.

    ``raiz_usb`` e ``real`` existem porque ``entradas_do_gabinete.entrada_de``
    atravessa o symlink ``<aparelho>/port`` antes de cair no índice invertido —
    e um default de módulo tocaria o ``/sys`` desta máquina de dentro de uma
    bateria (``CANARIO-FS-01``, ``tests/conftest.py``). Quem chama passa os
    MESMOS valores que passou a ``listar_entradas``; medir com duas raízes
    diferentes é medir duas máquinas.

    Vazio quando o aparelho não foi achado, quando ele pendura direto num
    hub-raiz, ou quando o ``/sys`` não publicou o nó da entrada. Os três casos
    dão a mesma resposta honesta, e nenhum deles vira palpite.
    """
    furo = entrada_de(caminho, entradas, raiz_usb=raiz_usb, real=real)
    if furo is None:
        return frozenset()
    classes = hubs_do_mesmo_plastico(entradas)
    achados: set[str] = set()
    for entrada in furo.entradas:
        if not entrada.hub or _HUB_RAIZ.match(entrada.hub):
            continue
        achados |= classes.get(entrada.hub, {entrada.hub})
    return frozenset(achados)


def mesmo_hub_fisico(
    um: str,
    outro: str,
    entradas: Sequence[NoDeEntrada],
    *,
    raiz_usb: str = RAIZ_USB_PADRAO,
    real: Callable[[str], str] = os.path.realpath,
) -> bool:
    """Os dois aparelhos estão pendurados no mesmo pedaço de plástico?

    É a função que faz R1 enxergar através do ``busnum``. Um aparelho no lado
    3.0 (``4-1.1.2``) e outro no lado 2.0 (``3-1.1.4``) do mesmo hub respondem
    ``True`` aqui, e respondem ``False`` em qualquer comparação que use o número
    do barramento.

    ``False`` quando qualquer um dos dois não tem hub conhecido: não saber onde
    o aparelho está NÃO é o mesmo que saber que ele está longe, e a ordem que
    sai daqui manda uma pessoa se ajoelhar atrás do gabinete.
    """
    if um == outro:
        return False
    daqui = hubs_de(um, entradas, raiz_usb=raiz_usb, real=real)
    dali = hubs_de(outro, entradas, raiz_usb=raiz_usb, real=real)
    return bool(daqui and dali and daqui & dali)


def mesmo_soquete_fisico(
    um: str,
    outro: str,
    entradas: Sequence[NoDeEntrada],
    *,
    raiz_usb: str = RAIZ_USB_PADRAO,
    real: Callable[[str], str] = os.path.realpath,
) -> bool:
    """Os dois aparelhos estão no MESMO buraco? (Só por extensão ou hub.)

    Dois aparelhos no mesmo buraco físico só acontecem com um cabo de extensão
    ou um hub no meio — e é o caso em que "mude um dos dois de entrada" é a
    ordem errada, porque não há dois buracos para separar.
    """
    if um == outro:
        return False
    daqui = entrada_de(um, entradas, raiz_usb=raiz_usb, real=real)
    dali = entrada_de(outro, entradas, raiz_usb=raiz_usb, real=real)
    return daqui is not None and dali is not None and daqui.nos == dali.nos


def livres(entradas: Sequence[NoDeEntrada]) -> tuple[Furo, ...]:
    """Os buracos VAZIOS que uma pessoa alcança — buraco, nunca nó.

    Delega a contagem inteira a ``entradas_do_gabinete.vazias`` e acrescenta um
    filtro só: ``connect_type == "hotplug"``. Reimplementar a conta aqui daria
    duas réguas para o mesmo fato, e é o que o C5 da sprint proíbe por escrito.

    ``connect_type`` ausente NÃO passa no filtro. A assimetria é a mesma de
    ``NoDeEntrada.vazio``, e pelo mesmo motivo: mandar alguém encaixar um cabo
    num conector soldado dentro do gabinete é um custo real, e "não sei se dá
    para alcançar" não autoriza a ordem.
    """
    return tuple(
        furo for furo in vazias(entradas) if furo.tipo_de_encaixe == ENCAIXE_ALCANCAVEL
    )


def livres_fora_de(
    hubs: frozenset[str], entradas: Sequence[NoDeEntrada]
) -> tuple[Furo, ...]:
    """Os buracos livres e alcançáveis que NÃO ficam nestes hubs.

    É a contra-regra de R3 virada em função: *"há entrada livre no próprio
    computador"* só é verdade se a entrada livre não estiver dentro do mesmo hub
    de onde a ordem manda tirar o aparelho. Sem isto, a ordem mandaria mudar o
    dongle de buraco dentro do hub e chamaria isso de conserto.
    """
    proibidos = set(hubs)
    classes = hubs_do_mesmo_plastico(entradas)
    for hub in list(proibidos):
        proibidos |= classes.get(hub, set())
    return tuple(
        furo
        for furo in livres(entradas)
        if not any(entrada.hub in proibidos for entrada in furo.entradas)
    )


__all__ = [
    "ENCAIXE_ALCANCAVEL",
    "hubs_de",
    "hubs_do_mesmo_plastico",
    "livres",
    "livres_fora_de",
    "mesmo_hub_fisico",
    "mesmo_soquete_fisico",
]
