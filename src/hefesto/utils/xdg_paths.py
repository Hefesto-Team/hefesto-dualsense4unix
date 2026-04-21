"""Paths XDG do Hefesto, via `platformdirs`.

Centraliza config / data / cache / runtime paths. `ensure_dir=True`
cria o diretório se não existir.
"""
from __future__ import annotations

from pathlib import Path

from platformdirs import PlatformDirs

_DIRS = PlatformDirs("hefesto")


def config_dir(ensure: bool = False) -> Path:
    p = Path(_DIRS.user_config_dir)
    if ensure:
        p.mkdir(parents=True, exist_ok=True)
    return p


def data_dir(ensure: bool = False) -> Path:
    p = Path(_DIRS.user_data_dir)
    if ensure:
        p.mkdir(parents=True, exist_ok=True)
    return p


def cache_dir(ensure: bool = False) -> Path:
    p = Path(_DIRS.user_cache_dir)
    if ensure:
        p.mkdir(parents=True, exist_ok=True)
    return p


def runtime_dir(ensure: bool = False) -> Path:
    """XDG_RUNTIME_DIR/hefesto, fallback para cache/runtime se XDG_RUNTIME_DIR ausente."""
    runtime = _DIRS.user_runtime_dir
    p = Path(runtime) if runtime else cache_dir() / "runtime"
    if ensure:
        p.mkdir(parents=True, exist_ok=True)
    return p


def profiles_dir(ensure: bool = False) -> Path:
    p = config_dir() / "profiles"
    if ensure:
        p.mkdir(parents=True, exist_ok=True)
    return p


def ipc_socket_path() -> Path:
    return runtime_dir(ensure=True) / "hefesto.sock"


__all__ = [
    "cache_dir",
    "config_dir",
    "data_dir",
    "ipc_socket_path",
    "profiles_dir",
    "runtime_dir",
]
