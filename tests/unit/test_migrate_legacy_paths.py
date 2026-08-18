"""Testes da migração de caminhos XDG legados (curto → longo).

Cobre CHORE-CONFIG-MIGRATE-LEGACY-SHORT-PATH-01: copia perfis/sessão/prefs do
layout antigo `~/.config/hefesto` para `~/.config/hefesto-dualsense4unix` sem
sobrescrever nada e de forma idempotente.
"""
from __future__ import annotations

import json
import types

import hefesto_dualsense4unix.utils.migrate_legacy_paths as mlp
from hefesto_dualsense4unix.utils import xdg_paths


def _wire(monkeypatch, legacy_cfg, legacy_data, target_cfg, target_data):
    monkeypatch.setattr(
        mlp,
        "_LEGACY",
        types.SimpleNamespace(
            user_config_dir=str(legacy_cfg),
            user_data_dir=str(legacy_data),
        ),
    )
    monkeypatch.setattr(xdg_paths, "config_dir", lambda ensure=False: target_cfg)
    monkeypatch.setattr(xdg_paths, "data_dir", lambda ensure=False: target_data)


def test_migra_arquivos_ausentes(tmp_path, monkeypatch):
    legacy_cfg = tmp_path / "legacy_config"
    (legacy_cfg / "profiles").mkdir(parents=True)
    (legacy_cfg / "profiles" / "fps.json").write_text("{}", encoding="utf-8")
    (legacy_cfg / "gui_preferences.json").write_text('{"advanced_editor": true}', encoding="utf-8")
    legacy_data = tmp_path / "legacy_data"
    (legacy_data / "glyphs").mkdir(parents=True)
    (legacy_data / "glyphs" / "x.svg").write_text("<svg/>", encoding="utf-8")

    target_cfg = tmp_path / "config"
    target_data = tmp_path / "data"
    target_cfg.mkdir()
    target_data.mkdir()

    _wire(monkeypatch, legacy_cfg, legacy_data, target_cfg, target_data)
    result = mlp.migrate_legacy_paths()

    assert (target_cfg / "profiles" / "fps.json").exists()
    assert (target_cfg / "gui_preferences.json").exists()
    assert (target_data / "glyphs" / "x.svg").exists()
    assert sorted(result["config"]) == ["gui_preferences.json", "profiles/fps.json"]
    assert result["data"] == ["glyphs/x.svg"]


def test_nao_sobrescreve_existente(tmp_path, monkeypatch):
    legacy_cfg = tmp_path / "legacy_config"
    (legacy_cfg / "profiles").mkdir(parents=True)
    (legacy_cfg / "profiles" / "fps.json").write_text('{"legacy": true}', encoding="utf-8")
    legacy_data = tmp_path / "legacy_data"
    legacy_data.mkdir()

    target_cfg = tmp_path / "config"
    (target_cfg / "profiles").mkdir(parents=True)
    (target_cfg / "profiles" / "fps.json").write_text('{"current": true}', encoding="utf-8")
    target_data = tmp_path / "data"
    target_data.mkdir()

    _wire(monkeypatch, legacy_cfg, legacy_data, target_cfg, target_data)
    result = mlp.migrate_legacy_paths()

    kept = json.loads((target_cfg / "profiles" / "fps.json").read_text(encoding="utf-8"))
    assert kept == {"current": True}
    assert "config" not in result


def test_idempotente_sem_legado(tmp_path, monkeypatch):
    _wire(
        monkeypatch,
        tmp_path / "nao_existe_cfg",
        tmp_path / "nao_existe_data",
        tmp_path / "cfg",
        tmp_path / "data",
    )
    assert mlp.migrate_legacy_paths() == {}
