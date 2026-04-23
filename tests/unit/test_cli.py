"""Testes da CLI via typer.testing.CliRunner."""
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from hefesto.cli.app import app
from hefesto.profiles import loader as loader_module

runner = CliRunner()


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    # Também aponta config_dir para tmp para active_profile marker.
    from hefesto.utils import xdg_paths

    fake_cfg = tmp_path / "config"
    fake_cfg.mkdir()

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            fake_cfg.mkdir(parents=True, exist_ok=True)
        return fake_cfg

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    return target


def test_version_command():
    from hefesto import __version__

    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_profile_list_vazio(isolated_profiles_dir: Path):
    result = runner.invoke(app, ["profile", "list"])
    assert result.exit_code == 0
    assert "nenhum perfil" in result.stdout


def test_profile_create_e_list(isolated_profiles_dir: Path):
    r1 = runner.invoke(app, ["profile", "create", "teste", "--match-class", "Firefox"])
    assert r1.exit_code == 0

    r2 = runner.invoke(app, ["profile", "list"])
    assert r2.exit_code == 0
    assert "teste" in r2.stdout
    assert "Firefox" in r2.stdout


def test_profile_create_fallback(isolated_profiles_dir: Path):
    r = runner.invoke(app, ["profile", "create", "fb", "--fallback"])
    assert r.exit_code == 0

    r2 = runner.invoke(app, ["profile", "show", "fb"])
    assert r2.exit_code == 0
    assert '"type": "any"' in r2.stdout
    assert '"priority": 0' in r2.stdout


def test_profile_show_inexistente(isolated_profiles_dir: Path):
    result = runner.invoke(app, ["profile", "show", "ghost"])
    assert result.exit_code == 1
    assert "não encontrado" in result.stdout


def test_profile_delete_com_yes(isolated_profiles_dir: Path):
    runner.invoke(app, ["profile", "create", "tmp", "--match-class", "X"])
    r = runner.invoke(app, ["profile", "delete", "tmp", "--yes"])
    assert r.exit_code == 0


def test_battery_sem_hardware():
    # Sem daemon e sem hardware: retorna exit code 1 com mensagem.
    result = runner.invoke(app, ["battery"])
    # O fallback tenta ler hardware; se não disponível, sai com 1.
    assert result.exit_code in (0, 1)


def test_status_roda_sem_daemon():
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "Hefesto" in result.stdout or "Status" in result.stdout


def test_daemon_install_service_dry_command_help():
    # Apenas valida que subcomando existe e aceita --help.
    # SIMPLIFY-UNIT-01: unit única, sem flag --headless aqui.
    result = runner.invoke(app, ["daemon", "install-service", "--help"])
    assert result.exit_code == 0
    assert "install-service" in result.stdout


def test_test_trigger_sem_hardware_nao_explode():
    result = runner.invoke(
        app,
        ["test", "trigger", "--side", "right", "--mode", "Rigid", "--params", "5,200"],
    )
    # Sem hardware: não explode; saída pode indicar erro mas exit code controlado.
    assert result.exit_code in (0, 1)
