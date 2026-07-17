"""Testes de persistência de sessão (FEAT-PERSIST-SESSION-01 + PERFIL-03).

Cobre:
  - save_last_profile / load_last_profile round-trip.
  - load retorna None quando arquivo ausente.
  - load retorna None quando JSON inválido.
  - ProfileManager.activate() persiste o perfil via save_last_profile SÓ no
    gesto manual (PERFIL-03): origin="autoswitch"/"system" não gravam.
  - resolve_boot_profile: seed de migração do marker `active_profile.txt`
    quando ele diverge do session.json herdado (o autoswitch clobberava).
  - Aceite 1 do PERFIL-03 fim a fim: escolha manual sobrevive a N ativações
    do autoswitch e o restore de boot re-ativa a escolha MANUAL sem regravar.
"""
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redireciona config_dir para tmp_path durante o teste."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session._session_path",
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
    # Diretório pai não existe — save deve falhar silenciosamente.
    save_last_profile("shooter")
    # Sem exception: teste passou.


# ---------------------------------------------------------------------------
# Integração com ProfileManager
# ---------------------------------------------------------------------------


def _mgr_and_saved() -> tuple[object, list[str], object]:
    """Manager com controller dublado + captura de save_last_profile.

    PERFIL-01: `apply()` migrou de `apply_led_settings` para a API por-uniq
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
    """Gesto manual (default) persiste o perfil via save_last_profile.

    PERFIL-03: era `test_activate_chama_save_last_profile`, que asseverava
    gravação em TODA ativação — quebra prevista pelo sprint doc. Agora só o
    origin="manual" (o default, deliberado) grava a intenção da usuária.
    """
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
    """PERFIL-03: autoswitch e restores de sistema NÃO reescrevem a intenção
    manual — era o bug provado (session.json dizia "Navegação" porque o
    autoswitch gravava a cada troca de janela). O perfil ainda é aplicado e
    marcado como ativo no store."""
    mgr, saved, fake_profile = _mgr_and_saved()
    with (
        patch("hefesto_dualsense4unix.profiles.manager.load_profile", return_value=fake_profile),
        patch("hefesto_dualsense4unix.utils.session.save_last_profile", side_effect=saved.append),
    ):
        mgr.activate("shooter", origin=origin)  # type: ignore[attr-defined]

    assert saved == []
    assert mgr.store.active_profile == "shooter"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# PERFIL-03 — resolve_boot_profile (seed de migração do marker manual)
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isola config_dir (session.json + active_profile.txt) em tmp_path.

    Dois patches porque o módulo usa os dois caminhos: `_session_path` chama o
    `config_dir` importado no topo de utils.session; as funções do marker
    fazem import lazy de `xdg_paths.config_dir` (ponto de monkeypatch
    documentado no próprio módulo).
    """
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


def test_resolve_boot_sem_nada_retorna_none(isolated_config: Path) -> None:
    assert resolve_boot_profile() is None


def test_resolve_boot_sem_marker_usa_session(isolated_config: Path) -> None:
    """Sem escolha manual registrada (marker ausente), o restore não regride:
    cai no comportamento histórico (session.json) — risco 4 do sprint doc."""
    save_last_profile("shooter")
    assert resolve_boot_profile() == "shooter"


def test_resolve_boot_seed_marker_vence_session_divergente(
    isolated_config: Path,
) -> None:
    """Aceite 3 do PERFIL-03: session.json='Navegação' (clobber herdado do
    autoswitch) + active_profile.txt='vitoria' (intenção manual) → o 1º
    restore pós-update prefere o marker."""
    save_last_profile("Navegação")
    save_active_marker("vitoria")
    assert resolve_boot_profile() == "vitoria"


def test_resolve_boot_convergidos_usa_session(isolated_config: Path) -> None:
    """Pós-fix os dois arquivos convergem a cada gesto manual — o seed vira
    no-op e o canônico (session.json) responde."""
    save_last_profile("vitoria")
    save_active_marker("vitoria")
    assert resolve_boot_profile() == "vitoria"


def test_resolve_boot_so_marker_usa_marker(isolated_config: Path) -> None:
    """Marker manual presente com session.json ausente (ex.: apagado) ainda
    restaura a intenção manual."""
    save_active_marker("vitoria")
    assert resolve_boot_profile() == "vitoria"


# ---------------------------------------------------------------------------
# PERFIL-03 — aceite 1 fim a fim: manual sobrevive ao autoswitch + boot
# ---------------------------------------------------------------------------


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


@pytest.mark.asyncio
async def test_aceite_boot_restaura_escolha_manual_e_nao_o_autoswitch(
    isolated_config: Path, isolated_profiles: Path
) -> None:
    """Aceite 1 do PERFIL-03, fim a fim com manager e sessão REAIS:

    ativar 'vitoria' manualmente → 3 ativações do autoswitch (outros perfis)
    → session.json ainda aponta 'vitoria' → "restart" do daemon
    (`restore_last_profile`) re-ativa 'vitoria' com origin="system" (que NÃO
    regrava a sessão)."""
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

    # Gesto manual (paridade do marker é feita pelos call sites — IPC/hotkey).
    mgr.activate("vitoria")
    save_active_marker("vitoria")
    # 3 trocas de janela: o autoswitch ativa outros perfis...
    mgr.activate("navegacao", origin="autoswitch")
    mgr.activate("steamjogo", origin="autoswitch")
    mgr.activate("navegacao", origin="autoswitch")

    # ...e a intenção manual continua intacta nos DOIS arquivos.
    assert load_last_profile() == "vitoria"
    assert read_active_marker() == "vitoria"
    assert store.active_profile == "navegacao"  # o ativo em memória segue a janela

    # "Restart": um daemon novo restaura a escolha MANUAL dela...
    store2 = StateStore()
    daemon = _BootDaemon(controller=fc, store=store2)
    await restore_last_profile(daemon)  # type: ignore[arg-type]
    assert store2.active_profile == "vitoria"
    # ...sem regravar a sessão (origin="system" não é gesto novo).
    assert load_last_profile() == "vitoria"


@pytest.mark.asyncio
async def test_aceite_boot_seed_pos_update_ativa_a_intencao_manual(
    isolated_config: Path, isolated_profiles: Path
) -> None:
    """Aceite 3 fim a fim: herança pré-fix (session.json='navegacao' gravado
    pelo autoswitch antigo, marker='vitoria' manual) → o 1º boot pós-update
    ativa 'vitoria', não 'navegacao'."""
    from hefesto_dualsense4unix.daemon.connection import restore_last_profile
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
    from hefesto_dualsense4unix.testing import FakeController

    for name in ("vitoria", "navegacao"):
        save_profile(Profile(name=name, match=MatchAny(), priority=5))

    save_last_profile("navegacao")  # clobber herdado da versão antiga
    save_active_marker("vitoria")  # a última escolha MANUAL real

    fc = FakeController()
    fc.connect()
    store = StateStore()
    daemon = _BootDaemon(controller=fc, store=store)
    await restore_last_profile(daemon)  # type: ignore[arg-type]

    assert store.active_profile == "vitoria"


@pytest.mark.asyncio
async def test_boot_marker_orfao_cai_no_session_json(
    isolated_config: Path, isolated_profiles: Path
) -> None:
    """Fix do review (2026-07-16, MED): o marker vence na divergência, mas
    pode apontar perfil renomeado/apagado (sem novo gesto manual, a
    divergência nunca se cura). O restore NÃO pode ficar sem perfil: cai no
    session.json carregável, com o log `last_profile_seed_marker_invalido`."""
    import structlog

    from hefesto_dualsense4unix.daemon.connection import restore_last_profile
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
    from hefesto_dualsense4unix.testing import FakeController

    save_profile(Profile(name="navegacao", match=MatchAny(), priority=5))
    save_last_profile("navegacao")
    save_active_marker("vitoria")  # órfão: o perfil foi renomeado/apagado

    fc = FakeController()
    fc.connect()
    store = StateStore()
    daemon = _BootDaemon(controller=fc, store=store)
    with structlog.testing.capture_logs() as captured:
        await restore_last_profile(daemon)  # type: ignore[arg-type]

    assert store.active_profile == "navegacao"
    eventos = [rec.get("event") for rec in captured]
    assert "last_profile_seed_marker_invalido" in eventos


@pytest.mark.asyncio
async def test_boot_marker_e_session_orfaos_nao_explode(
    isolated_config: Path, isolated_profiles: Path
) -> None:
    """Marker E session apontando perfis inexistentes: o boot segue sem
    perfil (dois warnings), sem propagar exceção."""
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
    """Aceite 2 do PERFIL-03 (metade que GRAVA): o ciclo por hotkey (PS+dpad)
    é botão físico = gesto MANUAL — persiste session.json E o marker em
    paridade, fim a fim com manager e sessão reais."""
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

    # Saiu de 'alfa' para o outro perfil e persistiu a intenção manual.
    assert daemon.store.active_profile == "beta"
    assert load_last_profile() == "beta"
    assert read_active_marker() == "beta"
