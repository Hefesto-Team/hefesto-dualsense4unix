"""A topologia FÍSICA das entradas — o que o ``busnum`` esconde."""
from __future__ import annotations

import re
from collections.abc import Sequence

from hefesto_dualsense4unix.integrations.entradas_do_gabinete import (
    Furo,
    NoDeEntrada,
    furos,
    vazias,
)

ENCAIXE_ALCANCAVEL = "hotplug"

_HUB_RAIZ = re.compile(r"^usb[0-9]+$")


def hubs_do_mesmo_plastico(
    entradas: Sequence[NoDeEntrada],
) -> dict[str, frozenset[str]]:
    """``{nome do hub: todos os hubs que são o mesmo plástico}``."""
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
    """Os buracos VAZIOS que uma pessoa alcança — buraco, nunca nó."""
    return tuple(
        furo for furo in vazias(entradas) if furo.tipo_de_encaixe == ENCAIXE_ALCANCAVEL
    )


__all__ = [
    "ENCAIXE_ALCANCAVEL",
    "hubs_do_mesmo_plastico",
    "livres",
]
