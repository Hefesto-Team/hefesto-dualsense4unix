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
faz: agrupar os hubs que são o mesmo plástico (quem pergunta é o catálogo de
ordens, ``ordens_da_mesa.mesmo_hub_fisico``) e contar os buracos livres que a
mão alcança (quem pergunta é a seção da mesa, ``secao_mesa``).

AS TRÊS PERGUNTAS DE PAR SAÍRAM EM 28/09/2026 (A-CONEXOES-DIZ-O-QUE-O-PRODUTO-
JA-MEDE-01): ``mesmo_hub_fisico``, ``mesmo_soquete_fisico`` e ``livres_fora_de``
nasceram em 25/08 para o catálogo de ordens, e o catálogo fez as dele —
``ordens_da_mesa.mesmo_hub_fisico``, pelo mesmo ``hubs_do_mesmo_plastico``, e
``_livres_fora_da_controladora``. As daqui ficaram sem chamador nenhum, nem de
teste; duas réguas para a mesma pergunta divergiriam na primeira mudança.

**Duas réguas independentes para "buraco livre" seriam
`PORTÕES-EM-SÉRIE-ENGANAM` esperando acontecer** — é o C5 da própria sprint que
pediu este arquivo. Por isso :func:`livres` delega a ``vazias()`` e só
acrescenta um filtro; ela não conta buraco nenhum por conta própria.

O QUE UM HUB-RAIZ NÃO É
------------------------

``usb1``/``usb3`` são hubs-raiz do controlador xHCI, não aparelho de bancada.
:func:`hubs_do_mesmo_plastico` os ignora de propósito: dois aparelhos
encaixados direto na placa-mãe não estão "no mesmo hub" em nenhum sentido que
interesse a uma ordem de serviço — e a ordem que R1 dá é justamente *mova para
uma entrada do próprio computador*. Contá-los faria a regra acusar o destino
que ela recomenda.
"""
from __future__ import annotations

import re
from collections.abc import Sequence

from hefesto_dualsense4unix.integrations.entradas_do_gabinete import (
    Furo,
    NoDeEntrada,
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


__all__ = [
    "ENCAIXE_ALCANCAVEL",
    "hubs_do_mesmo_plastico",
    "livres",
]
