"""FEAT-DSX-GAMEPAD-ALWAYS-LIVE-01 — o gamepad virtual continua recebendo input
mesmo com o daemon PAUSADO (daemon.pause) e/ou em MODO JOGO (supressão), senão o
controle morre no jogo.

Regressão de "o controle não funciona no jogo mesmo com gatilhos/cores aplicados":
o forward do gamepad virtual estava DENTRO dos dois gates de emulação de DESKTOP
no poll loop — `_paused` (via o `continue` do gate de pausa/grace, antes do
dispatch) e `_emulation_suppressed` (via `emu_active`). Como o controle físico
fica EVIOCGRAB-grabado quando o gamepad está ligado (fonte única), congelar o
virtual deixava o jogo sem ver NADA: real escondido + virtual mudo. Pior, a pausa
persistia em disco e o daemon renascia pausado no boot.

Estes testes provam que o gamepad é despachado mesmo sob pausa/supressão, e que o
mouse/teclado de desktop continuam corretamente suspensos.
"""
from __future__ import annotations

import asyncio
from typing import ClassVar
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.testing import FakeController


def _mk_states(n: int) -> list[ControllerState]:
    return [
        ControllerState(
            battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
        for _ in range(n)
    ]


class _SnapCross:
    """Snapshot de evdev com um botão sempre pressionado (input fluindo)."""

    buttons_pressed: ClassVar[list[str]] = ["cross"]


def _config() -> DaemonConfig:
    return DaemonConfig(
        poll_hz=200,
        auto_reconnect=False,
        ipc_enabled=False,
        udp_enabled=False,
        autoswitch_enabled=False,
        mouse_emulation_enabled=False,
        keyboard_emulation_enabled=False,
    )


async def _run_with_gates(
    monkeypatch: pytest.MonkeyPatch, *, paused: bool, suppressed: bool
) -> tuple[MagicMock, MagicMock]:
    """Sobe o poll loop com gamepad + teclado mockados, liga os gates pedidos
    DEPOIS do grace, e devolve (gamepad_mock, keyboard_mock) com os mocks zerados
    no momento em que os gates foram aplicados (mede só o regime gateado)."""
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.0)
    fc = FakeController(transport="usb", states=_mk_states(2000))
    mock_evdev = MagicMock()
    mock_evdev.is_available.return_value = True
    mock_evdev.snapshot.return_value = _SnapCross()
    fc._evdev = mock_evdev

    daemon = Daemon(controller=fc, config=_config())
    gp = MagicMock()
    kbd = MagicMock()
    daemon._gamepad_device = gp
    daemon._keyboard_device = kbd

    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.05)  # passa o grace, despacha em regime normal
    if suppressed:
        daemon.set_emulation_suppressed(True)
    if paused:
        daemon.pause()
    gp.reset_mock()
    kbd.reset_mock()
    await asyncio.sleep(0.06)  # mede o regime gateado
    daemon.stop()
    await run_task
    return gp, kbd


@pytest.mark.asyncio
async def test_gamepad_vivo_sob_suppress(monkeypatch: pytest.MonkeyPatch) -> None:
    gp, kbd = await _run_with_gates(monkeypatch, paused=False, suppressed=True)
    assert gp.forward_buttons.call_count > 0, "gamepad congelou em modo jogo (suppress)"
    assert kbd.dispatch.call_count == 0, "teclado de desktop deveria estar suspenso"


@pytest.mark.asyncio
async def test_gamepad_vivo_sob_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    gp, kbd = await _run_with_gates(monkeypatch, paused=True, suppressed=False)
    assert gp.forward_buttons.call_count > 0, "gamepad congelou com o daemon pausado"
    assert kbd.dispatch.call_count == 0, "teclado de desktop deveria estar suspenso"


@pytest.mark.asyncio
async def test_gamepad_vivo_sob_pause_e_suppress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gp, kbd = await _run_with_gates(monkeypatch, paused=True, suppressed=True)
    assert gp.forward_buttons.call_count > 0, "gamepad congelou com pause + suppress"
    assert kbd.dispatch.call_count == 0


@pytest.mark.asyncio
async def test_gamepad_respeita_grace_period(monkeypatch: pytest.MonkeyPatch) -> None:
    """O gamepad NÃO deve despachar durante o grace-period (anti-ghost-input):
    a imunidade a pause/suppress não pode furar o settling pós-conexão."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 10.0
    )
    fc = FakeController(transport="usb", states=_mk_states(2000))
    mock_evdev = MagicMock()
    mock_evdev.is_available.return_value = True
    mock_evdev.snapshot.return_value = _SnapCross()
    fc._evdev = mock_evdev

    daemon = Daemon(controller=fc, config=_config())
    gp = MagicMock()
    daemon._gamepad_device = gp

    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.06)  # bem dentro do grace de 10s
    daemon.stop()
    await run_task
    assert gp.forward_buttons.call_count == 0, (
        "gamepad despachou durante o grace-period (ghost input)"
    )
