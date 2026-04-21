"""Testes do AutoSwitcher."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from hefesto.profiles import loader as loader_module
from hefesto.profiles.autoswitch import AutoSwitcher
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
from tests.fixtures.fake_controller import FakeController


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


def _mk_profile(name: str, **kw) -> Profile:
    defaults = {
        "match": MatchCriteria(window_class=[f"{name}_class"]),
        "priority": 10,
        "triggers": TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Rigid", params=[0, 100]),
        ),
        "leds": LedsConfig(lightbar=(10, 20, 30)),
    }
    defaults.update(kw)
    return Profile(name=name, **defaults)


@pytest.mark.asyncio
async def test_disabled_via_env(monkeypatch: pytest.MonkeyPatch, isolated_profiles_dir: Path):
    monkeypatch.setenv("HEFESTO_NO_WINDOW_DETECT", "1")
    save_profile(_mk_profile("shooter"))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)

    reads: list[dict] = []
    switcher = AutoSwitcher(
        manager=manager, window_reader=lambda: reads.append({}) or {}
    )
    assert switcher.disabled() is True
    await switcher.run()  # deve sair imediatamente sem erro
    assert reads == []


@pytest.mark.asyncio
async def test_aplica_apos_debounce(isolated_profiles_dir: Path):
    save_profile(_mk_profile("shooter", match=MatchCriteria(window_class=["Doom"])))
    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)

    sequence = [
        {"wm_class": "Inkscape"},
        {"wm_class": "Doom"},
        {"wm_class": "Doom"},
        {"wm_class": "Doom"},
        {"wm_class": "Doom"},
        {"wm_class": "Doom"},
    ]
    idx = {"i": 0}

    def reader() -> dict:
        i = idx["i"]
        idx["i"] = min(i + 1, len(sequence) - 1)
        return sequence[i]

    switcher = AutoSwitcher(
        manager=manager,
        window_reader=reader,
        poll_interval_sec=0.02,
        debounce_sec=0.05,
    )
    switcher.start()
    await asyncio.sleep(0.25)
    switcher.stop()
    await switcher._task  # type: ignore[union-attr]

    assert switcher._current_profile == "shooter"
    # Também marcou no store via manager
    assert manager.store.active_profile == "shooter"


@pytest.mark.asyncio
async def test_nao_reaplica_mesmo_perfil(isolated_profiles_dir: Path):
    save_profile(_mk_profile("driving", match=MatchCriteria(window_class=["Forza"])))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)

    def reader() -> dict:
        return {"wm_class": "Forza"}

    switcher = AutoSwitcher(
        manager=manager,
        window_reader=reader,
        poll_interval_sec=0.02,
        debounce_sec=0.02,
    )
    switcher.start()
    await asyncio.sleep(0.2)
    switcher.stop()
    await switcher._task  # type: ignore[union-attr]

    # Manager.activate foi chamado só 1x → bump de contador igual a 1
    assert manager.store.counter("profile.activated") == 1


@pytest.mark.asyncio
async def test_flicker_alt_tab_suprimido(isolated_profiles_dir: Path):
    save_profile(_mk_profile("shooter", match=MatchCriteria(window_class=["Doom"])))
    save_profile(_mk_profile("driving", match=MatchCriteria(window_class=["Forza"])))

    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)

    alternating = [
        {"wm_class": "Doom"},
        {"wm_class": "Forza"},
        {"wm_class": "Doom"},
        {"wm_class": "Forza"},
    ]
    idx = {"i": 0}

    def reader() -> dict:
        v = alternating[idx["i"] % len(alternating)]
        idx["i"] += 1
        return v

    switcher = AutoSwitcher(
        manager=manager,
        window_reader=reader,
        poll_interval_sec=0.02,
        debounce_sec=0.2,  # debounce maior que o alt-tab
    )
    switcher.start()
    await asyncio.sleep(0.3)
    switcher.stop()
    await switcher._task  # type: ignore[union-attr]

    # Nenhum dos dois se estabilizou por 200ms -> nenhum ativo.
    assert switcher._current_profile is None


@pytest.mark.asyncio
async def test_erro_no_window_reader_nao_derruba(isolated_profiles_dir: Path):
    save_profile(_mk_profile("x"))
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc)

    def reader() -> dict:
        raise RuntimeError("xlib broke")

    switcher = AutoSwitcher(
        manager=manager,
        window_reader=reader,
        poll_interval_sec=0.02,
        debounce_sec=0.02,
    )
    switcher.start()
    await asyncio.sleep(0.1)
    switcher.stop()
    # Terminou limpo, sem exception propagada
    await switcher._task  # type: ignore[union-attr]
