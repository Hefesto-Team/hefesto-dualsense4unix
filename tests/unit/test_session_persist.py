"""Testes de persistência de sessão (FEAT-PERSIST-SESSION-01).

Cobre:
  - save_last_profile / load_last_profile round-trip.
  - load retorna None quando arquivo ausente.
  - load retorna None quando JSON inválido.
  - ProfileManager.activate() persiste o perfil via save_last_profile.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hefesto.utils.session import load_last_profile, save_last_profile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redireciona config_dir para tmp_path durante o teste."""
    monkeypatch.setattr(
        "hefesto.utils.session._session_path",
        lambda: tmp_path / "session.json",
    )
    return tmp_path / "session.json"


# ---------------------------------------------------------------------------
# Testes de save + load
# ---------------------------------------------------------------------------


def test_save_e_load_round_trip(tmp_session: Path) -> None:
    save_last_profile("shooter")
    assert load_last_profile() == "shooter"


def test_load_retorna_none_sem_arquivo(tmp_session: Path) -> None:
    assert not tmp_session.exists()
    assert load_last_profile() is None


def test_load_retorna_none_com_json_invalido(tmp_session: Path) -> None:
    tmp_session.write_text("isto nao e json{{{", encoding="utf-8")
    assert load_last_profile() is None


def test_load_retorna_none_com_chave_ausente(tmp_session: Path) -> None:
    tmp_session.write_text(json.dumps({"other_key": "value"}), encoding="utf-8")
    assert load_last_profile() is None


def test_save_sobrescreve_valor_anterior(tmp_session: Path) -> None:
    save_last_profile("shooter")
    save_last_profile("browser")
    assert load_last_profile() == "browser"


def test_save_nao_explode_em_diretorio_inexistente(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "subdir" / "session.json"
    monkeypatch.setattr("hefesto.utils.session._session_path", lambda: path)
    # Diretório pai não existe — save deve falhar silenciosamente.
    save_last_profile("shooter")
    # Sem exception: teste passou.


# ---------------------------------------------------------------------------
# Integração com ProfileManager
# ---------------------------------------------------------------------------


def test_activate_chama_save_last_profile() -> None:
    """ProfileManager.activate() deve persistir o perfil via save_last_profile."""
    saved: list[str] = []

    from hefesto.profiles.schema import LedsConfig, MatchCriteria, Profile, TriggersConfig
    from hefesto.daemon.state_store import StateStore
    from hefesto.profiles.manager import ProfileManager

    fake_profile = Profile(
        name="shooter",
        match=MatchCriteria(),
        triggers=TriggersConfig(),
        leds=LedsConfig(),
    )

    ctrl = MagicMock()
    store = StateStore()
    mgr = ProfileManager(controller=ctrl, store=store)

    with patch("hefesto.profiles.manager.load_profile", return_value=fake_profile):
        with patch("hefesto.profiles.manager.apply_led_settings"):
            with patch("hefesto.utils.session.save_last_profile", side_effect=saved.append):
                mgr.activate("shooter")

    assert saved == ["shooter"]
