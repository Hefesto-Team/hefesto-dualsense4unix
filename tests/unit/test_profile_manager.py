"""Testes do ProfileManager."""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto.daemon.state_store import StateStore
from hefesto.profiles import loader as loader_module
from hefesto.profiles.loader import save_profile
from hefesto.profiles.manager import ProfileManager
from hefesto.profiles.schema import (
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)
from hefesto.testing import FakeController


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


def _mk_profile(name: str, priority: int = 10, **kw) -> Profile:
    defaults = {
        "match": MatchCriteria(window_class=[f"{name}_class"]),
        "priority": priority,
        "triggers": TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Rigid", params=[5, 200]),
        ),
        "leds": LedsConfig(lightbar=(10, 20, 30), player_leds=[True] * 5),
    }
    defaults.update(kw)
    return Profile(name=name, **defaults)


def test_activate_aplica_trigger_e_led(isolated_profiles_dir: Path):
    save_profile(_mk_profile("shooter"))
    fc = FakeController()
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)

    applied = manager.activate("shooter")
    assert applied.name == "shooter"
    assert store.active_profile == "shooter"

    triggers = [c for c in fc.commands if c.kind == "set_trigger"]
    assert len(triggers) == 2
    # Right = Rigid (RIGID_B = 5 bits), forces[1] = 200 (force cru)
    right_call = next(c for c in triggers if c.payload[0] == "right")
    assert right_call.payload[1].forces == (5, 200, 0, 0, 0, 0, 0)

    leds = [c for c in fc.commands if c.kind == "set_led"]
    assert len(leds) == 1
    assert leds[0].payload == (10, 20, 30)


def test_list_profiles_ordenado(isolated_profiles_dir: Path):
    save_profile(_mk_profile("driving"))
    save_profile(_mk_profile("shooter"))
    save_profile(_mk_profile("bow"))
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    names = [p.name for p in manager.list_profiles()]
    assert names == ["bow", "driving", "shooter"]


def test_select_for_window_retorna_maior_prioridade(isolated_profiles_dir: Path):
    save_profile(
        _mk_profile("driving", priority=10, match=MatchCriteria(window_class=["Forza"]))
    )
    save_profile(
        _mk_profile(
            "shooter",
            priority=20,
            match=MatchCriteria(window_class=["Forza"]),
        )
    )
    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    picked = manager.select_for_window({"wm_class": "Forza"})
    assert picked is not None
    assert picked.name == "shooter"  # maior priority


def test_select_for_window_fallback(isolated_profiles_dir: Path):
    save_profile(
        _mk_profile("shooter", match=MatchCriteria(window_class=["DoomEternal"]))
    )
    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    picked = manager.select_for_window({"wm_class": "Inkscape"})
    assert picked is not None
    assert picked.name == "fallback"


def test_select_for_window_sem_match_sem_fallback(isolated_profiles_dir: Path):
    save_profile(_mk_profile("shooter", match=MatchCriteria(window_class=["X"])))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    picked = manager.select_for_window({"wm_class": "Nada"})
    assert picked is None


def test_delete_do_ativo_reseta_active_profile(isolated_profiles_dir: Path):
    save_profile(_mk_profile("tmp"))
    fc = FakeController()
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    manager.activate("tmp")
    assert store.active_profile == "tmp"
    manager.delete("tmp")
    assert store.active_profile is None


def test_create_persiste_no_disco(isolated_profiles_dir: Path):
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    profile = _mk_profile("new_one")
    manager.create(profile)
    assert (isolated_profiles_dir / "new_one.json").exists()


def test_apply_propaga_brightness(isolated_profiles_dir: Path):
    """FEAT-LED-BRIGHTNESS-02: brightness do perfil chega ao hardware via FakeController.

    Cria perfil com lightbar_brightness=0.25 (25%) e lightbar=(200, 100, 50).
    Apos apply(), verifica que o set_led recebeu valores escalados a 25%.
    """
    profile = _mk_profile(
        "dim_test",
        leds=LedsConfig(lightbar=(200, 100, 50), lightbar_brightness=0.25),
    )
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    manager.apply(profile)

    assert fc.last_led is not None, "set_led não foi chamado"
    # RGB escalado: 200*0.25=50, 100*0.25=25, 50*0.25=12
    r, g, b = fc.last_led.color
    assert r == 50, f"canal R esperado 50, recebeu {r}"
    assert g == 25, f"canal G esperado 25, recebeu {g}"
    assert b == 12, f"canal B esperado 12, recebeu {b}"


def test_apply_brightness_maximo_nao_escala(isolated_profiles_dir: Path):
    """Brightness 1.0 (padrao) não altera os valores RGB."""
    profile = _mk_profile(
        "full_test",
        leds=LedsConfig(lightbar=(200, 100, 50), lightbar_brightness=1.0),
    )
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)
    manager.apply(profile)

    assert fc.last_led is not None
    assert fc.last_led.color == (200, 100, 50)
