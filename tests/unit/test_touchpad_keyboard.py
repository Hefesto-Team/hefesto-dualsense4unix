"""Testa integração TouchpadReader ↔ dispatch_keyboard.

`dispatch_keyboard` mescla `regions_pressed()` ao frozenset de botões antes
de passar ao UinputKeyboardDevice, permitindo que as 3 regiões (left/middle/
right) emitam KEY_BACKSPACE/ENTER/DELETE via bindings default.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hefesto_dualsense4unix.core.keyboard_mappings import DEFAULT_BUTTON_BINDINGS
from hefesto_dualsense4unix.daemon.subsystems.keyboard import dispatch_keyboard


@dataclass
class _FakeReader:
    regions: frozenset[str] = field(default_factory=frozenset)

    def regions_pressed(self) -> frozenset[str]:
        return self.regions


@dataclass
class _FakeDevice:
    received: list[frozenset[str]] = field(default_factory=list)

    def dispatch(self, buttons_pressed: frozenset[str]) -> None:
        self.received.append(buttons_pressed)


@dataclass
class _FakeDaemon:
    _keyboard_device: Any = None
    _touchpad_reader: Any = None


def test_default_bindings_incluem_3_touchpad_regions() -> None:
    assert DEFAULT_BUTTON_BINDINGS["touchpad_left_press"] == ("KEY_BACKSPACE",)
    assert DEFAULT_BUTTON_BINDINGS["touchpad_middle_press"] == ("KEY_ENTER",)
    assert DEFAULT_BUTTON_BINDINGS["touchpad_right_press"] == ("KEY_DELETE",)


def test_dispatch_mescla_regions_com_buttons() -> None:
    device = _FakeDevice()
    reader = _FakeReader(regions=frozenset({"touchpad_left_press"}))
    daemon = _FakeDaemon(_keyboard_device=device, _touchpad_reader=reader)

    dispatch_keyboard(daemon, frozenset({"r1"}))

    assert device.received == [frozenset({"r1", "touchpad_left_press"})]


def test_dispatch_sem_reader_passa_so_buttons() -> None:
    device = _FakeDevice()
    daemon = _FakeDaemon(_keyboard_device=device, _touchpad_reader=None)

    dispatch_keyboard(daemon, frozenset({"l1"}))

    assert device.received == [frozenset({"l1"})]


def test_dispatch_reader_excecao_continua_com_buttons() -> None:
    device = _FakeDevice()

    class _BadReader:
        def regions_pressed(self) -> frozenset[str]:
            raise RuntimeError("disco cheio")

    daemon = _FakeDaemon(_keyboard_device=device, _touchpad_reader=_BadReader())

    # Não deve levantar. device recebe só buttons_pressed (regions zeradas).
    dispatch_keyboard(daemon, frozenset({"options"}))

    assert device.received == [frozenset({"options"})]


def test_dispatch_sem_device_noop() -> None:
    daemon = _FakeDaemon(_keyboard_device=None, _touchpad_reader=_FakeReader())
    # Não deve levantar.
    dispatch_keyboard(daemon, frozenset({"r1"}))
