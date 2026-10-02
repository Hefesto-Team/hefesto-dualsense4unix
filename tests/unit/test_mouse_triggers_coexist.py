"""Coexistência entre emulação de mouse e triggers manuais (BUG-MOUSE-TRIGGERS-01)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core.controller import TriggerEffect
from hefesto_dualsense4unix.core.trigger_effects import build_from_name
from hefesto_dualsense4unix.integrations.uinput_mouse import UinputMouseDevice
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)
from hefesto_dualsense4unix.testing import FakeController, FakeControllerCommand


def _fake_uinput_module() -> MagicMock:
    """Módulo uinput fake com constantes mínimas para os emits."""
    mod = MagicMock()
    for name in (
        "REL_X", "REL_Y", "REL_WHEEL", "REL_HWHEEL",
        "BTN_LEFT", "BTN_RIGHT", "BTN_MIDDLE",
        "KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT",
    ):
        setattr(mod, name, (1, hash(name) & 0xFFFF))
    return mod


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


def test_mouse_dispatch_nao_chama_set_trigger_no_controller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UinputMouseDevice.dispatch N vezes: zero side-effects em triggers."""
    fake_mod = _fake_uinput_module()
    fake_device = MagicMock()
    fake_mod.Device.return_value = fake_device
    monkeypatch.setitem(sys.modules, "uinput", fake_mod)

    fc = FakeController()
    fc.connect()

    effect: TriggerEffect = build_from_name("Galloping", [0, 9, 7, 7, 10])
    fc.set_trigger("right", effect)

    mouse = UinputMouseDevice()
    assert mouse.start() is True

    for tick in range(120):
        mouse.dispatch(
            lx=200,
            ly=60,
            rx=128,
            ry=128,
            l2=100,
            r2=200,
            buttons=frozenset({"cross", "dpad_up"}),
            now=0.1 * tick,
        )

    trigger_cmds = [
        c for c in fc.commands
        if isinstance(c, FakeControllerCommand) and c.kind == "set_trigger"
    ]
    assert len(trigger_cmds) == 1, (
        f"UinputMouseDevice.dispatch chamou set_trigger como side-effect "
        f"(hipótese 2 confirmada). Comandos: {trigger_cmds!r}"
    )
    for kind in ("set_led", "set_rumble"):
        extras = [c for c in fc.commands if c.kind == kind]
        assert not extras, f"{kind} foi chamado pelo dispatch: {extras!r}"


def _mk_profile_with_trigger(name: str, wm_class: list[str] | None = None) -> Profile:
    return Profile(
        name=name,
        match=MatchCriteria(window_class=wm_class or [f"{name}_class"]),
        priority=10,
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Rigid", params=[0, 100]),
        ),
        leds=LedsConfig(lightbar=(10, 20, 30)),
    )


def _mk_fallback_off() -> Profile:
    return Profile(
        name="fallback",
        match=MatchAny(),
        priority=-1000,
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Off"),
        ),
        leds=LedsConfig(lightbar=(40, 40, 40)),
    )


