"""Testes do EvdevReader (HOTFIX-2)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core.evdev_reader import (
    DUALSENSE_PIDS,
    DUALSENSE_VENDOR,
    EvdevReader,
    EvdevSnapshot,
)


def test_snapshot_default_centro():
    snap = EvdevSnapshot()
    assert snap.l2_raw == 0
    assert snap.r2_raw == 0
    assert snap.lx == 128
    assert snap.ly == 128
    assert snap.buttons_pressed == frozenset()


def test_reader_sem_device_nao_disponivel():
    reader = EvdevReader(device_path=None)
    reader._device_path = None  # type: ignore[assignment]
    assert reader.is_available() is False
    assert reader.start() is False


def test_reader_start_com_device_fake(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """EvdevReader inicia thread quando device_path está presente.

    Substitui o `InputDevice` por fake que emite um evento e termina.
    """
    device_path = tmp_path / "fake_event"
    device_path.touch()

    reader = EvdevReader(device_path=device_path)
    assert reader.is_available() is True

    # Mock o import interno de evdev
    fake_ecodes = MagicMock()
    fake_ecodes.EV_ABS = 3
    fake_ecodes.EV_KEY = 1
    fake_ecodes.ABS_X = 0
    fake_ecodes.ABS_Y = 1
    fake_ecodes.ABS_Z = 2
    fake_ecodes.ABS_RX = 3
    fake_ecodes.ABS_RY = 4
    fake_ecodes.ABS_RZ = 5
    fake_ecodes.ABS_HAT0X = 16
    fake_ecodes.ABS_HAT0Y = 17
    fake_ecodes.BTN_SOUTH = 304
    fake_ecodes.BTN_EAST = 305
    fake_ecodes.BTN_MODE = 316

    def fake_event(typ: int, code: int, value: int):
        ev = MagicMock()
        ev.type = typ
        ev.code = code
        ev.value = value
        return ev

    fake_device = MagicMock()
    fake_device.name = "fake"
    fake_device.read_loop.return_value = iter(
        [
            fake_event(3, fake_ecodes.ABS_Z, 180),  # L2
            fake_event(3, fake_ecodes.ABS_RZ, 255),  # R2
            fake_event(3, fake_ecodes.ABS_X, 50),  # LX
            fake_event(1, fake_ecodes.BTN_SOUTH, 1),  # cross pressionado
        ]
    )

    import sys

    fake_mod = MagicMock()
    fake_mod.InputDevice = lambda *_a, **_kw: fake_device
    fake_mod.ecodes = fake_ecodes

    monkeypatch.setitem(sys.modules, "evdev", fake_mod)

    reader.start()
    # Esgota o read_loop iterator rápido
    import time

    time.sleep(0.1)

    snap = reader.snapshot()
    assert snap.l2_raw == 180
    assert snap.r2_raw == 255
    assert snap.lx == 50
    assert "cross" in snap.buttons_pressed

    reader.stop()


def test_keycode_name_mapping():
    # mapa estático deve ter todos os botões esperados
    mapped = set(EvdevReader.BUTTON_MAP.values())
    esperados = {
        "cross",
        "circle",
        "triangle",
        "square",
        "l1",
        "r1",
        "l2_btn",
        "r2_btn",
        "create",
        "options",
        "ps",
        "l3",
        "r3",
    }
    assert mapped == esperados


def test_dpad_direcoes_converte_para_nomes():
    reader = EvdevReader(device_path=None)
    reader._dpad_x = 0
    reader._dpad_y = -1
    reader._refresh_dpad_buttons()
    snap = reader.snapshot()
    assert "dpad_up" in snap.buttons_pressed
    assert "dpad_down" not in snap.buttons_pressed

    reader._dpad_y = 1
    reader._refresh_dpad_buttons()
    snap = reader.snapshot()
    assert "dpad_down" in snap.buttons_pressed
    assert "dpad_up" not in snap.buttons_pressed


def test_pids_contemplam_edge():
    assert 0x0CE6 in DUALSENSE_PIDS  # DualSense
    assert 0x0DF2 in DUALSENSE_PIDS  # DualSense Edge
    assert DUALSENSE_VENDOR == 0x054C


def test_reset_buttons_on_disconnect_limpa_pressed():
    """HOTFIX-3: botoes pressionados somem quando device cai."""
    reader = EvdevReader(device_path=None)
    reader._pressed = {"cross", "dpad_up", "r2_btn"}
    reader._dpad_x = 1
    reader._dpad_y = -1
    reader._snapshot = EvdevSnapshot(buttons_pressed=frozenset(reader._pressed))
    reader._reset_buttons_on_disconnect()
    snap = reader.snapshot()
    assert snap.buttons_pressed == frozenset()
    assert reader._dpad_x == 0
    assert reader._dpad_y == 0
    assert reader._pressed == set()


def test_auto_reconnect_apos_oserror(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """HOTFIX-3: se read_loop levanta OSError, reader tenta reabrir.

    1a tentativa levanta OSError (device sumiu); 2a entrega eventos.
    Após tempo suficiente, snapshot reflete evento da segunda conexao.
    """
    device_path = tmp_path / "fake_event"
    device_path.touch()

    reader = EvdevReader(device_path=device_path)

    fake_ecodes = MagicMock()
    fake_ecodes.EV_KEY = 1
    fake_ecodes.EV_ABS = 3
    fake_ecodes.ABS_Z = 2
    fake_ecodes.ABS_X = 0
    fake_ecodes.ABS_Y = 1
    fake_ecodes.ABS_RX = 3
    fake_ecodes.ABS_RY = 4
    fake_ecodes.ABS_RZ = 5
    fake_ecodes.ABS_HAT0X = 16
    fake_ecodes.ABS_HAT0Y = 17

    def fake_event(typ: int, code: int, value: int):
        ev = MagicMock()
        ev.type = typ
        ev.code = code
        ev.value = value
        return ev

    first_device = MagicMock()
    first_device.name = "first"
    first_device.read_loop.side_effect = OSError(19, "No such device")

    second_device = MagicMock()
    second_device.name = "second"
    second_device.read_loop.return_value = iter([
        fake_event(3, fake_ecodes.ABS_Z, 200),
    ])

    devices = [first_device, second_device]

    def device_factory(*_a, **_kw):
        if devices:
            return devices.pop(0)
        later = MagicMock()
        later.read_loop.return_value = iter([])
        return later

    import sys

    fake_mod = MagicMock()
    fake_mod.InputDevice = device_factory
    fake_mod.ecodes = fake_ecodes

    monkeypatch.setitem(sys.modules, "evdev", fake_mod)

    # Mock find_dualsense_evdev pra re-probe funcionar apos OSError
    from hefesto_dualsense4unix.core import evdev_reader as er_mod
    monkeypatch.setattr(er_mod, "find_dualsense_evdev", lambda: device_path)

    reader.start()
    import time

    time.sleep(0.8)

    snap = reader.snapshot()
    reader.stop()

    # Após reconnect, o evento ABS_Z=200 deve ter sido processado
    assert snap.l2_raw == 200
