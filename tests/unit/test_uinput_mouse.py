"""Testes do UinputMouseDevice (FEAT-MOUSE-01)."""
from __future__ import annotations

import builtins
import sys
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto.integrations.uinput_mouse import (
    BUTTON_TO_UINPUT,
    DEFAULT_MOUSE_SPEED,
    DEFAULT_SCROLL_SPEED,
    DEVICE_NAME,
    DPAD_TO_KEY,
    MOVE_DEADZONE,
    SCROLL_DEADZONE,
    SCROLL_RATE_LIMIT_SEC,
    TRIGGER_PRESS_THRESHOLD,
    UinputMouseDevice,
    _compute_move,
    _compute_scroll_step,
)


def _fake_uinput_module() -> MagicMock:
    """Fabrica um módulo uinput fake com constantes suficientes para todos os emits."""
    mod = MagicMock()
    for name in (
        "REL_X", "REL_Y", "REL_WHEEL", "REL_HWHEEL",
        "BTN_LEFT", "BTN_RIGHT", "BTN_MIDDLE",
        "KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT",
    ):
        setattr(mod, name, (1, hash(name) & 0xFFFF))
    return mod


def _started_device(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[UinputMouseDevice, MagicMock, MagicMock]:
    fake_mod = _fake_uinput_module()
    fake_device = MagicMock()
    fake_mod.Device.return_value = fake_device
    monkeypatch.setitem(sys.modules, "uinput", fake_mod)
    dev = UinputMouseDevice()
    assert dev.start() is True
    return dev, fake_mod, fake_device


def _emits_for(fake_device: MagicMock, code: Any) -> list:
    """Extrai lista de chamadas `emit(code, value, ...)` para o código dado."""
    return [
        c for c in fake_device.method_calls
        if c[0] == "emit" and c[1][0] == code
    ]


# --- configuração / constantes -----------------------------------------------

def test_constantes_default_coerentes():
    assert DEFAULT_MOUSE_SPEED == 6
    assert DEFAULT_SCROLL_SPEED == 1
    assert MOVE_DEADZONE == 20
    assert SCROLL_DEADZONE == 40
    assert SCROLL_RATE_LIMIT_SEC == 0.050
    assert TRIGGER_PRESS_THRESHOLD == 64
    assert "Hefesto" in DEVICE_NAME


def test_button_map_canonico():
    assert BUTTON_TO_UINPUT == {
        "cross": "BTN_LEFT",
        "triangle": "BTN_RIGHT",
        "r3": "BTN_MIDDLE",
    }
    assert DPAD_TO_KEY == {
        "dpad_up": "KEY_UP",
        "dpad_down": "KEY_DOWN",
        "dpad_left": "KEY_LEFT",
        "dpad_right": "KEY_RIGHT",
    }


# --- deadzone / escala de movimento -----------------------------------------

def test_deadzone_movimento_retorna_zero_perto_do_centro():
    # Dentro da deadzone (|offset| < 20)
    assert _compute_move(128, 6) == 0
    assert _compute_move(128 + 19, 6) == 0
    assert _compute_move(128 - 19, 6) == 0


def test_deadzone_movimento_respeita_escala():
    # offset = 100, speed = 6 → int(100/128*6) = 4
    assert _compute_move(228, 6) == 4
    # offset = -100, speed = 6 → int(-100/128*6) = -4 (int() trunca para 0)
    assert _compute_move(28, 6) == -4
    # speed maior amplifica
    assert abs(_compute_move(228, 12)) > abs(_compute_move(228, 6))


def test_deadzone_scroll_exige_amplitude_maior():
    # Stick a 30 de offset passa no move (>20) mas não no scroll (<40)
    assert _compute_move(128 + 30, 6) != 0
    assert _compute_scroll_step(128 + 30) == 0
    # Acima de 40 passa
    assert _compute_scroll_step(128 + 41) == 1
    assert _compute_scroll_step(128 - 41) == -1


# --- start / stop ------------------------------------------------------------

def test_start_sem_uinput_retorna_false(monkeypatch: pytest.MonkeyPatch):
    real_import = builtins.__import__

    def broken_import(name, *args, **kwargs):
        if name == "uinput":
            raise ImportError("uinput não instalado (mock)")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", broken_import)
    dev = UinputMouseDevice()
    assert dev.start() is False
    assert dev.is_active() is False


def test_start_e_stop_idempotente(monkeypatch: pytest.MonkeyPatch):
    dev, fake_mod, fake_device = _started_device(monkeypatch)
    assert dev.is_active() is True
    fake_mod.Device.assert_called_once()
    # Segunda chamada não recria
    assert dev.start() is True
    fake_mod.Device.assert_called_once()

    dev.stop()
    fake_device.destroy.assert_called_once()
    assert dev.is_active() is False
    # Stop idempotente
    dev.stop()
    fake_device.destroy.assert_called_once()


def test_dispatch_sem_start_nao_emite(monkeypatch: pytest.MonkeyPatch):
    dev = UinputMouseDevice()
    # Sem start, dispatch é no-op (não levanta)
    dev.dispatch(
        lx=200, ly=200, rx=200, ry=200, l2=0, r2=0,
        buttons=frozenset({"cross"}),
    )


# --- botões: edge-trigger ----------------------------------------------------

def test_cross_press_release_emite_bt_left(monkeypatch: pytest.MonkeyPatch):
    dev, fake_mod, fake_device = _started_device(monkeypatch)

    # Press
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset({"cross"}), now=0.0,
    )
    left_emits = [
        c for c in fake_device.method_calls
        if c[0] == "emit" and c[1][0] == fake_mod.BTN_LEFT
    ]
    assert len(left_emits) == 1
    assert left_emits[-1][1][1] == 1  # value=1 (press)

    fake_device.reset_mock()

    # Hold (mesmo estado): sem novo emit de BTN_LEFT
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset({"cross"}), now=0.1,
    )
    held = [
        c for c in fake_device.method_calls
        if c[0] == "emit" and c[1][0] == fake_mod.BTN_LEFT
    ]
    assert held == []

    # Release
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset(), now=0.2,
    )
    released = [
        c for c in fake_device.method_calls
        if c[0] == "emit" and c[1][0] == fake_mod.BTN_LEFT
    ]
    assert len(released) == 1
    assert released[-1][1][1] == 0


def test_triangle_e_r3_mapeam_right_e_middle(monkeypatch: pytest.MonkeyPatch):
    dev, fake_mod, fake_device = _started_device(monkeypatch)

    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset({"triangle", "r3"}), now=0.0,
    )

    right_press = any(
        c[0] == "emit" and c[1][0] == fake_mod.BTN_RIGHT and c[1][1] == 1
        for c in fake_device.method_calls
    )
    middle_press = any(
        c[0] == "emit" and c[1][0] == fake_mod.BTN_MIDDLE and c[1][1] == 1
        for c in fake_device.method_calls
    )
    assert right_press
    assert middle_press


def test_l2_analogico_acima_do_threshold_dispara_botao_esquerdo(monkeypatch: pytest.MonkeyPatch):
    dev, fake_mod, fake_device = _started_device(monkeypatch)

    # L2 abaixo do threshold: não dispara
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=40, r2=0,
        buttons=frozenset(), now=0.0,
    )
    assert not any(
        c[0] == "emit" and c[1][0] == fake_mod.BTN_LEFT
        for c in fake_device.method_calls
    )

    fake_device.reset_mock()

    # L2 acima: dispara
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=200, r2=0,
        buttons=frozenset(), now=0.1,
    )
    press = [
        c for c in fake_device.method_calls
        if c[0] == "emit" and c[1][0] == fake_mod.BTN_LEFT
    ]
    assert press and press[-1][1][1] == 1


def test_r2_analogico_acima_do_threshold_dispara_botao_direito(monkeypatch: pytest.MonkeyPatch):
    dev, fake_mod, fake_device = _started_device(monkeypatch)

    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=200,
        buttons=frozenset(), now=0.0,
    )
    press = [
        c for c in fake_device.method_calls
        if c[0] == "emit" and c[1][0] == fake_mod.BTN_RIGHT
    ]
    assert press and press[-1][1][1] == 1


# --- movimento ---------------------------------------------------------------

def test_stick_esquerdo_fora_do_centro_emite_rel(monkeypatch: pytest.MonkeyPatch):
    dev, fake_mod, fake_device = _started_device(monkeypatch)

    dev.dispatch(
        lx=228, ly=228, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset(), now=0.0,
    )
    rel_x = [c for c in fake_device.method_calls if c[0] == "emit" and c[1][0] == fake_mod.REL_X]
    rel_y = [c for c in fake_device.method_calls if c[0] == "emit" and c[1][0] == fake_mod.REL_Y]
    assert rel_x and rel_x[-1][1][1] > 0
    assert rel_y and rel_y[-1][1][1] > 0


def test_stick_esquerdo_no_centro_nao_emite(monkeypatch: pytest.MonkeyPatch):
    dev, fake_mod, fake_device = _started_device(monkeypatch)

    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset(), now=0.0,
    )
    assert not any(
        c[0] == "emit" and c[1][0] in (fake_mod.REL_X, fake_mod.REL_Y)
        for c in fake_device.method_calls
    )


def test_set_speed_limites():
    dev = UinputMouseDevice()
    dev.set_speed(mouse_speed=100)
    assert dev.mouse_speed == 12  # clamp superior
    dev.set_speed(mouse_speed=-5)
    assert dev.mouse_speed == 1  # clamp inferior
    dev.set_speed(scroll_speed=10)
    assert dev.scroll_speed == 5
    dev.set_speed(scroll_speed=0)
    assert dev.scroll_speed == 1


# --- scroll / rate-limit -----------------------------------------------------

def test_scroll_rate_limit_50ms(monkeypatch: pytest.MonkeyPatch):
    dev, fake_mod, fake_device = _started_device(monkeypatch)

    # Primeiro scroll em t=0: passa
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=200, l2=0, r2=0,
        buttons=frozenset(), now=0.0,
    )
    first = _emits_for(fake_device, fake_mod.REL_WHEEL)
    assert len(first) == 1

    fake_device.reset_mock()

    # t=0.020 (20ms): dentro do rate-limit, NÃO emite
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=200, l2=0, r2=0,
        buttons=frozenset(), now=0.020,
    )
    blocked = _emits_for(fake_device, fake_mod.REL_WHEEL)
    assert blocked == []

    # t=0.060 (60ms): fora do rate-limit, emite
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=200, l2=0, r2=0,
        buttons=frozenset(), now=0.060,
    )
    passed = _emits_for(fake_device, fake_mod.REL_WHEEL)
    assert len(passed) == 1


def test_scroll_vertical_sentido_convencional(monkeypatch: pytest.MonkeyPatch):
    """Stick direito empurrado para cima (ry<128) → scroll positivo (up)."""
    dev, fake_mod, fake_device = _started_device(monkeypatch)
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=50, l2=0, r2=0,
        buttons=frozenset(), now=0.0,
    )
    wheel = _emits_for(fake_device, fake_mod.REL_WHEEL)
    assert wheel and wheel[-1][1][1] > 0


def test_scroll_horizontal_hwheel(monkeypatch: pytest.MonkeyPatch):
    dev, fake_mod, fake_device = _started_device(monkeypatch)
    dev.dispatch(
        lx=128, ly=128, rx=200, ry=128, l2=0, r2=0,
        buttons=frozenset(), now=0.0,
    )
    hwheel = _emits_for(fake_device, fake_mod.REL_HWHEEL)
    assert hwheel and hwheel[-1][1][1] != 0


# --- D-pad → setas -----------------------------------------------------------

def test_dpad_up_emite_key_up_edge_trigger(monkeypatch: pytest.MonkeyPatch):
    dev, fake_mod, fake_device = _started_device(monkeypatch)

    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset({"dpad_up"}), now=0.0,
    )
    press = [c for c in fake_device.method_calls if c[0] == "emit" and c[1][0] == fake_mod.KEY_UP]
    assert press and press[-1][1][1] == 1

    fake_device.reset_mock()

    # Mantido: sem novo emit
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset({"dpad_up"}), now=0.05,
    )
    held = [c for c in fake_device.method_calls if c[0] == "emit" and c[1][0] == fake_mod.KEY_UP]
    assert held == []

    # Solto: release
    dev.dispatch(
        lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
        buttons=frozenset(), now=0.1,
    )
    release = [c for c in fake_device.method_calls if c[0] == "emit" and c[1][0] == fake_mod.KEY_UP]
    assert release and release[-1][1][1] == 0


def test_dpad_cobre_quatro_direcoes(monkeypatch: pytest.MonkeyPatch):
    dev, fake_mod, fake_device = _started_device(monkeypatch)

    t = 0.0
    for name, key_attr in (
        ("dpad_up", "KEY_UP"),
        ("dpad_down", "KEY_DOWN"),
        ("dpad_left", "KEY_LEFT"),
        ("dpad_right", "KEY_RIGHT"),
    ):
        fake_device.reset_mock()
        dev.dispatch(
            lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
            buttons=frozenset({name}), now=t,
        )
        key = getattr(fake_mod, key_attr)
        press = [c for c in fake_device.method_calls if c[0] == "emit" and c[1][0] == key]
        assert press and press[-1][1][1] == 1, f"{name} não emitiu {key_attr} press"
        t += 0.2  # desacopla do rate-limit de scroll
        dev.dispatch(
            lx=128, ly=128, rx=128, ry=128, l2=0, r2=0,
            buttons=frozenset(), now=t,
        )
        t += 0.2


# "A liberdade é nada mais que uma chance de ser melhor." — Albert Camus
