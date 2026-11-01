"""O LUGAR de uma porta (D3) — a grafia e a tradução, num lugar só, e sem pydantic."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence

FORMA_DO_LUGAR = re.compile(
    r"^pci-(?P<pci>[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9a-f])"
    r"(?:-usb-0:(?P<devpath>[0-9]+(?:\.[0-9]+)*))?$"
)

FORMA_DO_CAMINHO = re.compile(r"^[0-9]+-[0-9]+(\.[0-9]+)*$")

FORMA_DO_NO = re.compile(r"^(?P<hub>usb[0-9]+|[0-9]+-[0-9]+(?:\.[0-9]+)*)-port(?P<n>[0-9]+)$")

_HUB_RAIZ = re.compile(r"^usb([0-9]+)$")

FORMA_DO_PCI = re.compile(
    r"^(?P<dominio>[0-9a-f]{4}):(?P<barramento>[0-9a-f]{2}):(?P<posicao>[0-9a-f]{2}\.[0-9a-f])$"
)


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
    ``05e3`` desta máquina de teste é ``3-4`` e ``4-4``). O DualSense e os dongles são
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


def lugar_reapontado(lugar: str, novos: Mapping[str, str]) -> str:
    """O mesmo lugar no endereço vivo do controlador; o que não anda volta igual."""
    partes = partes_do_lugar(lugar)
    if partes is None or partes[0] not in novos:
        return lugar
    return lugar_de(novos[partes[0]], partes[1])


def _funcao(endereco: str) -> str:
    return endereco.rpartition(".")[2]


def _forma(endereco: str) -> tuple[str, str] | None:
    casado = FORMA_DO_PCI.match(endereco)
    return None if casado is None else (casado.group("dominio"), casado.group("posicao"))


def _iguais(tabela: Mapping[str, str], familia: str, funcao: str) -> list[str]:
    return sorted(e for e, f in tabela.items() if f == familia and _funcao(e) == funcao)


def reconhecer_os_controladores(
    gravados: Iterable[str],
    vivos: Mapping[str, str],
    identidades: Mapping[str, str] | None = None,
) -> dict[str, str] | None:
    """O endereço vivo de cada controlador USB gravado; ``None`` se um deles não se reconhece.

    ``vivos`` e ``identidades`` levam o endereço PCI ao ``vendor:device`` (``""`` quando não
    se lê). Com a identidade gravada, o controlador é o k-ésimo do mesmo ``vendor:device`` e
    da mesma função, contados nos dois lados; sem a identidade, o k-ésimo da mesma posição no
    mesmo domínio. Contagens que não batem só valem pelo endereço que continua vivo e igual.
    """
    conhecidos = {e: f for e, f in (identidades or {}).items() if f}
    familias_vivas = {e: f for e, f in vivos.items() if f}
    sem_identidade = sorted({g for g in gravados if g not in conhecidos})
    novos: dict[str, str] = {}
    for gravado in sorted(set(gravados)):
        if gravado in conhecidos:
            familia, funcao = conhecidos[gravado], _funcao(gravado)
            antes = _iguais(conhecidos, familia, funcao)
            agora = _iguais(familias_vivas, familia, funcao)
            mesmo_vivo = familias_vivas.get(gravado) == conhecidos[gravado]
        else:
            forma = _forma(gravado)
            if forma is None:
                return None
            antes = [g for g in sem_identidade if _forma(g) == forma]
            agora = sorted(e for e in vivos if _forma(e) == forma)
            mesmo_vivo = gravado in vivos
        if len(antes) == len(agora):
            novos[gravado] = agora[antes.index(gravado)]
        elif mesmo_vivo:
            novos[gravado] = gravado
        else:
            return None
    if len(set(novos.values())) != len(novos):
        return None
    return novos


__all__ = [
    "FORMA_DO_CAMINHO",
    "FORMA_DO_LUGAR",
    "FORMA_DO_NO",
    "FORMA_DO_PCI",
    "caminho_do_lado_20",
    "caminho_do_no",
    "caminhos_do_lugar",
    "lugar_de",
    "lugar_do_caminho",
    "lugar_do_no",
    "lugar_reapontado",
    "no_do_caminho",
    "partes_do_lugar",
    "reconhecer_os_controladores",
]
