"""FEAT-MOUSE-PERSIST-01: o toggle de emulação de mouse persiste em
restart/reboot via flag-file no config_dir.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.utils import session


@pytest.fixture()
def tmp_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redireciona config_dir do session para tmp_path."""
    monkeypatch.setattr(session, "config_dir", lambda ensure=False: tmp_path)
    return tmp_path


def test_roundtrip_liga_desliga(tmp_config: Path) -> None:
    assert session.load_mouse_emulation_enabled() is False
    session.save_mouse_emulation_enabled(True)
    assert (tmp_config / "mouse_emulation.flag").exists()
    assert session.load_mouse_emulation_enabled() is True
    session.save_mouse_emulation_enabled(False)
    assert not (tmp_config / "mouse_emulation.flag").exists()
    assert session.load_mouse_emulation_enabled() is False


def test_load_false_sem_arquivo(tmp_config: Path) -> None:
    assert session.load_mouse_emulation_enabled() is False


def test_save_best_effort_nao_propaga_excecao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_a: object, **_k: object) -> Path:
        raise OSError("config dir indisponível")

    monkeypatch.setattr(session, "config_dir", _boom)
    # Não deve levantar (best-effort); e load também é tolerante.
    session.save_mouse_emulation_enabled(True)
    assert session.load_mouse_emulation_enabled() is False
