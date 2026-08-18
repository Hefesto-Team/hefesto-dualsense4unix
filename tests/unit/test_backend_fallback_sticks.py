"""Fallback HID-raw do backend: sticks da pydualsense são centrados em 0 (A6).

FEAT-MOUSE-CURSOR-FEEL-01: a pydualsense 0.7.5 instalada armazena
``state.LX = states[1] - 128`` (range -128..127). O fallback (sem evdev) fazia
``int(state.LX) & 0xFF``, que transformava repouso (cru 128 → LX=0) em raw 0 e
drift leve (cru 125 → LX=-3) em raw 253 — o cursor "voava" na diagonal e o
gamepad virtual/scroll/check de neutralidade herdavam o mesmo lixo.

Cadeia REAL sem hardware (espelha o repro do diagnóstico 2026-07-03):
report USB 64 bytes → ``pydualsense.readInput`` (código instalado) →
``PyDualSenseController.read_state`` (ramo fallback) → pipeline de movimento.
"""
from __future__ import annotations

import pytest
from pydualsense.enums import ConnectionType
from pydualsense.pydualsense import DSBattery, DSState, pydualsense

from hefesto_dualsense4unix.core.backend_pydualsense import (
    PyDualSenseController,
    _centered_stick_to_raw,
)
from hefesto_dualsense4unix.integrations.uinput_mouse import (
    DEFAULT_MOUSE_SPEED,
    _compute_move_px_per_sec,
)


class _NoEvdev:
    """EvdevReader fake indisponível — força o ramo fallback do read_state."""

    def is_available(self) -> bool:
        return False


def _fake_ds() -> pydualsense:
    """pydualsense real sem tocar hidapi (o construtor não abre device)."""
    ds = pydualsense()
    ds.state = DSState()
    ds.conType = ConnectionType.USB
    ds.is_edge = False
    ds.battery = DSBattery()
    ds.connected = True
    return ds


def _inject_usb_report(ds: pydualsense, sticks: int) -> None:
    """Injeta um report de input USB (0x01) com os 4 sticks no valor cru dado."""
    report = [0x01] + [0] * 63
    report[1] = report[2] = report[3] = report[4] = sticks
    ds.readInput(report)


def _backend_with(ds: pydualsense) -> PyDualSenseController:
    backend = PyDualSenseController(evdev_reader=_NoEvdev())
    backend._ds = ds  # seam de compat do backend para o handle primário
    return backend


@pytest.mark.parametrize("cru", [128, 125])
def test_fallback_preserva_repouso_dos_sticks(cru: int) -> None:
    """Repouso cru 128 (centro perfeito) e 125 (drift típico) → raw idêntico ao
    cru e cursor PARADO (antes: raw 0/253 → cursor voava na diagonal)."""
    ds = _fake_ds()
    _inject_usb_report(ds, cru)
    # Sanidade do repro: a lib instalada centraliza em 0 (states[n] - 128).
    # (ordem invertida por causa do SIM300 — LX em maiúsculas parece constante)
    assert cru - 128 == ds.state.LX

    state = _backend_with(ds).read_state()

    assert (state.raw_lx, state.raw_ly) == (cru, cru)
    assert (state.raw_rx, state.raw_ry) == (cru, cru)
    # Pipeline de movimento: repouso (dentro da deadzone) → velocidade 0.
    assert _compute_move_px_per_sec(
        state.raw_lx, state.raw_ly, DEFAULT_MOUSE_SPEED
    ) == (0.0, 0.0)


def test_fallback_preserva_deflexao_real() -> None:
    """Deflexão de verdade sobrevive à ida e volta (cru 200 → raw 200)."""
    ds = _fake_ds()
    _inject_usb_report(ds, 200)
    state = _backend_with(ds).read_state()
    assert state.raw_lx == 200
    vx, _ = _compute_move_px_per_sec(state.raw_lx, 128, DEFAULT_MOUSE_SPEED)
    assert vx > 0.0  # move para a direita, como o stick físico pede


def test_fallback_nao_toca_gatilhos() -> None:
    """L2/R2 já são crus 0-255 na pydualsense — a correção não soma 128 neles."""
    ds = _fake_ds()
    report = [0x01] + [0] * 63
    report[1] = report[2] = report[3] = report[4] = 128
    report[5] = 200  # L2 cru
    report[6] = 50   # R2 cru
    ds.readInput(report)
    state = _backend_with(ds).read_state()
    assert state.l2_raw == 200
    assert state.r2_raw == 50


def test_centered_stick_to_raw_clampa_extremos() -> None:
    assert _centered_stick_to_raw(0) == 128
    assert _centered_stick_to_raw(-128) == 0
    assert _centered_stick_to_raw(127) == 255
    # Valores fora do range teórico não estouram o contrato 0-255.
    assert _centered_stick_to_raw(-300) == 0
    assert _centered_stick_to_raw(300) == 255
