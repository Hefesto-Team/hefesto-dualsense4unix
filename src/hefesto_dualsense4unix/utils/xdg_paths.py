"""Paths XDG do Hefesto - DualSense4Unix, via `platformdirs`.

Centraliza config / data / cache / runtime paths. `ensure_dir=True`
cria o diretório se não existir.
"""
from __future__ import annotations

import os
from pathlib import Path

from platformdirs import PlatformDirs

from hefesto_dualsense4unix.utils import identidade

# state, perfis e o diretório do socket IPC saem todos daqui. Por isso ele não
_DIRS = PlatformDirs(identidade.atual().slug)


IPC_SOCKET_DEFAULT_NAME = "hefesto-dualsense4unix.sock"
IPC_SOCKET_ENV_VAR = "HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME"

FAKE_ENV_VAR = "HEFESTO_DUALSENSE4UNIX_FAKE"
IPC_SOCKET_FAKE_NAME = "hefesto-dualsense4unix-fake.sock"


def fake_mode_enabled() -> bool:
    """True se o backend fake está ligado via `HEFESTO_DUALSENSE4UNIX_FAKE=1`."""
    return os.environ.get(FAKE_ENV_VAR) == "1"


def ipc_socket_name() -> str:
    """Nome-base do socket IPC, com isolamento AUTOMÁTICO no modo fake."""
    explicit = os.environ.get(IPC_SOCKET_ENV_VAR, "").strip()
    if explicit and "/" not in explicit and explicit not in ("..", "."):
        return explicit
    if fake_mode_enabled():
        return IPC_SOCKET_FAKE_NAME
    return IPC_SOCKET_DEFAULT_NAME


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


def state_dir(ensure: bool = False) -> Path:
    """XDG_STATE_HOME/hefesto-dualsense4unix (~/.local/state/... por default)."""
    p = Path(_DIRS.user_state_dir)
    if ensure:
        p.mkdir(parents=True, exist_ok=True)
    return p


def launch_env_dir(ensure: bool = False) -> Path:
    """Diretório dos arquivos de env materializados para o wrapper de launch."""
    p = state_dir() / "launch_env"
    if ensure:
        p.mkdir(parents=True, exist_ok=True)
    return p


def profiles_dir(ensure: bool = False) -> Path:
    p = config_dir() / "profiles"
    if ensure:
        p.mkdir(parents=True, exist_ok=True)
    return p


def wireplumber_config_dir(ensure: bool = False) -> Path:
    """Diretório dos drop-ins do WirePlumber — honra `XDG_CONFIG_HOME` (T-05,
    ONDA0-Z7, 24/08/2026).

    O WirePlumber em si HONRA `XDG_CONFIG_HOME`; dois pontos do Hefesto
    escreviam/liam nele calados, incondicionalmente em `Path.home() /
    ".config"` — `integrations/storm_doctor.check_wireplumber` e
    `app/actions/emulation_actions._wp_dropin_dir` (medido em 23/08/2026,
    §3.4 da sprint O AMBIENTE PRESUMIDO 01: quem move `XDG_CONFIG_HOME` leva
    o drop-in do microfone, e o Hefesto continuava olhando o lugar velho).
    Um dono só, chamado pelos dois — mesmo padrão de `${XDG_CONFIG_HOME:-
    $HOME/.config}` que os shells desta casa já resolvem
    (`scripts/disable_steam_input.sh:257`, `scripts/doctor.sh`).
    """
    base = os.environ.get("XDG_CONFIG_HOME", "").strip()
    raiz = Path(base) if base else Path.home() / ".config"
    p = raiz / "wireplumber" / "wireplumber.conf.d"
    if ensure:
        p.mkdir(parents=True, exist_ok=True)
    return p


def ipc_socket_path() -> Path:
    """Resolve o path do socket IPC."""
    return runtime_dir(ensure=True) / ipc_socket_name()


__all__ = [
    "FAKE_ENV_VAR",
    "IPC_SOCKET_DEFAULT_NAME",
    "IPC_SOCKET_ENV_VAR",
    "IPC_SOCKET_FAKE_NAME",
    "cache_dir",
    "config_dir",
    "data_dir",
    "fake_mode_enabled",
    "ipc_socket_name",
    "ipc_socket_path",
    "launch_env_dir",
    "profiles_dir",
    "runtime_dir",
    "state_dir",
    "wireplumber_config_dir",
]
