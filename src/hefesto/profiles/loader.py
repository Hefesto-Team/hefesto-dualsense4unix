"""Read/write de perfis em JSON com `filelock` para evitar races.

Padrão:
    profiles = load_all_profiles()               # lista Profile
    save_profile(profile)                        # grava <name>.json
    delete_profile("shooter")                    # remove arquivo
    profile = load_profile("shooter")            # lê um específico

Paths via `hefesto.utils.xdg_paths.profiles_dir()`. Escritas fazem write
atômico (tmpfile + rename) para evitar arquivos truncados em crash.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from filelock import FileLock

from hefesto.profiles.schema import Profile
from hefesto.utils.xdg_paths import profiles_dir

LOCK_SUFFIX = ".lock"


def _lock_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + LOCK_SUFFIX)


def _profile_path(name: str) -> Path:
    return profiles_dir(ensure=True) / f"{name}.json"


def load_profile(name: str) -> Profile:
    path = _profile_path(name)
    if not path.exists():
        raise FileNotFoundError(f"perfil nao encontrado: {name}")
    with FileLock(str(_lock_path(path))):
        raw = json.loads(path.read_text(encoding="utf-8"))
    return Profile.model_validate(raw)


def load_all_profiles() -> list[Profile]:
    directory = profiles_dir(ensure=True)
    profiles: list[Profile] = []
    for path in sorted(directory.glob("*.json")):
        with FileLock(str(_lock_path(path))):
            raw = json.loads(path.read_text(encoding="utf-8"))
        profiles.append(Profile.model_validate(raw))
    return profiles


def save_profile(profile: Profile) -> Path:
    path = _profile_path(profile.name)
    payload = profile.model_dump(mode="json")
    with FileLock(str(_lock_path(path))):
        _atomic_write_json(path, payload)
    return path


def delete_profile(name: str) -> None:
    path = _profile_path(name)
    if not path.exists():
        raise FileNotFoundError(f"perfil nao encontrado: {name}")
    with FileLock(str(_lock_path(path))):
        path.unlink()


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
