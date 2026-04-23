"""Testes do UinputGamepad (W6.3)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hefesto.integrations.uinput_gamepad import (
    BUTTON_TO_UINPUT,
    DEVICE_NAME,
    XBOX360_PRODUCT,
    XBOX360_VENDOR,
    UinputGamepad,
)


def _fake_uinput_module() -> MagicMock:
    mod = MagicMock()
    # Lista mínima de constantes para _build_capabilities + forward_analog
    for name in (
        "ABS_X", "ABS_Y", "ABS_RX", "ABS_RY", "ABS_Z", "ABS_RZ",
        "ABS_HAT0X", "ABS_HAT0Y",
        "BTN_A", "BTN_B", "BTN_X", "BTN_Y",
        "BTN_TL", "BTN_TR",
        "BTN_SELECT", "BTN_START", "BTN_MODE",
        "BTN_THUMBL", "BTN_THUMBR",
    ):
        setattr(mod, name, (1, hash(name) & 0xFFFF))
    return mod


def test_constantes_xbox360():
    assert XBOX360_VENDOR == 0x045E
    assert XBOX360_PRODUCT == 0x028E
    assert "Hefesto" in DEVICE_NAME


def test_button_map_cobre_face_buttons():
    for name in ("cross", "circle", "square", "triangle", "ps"):
        assert name in BUTTON_TO_UINPUT


def test_start_sem_uinput_retorna_false(monkeypatch: pytest.MonkeyPatch):
    import sys
    # Esconde uinput pra simular ambiente sem a lib
    monkeypatch.setitem(sys.modules, "uinput", None)
    gp = UinputGamepad()
    # Forçar ImportError
    import builtins
    real_import = builtins.__import__

    def broken_import(name, *args, **kwargs):
        if name == "uinput":
            raise ImportError("uinput não instalado (mock)")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", broken_import)
    assert gp.start() is False
    assert gp.is_active() is False


def test_start_com_uinput_mockado(monkeypatch: pytest.MonkeyPatch):
    import sys

    fake_mod = _fake_uinput_module()
    fake_device = MagicMock()
    fake_mod.Device.return_value = fake_device
    monkeypatch.setitem(sys.modules, "uinput", fake_mod)

    gp = UinputGamepad()
    assert gp.start() is True
    assert gp.is_active() is True
    fake_mod.Device.assert_called_once()

    gp.stop()
    fake_device.destroy.assert_called_once()
    assert gp.is_active() is False


def test_forward_analog_emite_seis_eventos(monkeypatch: pytest.MonkeyPatch):
    import sys

    fake_mod = _fake_uinput_module()
    fake_device = MagicMock()
    fake_mod.Device.return_value = fake_device
    monkeypatch.setitem(sys.modules, "uinput", fake_mod)

    gp = UinputGamepad()
    gp.start()
    gp.forward_analog(lx=100, ly=200, rx=128, ry=128, l2=50, r2=255)

    # 6 chamadas de emit (syn=False) + 1 syn()
    emit_calls = [c for c in fake_device.method_calls if c[0] == "emit"]
    assert len(emit_calls) == 6
    fake_device.syn.assert_called()


def test_forward_buttons_press_e_release(monkeypatch: pytest.MonkeyPatch):
    import sys

    fake_mod = _fake_uinput_module()
    fake_device = MagicMock()
    fake_mod.Device.return_value = fake_device
    monkeypatch.setitem(sys.modules, "uinput", fake_mod)

    gp = UinputGamepad()
    gp.start()

    # Pressiona cross + circle
    gp.forward_buttons(frozenset({"cross", "circle"}))
    emit_calls = [c for c in fake_device.method_calls if c[0] == "emit"]
    # 2 botões (valor=1) + HAT0X + HAT0Y só emitem se mudaram (não mudaram, permanecem 0)
    # Então esperamos pelo menos 2 emits
    assert len(emit_calls) >= 2

    # Limpa histórico
    fake_device.reset_mock()

    # Solta circle, mantém cross
    gp.forward_buttons(frozenset({"cross"}))
    emit_calls = [c for c in fake_device.method_calls if c[0] == "emit"]
    # Circle deve ter sido soltado (valor=0); cross permanece
    assert len(emit_calls) >= 1


def test_forward_buttons_dpad_atualiza_hat(monkeypatch: pytest.MonkeyPatch):
    import sys

    fake_mod = _fake_uinput_module()
    fake_device = MagicMock()
    fake_mod.Device.return_value = fake_device
    monkeypatch.setitem(sys.modules, "uinput", fake_mod)

    gp = UinputGamepad()
    gp.start()

    gp.forward_buttons(frozenset({"dpad_up"}))

    # Deve ter emitido ABS_HAT0Y = -1
    emit_calls = [
        c for c in fake_device.method_calls
        if c[0] == "emit" and c[1][0] == fake_mod.ABS_HAT0Y
    ]
    assert emit_calls
    assert emit_calls[-1][1][1] == -1

    # dpad_right → HAT0X = 1
    fake_device.reset_mock()
    gp.forward_buttons(frozenset({"dpad_right"}))
    calls_x = [
        c for c in fake_device.method_calls
        if c[0] == "emit" and c[1][0] == fake_mod.ABS_HAT0X
    ]
    assert any(c[1][1] == 1 for c in calls_x)
    calls_y_zero = [
        c for c in fake_device.method_calls
        if c[0] == "emit" and c[1][0] == fake_mod.ABS_HAT0Y
    ]
    assert any(c[1][1] == 0 for c in calls_y_zero)  # HAT0Y voltou a 0


def test_dpad_vector_estatico():
    assert UinputGamepad._dpad_vector(frozenset()) == (0, 0)
    assert UinputGamepad._dpad_vector(frozenset({"dpad_up"})) == (0, -1)
    assert UinputGamepad._dpad_vector(frozenset({"dpad_down"})) == (0, 1)
    assert UinputGamepad._dpad_vector(frozenset({"dpad_left"})) == (-1, 0)
    assert UinputGamepad._dpad_vector(frozenset({"dpad_right"})) == (1, 0)
    assert UinputGamepad._dpad_vector(frozenset({"dpad_up", "dpad_right"})) == (1, -1)
