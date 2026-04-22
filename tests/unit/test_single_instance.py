"""Testes de single_instance (BUG-MULTI-INSTANCE-01).

Cobre:
  - `acquire_or_takeover` cria pid file e adquire flock.
  - `is_alive` reporta ESRCH como morto.
  - Takeover envia SIGTERM ao predecessor (via fork) e vence o lock.
  - Pid órfão (processo já morto) é sobrescrito sem SIGTERM.
"""
from __future__ import annotations

import os
import signal
import time
from pathlib import Path

import pytest

from hefesto.utils import single_instance


@pytest.fixture
def isolated_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redireciona $XDG_RUNTIME_DIR para tmp_path; isola pid files."""
    target = tmp_path / "runtime"
    target.mkdir()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(target))
    # platformdirs cacheia o valor em módulo — reimporta para pegar novo env.
    import importlib

    from hefesto.utils import xdg_paths as xdg
    importlib.reload(xdg)
    importlib.reload(single_instance)
    return target


def test_acquire_retorna_pid_atual(isolated_runtime: Path) -> None:
    pid = single_instance.acquire_or_takeover("daemon")
    assert pid == os.getpid()
    pid_file = Path(os.environ["XDG_RUNTIME_DIR"]) / "hefesto" / "daemon.pid"
    assert pid_file.exists()
    assert pid_file.read_text().strip() == str(pid)
    single_instance.release("daemon")


def test_is_alive_processo_morto(isolated_runtime: Path) -> None:
    assert not single_instance.is_alive(999_999_999)


def test_is_alive_processo_proprio(isolated_runtime: Path) -> None:
    assert single_instance.is_alive(os.getpid())


def test_pid_orfao_sem_sigterm(isolated_runtime: Path) -> None:
    """Pid file com PID morto é sobrescrito sem tentar matar."""
    pid_file = Path(os.environ["XDG_RUNTIME_DIR"]) / "hefesto" / "daemon.pid"
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text("999999999\n")
    pid = single_instance.acquire_or_takeover("daemon")
    assert pid == os.getpid()
    assert pid_file.read_text().strip() == str(pid)
    single_instance.release("daemon")


def test_takeover_mata_predecessor(isolated_runtime: Path) -> None:
    """Filho adquire lock, pai faz takeover; filho recebe SIGTERM e sai."""
    child_pid = os.fork()
    if child_pid == 0:
        # Dentro do filho: adquire o lock e dorme até ser morto.
        try:
            single_instance.acquire_or_takeover("gui")
            # Reinstala SIGTERM default caso pytest tenha mascarado.
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
            time.sleep(30)
        finally:
            os._exit(0)

    # No pai: espera o filho escrever seu PID no arquivo.
    pid_file = Path(os.environ["XDG_RUNTIME_DIR"]) / "hefesto" / "gui.pid"
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if pid_file.exists() and pid_file.read_text().strip() == str(child_pid):
            break
        time.sleep(0.05)
    else:
        os.kill(child_pid, signal.SIGKILL)
        os.waitpid(child_pid, 0)
        pytest.fail("filho não escreveu pid file")

    # Takeover pelo pai.
    own = single_instance.acquire_or_takeover("gui")
    assert own == os.getpid()
    assert pid_file.read_text().strip() == str(own)

    # Filho deve ter saído — reap para não deixar zombie.
    waited_pid, status = os.waitpid(child_pid, 0)
    assert waited_pid == child_pid
    assert os.WIFSIGNALED(status) or os.WEXITSTATUS(status) == 0
    assert not single_instance.is_alive(child_pid)

    single_instance.release("gui")


def test_release_sem_acquire_e_noop(isolated_runtime: Path) -> None:
    # Não deve levantar.
    single_instance.release("nao_adquirido")
