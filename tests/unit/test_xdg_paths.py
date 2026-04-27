"""Testes dos paths XDG — foco em `ipc_socket_path()` e env override."""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.utils import xdg_paths
from hefesto_dualsense4unix.utils.xdg_paths import (
    IPC_SOCKET_DEFAULT_NAME,
    IPC_SOCKET_ENV_VAR,
    ipc_socket_path,
)


@pytest.fixture
def runtime_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redireciona `runtime_dir` para um tmp_path isolado."""

    def _fake_runtime_dir(ensure: bool = False) -> Path:
        if ensure:
            tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path

    monkeypatch.setattr(xdg_paths, "runtime_dir", _fake_runtime_dir)
    return tmp_path


def test_ipc_socket_path_default_sem_env(
    runtime_tmp: Path, monkeypatch: pytest.MonkeyPatch
):
    """Sem env var definida, usa `hefesto-dualsense4unix.sock`."""
    monkeypatch.delenv(IPC_SOCKET_ENV_VAR, raising=False)
    path = ipc_socket_path()
    assert path.name == IPC_SOCKET_DEFAULT_NAME
    assert path == runtime_tmp / "hefesto-dualsense4unix.sock"


def test_ipc_socket_path_respeita_env_override(
    runtime_tmp: Path, monkeypatch: pytest.MonkeyPatch
):
    """Env var `HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME` parametriza o nome do arquivo."""
    monkeypatch.setenv(IPC_SOCKET_ENV_VAR, "hefesto-dualsense4unix-smoke.sock")
    path = ipc_socket_path()
    assert path.name == "hefesto-dualsense4unix-smoke.sock"
    assert path == runtime_tmp / "hefesto-dualsense4unix-smoke.sock"


def test_ipc_socket_path_rejeita_nome_com_barra(
    runtime_tmp: Path, monkeypatch: pytest.MonkeyPatch
):
    """Nome com `/` é ignorado (protege contra path traversal trivial)."""
    monkeypatch.setenv(IPC_SOCKET_ENV_VAR, "../fora/hefesto-dualsense4unix.sock")
    path = ipc_socket_path()
    assert path.name == IPC_SOCKET_DEFAULT_NAME


def test_ipc_socket_path_rejeita_nome_vazio(
    runtime_tmp: Path, monkeypatch: pytest.MonkeyPatch
):
    """Nome vazio/whitespace cai no default."""
    monkeypatch.setenv(IPC_SOCKET_ENV_VAR, "   ")
    path = ipc_socket_path()
    assert path.name == IPC_SOCKET_DEFAULT_NAME
