"""CLUSTER-IPC-STATE-PROFILE-01 Bug C — autoswitch respeita lock manual.

Garante que:
  - StateStore expõe API isolada `mark_manual_profile_lock` /
    `manual_profile_lock_active`.
  - AutoSwitcher._activate respeita o lock e faz no-op silencioso.
  - Lock expira sozinho (sem reset explícito).
  - Lock é renovado a cada profile.switch (escolha mais recente vence).
  - Constante MANUAL_PROFILE_LOCK_SEC vale 30s (canônico fixo).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon.state_store import (
    MANUAL_PROFILE_LOCK_SEC,
    StateStore,
)
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)
from hefesto_dualsense4unix.testing import FakeController


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return target


def _mk_profile(name: str, **kw: object) -> Profile:
    defaults: dict[str, object] = {
        "match": MatchCriteria(window_class=[f"{name}_class"]),
        "priority": 10,
        "triggers": TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Off"),
        ),
        "leds": LedsConfig(lightbar=(10, 20, 30)),
    }
    defaults.update(kw)
    return Profile(name=name, **defaults)  # type: ignore[arg-type]


# --- Store API isolada -----------------------------------------------------


def test_store_lock_inicia_inativo() -> None:
    """Store fresca não tem lock manual ativo."""
    store = StateStore()
    assert store.manual_profile_lock_active(now=100.0) is False


def test_store_lock_ativo_apos_mark() -> None:
    """`mark_manual_profile_lock` arma o lock até o instante informado."""
    store = StateStore()
    store.mark_manual_profile_lock(until=150.0)
    assert store.manual_profile_lock_active(now=100.0) is True
    assert store.manual_profile_lock_active(now=149.99) is True
    # Lock expira no instante exato (now == until).
    assert store.manual_profile_lock_active(now=150.0) is False
    assert store.manual_profile_lock_active(now=200.0) is False


def test_store_lock_renovado_escolha_mais_recente_vence() -> None:
    """Renovar com `until` menor encurta o lock; com maior estende."""
    store = StateStore()
    store.mark_manual_profile_lock(until=200.0)
    assert store.manual_profile_lock_active(now=150.0) is True

    # Renovação para um valor menor (ex: profile.switch chamado de novo
    # com janela ainda menor — improvável mas possível). Armazena e respeita.
    store.mark_manual_profile_lock(until=160.0)
    assert store.manual_profile_lock_active(now=150.0) is True
    assert store.manual_profile_lock_active(now=170.0) is False


def test_store_lock_constante_canonica_30s() -> None:
    """MANUAL_PROFILE_LOCK_SEC é o canônico fixo desta sprint."""
    assert MANUAL_PROFILE_LOCK_SEC == 30.0


# --- AutoSwitcher integra com lock -----------------------------------------


def test_activate_suprimido_quando_lock_ativo(
    isolated_profiles_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_activate` faz no-op se store.manual_profile_lock_active retornar True."""
    save_profile(_mk_profile("shooter"))
    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))

    fc = FakeController()
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    activate_calls: list[str] = []
    original_activate = manager.activate

    def spy_activate(name: str) -> object:
        activate_calls.append(name)
        return original_activate(name)

    monkeypatch.setattr(manager, "activate", spy_activate)

    # Arma lock no instante 0 até instante 100; relógio fake retorna 50.
    store.mark_manual_profile_lock(until=100.0)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.profiles.autoswitch.time.monotonic",
        lambda: 50.0,
    )

    switcher = AutoSwitcher(
        manager=manager, window_reader=lambda: {}, store=store
    )
    switcher._activate("shooter", {"wm_class": "Doom"})

    # Manager.activate NÃO foi chamado: lock suprimiu.
    assert activate_calls == []
    assert switcher._current_profile is None


def test_activate_volta_a_operar_apos_lock_expirar(
    isolated_profiles_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Após lock expirar, autoswitch retoma normalmente."""
    save_profile(_mk_profile("shooter"))
    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))

    fc = FakeController()
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)

    # Lock até instante 100; relógio fake já em 200 → expirou.
    store.mark_manual_profile_lock(until=100.0)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.profiles.autoswitch.time.monotonic",
        lambda: 200.0,
    )

    switcher = AutoSwitcher(
        manager=manager, window_reader=lambda: {}, store=store
    )
    switcher._activate("shooter", {"wm_class": "Doom"})

    assert switcher._current_profile == "shooter"


def test_activate_sem_store_nao_quebra(
    isolated_profiles_dir: Path,
) -> None:
    """AutoSwitcher sem store (testes legados) ignora lock graciosamente."""
    save_profile(_mk_profile("shooter"))
    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    switcher = AutoSwitcher(
        manager=manager, window_reader=lambda: {}, store=None
    )
    switcher._activate("shooter", {"wm_class": "Doom"})
    assert switcher._current_profile == "shooter"


def test_activate_lock_independente_de_manual_trigger_active(
    isolated_profiles_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lock manual de profile e manual_trigger_active são checks independentes.

    Ambos suprimem `_activate`, mas com logs distintos. Garantimos que cada
    um sozinho suprime; a ordem de check não interfere no resultado.
    """
    save_profile(_mk_profile("shooter"))
    fc = FakeController()
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)

    activate_calls: list[str] = []
    monkeypatch.setattr(
        manager, "activate", lambda name: activate_calls.append(name) or MagicMock()
    )

    # Apenas trigger active → suprime
    store.mark_manual_trigger_active()
    switcher = AutoSwitcher(
        manager=manager, window_reader=lambda: {}, store=store
    )
    switcher._activate("shooter", {"wm_class": "Doom"})
    assert activate_calls == []

    # Limpa trigger, arma profile lock → suprime
    store.clear_manual_trigger_active()
    store.mark_manual_profile_lock(until=999.0)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.profiles.autoswitch.time.monotonic",
        lambda: 0.0,
    )
    switcher2 = AutoSwitcher(
        manager=manager, window_reader=lambda: {}, store=store
    )
    switcher2._activate("shooter", {"wm_class": "Doom"})
    assert activate_calls == []
