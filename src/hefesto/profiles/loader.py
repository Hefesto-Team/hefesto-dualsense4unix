"""Read/write de perfis em JSON com `filelock` para evitar races.

Padrão:
    profiles = load_all_profiles()               # lista Profile
    save_profile(profile)                        # grava <slug(name)>.json
    delete_profile("shooter")                    # remove arquivo
    profile = load_profile("shooter")            # lê um específico

Paths via `hefesto.utils.xdg_paths.profiles_dir()`. Escritas fazem write
atômico (tmpfile + rename) para evitar arquivos truncados em crash.

PROFILE-SLUG-SEPARATION-01: filename é derivado de `slugify(profile.name)`.
`load_profile` aceita tanto slug direto (literal ASCII) quanto display name
acentuado via busca adaptativa em três camadas.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from filelock import FileLock

from hefesto.profiles.schema import Profile
from hefesto.profiles.slug import slugify
from hefesto.utils.xdg_paths import profiles_dir

LOCK_SUFFIX = ".lock"

# AUDIT-FINDING-PROFILE-PATH-TRAVERSAL-01: tokens proibidos em identifier.
# Path('/dir') / '/etc/passwd' devolve '/etc/passwd' (escape absoluto);
# '..' escapa relativo após resolve(). Null byte quebra syscalls de fs.
_FORBIDDEN_IDENTIFIER_TOKENS = ("/", "\\", "\x00")


def _reject_traversal(identifier: str) -> None:
    """Rejeita identifier que tente path traversal no diretório de perfis.

    Display names acentuados (ex.: "Ação Rápida") são permitidos — o pipeline
    do loader normaliza via `slugify()`. O que NÃO é permitido: separadores
    de path, componentes `..`, null bytes. Defesa em boundary antes de qualquer
    `directory / identifier`.
    """
    if not isinstance(identifier, str) or not identifier:
        raise ValueError("identifier de perfil vazio ou inválido")
    for token in _FORBIDDEN_IDENTIFIER_TOKENS:
        if token in identifier:
            raise ValueError(
                f"identifier de perfil contém caractere proibido: {token!r}"
            )
    # '..' em qualquer posição (ex.: '../x', 'x/..', '..', '..bar', 'foo..bar').
    # Display names legítimos nunca contêm '..'; separadores já foram rejeitados.
    if ".." in identifier:
        raise ValueError("identifier de perfil contém sequência '..'")


def _lock_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + LOCK_SUFFIX)


def _profile_path(identifier: str | Profile) -> Path:
    """Resolve filename a partir de slug direto ou de Profile.

    - Se `identifier` é `Profile`, deriva slug de `profile.name`.
    - Se `identifier` é `str`, assume que já é slug (ou filename ASCII).
    """
    if isinstance(identifier, Profile):
        return profiles_dir(ensure=True) / f"{slugify(identifier.name)}.json"
    _reject_traversal(identifier)
    return profiles_dir(ensure=True) / f"{identifier}.json"


def _read_profile(path: Path) -> Profile:
    with FileLock(str(_lock_path(path))):
        raw = json.loads(path.read_text(encoding="utf-8"))
    return Profile.model_validate(raw)


def load_profile(identifier: str) -> Profile:
    """Carrega perfil por slug direto ou por display name.

    Ordem de busca:
    1. `<identifier>.json` direto (assume que `identifier` já é slug/filename).
    2. `<slugify(identifier)>.json` (se `identifier` era display name acentuado).
    3. Varredura fallback: itera o diretório buscando `profile.name` cujo
       slug bata com `slugify(identifier)`. Cobre arquivos cujo filename
       não acompanhou o slug atual (ex.: `meu-perfil.json` com name "Meu Perfil").
    """
    _reject_traversal(identifier)
    directory = profiles_dir(ensure=True)
    direct = directory / f"{identifier}.json"
    # Defesa em profundidade: mesmo após rejeição de tokens, confirmar que o
    # path resolvido não escapa do diretório de perfis (ex.: symlink hostil).
    directory_resolved = directory.resolve()
    if not direct.resolve().is_relative_to(directory_resolved):
        raise ValueError("identifier de perfil escapa do diretório de perfis")
    if direct.exists():
        return _read_profile(direct)

    try:
        slug = slugify(identifier)
    except ValueError:
        raise FileNotFoundError(f"perfil não encontrado: {identifier}") from None

    slugged = directory / f"{slug}.json"
    if slugged.exists():
        return _read_profile(slugged)

    for path in directory.glob("*.json"):
        try:
            profile = _read_profile(path)
        except Exception:
            continue
        try:
            if slugify(profile.name) == slug:
                return profile
        except ValueError:
            continue

    raise FileNotFoundError(f"perfil não encontrado: {identifier}")


def load_all_profiles() -> list[Profile]:
    directory = profiles_dir(ensure=True)
    profiles: list[Profile] = []
    for path in sorted(directory.glob("*.json")):
        with FileLock(str(_lock_path(path))):
            raw = json.loads(path.read_text(encoding="utf-8"))
        profiles.append(Profile.model_validate(raw))
    return profiles


def save_profile(profile: Profile) -> Path:
    """Grava perfil em `<slugify(profile.name)>.json` de forma atômica."""
    path = _profile_path(profile)
    payload = profile.model_dump(mode="json")
    with FileLock(str(_lock_path(path))):
        _atomic_write_json(path, payload)
    return path


def delete_profile(identifier: str) -> None:
    """Remove o arquivo do perfil. Aceita slug ou display name.

    Resolve o path via `load_profile` para garantir que o filename correto
    seja alvo do unlink — importante para perfis cujo filename não casa
    com o slug do `name` atual.
    """
    try:
        profile = load_profile(identifier)
    except FileNotFoundError:
        raise FileNotFoundError(f"perfil não encontrado: {identifier}") from None

    directory = profiles_dir(ensure=True)
    slug = slugify(profile.name)
    candidate = directory / f"{slug}.json"
    if not candidate.exists():
        direct = directory / f"{identifier}.json"
        if direct.exists():
            candidate = direct
        else:
            for path in directory.glob("*.json"):
                try:
                    other = _read_profile(path)
                except Exception:
                    continue
                if other.name == profile.name:
                    candidate = path
                    break

    with FileLock(str(_lock_path(candidate))):
        candidate.unlink()


def _atomic_write_json(target: Path, payload: object) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, target)
    except Exception:
        if Path(tmp_name).exists():
            Path(tmp_name).unlink(missing_ok=True)
        raise


__all__ = [
    "delete_profile",
    "load_all_profiles",
    "load_profile",
    "save_profile",
]
