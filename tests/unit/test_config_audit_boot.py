"""Auditoria de perfis no boot (FEAT-CONFIG-AUDIT-BOOT-01)."""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile


def test_audit_profiles_detecta_corrompido(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    loader_module.save_profile(Profile(name="ok", match=MatchAny(), priority=0))
    (target / "lixo.json").write_text("{{ broken json [", encoding="utf-8")

    invalid = loader_module.audit_profiles()
    nomes = [name for name, _err in invalid]
    assert "lixo.json" in nomes
    assert all("ok" not in n for n in nomes)


