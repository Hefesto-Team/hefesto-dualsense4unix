"""Testes do instalador da unit systemd --user `hefesto-dualsense4unix.service`.

SIMPLIFY-UNIT-01: unit única. Não há mais variante headless.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.daemon import service_install as si
from hefesto_dualsense4unix.daemon.service_install import (
    SERVICE_NORMAL,
    ServiceInstaller,
    find_assets_dir,
)


@pytest.fixture
def isolated_systemd_user(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Aponta `user_unit_dir()` para tmp e força `find_assets_dir()` ao repo."""
    xdg_config = tmp_path / "config"
    xdg_config.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))
    return xdg_config / "systemd" / "user"


class DummyResult:
    def __init__(self, stdout: str = "") -> None:
        self.stdout = stdout
        self.returncode = 0


@pytest.fixture
def dummy_systemctl(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def fake_run(cmd, check=True, capture_output=True, text=True):
        calls.append(list(cmd))
        return DummyResult(stdout="active (running)\n")

    monkeypatch.setattr(si.subprocess, "run", fake_run)
    return calls


def test_find_assets_dir_retorna_path_existente():
    assets = find_assets_dir()
    assert (assets / SERVICE_NORMAL).exists()


def test_install_copia_unit_sem_enable_por_default(
    isolated_systemd_user: Path, dummy_systemctl: list
):
    """BUG-MULTI-INSTANCE-01: auto-start é opt-in (enable=False por padrão)."""
    installer = ServiceInstaller()
    dst = installer.install()
    assert dst.name == SERVICE_NORMAL
    assert dst.parent == isolated_systemd_user
    assert dst.exists()

    cmds = [" ".join(c) for c in dummy_systemctl]
    assert any("daemon-reload" in c for c in cmds)
    assert not any(f"enable {SERVICE_NORMAL}" in c for c in cmds)


def test_install_enable_opt_in(
    isolated_systemd_user: Path, dummy_systemctl: list
):
    """enable=True habilita auto-start no boot."""
    installer = ServiceInstaller()
    installer.install(enable=True)

    cmds = [" ".join(c) for c in dummy_systemctl]
    assert any(f"enable {SERVICE_NORMAL}" in c for c in cmds)


def test_uninstall_remove_arquivo(isolated_systemd_user: Path, dummy_systemctl: list):
    isolated_systemd_user.mkdir(parents=True, exist_ok=True)
    (isolated_systemd_user / SERVICE_NORMAL).write_text("stub")

    installer = ServiceInstaller()
    removed = installer.uninstall()
    assert len(removed) == 1
    assert not (isolated_systemd_user / SERVICE_NORMAL).exists()


def test_uninstall_sem_nada_instalado(isolated_systemd_user: Path, dummy_systemctl: list):
    installer = ServiceInstaller()
    removed = installer.uninstall()
    assert removed == []


def test_start_stop_restart_status(isolated_systemd_user: Path, dummy_systemctl: list):
    installer = ServiceInstaller()
    installer.start()
    installer.stop()
    installer.restart()
    text = installer.status_text()
    assert "active" in text

    cmds = [" ".join(c) for c in dummy_systemctl]
    assert any(f"start {SERVICE_NORMAL}" in c for c in cmds)
    assert any(f"stop {SERVICE_NORMAL}" in c for c in cmds)
    assert any(f"restart {SERVICE_NORMAL}" in c for c in cmds)


def test_detect_installed_unit(
    isolated_systemd_user: Path,
    dummy_systemctl: list,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    # Detect agora checa também SYSTEM_UNIT_DIRS (/usr/lib/systemd/user etc)
    # para suporte a .deb. Para isolar do ambiente real do CI/dev, monkeypatch
    # SYSTEM_UNIT_DIRS para paths inexistentes em tmp.
    from hefesto_dualsense4unix.daemon import service_install as si_mod
    fake_dirs = [tmp_path / "fake-usr-lib", tmp_path / "fake-etc"]
    monkeypatch.setattr(si_mod, "SYSTEM_UNIT_DIRS", fake_dirs)

    installer = ServiceInstaller()
    assert installer.detect_installed_unit() is None

    isolated_systemd_user.mkdir(parents=True, exist_ok=True)
    (isolated_systemd_user / SERVICE_NORMAL).write_text("stub")
    assert installer.detect_installed_unit() == "hefesto-dualsense4unix"


def test_dry_run_nao_copia(isolated_systemd_user: Path, dummy_systemctl: list):
    installer = ServiceInstaller(dry_run=True)
    installer.install()
    # Arquivo não copiado; systemctl não chamado (retornou None).
    assert not (isolated_systemd_user / SERVICE_NORMAL).exists()


def test_find_assets_dir_respeita_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake = tmp_path / "fake_assets"
    fake.mkdir()
    (fake / SERVICE_NORMAL).write_text("stub")
    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_ASSETS_DIR", str(fake))

    assert find_assets_dir() == fake
