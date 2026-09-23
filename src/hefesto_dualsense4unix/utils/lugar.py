"""O LUGAR de uma porta (D3) — a grafia e a tradução, num lugar só, e sem pydantic.

ENTRADA-A-ENTRADA-01 (23/09/2026) decidiu que há DUAS chaves de porta nesta
casa e que a tradução entre elas mora num lugar só:

* o **caminho de barramento** (``3-4.1.4``) — o nome do kernel, com o número
  do barramento na frente. É o que o ``mapa`` do ``maquina.json`` grava e o que
  a ponte root escreve no diário;
* o **lugar** (``pci-0000:0c:00.3-usb-0:4.1.4``) — o controlador PCI mais a
  cadeia de portas, na grafia do ``ID_PATH`` do udev. É a chave do dono do
  BlueZ e a que o «Mapear Entrada a Entrada» grava.

O número do barramento é a ORDEM em que os dois xHCI sobem (medido em 23/09:
``usb1``/``usb2`` = ``0000:02:00.0``, ``usb3``/``usb4`` = ``0000:0c:00.3``), e
um kernel novo ou uma placa a mais o troca calado. O lugar não carrega esse
número, e é esse o ponto.

POR QUE ESTE MÓDULO EXISTE À PARTE DO ``utils/maquina.py``
----------------------------------------------------------

ENTRADA-A-ENTRADA-02 (23/09/2026), o item 5 da sprint. A grafia morava no
``utils/maquina.py``, e o ``bluez_dbus`` e o ``mesa_de_radio`` a pediam por
import TARDIO para continuarem stdlib no import. Só no import: pelo ``python3``
do sistema — o recurso do doctor, que aqui tem pydantic 1.10 — a CHAMADA
levantava ``ImportError`` (``field_validator``), e todo adaptador ficava sem
lugar, calado. Medido nesta máquina em 23/09::

    /usr/bin/python3 -c "…bluez_dbus.lugar_de('0000:0c:00.3', '4.1.4')"
    ImportError: cannot import name 'field_validator' from 'pydantic'

Por isso a grafia saiu para cá, e **só biblioteca padrão** entra aqui. O
``utils/maquina.py`` a reexporta — todo leitor que já perguntava a ele continua
perguntando —, e o dono é este arquivo: montar ``…-usb-0:…`` em qualquer outro
lugar é a segunda grafia que diverge da primeira no dia em que uma mudar.

A REFERÊNCIA É O UDEV
---------------------

A grafia é a do ``ID_PATH`` que o udev publica para o aparelho USB
(``udevadm info`` do ``3-4.1.4``: ``ID_PATH=pci-0000:0c:00.3-usb-0:4.1.4``). O
``bt_active_mode.sh``, que é root e não roda o Python da casa, lê o lugar DO
UDEV, e não o monta — as duas pontas concordam porque falam a língua de quem
publica.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

#: O lugar, na grafia do ``ID_PATH`` do udev. ``pci-<controlador>`` sem portas
#: é o adaptador que não pendura em USB nenhum.
FORMA_DO_LUGAR = re.compile(
    r"^pci-(?P<pci>[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9a-f])"
    r"(?:-usb-0:(?P<devpath>[0-9]+(?:\.[0-9]+)*))?$"
)

#: O caminho de barramento na palavra do kernel — ``3-1.1.4`` é o barramento
#: mais a cadeia de portas até o aparelho, e é o nome do diretório em
#: ``/sys/bus/usb/devices``.
FORMA_DO_CAMINHO = re.compile(r"^[0-9]+-[0-9]+(\.[0-9]+)*$")

#: O nome de kernel de um NÓ DE ENTRADA — ``usb1-port5`` (entrada de hub-raiz)
#: ou ``3-1-port2`` (entrada de hub comum). Os dois grupos são o hub que
#: hospeda e o número da entrada nele: a mesma forma de
#: ``integrations/entradas_do_gabinete._NO_DE_ENTRADA``.
FORMA_DO_NO = re.compile(r"^(?P<hub>usb[0-9]+|[0-9]+-[0-9]+(?:\.[0-9]+)*)-port(?P<n>[0-9]+)$")

_HUB_RAIZ = re.compile(r"^usb([0-9]+)$")


def lugar_de(controlador_pci: str, devpath: str) -> str:
    """O LUGAR de uma porta: o controlador PCI e a cadeia de portas do USB.

    ``lugar_de("0000:0c:00.3", "4.1.4")`` → ``pci-0000:0c:00.3-usb-0:4.1.4``.
    ``""`` quando não há controlador — "não sei onde". Sem ``devpath``, só o
    controlador: é o adaptador que não pendura em USB nenhum.
    """
    if not controlador_pci:
        return ""
    if not devpath:
        return f"pci-{controlador_pci}"
    return f"pci-{controlador_pci}-usb-0:{devpath}"


def partes_do_lugar(lugar: str) -> tuple[str, str] | None:
    """``(controlador, devpath)`` de um lugar — ``None`` se não é um lugar."""
    casado = FORMA_DO_LUGAR.match(lugar or "")
    if casado is None:
        return None
    return casado.group("pci"), casado.group("devpath") or ""


def lugar_do_caminho(caminho: str, controladores: Mapping[int, str]) -> str:
    """O caminho de barramento vira lugar: ``3-4.1.4`` → ``pci-…-usb-0:4.1.4``.

    ``controladores`` é ``{busnum: controlador PCI}`` DESTE boot — quem lê é
    ``mesa_de_radio.controladores_dos_barramentos``. ``""`` quando o caminho
    não tem a forma do kernel ou o barramento não está na leitura: "não sei",
    nunca um lugar inventado.
    """
    if not caminho or not FORMA_DO_CAMINHO.match(caminho):
        return ""
    busnum, _, devpath = caminho.partition("-")
    controlador = controladores.get(int(busnum), "")
    return lugar_de(controlador, devpath) if controlador else ""


def caminhos_do_lugar(lugar: str, controladores: Mapping[int, str]) -> tuple[str, ...]:
    """O inverso — e são ATÉ DOIS, e esta função não escolhe.

    Um controlador xHCI publica dois barramentos, o lado 2.0 e o 3.x, e o
    ``ID_PATH`` é o mesmo nos dois lados de um buraco (medido em 23/09: o hub
    ``05e3`` desta bancada é ``3-4`` e ``4-4``). O DualSense e os dongles são
    2.0 e enumeram sempre do lado 2.0; quem precisa de UM caminho olha qual
    dos candidatos está no barramento agora.
    """
    partes = partes_do_lugar(lugar)
    if partes is None or not partes[1]:
        return ()
    controlador, devpath = partes
    return tuple(
        f"{busnum}-{devpath}"
        for busnum, dono in sorted(controladores.items())
        if dono == controlador
    )


def caminho_do_no(no: str) -> str:
    """O caminho que um aparelho encaixado NESTE nó de entrada teria.

    ``usb3-port4`` → ``3-4``; ``3-4-port2`` → ``3-4.2``. É a regra de nomes do
    kernel, e é o que dá LUGAR a uma entrada VAZIA: o nó existe com o buraco
    vazio, o aparelho não. ``""`` quando o nome não é de nó de entrada.
    """
    casado = FORMA_DO_NO.match(no or "")
    if casado is None:
        return ""
    hub, numero = casado.group("hub"), casado.group("n")
    raiz = _HUB_RAIZ.match(hub)
    if raiz is not None:
        return f"{raiz.group(1)}-{numero}"
    return f"{hub}.{numero}"


def lugar_do_no(no: str, controladores: Mapping[int, str]) -> str:
    """O LUGAR de um nó de entrada, cheio ou vazio — ``""`` = não sei."""
    return lugar_do_caminho(caminho_do_no(no), controladores)


__all__ = [
    "FORMA_DO_CAMINHO",
    "FORMA_DO_LUGAR",
    "FORMA_DO_NO",
    "caminho_do_no",
    "caminhos_do_lugar",
    "lugar_de",
    "lugar_do_caminho",
    "lugar_do_no",
    "partes_do_lugar",
]
