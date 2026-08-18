"""Auditoria de perfis no boot (FEAT-CONFIG-AUDIT-BOOT-01).

`audit_profiles()` valida todos os perfis e coleta os corrompidos (sem levantar);
o daemon usa isso no boot para AVISAR o usuário (log + notificação), em vez de
só pular o perfil silenciosamente no fallback.
"""
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
    # Perfil válido (formato garantido) + um corrompido.
    loader_module.save_profile(Profile(name="ok", match=MatchAny(), priority=0))
    (target / "lixo.json").write_text("{{ broken json [", encoding="utf-8")

    invalid = loader_module.audit_profiles()
    nomes = [name for name, _err in invalid]
    assert "lixo.json" in nomes
    assert all("ok" not in n for n in nomes)  # o válido não é reportado


def test_notify_config_errors_vazio_nao_notifica(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hefesto_dualsense4unix.integrations import desktop_notifications as dn

    called: list[object] = []
    monkeypatch.setattr(dn, "_notifications_enabled", lambda: True)
    monkeypatch.setattr(dn, "notify", lambda *a, **k: called.append((a, k)) or True)

    assert dn.notify_config_errors([]) is False
    assert called == []
    # Com inválidos, notifica uma vez.
    assert dn.notify_config_errors([("x.json", "erro")]) is True
    assert len(called) == 1
