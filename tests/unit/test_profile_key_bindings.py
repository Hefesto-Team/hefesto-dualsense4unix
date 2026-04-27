"""Testes de FEAT-KEYBOARD-PERSISTENCE-01.

Cobre:
- Validator de `Profile.key_bindings` (regex + evdev.ecodes lookup).
- Helper puro `_to_key_bindings` (None/vazio/override).
- `ProfileManager.apply_keyboard` (armadilha A-06 — teste dedicado do mapper).
- Integração `activate()` com FakeController + mock de UinputKeyboardDevice
  confirmando que `set_bindings` é chamado com o mapping resolvido.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core.keyboard_mappings import DEFAULT_BUTTON_BINDINGS
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager, _to_key_bindings
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
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


# ----------------------------------------------------------------------
# Helper _to_key_bindings
# ----------------------------------------------------------------------


def test_to_key_bindings_none_usa_defaults() -> None:
    profile = _mk_profile("default_kbd", key_bindings=None)
    resolved = _to_key_bindings(profile)
    assert resolved == dict(DEFAULT_BUTTON_BINDINGS)
    # Valores são tuplas (KeyBinding) mesmo vindo dos defaults.
    for value in resolved.values():
        assert isinstance(value, tuple)


def test_to_key_bindings_vazio_desativa() -> None:
    profile = _mk_profile("silent_kbd", key_bindings={})
    resolved = _to_key_bindings(profile)
    assert resolved == {}


def test_to_key_bindings_override_parcial() -> None:
    profile = _mk_profile(
        "c_override",
        key_bindings={"triangle": ["KEY_C"], "r1": ["KEY_LEFTCTRL", "KEY_Z"]},
    )
    resolved = _to_key_bindings(profile)
    # Override é explícito — não mescla com DEFAULT_BUTTON_BINDINGS.
    assert resolved == {
        "triangle": ("KEY_C",),
        "r1": ("KEY_LEFTCTRL", "KEY_Z"),
    }
    for value in resolved.values():
        assert isinstance(value, tuple)


# ----------------------------------------------------------------------
# Validator do schema
# ----------------------------------------------------------------------


def test_validator_rejeita_key_inexistente() -> None:
    """KEY_XYZINEXISTENTE não está em evdev.ecodes — deve levantar."""
    with pytest.raises(ValueError, match="KEY_XYZINEXISTENTE"):
        _mk_profile("bad", key_bindings={"triangle": ["KEY_XYZINEXISTENTE"]})


def test_validator_rejeita_token_mal_formado() -> None:
    """Token que não casa '^(KEY_[A-Z0-9_]+|__[A-Z_]+__)$' deve levantar."""
    with pytest.raises(ValueError, match="não casa padrão"):
        _mk_profile("bad", key_bindings={"triangle": ["key_c"]})  # lowercase


def test_validator_aceita_token_virtual() -> None:
    """Tokens __*__ são reservados para OSK (59.3) — aceitos sem ecodes lookup."""
    prof = _mk_profile("osk", key_bindings={"l3": ["__OPEN_OSK__"]})
    assert prof.key_bindings == {"l3": ["__OPEN_OSK__"]}


# ----------------------------------------------------------------------
# A-06: mapper dedicado — ProfileManager.apply_keyboard propaga
# ----------------------------------------------------------------------


def test_apply_propaga_key_bindings(isolated_profiles_dir: Path) -> None:
    """A-06: `activate()` chama set_bindings com mapping resolvido.

    Sem essa propagação o perfil salva o override mas o hardware virtual
    continua com os bindings anteriores — caso clássico da armadilha A-06.
    """
    save_profile(_mk_profile("triangle_c", key_bindings={"triangle": ["KEY_C"]}))
    fc = FakeController()
    fc.connect()
    kbd_mock = MagicMock()
    store = StateStore()
    manager = ProfileManager(
        controller=fc,
        store=store,
        keyboard_device=kbd_mock,
    )

    manager.activate("triangle_c")

    # set_bindings foi chamado exatamente 1x com o mapping resolvido.
    kbd_mock.set_bindings.assert_called_once()
    arg = kbd_mock.set_bindings.call_args[0][0]
    assert arg == {"triangle": ("KEY_C",)}


def test_apply_keyboard_none_nao_quebra(isolated_profiles_dir: Path) -> None:
    """Sem keyboard_device (CLI/teste), activate() segue sem propagar."""
    save_profile(_mk_profile("no_kbd"))
    fc = FakeController()
    fc.connect()
    manager = ProfileManager(controller=fc, store=StateStore(), keyboard_device=None)
    # Não deve levantar.
    manager.activate("no_kbd")


def test_apply_keyboard_none_bindings_usa_defaults(
    isolated_profiles_dir: Path,
) -> None:
    """Perfil com key_bindings=None propaga DEFAULT_BUTTON_BINDINGS."""
    save_profile(_mk_profile("default_bind", key_bindings=None))
    fc = FakeController()
    fc.connect()
    kbd_mock = MagicMock()
    manager = ProfileManager(
        controller=fc,
        store=StateStore(),
        keyboard_device=kbd_mock,
    )

    manager.activate("default_bind")

    arg = kbd_mock.set_bindings.call_args[0][0]
    assert arg == dict(DEFAULT_BUTTON_BINDINGS)
