"""Testes dos paths XDG — foco em `ipc_socket_path()`/`ipc_socket_name()` e no
isolamento automático do socket no modo fake (BUG-FAKE-SOCKET-SYNC-01).

Nota: o `conftest` liga `HEFESTO_DUALSENSE4UNIX_FAKE=1` em todo teste (hermetismo
sem hardware). Os testes de comportamento de PRODUÇÃO desligam o fake explicitamente
via `monkeypatch.delenv(FAKE_ENV_VAR)`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.utils import xdg_paths
from hefesto_dualsense4unix.utils.xdg_paths import (
    FAKE_ENV_VAR,
    IPC_SOCKET_DEFAULT_NAME,
    IPC_SOCKET_ENV_VAR,
    IPC_SOCKET_FAKE_NAME,
    ipc_socket_name,
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


@pytest.fixture
def producao(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contexto de produção: desliga o fake que o conftest injeta."""
    monkeypatch.delenv(FAKE_ENV_VAR, raising=False)


# ---- produção (sem fake) --------------------------------------------------


def test_ipc_socket_path_default_sem_env(
    runtime_tmp: Path, producao: None, monkeypatch: pytest.MonkeyPatch
):
    """Produção sem env var → `hefesto-dualsense4unix.sock`."""
    monkeypatch.delenv(IPC_SOCKET_ENV_VAR, raising=False)
    path = ipc_socket_path()
    assert path.name == IPC_SOCKET_DEFAULT_NAME
    assert path == runtime_tmp / "hefesto-dualsense4unix.sock"


def test_ipc_socket_path_respeita_env_override(
    runtime_tmp: Path, monkeypatch: pytest.MonkeyPatch
):
    """Override explícito parametriza o nome do arquivo (vence até o fake)."""
    monkeypatch.setenv(IPC_SOCKET_ENV_VAR, "hefesto-dualsense4unix-smoke.sock")
    path = ipc_socket_path()
    assert path.name == "hefesto-dualsense4unix-smoke.sock"
    assert path == runtime_tmp / "hefesto-dualsense4unix-smoke.sock"


def test_ipc_socket_path_rejeita_nome_com_barra(
    runtime_tmp: Path, producao: None, monkeypatch: pytest.MonkeyPatch
):
    """Nome com `/` é ignorado (protege contra path traversal trivial)."""
    monkeypatch.setenv(IPC_SOCKET_ENV_VAR, "../fora/hefesto-dualsense4unix.sock")
    path = ipc_socket_path()
    assert path.name == IPC_SOCKET_DEFAULT_NAME


def test_ipc_socket_path_rejeita_nome_vazio(
    runtime_tmp: Path, producao: None, monkeypatch: pytest.MonkeyPatch
):
    """Nome vazio/whitespace cai no default (em produção)."""
    monkeypatch.setenv(IPC_SOCKET_ENV_VAR, "   ")
    path = ipc_socket_path()
    assert path.name == IPC_SOCKET_DEFAULT_NAME


# ---- fake: isolamento AUTOMÁTICO (BUG-FAKE-SOCKET-SYNC-01) -----------------


def test_fake_auto_isola_socket_sem_override(
    runtime_tmp: Path, monkeypatch: pytest.MonkeyPatch
):
    """FAKE=1 sem override → socket fake isolado (NUNCA o de produção).

    Este é o coração do fix: um `daemon start` cru só com FAKE=1 não pode mais
    sequestrar o socket de produção.
    """
    monkeypatch.setenv(FAKE_ENV_VAR, "1")
    monkeypatch.delenv(IPC_SOCKET_ENV_VAR, raising=False)
    assert ipc_socket_name() == IPC_SOCKET_FAKE_NAME
    assert ipc_socket_path().name == IPC_SOCKET_FAKE_NAME
    assert ipc_socket_name() != IPC_SOCKET_DEFAULT_NAME


def test_override_explicito_vence_o_fake(
    runtime_tmp: Path, monkeypatch: pytest.MonkeyPatch
):
    """Override explícito (ex.: smoke) tem precedência sobre a auto-isolação do fake."""
    monkeypatch.setenv(FAKE_ENV_VAR, "1")
    monkeypatch.setenv(IPC_SOCKET_ENV_VAR, "hefesto-dualsense4unix-smoke.sock")
    assert ipc_socket_name() == "hefesto-dualsense4unix-smoke.sock"


def test_fake_e_producao_usam_sockets_distintos(monkeypatch: pytest.MonkeyPatch):
    """Invariante: fake e produção nunca resolvem para o mesmo socket."""
    monkeypatch.delenv(IPC_SOCKET_ENV_VAR, raising=False)
    monkeypatch.delenv(FAKE_ENV_VAR, raising=False)
    prod = ipc_socket_name()
    monkeypatch.setenv(FAKE_ENV_VAR, "1")
    fake = ipc_socket_name()
    assert prod == IPC_SOCKET_DEFAULT_NAME
    assert fake == IPC_SOCKET_FAKE_NAME
    assert prod != fake
