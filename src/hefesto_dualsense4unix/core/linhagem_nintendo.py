"""linhagem_nintendo.py — quem é um Pro Controller, e quem só se parece com um."""

from __future__ import annotations

from collections.abc import Iterable

OUIS_CLONE = frozenset({"e417d8"})

OUI_PRO_DESTA_BANCADA = "e0f6b5"

OUIS_NINTENDO_VISTAS = frozenset({OUI_PRO_DESTA_BANCADA})

VIDS_NINTENDO = frozenset({"057e"})

VIDPID_PRO = frozenset({"057e:2009"})

#: NÃO casa ``"DualSense Wireless Controller"`` e NÃO casa ``"8BitDo Pro 2"``
NOMES_PRO = ("pro controller",)

NOMES_LINHAGEM = ("pro controller", "nintendo")

_SEPARADORES = (":", "-", ".")


def normalizar_oui(uniq: str | None) -> str | None:
    """OUI em 6 hex minúsculos, ou ``None`` quando não há endereço legível."""
    if not uniq:
        return None
    bruto = uniq.strip().lower()
    for sep in _SEPARADORES:
        bruto = bruto.replace(sep, "")
    if len(bruto) < 6:
        return None
    faixa = bruto[:6]
    if any(c not in "0123456789abcdef" for c in faixa):
        return None
    return faixa


def e_clone_conhecido(uniq: str | None) -> bool:
    """O endereço está numa faixa de clone conhecida (hoje: só a 8BitDo)?"""
    faixa = normalizar_oui(uniq)
    return faixa is not None and faixa in OUIS_CLONE


def parece_pro(*, nome: str = "", vid: str = "", pid: str = "") -> bool:
    """O device SE APRESENTA como Pro Controller — genuíno ou clone.

    Não decide autenticidade: é de propósito que o clone passe aqui. Quem
    separa os dois é a OUI, em :func:`e_pro_genuino`.

    Com VID presente, ele tem de ser da Nintendo — é o que impede um DualSense
    ou um gamepad qualquer de entrar por causa do nome. Com VID ausente (o
    caminho em que só há ``HID_NAME``), o nome decide sozinho.
    """
    v = (vid or "").strip().lower()
    p = (pid or "").strip().lower()
    if v and v not in VIDS_NINTENDO:
        return False
    if v and f"{v}:{p}" in VIDPID_PRO:
        return True
    return any(marca in (nome or "").strip().lower() for marca in NOMES_PRO)


def e_pro_genuino(
    *, uniq: str | None, nome: str = "", vid: str = "", pid: str = ""
) -> bool:
    """Pro Controller da Nintendo, e não o clone — a pergunta por NEGATIVA.

    Verdadeiro quando o aparelho se apresenta como Pro (:func:`parece_pro`) e o
    endereço dele **não** está numa faixa de clone conhecida. Qualquer faixa da
    Nintendo serve, inclusive as 81 que esta bancada nunca viu.

    ``False`` sem endereço legível: sem OUI não dá para descartar o clone.
    """
    if not parece_pro(nome=nome, vid=vid, pid=pid):
        return False
    if normalizar_oui(uniq) is None:
        return False
    return not e_clone_conhecido(uniq)


def _e_da_linhagem_nintendo(*, nome: str = "", uniq: str | None = None) -> bool:
    """Este controle lê o nome Bluetooth do host? Genuíno e clone respondem sim."""
    faixa = normalizar_oui(uniq)
    if faixa is not None and (faixa in OUIS_CLONE or faixa in OUIS_NINTENDO_VISTAS):
        return True
    minusculo = (nome or "").strip().lower()
    return any(marca in minusculo for marca in NOMES_LINHAGEM)


def com_dois_pontos(ouis: Iterable[str]) -> frozenset[str]:
    """``{"e417d8"}`` -> ``{"e4:17:d8"}``. Para quem casa contra ``uniq`` cru."""
    return frozenset(f"{o[0:2]}:{o[2:4]}:{o[4:6]}" for o in ouis)


OUIS_LINHAGEM_COM_DOIS_PONTOS = com_dois_pontos(OUIS_NINTENDO_VISTAS | OUIS_CLONE)


__all__ = [
    "NOMES_LINHAGEM",
    "NOMES_PRO",
    "OUIS_CLONE",
    "OUIS_LINHAGEM_COM_DOIS_PONTOS",
    "OUIS_NINTENDO_VISTAS",
    "OUI_PRO_DESTA_BANCADA",
    "VIDPID_PRO",
    "VIDS_NINTENDO",
    "com_dois_pontos",
    "e_clone_conhecido",
    "e_pro_genuino",
    "normalizar_oui",
    "parece_pro",
]
