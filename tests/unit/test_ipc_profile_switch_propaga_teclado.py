"""Teste IPC: `profile.switch` propaga key_bindings ao device virtual.

Cobre o caminho end-to-end: GUI (ou CLI) manda `profile.switch` via IPC; o
IpcServer chama `profile_manager.activate(name)`; o manager (com keyboard_device
injetado) chama `device.set_bindings(resolved)` — completando a armadilha A-06
pelo caminho do usuário real.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hefesto.daemon.ipc_server import IpcServer
from hefesto.daemon.state_store import StateStore
from hefesto.profiles import loader as loader_module
from hefesto.profiles.loader import save_profile
from hefesto.profiles.manager import ProfileManager
from hefesto.profiles.schema import (
    LedsConfig,
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


def _mk_profile(name: str, **kw) -> Profile:
    defaults: dict[str, object] = {
        "match": MatchCriteria(window_class=[f"{name}_class"]),
        "priority": 10,
        "triggers": TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Off"),
        ),
        "leds": LedsConfig(lightbar=(0, 0, 0), player_leds=[False] * 5),
    }
    defaults.update(kw)
    return Profile(name=name, **defaults)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_profile_switch_propaga_keyboard_bindings(
    isolated_profiles_dir: Path,
) -> None:
    save_profile(
        _mk_profile("overwatch_kbd", key_bindings={"triangle": ["KEY_V"]})
    )
    fc = FakeController()
    fc.connect()
    kbd_mock = MagicMock()
    store = StateStore()
    manager = ProfileManager(
        controller=fc, store=store, keyboard_device=kbd_mock
    )
    server = IpcServer(controller=fc, store=store, profile_manager=manager)

    # Invoca o handler diretamente (evita precisar de server socket real).
    result = await server._handle_profile_switch({"name": "overwatch_kbd"})

    assert result == {"active_profile": "overwatch_kbd"}
    kbd_mock.set_bindings.assert_called_once()
    arg = kbd_mock.set_bindings.call_args[0][0]
    assert arg == {"triangle": ("KEY_V",)}
