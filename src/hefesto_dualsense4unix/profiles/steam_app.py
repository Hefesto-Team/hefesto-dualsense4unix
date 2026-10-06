"""Fonte ÚNICA do predicado "esta `wm_class` é uma janela de jogo da Steam"."""
from __future__ import annotations

import re

_STEAM_APP_WC_RE = re.compile(r"^steam_app_(\d+)$", re.IGNORECASE)


_WC_CLIENTE_STEAM = frozenset({"steam", "steamwebhelper"})


def e_janela_do_cliente_steam(wm_class: str | None) -> bool:
    """True se `wm_class` é o CLIENTE Steam (loja/biblioteca/Big Picture)."""
    if not isinstance(wm_class, str):
        return False
    return wm_class.strip().lower() in _WC_CLIENTE_STEAM


def steam_appid_from_wm_class(wm_class: str | None) -> int | None:
    """Appid do jogo a partir da wm_class (`steam_app_N`), ou None."""
    if not isinstance(wm_class, str):
        return None
    m = _STEAM_APP_WC_RE.match(wm_class.strip())
    return int(m.group(1)) if m is not None else None


_LOJA_STEAM_RE = re.compile(
    r"^(?:https?://)?(?:[\w-]+\.)*store\.steampowered\.com(?::\d+)?"
    r"/(?:[^/?#]+/)*app/(\d+)(?:[/?#].*)?$",
    re.IGNORECASE,
)

_RUNGAMEID_RE = re.compile(
    r"^steam://rungameid/(\d+)(?:[/?#].*)?$",
    re.IGNORECASE,
)

_APPID_CRU_RE = re.compile(r"^(?:steam_app_)?(\d+)$", re.IGNORECASE)


def steam_appid_de_texto(texto: str | None) -> int | None:
    """Appid do que o usuário COLOU no campo, ou ``None`` quando não dá para saber."""
    if not isinstance(texto, str):
        return None
    limpo = texto.strip()
    if not limpo:
        return None
    for regex in (_APPID_CRU_RE, _RUNGAMEID_RE, _LOJA_STEAM_RE):
        achado = regex.match(limpo)
        if achado is not None:
            return int(achado.group(1))
    return None


def parece_endereco(texto: str | None) -> bool:
    """O texto parece um endereço COLADO — e não um nome sendo digitado?"""
    if not isinstance(texto, str):
        return False
    return "/" in texto.strip()


__all__ = [
    "parece_endereco",
    "steam_appid_de_texto",
    "steam_appid_from_wm_class",
]
