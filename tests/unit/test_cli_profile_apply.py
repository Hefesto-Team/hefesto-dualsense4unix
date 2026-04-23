"""Testes dos subcomandos `hefesto profile apply` e `profile save --from-active`
(FEAT-CLI-PARITY-01).

Mocka IPC e isola diretório de perfis via fixture semelhante ao
`test_cli.py` original.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from hefesto.cli.app import app
from hefesto.cli.ipc_client import IpcError
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

    from hefesto.utils import xdg_paths

    fake_cfg = tmp_path / "config"
    fake_cfg.mkdir()

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            fake_cfg.mkdir(parents=True, exist_ok=True)
        return fake_cfg

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    return target


@pytest.fixture
def mock_ipc(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    registry: dict[str, Any] = {"calls": [], "response": {"active_profile": "draft"}, "raise": None}

    def fake_run_call(
        method: str, params: dict[str, Any] | None = None, timeout: float | None = None
    ) -> Any:
        registry["calls"].append((method, dict(params or {})))
        if registry["raise"] is not None:
            raise registry["raise"]
        return registry["response"]

    import hefesto.app.ipc_bridge as bridge

    monkeypatch.setattr(bridge, "_run_call", fake_run_call)
    return registry


def _draft_json_valido() -> dict[str, Any]:
    return {
        "name": "draft",
        "priority": 5,
        "match": {"type": "criteria", "window_class": ["Firefox"]},
        "triggers": {
            "left": {"mode": "Off"},
            "right": {"mode": "Off"},
        },
        "leds": {"lightbar": [255, 128, 0]},
    }


def test_apply_valida_salva_e_ativa(
    tmp_path: Path,
    isolated_profiles_dir: Path,
    mock_ipc: dict[str, Any],
) -> None:
    draft = tmp_path / "draft.json"
    draft.write_text(json.dumps(_draft_json_valido()), encoding="utf-8")

    result = runner.invoke(app, ["profile", "apply", "--file", str(draft)])
    assert result.exit_code == 0, result.output

    # Perfil foi gravado
    saved = isolated_profiles_dir / "draft.json"
    assert saved.exists()

    # IPC foi chamado com profile.switch
    assert mock_ipc["calls"] == [("profile.switch", {"name": "draft"})]
    assert "ativado via daemon" in result.output


def test_apply_json_invalido_exit_1(
    tmp_path: Path,
    isolated_profiles_dir: Path,
) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{ not valid json", encoding="utf-8")

    result = runner.invoke(app, ["profile", "apply", "--file", str(broken)])
    assert result.exit_code == 1
    assert "ler JSON" in result.output


def test_apply_schema_invalido_exit_1(
    tmp_path: Path,
    isolated_profiles_dir: Path,
) -> None:
    bad = _draft_json_valido()
    # RGB fora de byte: valida contra LedsConfig.lightbar
    bad["leds"] = {"lightbar": [999, 0, 0]}
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad), encoding="utf-8")

    result = runner.invoke(app, ["profile", "apply", "--file", str(path)])
    assert result.exit_code == 1
    assert "não valida" in result.output


def test_apply_daemon_offline_grava_marker(
    tmp_path: Path,
    isolated_profiles_dir: Path,
    mock_ipc: dict[str, Any],
) -> None:
    mock_ipc["raise"] = FileNotFoundError("socket ausente")

    draft = tmp_path / "draft.json"
    draft.write_text(json.dumps(_draft_json_valido()), encoding="utf-8")

    result = runner.invoke(app, ["profile", "apply", "--file", str(draft)])
    assert result.exit_code == 0, result.output
    assert "offline" in result.output

    # Marker foi gravado
    from hefesto.utils import xdg_paths

    marker = xdg_paths.config_dir() / "active_profile.txt"
    assert marker.exists()
    assert marker.read_text(encoding="utf-8").strip() == "draft"


def test_apply_daemon_recusa_ipc_error(
    tmp_path: Path,
    isolated_profiles_dir: Path,
    mock_ipc: dict[str, Any],
) -> None:
    mock_ipc["raise"] = IpcError(-32002, "perfil não existe")

    draft = tmp_path / "draft.json"
    draft.write_text(json.dumps(_draft_json_valido()), encoding="utf-8")

    result = runner.invoke(app, ["profile", "apply", "--file", str(draft)])
    # Mesmo com recusa, marker é gravado e exit=0 (modo defensivo).
    assert result.exit_code == 0
    assert "recusou" in result.output


def test_apply_no_save_exige_perfil_pre_existente(
    tmp_path: Path,
    isolated_profiles_dir: Path,
    mock_ipc: dict[str, Any],
) -> None:
    draft = tmp_path / "draft.json"
    draft.write_text(json.dumps(_draft_json_valido()), encoding="utf-8")

    result = runner.invoke(
        app, ["profile", "apply", "--file", str(draft), "--no-save"]
    )
    assert result.exit_code == 1
    assert "ja presente" in result.output


def test_save_from_active_clona_perfil(
    isolated_profiles_dir: Path,
    mock_ipc: dict[str, Any],
) -> None:
    # Cria perfil original e marca como ativo.
    original = _draft_json_valido()
    original["name"] = "shooter"
    (isolated_profiles_dir / "shooter.json").write_text(
        json.dumps(original), encoding="utf-8"
    )

    from hefesto.utils import xdg_paths

    marker = xdg_paths.config_dir(ensure=True) / "active_profile.txt"
    marker.write_text("shooter\n", encoding="utf-8")

    result = runner.invoke(
        app, ["profile", "save", "meu_backup", "--from-active"]
    )
    assert result.exit_code == 0, result.output

    clone_path = isolated_profiles_dir / "meu_backup.json"
    assert clone_path.exists()
    clone_data = json.loads(clone_path.read_text(encoding="utf-8"))
    assert clone_data["name"] == "meu_backup"
    # Demais campos preservados
    assert clone_data["priority"] == 5
    assert clone_data["leds"]["lightbar"] == [255, 128, 0]


def test_save_sem_from_active_recusa(
    isolated_profiles_dir: Path,
) -> None:
    result = runner.invoke(app, ["profile", "save", "foo"])
    assert result.exit_code == 2
    assert "from-active" in result.output


def test_save_from_active_sem_marker(
    isolated_profiles_dir: Path,
) -> None:
    result = runner.invoke(app, ["profile", "save", "foo", "--from-active"])
    assert result.exit_code == 1
    assert "nenhum perfil ativo" in result.output
