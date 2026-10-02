"""Testes do EvdevReader (HOTFIX-2)."""
from __future__ import annotations

from typing import Any
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


def test_refresh_device_relocaliza_apos_boot_offline(monkeypatch: pytest.MonkeyPatch):
    """refresh_device() re-procura o evdev quando o path nasceu None (hotplug"""
    from pathlib import Path

    reader = EvdevReader(device_path=None)
    reader._device_path = None  # type: ignore[assignment]
    assert reader.is_available() is False
    monkeypatch.setattr(reader, "_find_device", lambda: Path("/dev/input/event2"))
    assert reader.refresh_device() is True
    assert reader.is_available() is True


def test_refresh_device_noop_quando_ja_tem_path(monkeypatch: pytest.MonkeyPatch):
    """refresh_device() não re-enumera se já há um path (evita custo ~60ms)."""
    from pathlib import Path

    reader = EvdevReader(device_path=Path("/dev/input/event2"))
    calls = {"n": 0}

    def _find() -> Path:
        calls["n"] += 1
        return Path("/dev/input/event9")

    monkeypatch.setattr(reader, "_find_device", _find)
    assert reader.refresh_device() is True
    assert calls["n"] == 0
    assert reader._device_path == Path("/dev/input/event2")


def test_reader_start_com_device_fake(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """EvdevReader inicia thread quando device_path está presente."""
    device_path = tmp_path / "fake_event"
    device_path.touch()

    reader = EvdevReader(device_path=device_path)
    assert reader.is_available() is True

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
    fake_device.fd = 0
    fake_device.read.return_value = iter(
        [
            fake_event(3, fake_ecodes.ABS_Z, 180),
            fake_event(3, fake_ecodes.ABS_RZ, 255),
            fake_event(3, fake_ecodes.ABS_X, 50),
            fake_event(1, fake_ecodes.BTN_SOUTH, 1),
        ]
    )

    import sys
    import time

    fake_mod = MagicMock()
    fake_mod.InputDevice = lambda *_a, **_kw: fake_device
    fake_mod.ecodes = fake_ecodes

    monkeypatch.setitem(sys.modules, "evdev", fake_mod)

    def _sempre_pronto(dev: object) -> list[object]:
        time.sleep(0.01)
        return [fake_device.fd]

    monkeypatch.setattr(reader, "_wait_ready", _sempre_pronto)

    reader.start()
    time.sleep(0.1)

    snap = reader.snapshot()
    assert snap.l2_raw == 180
    assert snap.r2_raw == 255
    assert snap.lx == 50
    assert "cross" in snap.buttons_pressed

    reader.stop()


def test_keycode_name_mapping():
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


def test_set_grab_sem_device_apenas_registra_intencao():
    """set_grab antes de abrir o device só guarda a intenção (sem lançar)."""
    reader = EvdevReader(device_path=None)
    assert reader._grab is False
    reader.set_grab(True)
    assert reader._grab is True
    reader.set_grab(False)
    assert reader._grab is False


def test_set_grab_aplica_no_device_aberto():
    """Com device aberto, set_grab chama grab()/ungrab() no InputDevice."""
    reader = EvdevReader(device_path=None)
    dev = MagicMock()
    reader._active_dev = dev
    reader.set_grab(True)
    dev.grab.assert_called_once()
    reader.set_grab(False)
    dev.ungrab.assert_called_once()


def test_set_grab_nao_propaga_excecao():
    """grab() que falha (device sumiu) não derruba o caller."""
    reader = EvdevReader(device_path=None)
    dev = MagicMock()
    dev.grab.side_effect = OSError("device foi embora")
    reader._active_dev = dev
    reader.set_grab(True)
    assert reader._grab is True


def test_set_grab_idempotente_nao_regraba_o_mesmo_fd():
    """BUG-GRAB-DOUBLE-EBUSY-01: re-grabar um fd já grabbed (troca de máscara)"""
    reader = EvdevReader(device_path=None)
    dev = MagicMock()
    reader._active_dev = dev
    assert reader.set_grab(True) is True
    assert reader.grab_state == "held"
    assert reader.set_grab(True) is True
    assert reader.grab_state == "held"
    dev.grab.assert_called_once()


def test_set_grab_ebusy_externo_ainda_marca_failed():
    """EBUSY de OUTRO leitor (estado nunca chegou a 'held') continua honesto:"""
    reader = EvdevReader(device_path=None)
    dev = MagicMock()
    dev.grab.side_effect = OSError(16, "Device or resource busy")
    reader._active_dev = dev
    assert reader.set_grab(True) is False
    assert reader.grab_state == "failed"


def test_ungrab_de_device_solto_e_noop():
    """ungrab quando este reader não graba (estado 'off') não chama ungrab()"""
    reader = EvdevReader(device_path=None)
    dev = MagicMock()
    reader._active_dev = dev
    assert reader.set_grab(False) is True
    assert reader.grab_state == "off"
    dev.ungrab.assert_not_called()


def test_pids_contemplam_edge():
    assert 0x0CE6 in DUALSENSE_PIDS  # DualSense
    assert 0x0DF2 in DUALSENSE_PIDS  # DualSense Edge
    assert DUALSENSE_VENDOR == 0x054C


def test_discover_nao_adota_o_vpad_uinput_0df2(monkeypatch: pytest.MonkeyPatch):
    """VPAD-04 (ressalva): `DUALSENSE_PIDS` inclui 0x0DF2 porque o DualSense Edge
    FÍSICO existe — então, com o vpad uinput agora nascendo Edge, a ÚNICA coisa
    que o separa de um Edge de verdade é a ancestralidade virtual
    (`_is_virtual_evdev`), nunca o VID/PID. Sem o filtro, o daemon adota o
    próprio vpad como controle físico — o feedback loop que o projeto já sofreu
    no UHID-02 (o daemon lendo a própria saída)."""
    from pathlib import Path
    from types import SimpleNamespace

    from evdev import ecodes

    from hefesto_dualsense4unix.core.evdev_reader import discover_dualsense_evdevs

    class _FakeDev:
        def __init__(self, path: str) -> None:
            self.path = path
            self.info = SimpleNamespace(vendor=0x054C, product=0x0DF2)
            self.uniq = "" if "event20" in path else "e8:47:3a:00:00:01"

        def capabilities(self) -> dict[int, list[int]]:
            return {ecodes.EV_KEY: [ecodes.BTN_SOUTH]}

        def close(self) -> None: ...

    monkeypatch.setattr(
        "evdev.list_devices",
        lambda: ["/dev/input/event20", "/dev/input/event21"],
    )
    monkeypatch.setattr("evdev.InputDevice", _FakeDev)
    monkeypatch.setattr(
        "os.path.realpath",
        lambda p: (
            "/sys/devices/virtual/input/input99/event20"
            if "event20" in p
            else "/sys/devices/pci0000:00/0000:00:08.1/0000:0c:00.3/usb3/3-4/"
            "3-4:1.3/0003:054C:0DF2.0009/input/input21/event21"
        ),
    )

    found = discover_dualsense_evdevs()

    assert found == {"e8473a000001": Path("/dev/input/event21")}, (
        "o vpad uinput-0df2 entrou na enumeração — feedback loop do UHID-02"
    )


def test_is_virtual_evdev_bluez_uhid_fisico_nao_e_virtual(
    monkeypatch: pytest.MonkeyPatch,
):
    """BLUEZ-UHID-01: com BlueZ ≥5.73 (UserspaceHID default) o bluetoothd cria"""
    from hefesto_dualsense4unix.core import evdev_reader as er

    monkeypatch.setattr(
        "os.path.realpath",
        lambda _p: (
            "/sys/devices/virtual/misc/uhid/0005:057E:2009.0016/input/input95"
        ),
    )
    attrs = {"phys": "aa:bb:cc:00:00:05", "uniq": "aa:bb:cc:00:00:03"}
    monkeypatch.setattr(er, "_read_input_attr", lambda _d, a: attrs.get(a, ""))

    assert er._is_virtual_evdev("/dev/input/event95") is False, (
        "físico BT via bluetoothd-uhid filtrado como vpad — BLUEZ-UHID-01"
    )

    attrs = {"phys": "hefesto-vpad", "uniq": "02:fe:00:00:00:01"}
    assert er._is_virtual_evdev("/dev/input/event96") is True

    attrs = {"phys": "", "uniq": "02:fe:00:00:00:01"}
    assert er._is_virtual_evdev("/dev/input/event96") is True, (
        "com o `phys` vazio que o hid_playstation de fato produz, quem tem de "
        "segurar o vpad é o `uniq` — se este caso cair, o daemon adota a "
        "própria saída"
    )

    attrs = {"phys": "", "uniq": "aa:bb:cc:00:00:65"}
    assert er._is_virtual_evdev("/dev/input/event96") is False, (
        "o controle de rádio tem `phys` vazio igual ao vpad — quem os separa é "
        "só o `uniq`, e não há segunda perna"
    )

    attrs = {}
    assert er._is_virtual_evdev("/dev/input/event98") is True

    monkeypatch.setattr(
        "os.path.realpath", lambda _p: "/sys/devices/virtual/input/input99"
    )
    assert er._is_virtual_evdev("/dev/input/event97") is True


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
    """HOTFIX-3: se a leitura levanta OSError, reader tenta reabrir."""
    import time

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
    first_device.fd = 1
    first_device.read.side_effect = OSError(19, "No such device")

    second_device = MagicMock()
    second_device.name = "second"
    second_device.fd = 2
    second_device.read.return_value = iter([
        fake_event(3, fake_ecodes.ABS_Z, 200),
    ])

    devices = [first_device, second_device]

    def device_factory(*_a, **_kw):
        if devices:
            return devices.pop(0)
        later = MagicMock()
        later.fd = 3
        later.read.return_value = iter([])
        return later

    import sys

    fake_mod = MagicMock()
    fake_mod.InputDevice = device_factory
    fake_mod.ecodes = fake_ecodes

    monkeypatch.setitem(sys.modules, "evdev", fake_mod)

    from hefesto_dualsense4unix.core import evdev_reader as er_mod
    monkeypatch.setattr(er_mod, "find_dualsense_evdev", lambda: device_path)

    def _sempre_pronto(dev: object) -> list[object]:
        time.sleep(0.01)
        return [dev.fd]

    monkeypatch.setattr(reader, "_wait_ready", _sempre_pronto)

    reader.start()
    time.sleep(0.8)

    snap = reader.snapshot()
    reader.stop()

    assert snap.l2_raw == 200


def test_stop_nao_loga_read_lost_no_teardown_intencional(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MISC-08 item 4 (2026-07-18) + HANG-01 (2026-07-19): `stop()` não fecha"""
    import os
    import sys
    import time
    from pathlib import Path
    from unittest.mock import MagicMock

    from hefesto_dualsense4unix.core import evdev_reader as er_mod

    idle_r, idle_w = os.pipe()

    class _DevOcioso:
        name = "DualSense fake ocioso"
        fd = idle_r

        def read(self) -> Any:
            return iter([])

        def close(self) -> None: ...

        def grab(self) -> None: ...

        def ungrab(self) -> None: ...

    fake_mod = MagicMock()
    fake_mod.InputDevice = lambda *_a, **_kw: _DevOcioso()
    fake_mod.ecodes = MagicMock()
    monkeypatch.setitem(sys.modules, "evdev", fake_mod)

    reader = EvdevReader(device_path=Path("/dev/input/event259"))
    spy = MagicMock()
    monkeypatch.setattr(er_mod, "logger", spy)

    try:
        assert reader.start() is True
        time.sleep(0.2)
        reader.stop()
    finally:
        os.close(idle_r)
        os.close(idle_w)

    warnings = [c.args[0] for c in spy.warning.call_args_list]
    assert "evdev_read_lost" not in warnings, (
        "teardown intencional não pode alarmar como perda de device"
    )
    debugs = [c.args[0] for c in spy.debug.call_args_list]
    assert "evdev_read_stopped" in debugs


def test_close_do_device_acontece_so_na_thread_dona(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HANG-01 (Sprint 2026-07-19): `stop()` nunca fecha o `InputDevice` de"""
    import os
    import sys
    import threading
    import time
    from pathlib import Path
    from unittest.mock import MagicMock

    idle_r, idle_w = os.pipe()
    closed_from: list[str] = []

    class _DevInstrumentado:
        name = "DualSense fake instrumentado"
        fd = idle_r

        def read(self) -> Any:
            return iter([])

        def close(self) -> None:
            closed_from.append(threading.current_thread().name)

        def grab(self) -> None: ...

        def ungrab(self) -> None: ...

    fake_mod = MagicMock()
    fake_mod.InputDevice = lambda *_a, **_kw: _DevInstrumentado()
    fake_mod.ecodes = MagicMock()
    monkeypatch.setitem(sys.modules, "evdev", fake_mod)

    reader = EvdevReader(device_path=Path("/dev/input/event260"))
    try:
        assert reader.start() is True
        time.sleep(0.2)
        reader.stop()
    finally:
        os.close(idle_r)
        os.close(idle_w)

    assert closed_from == ["hefesto-evdev"], (
        "close() rodou fora da thread dona — reabre o risco do wedge de GIL"
    )
    assert threading.current_thread().name != closed_from[0]


def test_read_lost_real_continua_com_warning_e_reset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O caminho de PERDA REAL (unplug/storm) fica intacto: warning"""
    import sys
    import time
    from pathlib import Path
    from unittest.mock import MagicMock

    from hefesto_dualsense4unix.core import evdev_reader as er_mod

    class _DevMorto:
        name = "DualSense fake que morre"
        fd = 0

        def read(self) -> Any:
            return iter([])

        def close(self) -> None: ...

        def grab(self) -> None: ...

        def ungrab(self) -> None: ...

    fake_mod = MagicMock()
    fake_mod.InputDevice = lambda *_a, **_kw: _DevMorto()
    fake_mod.ecodes = MagicMock()
    monkeypatch.setitem(sys.modules, "evdev", fake_mod)
    monkeypatch.setattr(er_mod, "find_dualsense_evdev", lambda: None)
    monkeypatch.setattr(er_mod, "discover_dualsense_evdevs", lambda: {})

    reader = EvdevReader(device_path=Path("/dev/input/event259"))
    spy = MagicMock()
    monkeypatch.setattr(er_mod, "logger", spy)

    def _boom(_dev: object) -> list[object]:
        raise OSError(19, "No such device")

    monkeypatch.setattr(reader, "_wait_ready", _boom)

    assert reader.start() is True
    time.sleep(0.2)
    reader.stop()

    warnings = [c.args[0] for c in spy.warning.call_args_list]
    assert "evdev_read_lost" in warnings
