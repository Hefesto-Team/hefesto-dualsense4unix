"""Paths XDG do Hefesto - Dualsense4Unix, via `platformdirs`.

Centraliza config / data / cache / runtime paths. `ensure_dir=True`
cria o diretório se não existir.
"""
from __future__ import annotations

import os
from pathlib import Path

from platformdirs import PlatformDirs

_DIRS = PlatformDirs("hefesto-dualsense4unix")

IPC_SOCKET_DEFAULT_NAME = "hefesto-dualsense4unix.sock"
IPC_SOCKET_ENV_VAR = "HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME"


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
    """XDG_RUNTIME_DIR/hefesto-dualsense4unix; fallback p/ cache/runtime se ausente."""
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
    """Resolve o path do socket IPC.

    Respeita a env var `HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME`
    (default `hefesto-dualsense4unix.sock`) para permitir isolamento entre daemon
    de produção e sessões efêmeras (ex.: smoke runs). Somente o nome-base é
    parametrizável; o diretório permanece sob `$XDG_RUNTIME_DIR/hefesto-dualsense4unix/`
    para manter invariantes de permissão e limpeza.
    """
    name = os.environ.get(IPC_SOCKET_ENV_VAR, IPC_SOCKET_DEFAULT_NAME).strip()
    if not name or "/" in name or name in ("..", "."):
        name = IPC_SOCKET_DEFAULT_NAME
    return runtime_dir(ensure=True) / name


__all__ = [
    "IPC_SOCKET_DEFAULT_NAME",
    "IPC_SOCKET_ENV_VAR",
    "cache_dir",
    "config_dir",
    "data_dir",
    "ipc_socket_path",
    "profiles_dir",
    "runtime_dir",
]
