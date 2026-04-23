"""Normalização de `Profile.name` para filename filesystem-safe.

Regras:
- Unicode NFKD + remoção de combining marks: "Ação" perde a cedilha.  # exemplo (noqa-acento)
- Lowercase normaliza para minúsculas.
- Espaço e traço viram underscore: `"Meu Perfil"` vira `"meu_perfil"`.
- Remove tudo que não for `[a-z0-9_]` — mantém só ASCII alfanumérico e underscore.
- Colapsa underscores consecutivos: `"a__b"` vira `"a_b"`.
- Trim de underscores de borda: `"_foo_"` vira `"foo"`.
- Resultado não-vazio obrigatório. Levanta `ValueError` se o nome de entrada
  estiver vazio ou se o slug resultante ficar vazio.
"""
from __future__ import annotations

import re
import unicodedata

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


__all__ = ["slugify"]
