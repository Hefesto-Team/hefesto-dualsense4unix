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

# Modo fake (FakeController, sem hardware). Fonte de verdade ÚNICA do switch —
# `daemon.main.build_controller` e `daemon.subsystems.keyboard` leem a mesma var.
FAKE_ENV_VAR = "HEFESTO_DUALSENSE4UNIX_FAKE"
# Socket isolado derivado AUTOMATICAMENTE quando o modo fake está ligado sem um
# override explícito. Ver `ipc_socket_name`.
IPC_SOCKET_FAKE_NAME = "hefesto-dualsense4unix-fake.sock"


def fake_mode_enabled() -> bool:
    """True se o backend fake está ligado via `HEFESTO_DUALSENSE4UNIX_FAKE=1`.

    Casa exatamente com `daemon.main.build_controller` (== "1"), o único ponto que
    decide FakeController vs. hardware real. Centralizar aqui garante que socket +
    lock + escolha de controller derivem do MESMO switch.
    """
    return os.environ.get(FAKE_ENV_VAR) == "1"


def ipc_socket_name() -> str:
    """Nome-base do socket IPC, com isolamento AUTOMÁTICO no modo fake.

    Precedência:
      1. `HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME` explícito e válido (ex.: smoke com
         nome próprio) — sempre respeitado.
      2. Modo fake (`HEFESTO_DUALSENSE4UNIX_FAKE=1`) sem override → socket fake isolado.
      3. Produção → socket default.

    BUG-FAKE-SOCKET-SYNC-01: antes o isolamento do fake dependia de o chamador setar
    DUAS variáveis em sincronia (`FAKE=1` **e** `IPC_SOCKET_NAME=…-fake.sock`, como o
    `run.sh --fake` faz). Um `daemon start` cru só com `FAKE=1` (ou um `FAKE` vazado
    no ambiente) caía no socket de PRODUÇÃO e **sequestrava** o daemon real — a GUI/
    applet/CLI passavam a falar com um FakeController ("Conectado Via USB" fantasma).
    Derivar o socket do próprio switch de fake elimina o footgun de sincronia: um
    daemon fake NUNCA toca o socket de produção, independentemente de quem o iniciou.
    """
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


def profiles_dir(ensure: bool = False) -> Path:
    p = config_dir() / "profiles"
    if ensure:
        p.mkdir(parents=True, exist_ok=True)
    return p


def ipc_socket_path() -> Path:
    """Resolve o path do socket IPC.

    Nome-base resolvido por `ipc_socket_name()` (respeita override explícito e
    isola automaticamente no modo fake). O diretório permanece sob
    `$XDG_RUNTIME_DIR/hefesto-dualsense4unix/` para manter invariantes de permissão
    e limpeza.
    """
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
    "profiles_dir",
    "runtime_dir",
]
