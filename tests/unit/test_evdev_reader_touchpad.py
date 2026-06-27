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


class TestFindIgnoraVirtual:
    """find_dualsense_evdev ignora o gamepad virtual (uinput) — FEAT-DSX-GAMEPAD-FLAVOR-01.

    Sem isso, o daemon poderia ler o próprio device virtual (mesmo VID/PID Sony).
    """

    def test_is_virtual_evdev_detecta_caminho_virtual(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import os

        from hefesto_dualsense4unix.core import evdev_reader as er

        monkeypatch.setattr(
            os.path, "realpath", lambda _p: "/sys/devices/virtual/input/input494"
        )
        assert er._is_virtual_evdev("/dev/input/event26") is True

    def test_is_virtual_evdev_falso_para_usb(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import os

        from hefesto_dualsense4unix.core import evdev_reader as er

        monkeypatch.setattr(
            os.path,
            "realpath",
            lambda _p: "/sys/devices/pci0000:00/0000:00:08.1/usb3/3-1/3-1:1.3/input/input12",
        )
        assert er._is_virtual_evdev("/dev/input/event12") is False

    def test_find_dualsense_evdev_pula_virtual(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Virtual vem primeiro na lista mas é pulado → retorna o real."""
        from hefesto_dualsense4unix.core import evdev_reader as er

        real = _fake_input_device(
            "Sony DualSense", DUALSENSE_VENDOR, next(iter(DUALSENSE_PIDS)),
            "/dev/input/event12",
        )
        from evdev import ecodes

        real.capabilities = MagicMock(return_value={ecodes.EV_KEY: [ecodes.BTN_SOUTH]})

        monkeypatch.setattr(
            er, "_is_virtual_evdev", lambda p: p.endswith("event26")
        )
        with patch(
            "evdev.list_devices",
            return_value=["/dev/input/event26", "/dev/input/event12"],
        ), patch("evdev.InputDevice", side_effect=lambda p: real):
            result = er.find_dualsense_evdev()
        assert result == Path("/dev/input/event12")


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
            ABS_Y=1,
            BTN_LEFT=272,
            BTN_TOUCH=330,
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
        ecodes = SimpleNamespace(EV_ABS=3, EV_KEY=1, ABS_X=0, ABS_Y=1, BTN_LEFT=272, BTN_TOUCH=330)
        reader._handle_event(
            SimpleNamespace(type=3, code=0, value=960), ecodes
        )
        reader._handle_event(
            SimpleNamespace(type=1, code=272, value=1), ecodes
        )
        assert reader.regions_pressed() == frozenset({"touchpad_middle_press"})

    def test_btn_left_release_limpa_estado(self) -> None:
        reader = TouchpadReader(device_path=Path("/dev/input/event22"))
        ecodes = SimpleNamespace(EV_ABS=3, EV_KEY=1, ABS_X=0, ABS_Y=1, BTN_LEFT=272, BTN_TOUCH=330)
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
        ecodes = SimpleNamespace(EV_ABS=3, EV_KEY=1, ABS_X=0, ABS_Y=1, BTN_LEFT=272, BTN_TOUCH=330)
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
        ecodes = SimpleNamespace(EV_ABS=3, EV_KEY=1, ABS_X=0, ABS_Y=1, BTN_LEFT=272, BTN_TOUCH=330)
        reader._handle_event(
            SimpleNamespace(type=1, code=272, value=1), ecodes
        )
        assert reader.regions_pressed() == frozenset({"touchpad_middle_press"})

    def test_reset_on_disconnect_limpa_regioes(self) -> None:
        reader = TouchpadReader(device_path=Path("/dev/input/event22"))
        ecodes = SimpleNamespace(EV_ABS=3, EV_KEY=1, ABS_X=0, ABS_Y=1, BTN_LEFT=272, BTN_TOUCH=330)
        reader._handle_event(
            SimpleNamespace(type=3, code=0, value=300), ecodes
        )
        reader._handle_event(
            SimpleNamespace(type=1, code=272, value=1), ecodes
        )
        assert reader.regions_pressed()
        reader._reset_on_disconnect()
        assert reader.regions_pressed() == frozenset()


_ECODES = SimpleNamespace(
    EV_ABS=3, EV_KEY=1, ABS_X=0, ABS_Y=1, BTN_LEFT=272, BTN_TOUCH=330
)


def _abs_x(reader: TouchpadReader, value: int) -> None:
    reader._handle_event(SimpleNamespace(type=3, code=0, value=value), _ECODES)


def _abs_y(reader: TouchpadReader, value: int) -> None:
    reader._handle_event(SimpleNamespace(type=3, code=1, value=value), _ECODES)


def _touch(reader: TouchpadReader, down: bool) -> None:
    reader._handle_event(
        SimpleNamespace(type=1, code=330, value=1 if down else 0), _ECODES
    )


class TestTouchpadReaderMotion:
    """Movimento do cursor via consume_motion (FEAT-DSX-TOUCHPAD-CURSOR-B4)."""

    def test_acumula_delta_enquanto_dedo_apoiado(self) -> None:
        reader = TouchpadReader(device_path=Path("/dev/input/event22"))
        _touch(reader, True)
        _abs_x(reader, 300)  # seeda âncora — não move
        _abs_x(reader, 350)  # +50
        _abs_y(reader, 500)  # seeda âncora Y — não move
        _abs_y(reader, 480)  # -20
        assert reader.consume_motion() == (50, -20)

    def test_consume_zera_o_acumulado(self) -> None:
        reader = TouchpadReader(device_path=Path("/dev/input/event22"))
        _touch(reader, True)
        _abs_x(reader, 100)
        _abs_x(reader, 130)
        assert reader.consume_motion() == (30, 0)
        # Segunda drenagem sem novo movimento = zero.
        assert reader.consume_motion() == (0, 0)

    def test_sem_dedo_nao_acumula(self) -> None:
        """ABS_X/Y sem BTN_TOUCH (dedo ausente) não move o cursor."""
        reader = TouchpadReader(device_path=Path("/dev/input/event22"))
        _abs_x(reader, 100)
        _abs_x(reader, 400)
        _abs_y(reader, 200)
        _abs_y(reader, 600)
        assert reader.consume_motion() == (0, 0)

    def test_reapoiar_dedo_em_outro_ponto_nao_pula(self) -> None:
        """Levantar e reapoiar o dedo zera a âncora — sem salto do cursor."""
        reader = TouchpadReader(device_path=Path("/dev/input/event22"))
        _touch(reader, True)
        _abs_x(reader, 300)
        _abs_x(reader, 400)  # +100
        assert reader.consume_motion() == (100, 0)
        _touch(reader, False)
        _touch(reader, True)  # reapoiou
        _abs_x(reader, 900)  # salto de 400→900 NÃO conta (re-seed)
        assert reader.consume_motion() == (0, 0)
        _abs_x(reader, 950)  # agora sim +50
        assert reader.consume_motion() == (50, 0)

    def test_reset_on_disconnect_zera_movimento(self) -> None:
        reader = TouchpadReader(device_path=Path("/dev/input/event22"))
        _touch(reader, True)
        _abs_x(reader, 100)
        _abs_x(reader, 200)
        reader._reset_on_disconnect()
        assert reader.consume_motion() == (0, 0)
        # Pós-reset o dedo é considerado solto: ABS_X sozinho não acumula.
        _abs_x(reader, 500)
        assert reader.consume_motion() == (0, 0)
