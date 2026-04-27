"""Cobertura de TouchpadReader (INFRA-EVDEV-TOUCHPAD-01).

Testes sem hardware: mocks de `evdev.list_devices` e `evdev.InputDevice`.
A região é calculada por função pura `_region_from_x`; o loop é testado
injetando events sintéticos no `_handle_event`.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from hefesto_dualsense4unix.core.evdev_reader import (
    DUALSENSE_PIDS,
    DUALSENSE_VENDOR,
    TouchpadReader,
    find_dualsense_touchpad_evdev,
)


def _fake_input_device(
    name: str, vendor: int, product: int, path: str
) -> SimpleNamespace:
    """Retorna um objeto que quackeia como evdev.InputDevice."""
    dev = SimpleNamespace()
    dev.name = name
    dev.info = SimpleNamespace(vendor=vendor, product=product)
    dev.path = path
    dev.close = MagicMock()
    return dev


class TestFindDualsenseTouchpadEvdev:
    def test_encontra_device_com_touchpad_no_nome(self) -> None:
        paths = ["/dev/input/event20", "/dev/input/event21", "/dev/input/event22"]
        devices = {
            "/dev/input/event20": _fake_input_device(
                "DualSense Wireless Controller",
                DUALSENSE_VENDOR,
                next(iter(DUALSENSE_PIDS)),
                "/dev/input/event20",
            ),
            "/dev/input/event21": _fake_input_device(
                "DualSense Wireless Controller Motion Sensors",
                DUALSENSE_VENDOR,
                next(iter(DUALSENSE_PIDS)),
                "/dev/input/event21",
            ),
            "/dev/input/event22": _fake_input_device(
                "DualSense Wireless Controller Touchpad",
                DUALSENSE_VENDOR,
                next(iter(DUALSENSE_PIDS)),
                "/dev/input/event22",
            ),
        }

        with patch(
            "evdev.list_devices", return_value=paths
        ), patch(
            "evdev.InputDevice", side_effect=lambda p: devices[p]
        ):
            result = find_dualsense_touchpad_evdev()

        assert result == Path("/dev/input/event22")

    def test_ignora_gamepad_principal(self) -> None:
        """Device com vendor/product Sony mas sem 'Touchpad' no nome é ignorado."""
        paths = ["/dev/input/event20"]
        devices = {
            "/dev/input/event20": _fake_input_device(
                "DualSense Wireless Controller",
                DUALSENSE_VENDOR,
                next(iter(DUALSENSE_PIDS)),
                "/dev/input/event20",
            ),
        }

        with patch(
            "evdev.list_devices", return_value=paths
        ), patch(
            "evdev.InputDevice", side_effect=lambda p: devices[p]
        ):
            result = find_dualsense_touchpad_evdev()

        assert result is None

    def test_ignora_outro_vendor(self) -> None:
        """Outro touchpad (ex: laptop) com 'Touchpad' no nome não casa por vendor."""
        paths = ["/dev/input/event5"]
        devices = {
            "/dev/input/event5": _fake_input_device(
                "SynPS/2 Synaptics TouchPad",
                0x06CB,
                0x1234,
                "/dev/input/event5",
            ),
        }

        with patch(
            "evdev.list_devices", return_value=paths
        ), patch(
            "evdev.InputDevice", side_effect=lambda p: devices[p]
        ):
            result = find_dualsense_touchpad_evdev()

        assert result is None


class TestRegionFromX:
    """Região via função pura — limites 640/1280 sobre 1920."""

    @pytest.mark.parametrize(
        "x,expected",
        [
            (0, "touchpad_left_press"),
            (320, "touchpad_left_press"),
            (639, "touchpad_left_press"),
            (640, "touchpad_middle_press"),
            (960, "touchpad_middle_press"),
            (1279, "touchpad_middle_press"),
            (1280, "touchpad_right_press"),
            (1600, "touchpad_right_press"),
            (1919, "touchpad_right_press"),
        ],
    )
    def test_regioes(self, x: int, expected: str) -> None:
        assert TouchpadReader._region_from_x(x) == expected


class TestTouchpadReaderBehavior:
    """Testa o loop injetando events sintéticos no _handle_event."""

    def test_is_available_false_quando_device_ausente(self) -> None:
        """Sem path descoberto e sem override, is_available = False."""
        with patch(
            "hefesto_dualsense4unix.core.evdev_reader.find_dualsense_touchpad_evdev",
            return_value=None,
        ):
            reader = TouchpadReader()
        assert reader.is_available() is False
        assert reader.start() is False

    def test_btn_left_press_na_regiao_esquerda(self) -> None:
        reader = TouchpadReader(device_path=Path("/dev/input/event22"))
        ecodes = SimpleNamespace(
            EV_ABS=3,
            EV_KEY=1,
            ABS_X=0,
            BTN_LEFT=272,
        )
        # ABS_X = 300 (esquerda)
        reader._handle_event(
            SimpleNamespace(type=3, code=0, value=300), ecodes
        )
        # BTN_LEFT value=1 (press)
        reader._handle_event(
            SimpleNamespace(type=1, code=272, value=1), ecodes
        )
        assert reader.regions_pressed() == frozenset({"touchpad_left_press"})

    def test_btn_left_press_na_regiao_meio(self) -> None:
        reader = TouchpadReader(device_path=Path("/dev/input/event22"))
        ecodes = SimpleNamespace(EV_ABS=3, EV_KEY=1, ABS_X=0, BTN_LEFT=272)
        reader._handle_event(
            SimpleNamespace(type=3, code=0, value=960), ecodes
        )
        reader._handle_event(
            SimpleNamespace(type=1, code=272, value=1), ecodes
        )
        assert reader.regions_pressed() == frozenset({"touchpad_middle_press"})

    def test_btn_left_release_limpa_estado(self) -> None:
        reader = TouchpadReader(device_path=Path("/dev/input/event22"))
        ecodes = SimpleNamespace(EV_ABS=3, EV_KEY=1, ABS_X=0, BTN_LEFT=272)
        reader._handle_event(
            SimpleNamespace(type=3, code=0, value=1600), ecodes
        )
        reader._handle_event(
            SimpleNamespace(type=1, code=272, value=1), ecodes
        )
        assert reader.regions_pressed() == frozenset({"touchpad_right_press"})
        reader._handle_event(
            SimpleNamespace(type=1, code=272, value=0), ecodes
        )
        assert reader.regions_pressed() == frozenset()

    def test_abs_y_nao_afeta_regioes(self) -> None:
        """ABS_Y (coordenada vertical) não interfere na região horizontal."""
        reader = TouchpadReader(device_path=Path("/dev/input/event22"))
        ecodes = SimpleNamespace(EV_ABS=3, EV_KEY=1, ABS_X=0, BTN_LEFT=272)
        reader._handle_event(
            SimpleNamespace(type=3, code=0, value=300), ecodes
        )
        # ABS_Y com code diferente (1) — deve ser ignorado
        reader._handle_event(
            SimpleNamespace(type=3, code=1, value=500), ecodes
        )
        reader._handle_event(
            SimpleNamespace(type=1, code=272, value=1), ecodes
        )
        assert reader.regions_pressed() == frozenset({"touchpad_left_press"})

    def test_default_x_centro_quando_press_sem_abs_prévio(self) -> None:
        """Se BTN_LEFT chega antes de qualquer ABS_X, default = centro (meio)."""
        reader = TouchpadReader(device_path=Path("/dev/input/event22"))
        ecodes = SimpleNamespace(EV_ABS=3, EV_KEY=1, ABS_X=0, BTN_LEFT=272)
        reader._handle_event(
            SimpleNamespace(type=1, code=272, value=1), ecodes
        )
        assert reader.regions_pressed() == frozenset({"touchpad_middle_press"})

    def test_reset_on_disconnect_limpa_regioes(self) -> None:
        reader = TouchpadReader(device_path=Path("/dev/input/event22"))
        ecodes = SimpleNamespace(EV_ABS=3, EV_KEY=1, ABS_X=0, BTN_LEFT=272)
        reader._handle_event(
            SimpleNamespace(type=3, code=0, value=300), ecodes
        )
        reader._handle_event(
            SimpleNamespace(type=1, code=272, value=1), ecodes
        )
        assert reader.regions_pressed()
        reader._reset_on_disconnect()
        assert reader.regions_pressed() == frozenset()
