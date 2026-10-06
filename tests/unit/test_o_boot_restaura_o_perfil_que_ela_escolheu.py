"""O boot restaura o perfil que ela ativou à mão, com regra de janela ou sem.

`D-2909-O-HEFESTO-ABRE-NA-ESCOLHA-DELA`, item 4: o boot não adia mais perfil de
janela, e o estado público não guarda espera nenhuma. O campo
`perfil_adiado_por_janela` saiu do `StateStore` em 03/10/2026, sem escritor
desde a decisão. As duas provas ficam: o Sackboy que ela ativou volta no boot, e
sem perfil nenhum o boot responde `None`.
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isola config_dir (session.json + active_profile.txt) em tmp_path."""
    config = tmp_path / "config"
    config.mkdir()

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            config.mkdir(parents=True, exist_ok=True)
        return config

    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.config_dir", fake_config_dir
    )
    from hefesto_dualsense4unix.utils import xdg_paths

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    return config


@pytest.fixture()
def isolated_profiles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isola profiles_dir em tmp_path (padrão dos testes de loader)."""
    from hefesto_dualsense4unix.profiles import loader as loader_module

    profiles = tmp_path / "profiles"
    profiles.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            profiles.mkdir(parents=True, exist_ok=True)
        return profiles

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return profiles


class _BootDaemon:
    """Daemon mínimo para `restore_last_profile` (executor inline)."""

    def __init__(self, controller: object, store: object) -> None:
        self.controller = controller
        self.store = store
        self._native_mode = False
        self._keyboard_device = None

    async def _run_blocking(self, fn: object, *args: object) -> object:
        return fn(*args)  # type: ignore[operator]


def _salvar_sackboy_dela() -> None:
    """Grava o perfil `Sackboy` COMO ELE ESTÁ na máquina do usuário (08/08 01:49)."""
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile

    save_profile(
        Profile(
            name="Sackboy",
            match=MatchCriteria(window_class=["steam_app_1599660"]),
            priority=200,
        )
    )


@pytest.mark.asyncio
async def test_boot_restaura_o_perfil_de_janela_que_ela_escolheu(
    isolated_config: Path, isolated_profiles: Path
) -> None:
    """O caso dela, fim a fim: o Sackboy que ela ativou à mão volta no boot."""
    from hefesto_dualsense4unix.daemon.connection import restore_last_profile
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.testing import FakeController
    from hefesto_dualsense4unix.utils.session import (
        save_active_marker,
        save_last_profile,
    )

    _salvar_sackboy_dela()
    save_last_profile("Sackboy")
    save_active_marker("Sackboy")

    fc = FakeController()
    fc.connect()
    store = StateStore()
    daemon = _BootDaemon(controller=fc, store=store)
    await restore_last_profile(daemon)  # type: ignore[arg-type]

    assert store.active_profile == "Sackboy"


@pytest.mark.asyncio
async def test_boot_sem_perfil_nenhum_nao_inventa_espera(
    isolated_config: Path, isolated_profiles: Path
) -> None:
    """Sem sessão nem perfil gravado, o boot não inventa perfil."""
    from hefesto_dualsense4unix.daemon.connection import restore_last_profile
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.testing import FakeController

    fc = FakeController()
    fc.connect()
    store = StateStore()
    daemon = _BootDaemon(controller=fc, store=store)
    await restore_last_profile(daemon)  # type: ignore[arg-type]

    assert store.active_profile is None
