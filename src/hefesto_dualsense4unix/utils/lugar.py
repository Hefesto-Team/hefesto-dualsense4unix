"""O LUGAR de uma porta (D3) — a grafia e a tradução, num lugar só, e sem pydantic."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

FORMA_DO_LUGAR = re.compile(
    r"^pci-(?P<pci>[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9a-f])"
    r"(?:-usb-0:(?P<devpath>[0-9]+(?:\.[0-9]+)*))?$"
)

FORMA_DO_CAMINHO = re.compile(r"^[0-9]+-[0-9]+(\.[0-9]+)*$")

FORMA_DO_NO = re.compile(r"^(?P<hub>usb[0-9]+|[0-9]+-[0-9]+(?:\.[0-9]+)*)-port(?P<n>[0-9]+)$")

_HUB_RAIZ = re.compile(r"^usb([0-9]+)$")


def lugar_de(controlador_pci: str, devpath: str) -> str:
    """O LUGAR de uma porta: o controlador PCI e a cadeia de portas do USB."""
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
    """O caminho de barramento vira lugar: ``3-4.1.4`` → ``pci-…-usb-0:4.1.4``."""
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
    """O caminho que um aparelho encaixado NESTE nó de entrada teria."""
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


def no_do_caminho(caminho: str) -> str:
    """O nó de entrada em que o aparelho deste caminho está encaixado."""
    if not caminho or not FORMA_DO_CAMINHO.match(caminho):
        return ""
    hub, _, numero = caminho.rpartition(".")
    if hub:
        return f"{hub}-port{numero}"
    busnum, _, porta = caminho.partition("-")
    return f"usb{busnum}-port{porta}"


def caminho_do_lado_20(nos: Sequence[str]) -> str:
    """O caminho que um aparelho 2.0 teria neste buraco — o do barramento menor.

    O xHCI registra a raiz 2.0 antes da 3.x, e o DualSense e os adaptadores
    (todos 2.0) enumeram sempre ali. ``""`` sem nó de entrada nenhum.
    """
    caminhos = sorted(
        (caminho_do_no(no) for no in nos if caminho_do_no(no)),
        key=lambda caminho: int(caminho.partition("-")[0]),
    )
    return caminhos[0] if caminhos else ""


__all__ = [
    "FORMA_DO_CAMINHO",
    "FORMA_DO_LUGAR",
    "FORMA_DO_NO",
    "caminho_do_lado_20",
    "caminho_do_no",
    "caminhos_do_lugar",
    "lugar_de",
    "lugar_do_caminho",
    "lugar_do_no",
    "no_do_caminho",
    "partes_do_lugar",
]
