"""Testes do UinputGamepad (W6.3 + FEAT-VPAD-FF-PASSTHROUGH-01).

O backend migrou de python-uinput para python-evdev (necessário para o
force-feedback); os fakes aqui simulam o módulo `evdev` (UInput/ecodes/
AbsInfo) — sem hardware, sem /dev/uinput. O protocolo de FF em si é coberto
em `test_vpad_ff_passthrough.py`; aqui ficam criação/forwarding/teardown.
"""
from __future__ import annotations

import sys
import types
from typing import Any, ClassVar, NamedTuple

import pytest

from hefesto_dualsense4unix.integrations.uinput_gamepad import (
    BUTTON_TO_UINPUT,
    DEVICE_NAME,
    DEVICE_VERSION,
    MAX_FF_EFFECTS,
    XBOX360_PRODUCT,
    XBOX360_VENDOR,
    UinputGamepad,
)


class _EC:
    """Constantes evdev mínimas (valores reais do linux/input-event-codes.h)."""

    EV_SYN = 0x00
    EV_KEY = 0x01
    EV_ABS = 0x03
    EV_FF = 0x15
    EV_UINPUT = 0x0101
    UI_FF_UPLOAD = 1
    UI_FF_ERASE = 2
    ABS_X = 0x00
    ABS_Y = 0x01
    ABS_Z = 0x02
    ABS_RX = 0x03
    ABS_RY = 0x04
    ABS_RZ = 0x05
    ABS_HAT0X = 0x10
    ABS_HAT0Y = 0x11
    BTN_A = 0x130
    BTN_B = 0x131
    BTN_X = 0x133
    BTN_Y = 0x134
    BTN_TL = 0x136
    BTN_TR = 0x137
    BTN_SELECT = 0x13A
    BTN_START = 0x13B
    BTN_MODE = 0x13C
    BTN_THUMBL = 0x13D
    BTN_THUMBR = 0x13E
    FF_RUMBLE = 0x50
    FF_PERIODIC = 0x51
    FF_SQUARE = 0x58
    FF_TRIANGLE = 0x59
    FF_SINE = 0x5A
    FF_GAIN = 0x60


class _AbsInfo(NamedTuple):
    value: int
    min: int
    max: int
    fuzz: int
    flat: int
    resolution: int


class _FakeUInput:
    """UInput falso: registra writes/syn/close e os kwargs de criação."""

    instances: ClassVar[list[_FakeUInput]] = []
    fail_always = False

    def __init__(self, events: dict[int, list[Any]], **kwargs: Any) -> None:
        if type(self).fail_always:
            raise OSError("uinput indisponível (fake)")
        self.events = events
        self.kwargs = kwargs
        self.writes: list[tuple[int, int, int]] = []
        self.synced = 0
        self.closed = False
        type(self).instances.append(self)

    def write(self, etype: int, code: int, value: int) -> None:
        self.writes.append((etype, code, value))

    def syn(self) -> None:
        self.synced += 1

    def close(self) -> None:
        self.closed = True

    def read_one(self) -> Any:
        return None


def _install_fake_evdev(monkeypatch: pytest.MonkeyPatch) -> type[_FakeUInput]:
    _FakeUInput.instances = []
    _FakeUInput.fail_always = False
    mod = types.ModuleType("evdev")
    mod.UInput = _FakeUInput  # type: ignore[attr-defined]
    mod.AbsInfo = _AbsInfo  # type: ignore[attr-defined]
    mod.ecodes = _EC  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "evdev", mod)
    return _FakeUInput


def test_constantes_xbox360() -> None:
    assert XBOX360_VENDOR == 0x045E
    assert XBOX360_PRODUCT == 0x028E
    assert "Hefesto - Dualsense4Unix" in DEVICE_NAME


def test_button_map_cobre_face_buttons() -> None:
    for name in ("cross", "circle", "square", "triangle", "ps"):
        assert name in BUTTON_TO_UINPUT


def test_start_sem_evdev_retorna_false(monkeypatch: pytest.MonkeyPatch) -> None:
    # sys.modules["evdev"] = None faz o import levantar ImportError (padrão
    # CPython para "import halted") — simula ambiente sem a lib.
    monkeypatch.setitem(sys.modules, "evdev", None)
    gp = UinputGamepad()
    assert gp.start() is False
    assert gp.is_active() is False


def test_start_com_evdev_mockado(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_evdev(monkeypatch)

    gp = UinputGamepad()
    assert gp.start() is True
    assert gp.is_active() is True
    assert len(fake.instances) == 1
    dev = fake.instances[0]
    # Máscara + FF anunciados na criação.
    assert dev.kwargs["vendor"] == XBOX360_VENDOR
    assert dev.kwargs["product"] == XBOX360_PRODUCT
    assert dev.kwargs["version"] == DEVICE_VERSION
    assert dev.kwargs["max_effects"] == MAX_FF_EFFECTS
    assert _EC.EV_FF in dev.events
    assert _EC.FF_RUMBLE in dev.events[_EC.EV_FF]
    assert gp.ff_supported is True

    gp.stop()
    assert dev.closed is True
    assert gp.is_active() is False


def test_start_idempotente_nao_recria(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_evdev(monkeypatch)
    gp = UinputGamepad()
    assert gp.start() is True
    assert gp.start() is True
    assert len(fake.instances) == 1


def test_start_falha_total_retorna_false(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_evdev(monkeypatch)
    fake.fail_always = True
    gp = UinputGamepad()
    assert gp.start() is False
    assert gp.is_active() is False


def test_forward_analog_emite_seis_eventos(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_evdev(monkeypatch)
    gp = UinputGamepad()
    gp.start()
    dev = fake.instances[0]

    gp.forward_analog(lx=100, ly=200, rx=127, ry=126, l2=50, r2=255)

    abs_writes = [w for w in dev.writes if w[0] == _EC.EV_ABS]
    assert len(abs_writes) == 6
    assert dev.synced == 1


def test_forward_analog_delta_nao_reemite_parado(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_evdev(monkeypatch)
    gp = UinputGamepad()
    gp.start()
    dev = fake.instances[0]

    gp.forward_analog(lx=128, ly=128, rx=128, ry=128, l2=0, r2=0)
    writes_before = len(dev.writes)
    gp.forward_analog(lx=128, ly=128, rx=128, ry=128, l2=0, r2=0)
    assert len(dev.writes) == writes_before  # tick parado = zero writes


def test_forward_buttons_press_e_release(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_evdev(monkeypatch)
    gp = UinputGamepad()
    gp.start()
    dev = fake.instances[0]

    gp.forward_buttons(frozenset({"cross", "circle"}))
    presses = [w for w in dev.writes if w[0] == _EC.EV_KEY and w[2] == 1]
    assert {w[1] for w in presses} == {_EC.BTN_A, _EC.BTN_B}

    dev.writes.clear()
    gp.forward_buttons(frozenset({"cross"}))  # solta circle, mantém cross
    releases = [w for w in dev.writes if w[0] == _EC.EV_KEY and w[2] == 0]
    assert {w[1] for w in releases} == {_EC.BTN_B}


def test_forward_buttons_dpad_atualiza_hat(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_evdev(monkeypatch)
    gp = UinputGamepad()
    gp.start()
    dev = fake.instances[0]

    gp.forward_buttons(frozenset({"dpad_up"}))
    assert (_EC.EV_ABS, _EC.ABS_HAT0Y, -1) in dev.writes

    dev.writes.clear()
    gp.forward_buttons(frozenset({"dpad_right"}))
    assert (_EC.EV_ABS, _EC.ABS_HAT0X, 1) in dev.writes
    assert (_EC.EV_ABS, _EC.ABS_HAT0Y, 0) in dev.writes  # HAT0Y voltou a 0


def test_dpad_vector_estatico() -> None:
    assert UinputGamepad._dpad_vector(frozenset()) == (0, 0)
    assert UinputGamepad._dpad_vector(frozenset({"dpad_up"})) == (0, -1)
    assert UinputGamepad._dpad_vector(frozenset({"dpad_down"})) == (0, 1)
    assert UinputGamepad._dpad_vector(frozenset({"dpad_left"})) == (-1, 0)
    assert UinputGamepad._dpad_vector(frozenset({"dpad_right"})) == (1, 0)
    assert UinputGamepad._dpad_vector(frozenset({"dpad_up", "dpad_right"})) == (1, -1)
