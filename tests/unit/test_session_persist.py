"""Testes de persistência de sessão (FEAT-PERSIST-SESSION-01 + PERFIL-03)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from hefesto_dualsense4unix.utils.session import (
    load_last_profile,
    read_active_marker,
    resolve_boot_profile,
    save_active_marker,
    save_last_profile,
)


@pytest.fixture()
def tmp_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redireciona config_dir para tmp_path durante o teste."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session._session_path",
        lambda: tmp_path / "session.json",
    )
    return tmp_path / "session.json"


def test_save_e_load_round_trip(tmp_session: Path) -> None:
    save_last_profile("shooter")
    assert load_last_profile() == "shooter"


def test_load_retorna_none_sem_arquivo(tmp_session: Path) -> None:
    assert not tmp_session.exists()
    assert load_last_profile() is None


def test_load_retorna_none_com_json_invalido(tmp_session: Path) -> None:
    tmp_session.write_text("isto não e json{{{", encoding="utf-8")
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
    monkeypatch.setattr("hefesto_dualsense4unix.utils.session._session_path", lambda: path)
    save_last_profile("shooter")


def _mgr_and_saved() -> tuple[object, list[str], object]:
    """Manager com controller dublado + captura de save_last_profile.

    PERFIL-01: `apply()` usa a API por-uniq
    (`controller.apply_output_defaults`) — o MagicMock do controller já
    absorve a chamada; não há mais função de LED no manager para patchear.
    """
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.profiles.schema import (
        LedsConfig,
        MatchCriteria,
        Profile,
        TriggersConfig,
    )

    fake_profile = Profile(
        name="shooter",
        match=MatchCriteria(),
        triggers=TriggersConfig(),
        leds=LedsConfig(),
    )
    ctrl = MagicMock()
    store = StateStore()
    mgr = ProfileManager(controller=ctrl, store=store)
    saved: list[str] = []
    return mgr, saved, fake_profile


def test_activate_manual_chama_save_last_profile() -> None:
    """Gesto manual (default) persiste o perfil via save_last_profile."""
    mgr, saved, fake_profile = _mgr_and_saved()
    with (
        patch("hefesto_dualsense4unix.profiles.manager.load_profile", return_value=fake_profile),
        patch("hefesto_dualsense4unix.utils.session.save_last_profile", side_effect=saved.append),
    ):
        mgr.activate("shooter")  # type: ignore[attr-defined]
        mgr.activate("shooter", origin="manual")  # type: ignore[attr-defined]

    assert saved == ["shooter", "shooter"]


@pytest.mark.parametrize("origin", ["autoswitch", "system"])
def test_activate_nao_manual_nao_grava_session(origin: str) -> None:
    """PERFIL-03: autoswitch e restores de sistema NÃO reescrevem a intenção"""
    mgr, saved, fake_profile = _mgr_and_saved()
    with (
        patch("hefesto_dualsense4unix.profiles.manager.load_profile", return_value=fake_profile),
        patch("hefesto_dualsense4unix.utils.session.save_last_profile", side_effect=saved.append),
    ):
        mgr.activate("shooter", origin=origin)  # type: ignore[attr-defined]

    assert saved == []
    assert mgr.store.active_profile == "shooter"  # type: ignore[attr-defined]


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


def _perfis(*nomes: str) -> None:
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    for nome in nomes:
        save_profile(Profile(name=nome, match=MatchAny(), priority=5))


def test_resolve_boot_sem_nada_retorna_none(isolated_config: Path) -> None:
    assert resolve_boot_profile() is None


def test_resolve_boot_usa_o_session_json_que_carrega(
    isolated_config: Path, isolated_profiles: Path
) -> None:
    save_last_profile("shooter")
    assert resolve_boot_profile() is None, "o perfil não está no disco: sem escolha"
    _perfis("shooter")
    assert resolve_boot_profile() == "shooter"


def test_o_marcador_e_espelho_e_nao_vence_o_session_json(
    isolated_config: Path, isolated_profiles: Path
) -> None:
    """O marcador divergente não decide: vale o `session.json`."""
    _perfis("Navegação", "vitoria")
    save_last_profile("Navegação")
    save_active_marker("vitoria")
    assert resolve_boot_profile() == "Navegação"


def test_so_o_marcador_e_sem_escolha(
    isolated_config: Path, isolated_profiles: Path
) -> None:
    """Sem `session.json`, o marcador sozinho não vira escolha."""
    _perfis("vitoria")
    save_active_marker("vitoria")
    assert resolve_boot_profile() is None


class _BootDaemon:
    """Daemon mínimo para `restore_last_profile` (executor inline)."""

    def __init__(self, controller: object, store: object) -> None:
        self.controller = controller
        self.store = store
        self._native_mode = False
        self._keyboard_device = None

    async def _run_blocking(self, fn: object, *args: object) -> object:
        return fn(*args)  # type: ignore[operator]


@pytest.mark.asyncio
async def test_aceite_boot_restaura_escolha_manual_e_nao_o_autoswitch(
    isolated_config: Path, isolated_profiles: Path
) -> None:
    """Aceite 1 do PERFIL-03, fim a fim com manager e sessão REAIS:"""
    from hefesto_dualsense4unix.daemon.connection import restore_last_profile
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
    from hefesto_dualsense4unix.testing import FakeController

    for name in ("vitoria", "navegacao", "steamjogo"):
        save_profile(Profile(name=name, match=MatchAny(), priority=5))

    fc = FakeController()
    fc.connect()
    store = StateStore()
    mgr = ProfileManager(controller=fc, store=store)

    mgr.activate("vitoria")
    save_active_marker("vitoria")
    mgr.activate("navegacao", origin="autoswitch")
    mgr.activate("steamjogo", origin="autoswitch")
    mgr.activate("navegacao", origin="autoswitch")

    assert load_last_profile() == "vitoria"
    assert read_active_marker() == "vitoria"
    assert store.active_profile == "navegacao"

    store2 = StateStore()
    daemon = _BootDaemon(controller=fc, store=store2)
    await restore_last_profile(daemon)  # type: ignore[arg-type]
    assert store2.active_profile == "vitoria"
    assert load_last_profile() == "vitoria"


@pytest.mark.asyncio
async def test_boot_restaura_a_escolha_com_regra_de_janela(
    isolated_config: Path, isolated_profiles: Path
) -> None:
    """A escolha dela volta no boot, com regra de janela ou sem."""
    from hefesto_dualsense4unix.daemon.connection import restore_last_profile
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile
    from hefesto_dualsense4unix.testing import FakeController

    save_profile(
        Profile(
            name="FPS",
            match=MatchCriteria(window_title_regex=".*(Doom|Control).*"),
            priority=60,
        )
    )
    save_last_profile("FPS")

    fc = FakeController()
    fc.connect()
    store = StateStore()
    daemon = _BootDaemon(controller=fc, store=store)
    await restore_last_profile(daemon)  # type: ignore[arg-type]
    assert store.active_profile == "FPS"


@pytest.mark.asyncio
async def test_boot_restaura_perfil_match_any_normalmente(
    isolated_config: Path, isolated_profiles: Path
) -> None:
    """Par da régua de cima: o perfil "sempre" (MatchAny) escolhido também volta."""
    from hefesto_dualsense4unix.daemon.connection import restore_last_profile
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
    from hefesto_dualsense4unix.testing import FakeController

    save_profile(Profile(name="meu_perfil", match=MatchAny(), priority=0))
    save_last_profile("meu_perfil")

    fc = FakeController()
    fc.connect()
    store = StateStore()
    daemon = _BootDaemon(controller=fc, store=store)
    await restore_last_profile(daemon)  # type: ignore[arg-type]
    assert store.active_profile == "meu_perfil"


@pytest.mark.asyncio
async def test_o_marcador_divergente_nao_desvia_o_boot(
    isolated_config: Path, isolated_profiles: Path
) -> None:
    """O marcador diz outro perfil, ou um que sumiu: o boot abre no `session.json`."""
    from hefesto_dualsense4unix.daemon.connection import restore_last_profile
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.testing import FakeController

    _perfis("vitoria", "navegacao")
    for marcador in ("vitoria", "sumiu"):
        save_last_profile("navegacao")
        save_active_marker(marcador)
        fc = FakeController()
        fc.connect()
        store = StateStore()
        await restore_last_profile(_BootDaemon(controller=fc, store=store))  # type: ignore[arg-type]
        assert store.active_profile == "navegacao", marcador


@pytest.mark.asyncio
async def test_boot_marker_e_session_orfaos_nao_explode(
    isolated_config: Path, isolated_profiles: Path
) -> None:
    """Marker E session apontando perfis inexistentes: o boot segue sem"""
    from hefesto_dualsense4unix.daemon.connection import restore_last_profile
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.testing import FakeController

    save_last_profile("sumiu_tambem")
    save_active_marker("sumiu")

    fc = FakeController()
    fc.connect()
    store = StateStore()
    daemon = _BootDaemon(controller=fc, store=store)
    await restore_last_profile(daemon)  # type: ignore[arg-type]

    assert store.active_profile is None


@pytest.mark.asyncio
async def test_aceite_hotkey_cycle_grava_session_json(
    isolated_config: Path, isolated_profiles: Path
) -> None:
    """Aceite 2 do PERFIL-03 (metade que GRAVA): o ciclo por hotkey (PS+dpad)"""
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
        build_profile_cycle_callback,
    )
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
    from hefesto_dualsense4unix.testing import FakeController

    for name in ("alfa", "beta"):
        save_profile(Profile(name=name, match=MatchAny(), priority=5))

    class _CycleDaemon:
        def __init__(self) -> None:
            self.controller = FakeController()
            self.controller.connect()
            self.store = StateStore()
            self.store.set_active_profile("alfa")
            self._keyboard_device = None

        async def _run_blocking(self, fn: object, *args: object) -> object:
            return fn(*args)  # type: ignore[operator]

    daemon = _CycleDaemon()
    await build_profile_cycle_callback(daemon, +1)()  # type: ignore[arg-type]

    assert daemon.store.active_profile == "beta"
    assert load_last_profile() == "beta"
    assert read_active_marker() == "beta"
