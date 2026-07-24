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
    """Qualquer objeto com display name — na prática, ``Profile``.

    Protocol em vez de importar ``profiles.schema`` para não inverter a
    dependência (o schema é quem importa o slug, lá no validador de ``name``).
    """

    name: str


_P = TypeVar("_P", bound=_TemNome)


def mesmo_slug(a: str, b: str) -> bool:
    """True quando dois nomes de EXIBIÇÃO disputam o MESMO arquivo.

    R-10 (auditoria 23/07): a identidade de um perfil em disco é o SLUG
    (``save_profile`` grava ``<slugify(name)>.json``), mas a GUI comparava o
    nome de exibição. Medido: com "Navegação" no disco, salvar um perfil
    chamado "Navegacao" (sem acento) passava batido pelas duas guardas —
    a de sobrescrita e a de downgrade para ``MatchAny`` — e o arquivo
    ``navegacao.json`` era substituído SEM aviso nenhum.

    Devolve ``False`` quando qualquer um dos nomes não produz slug (nome
    vazio/só símbolos): ``slugify`` levanta ``ValueError``, e o editor chama
    esta comparação a cada tecla digitada no campo Nome — um nome ainda pela
    metade não pode explodir a GUI, e "não sei" é honestamente "não é o
    mesmo arquivo".
    """
    try:
        return slugify(a) == slugify(b)
    except ValueError:
        return False


def find_by_slug(name: str, candidates: Iterable[_P]) -> _P | None:
    """Acha, entre ``candidates``, o perfil que OCUPA o arquivo de ``name``.

    R-10 (auditoria 23/07): é a busca que as guardas da GUI e do CLI precisam
    fazer antes de gravar — quem responde "quem vou sobrescrever?" é o slug,
    não o nome de exibição. Devolve o objeto (não o nome) porque o diálogo
    tem de citar o perfil REALMENTE afetado ("Navegação"), não o que a
    usuária acabou de digitar ("Navegacao").

    Tolerante em ambas as pontas: nome sem slug válido (do lado de cá ou de
    lá) simplesmente não casa, em vez de levantar.
    """
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
