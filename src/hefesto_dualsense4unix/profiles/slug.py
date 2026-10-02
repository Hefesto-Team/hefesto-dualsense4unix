"""Normalização de `Profile.name` para filename filesystem-safe."""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Protocol, TypeVar

_NON_ALNUM_UNDERSCORE = re.compile(r"[^a-z0-9_]")
_MULTI_UNDERSCORE = re.compile(r"_+")


def slugify(name: str) -> str:
    """Deriva slug ASCII filesystem-safe de um display name acentuado."""
    if not name or not name.strip():
        raise ValueError("slugify: nome vazio não tem slug")
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    lowered = ascii_only.lower()
    dashes_underscored = lowered.replace("-", "_").replace(" ", "_")
    alnum = _NON_ALNUM_UNDERSCORE.sub("", dashes_underscored)
    collapsed = _MULTI_UNDERSCORE.sub("_", alnum).strip("_")
    if not collapsed:
        raise ValueError(f"slugify: {name!r} não produz slug válido")
    return collapsed


class _TemNome(Protocol):
    """Qualquer objeto com display name — na prática, ``Profile``."""

    name: str


_P = TypeVar("_P", bound=_TemNome)


def mesmo_slug(a: str, b: str) -> bool:
    """True quando dois nomes de EXIBIÇÃO disputam o MESMO arquivo."""
    try:
        return slugify(a) == slugify(b)
    except ValueError:
        return False


def find_by_slug(name: str, candidates: Iterable[_P]) -> _P | None:
    """Acha, entre ``candidates``, o perfil que OCUPA o arquivo de ``name``."""
    try:
        alvo = slugify(name)
    except ValueError:
        return None
    for candidate in candidates:
        try:
            if slugify(candidate.name) == alvo:
                return candidate
        except (ValueError, AttributeError):
            continue
    return None


__all__ = ["find_by_slug", "mesmo_slug", "slugify"]
