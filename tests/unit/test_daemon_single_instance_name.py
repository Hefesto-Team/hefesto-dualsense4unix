"""BUG-MULTI-INSTANCE-ISOLATED-SOCKET-01 — o lock de instância única do daemon é
derivado do socket IPC, para que daemons com socket ISOLADO (fake/smoke/custom)
não briguem pelo pid-lock do daemon de PRODUÇÃO (que causava ping-pong com o
systemd e daemons órfãos disputando o socket).
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.daemon.main import single_instance_name
from hefesto_dualsense4unix.utils.xdg_paths import (
    FAKE_ENV_VAR,
    IPC_SOCKET_DEFAULT_NAME,
    IPC_SOCKET_ENV_VAR,
)


def test_producao_sem_env_usa_lock_daemon(monkeypatch: pytest.MonkeyPatch) -> None:
    # conftest liga FAKE=1 em todo teste; produção real desliga o fake.
    monkeypatch.delenv(FAKE_ENV_VAR, raising=False)
    monkeypatch.delenv(IPC_SOCKET_ENV_VAR, raising=False)
    assert single_instance_name() == "daemon"


def test_fake_sem_env_auto_isola_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    """BUG-FAKE-SOCKET-SYNC-01: FAKE=1 sem override → lock isolado, derivado do
    socket fake-aware. Um daemon fake cru nunca compartilha o lock do real."""
    monkeypatch.setenv(FAKE_ENV_VAR, "1")
    monkeypatch.delenv(IPC_SOCKET_ENV_VAR, raising=False)
    assert single_instance_name() == "daemon-hefesto-dualsense4unix-fake"


def test_producao_com_socket_default_usa_lock_daemon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(IPC_SOCKET_ENV_VAR, IPC_SOCKET_DEFAULT_NAME)
    assert single_instance_name() == "daemon"


def test_fake_tem_lock_isolado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(IPC_SOCKET_ENV_VAR, "hefesto-dualsense4unix-fake.sock")
    name = single_instance_name()
    assert name != "daemon"  # nunca compartilha o lock do real
    assert name == "daemon-hefesto-dualsense4unix-fake"


def test_smoke_tem_lock_isolado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(IPC_SOCKET_ENV_VAR, "hefesto-dualsense4unix-smoke.sock")
    assert single_instance_name() == "daemon-hefesto-dualsense4unix-smoke"


def test_socket_custom_tem_lock_isolado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(IPC_SOCKET_ENV_VAR, "meu-teste.sock")
    assert single_instance_name() == "daemon-meu-teste"


def test_fake_e_producao_nunca_colidem(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invariante central: o nome do fake e o do real são distintos, então o
    fake jamais faz SIGTERM-takeover do daemon de produção."""
    monkeypatch.setenv(IPC_SOCKET_ENV_VAR, IPC_SOCKET_DEFAULT_NAME)
    prod = single_instance_name()
    monkeypatch.setenv(IPC_SOCKET_ENV_VAR, "hefesto-dualsense4unix-fake.sock")
    fake = single_instance_name()
    assert prod != fake
