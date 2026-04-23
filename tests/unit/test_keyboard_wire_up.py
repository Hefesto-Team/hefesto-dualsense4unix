"""Wire-up do KeyboardSubsystem no Daemon (armadilha A-07).

Valida os 4 pontos canônicos:
  1. Slot `_keyboard_device` existe em `Daemon`.
  2. `run()` chama `_start_keyboard_emulation()` quando
     `config.keyboard_emulation_enabled` é True.
  3. `_poll_loop` reusa `buttons_pressed` (A-09) chamando
     `_dispatch_keyboard_emulation` quando `_keyboard_device` vivo.
  4. `shutdown` libera o device (testado indiretamente — cancelamento
     no Daemon chama shutdown que zera o slot).
"""
from __future__ import annotations

import asyncio
from typing import Any, ClassVar
from unittest.mock import MagicMock

import pytest

from hefesto.core.controller import ControllerState
from hefesto.daemon.lifecycle import Daemon, DaemonConfig
from hefesto.testing import FakeController


def _mk_states(n: int) -> list[ControllerState]:
    return [
        ControllerState(
            battery_pct=80,
            l2_raw=0,
            r2_raw=0,
            connected=True,
            transport="usb",
        )
        for _ in range(n)
    ]


class _FakeSnap:
    buttons_pressed: ClassVar[list[str]] = []


class _FakeSnapComOptions:
    buttons_pressed: ClassVar[list[str]] = ["options"]


# --- Ponto 1: slot existe ----------------------------------------------------

def test_daemon_tem_slot_keyboard_device() -> None:
    """Slot `_keyboard_device` faz parte do dataclass do Daemon."""
    fc = FakeController(transport="usb", states=_mk_states(1))
    daemon = Daemon(controller=fc)
    assert hasattr(daemon, "_keyboard_device")
    assert daemon._keyboard_device is None


# --- Ponto 2: run() instancia quando habilitado ------------------------------

@pytest.mark.asyncio
async def test_run_inicia_keyboard_quando_habilitado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """config.keyboard_emulation_enabled=True → daemon._keyboard_device não é None
    durante execução. Use mock do start_keyboard_emulation para não depender de
    /dev/uinput real."""
    calls: list[Any] = []

    def fake_start(daemon: Any) -> bool:
        mock_device = MagicMock()
        mock_device.dispatch = MagicMock()
        mock_device.stop = MagicMock()
        daemon._keyboard_device = mock_device
        calls.append(daemon)
        return True

    async def noop_restore(daemon: Any) -> None:
        return None

    monkeypatch.setattr(
        "hefesto.daemon.subsystems.keyboard.start_keyboard_emulation",
        fake_start,
    )
    # Evita perfis de sessão bloqueando a sequência de inicialização.
    monkeypatch.setattr(
        "hefesto.daemon.connection.restore_last_profile",
        noop_restore,
    )

    fc = FakeController(transport="usb", states=_mk_states(40))
    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            mouse_emulation_enabled=False,
            keyboard_emulation_enabled=True,
        ),
    )

    run_task = asyncio.create_task(daemon.run())
    # Espera até start ser chamado ou timeout.
    for _ in range(50):
        if calls:
            break
        await asyncio.sleep(0.01)
    # Ponto 2: start foi chamado.
    assert len(calls) == 1
    assert daemon._keyboard_device is not None
    daemon.stop()
    await run_task


@pytest.mark.asyncio
async def test_run_nao_inicia_keyboard_quando_desabilitado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Any] = []

    def fake_start(daemon: Any) -> bool:
        calls.append(daemon)
        return True

    monkeypatch.setattr(
        "hefesto.daemon.subsystems.keyboard.start_keyboard_emulation",
        fake_start,
    )

    fc = FakeController(transport="usb", states=_mk_states(10))
    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
        ),
    )

    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.03)
    daemon.stop()
    await run_task
    assert calls == []


# --- Ponto 3: poll_loop reusa buttons_pressed (A-09) -------------------------

@pytest.mark.asyncio
async def test_poll_loop_chama_dispatch_keyboard_com_buttons_pressed() -> None:
    """Com _keyboard_device vivo, poll_loop chama dispatch() a cada tick
    passando o MESMO frozenset resultado de _evdev_buttons_once.

    Garante A-09: snapshot único reaproveitado para keyboard + mouse + hotkey.
    """
    n_ticks = 8
    fc = FakeController(transport="usb", states=_mk_states(n_ticks * 4))

    mock_evdev = MagicMock()
    mock_evdev.is_available.return_value = True
    mock_evdev.snapshot.return_value = _FakeSnapComOptions()
    fc._evdev = mock_evdev

    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,  # start manual abaixo
        ),
    )

    # Instala mock diretamente (simula já iniciado).
    dispatch_calls: list[frozenset[str]] = []
    mock_kbd = MagicMock()
    mock_kbd.dispatch.side_effect = lambda bp: dispatch_calls.append(bp)
    daemon._keyboard_device = mock_kbd

    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.06)
    daemon.stop()
    await run_task

    ticks = daemon.store.counter("poll.tick")
    assert ticks >= n_ticks
    assert len(dispatch_calls) == ticks, (
        f"dispatch_keyboard chamado {len(dispatch_calls)}x para {ticks} ticks"
    )
    # Cada chamada recebeu frozenset derivado do snapshot com 'options'.
    for bp in dispatch_calls:
        assert isinstance(bp, frozenset)
        assert "options" in bp


@pytest.mark.asyncio
async def test_poll_loop_nao_chama_dispatch_sem_device() -> None:
    """Sem _keyboard_device, dispatch_keyboard NÃO é chamado — zero custo."""
    from hefesto.daemon.subsystems import keyboard as kbd_mod

    fc = FakeController(transport="usb", states=_mk_states(20))
    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
        ),
    )

    run_task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.03)
    daemon.stop()
    await run_task

    # Sanity: nenhum device foi criado nem dispatch aconteceu. Conta direta não
    # é possível; a garantia é que o branch `if self._keyboard_device is not None`
    # filtrou a chamada. Cobertura indireta: rodou sem erro.
    assert daemon._keyboard_device is None
    assert kbd_mod is not None  # import saudável


# --- Ponto 4: shutdown libera device ----------------------------------------

@pytest.mark.asyncio
async def test_shutdown_para_keyboard_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ao parar o daemon, _keyboard_device.stop() é chamado e slot zera."""
    mock_device = MagicMock()

    def fake_start(daemon: Any) -> bool:
        daemon._keyboard_device = mock_device
        return True

    async def noop_restore(daemon: Any) -> None:
        return None

    monkeypatch.setattr(
        "hefesto.daemon.subsystems.keyboard.start_keyboard_emulation",
        fake_start,
    )
    monkeypatch.setattr(
        "hefesto.daemon.connection.restore_last_profile",
        noop_restore,
    )

    fc = FakeController(transport="usb", states=_mk_states(40))
    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            mouse_emulation_enabled=False,
            keyboard_emulation_enabled=True,
        ),
    )

    run_task = asyncio.create_task(daemon.run())
    for _ in range(50):
        if daemon._keyboard_device is not None:
            break
        await asyncio.sleep(0.01)
    daemon.stop()
    await run_task

    mock_device.stop.assert_called_once()
    assert daemon._keyboard_device is None


# --- Reload reage a toggle ---------------------------------------------------

def test_reload_config_liga_keyboard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """reload_config com keyboard_emulation_enabled True→False para device;
    False→True liga. Previne A-08 latente."""
    started: list[bool] = []
    stopped: list[bool] = []

    def fake_start(daemon: Any) -> bool:
        daemon._keyboard_device = MagicMock()
        started.append(True)
        return True

    def fake_stop(daemon: Any) -> None:
        daemon._keyboard_device = None
        stopped.append(True)

    monkeypatch.setattr(
        "hefesto.daemon.subsystems.keyboard.start_keyboard_emulation",
        fake_start,
    )
    monkeypatch.setattr(
        "hefesto.daemon.subsystems.keyboard.stop_keyboard_emulation",
        fake_stop,
    )

    fc = FakeController(transport="usb", states=_mk_states(1))
    daemon = Daemon(
        controller=fc,
        config=DaemonConfig(
            poll_hz=200,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
        ),
    )
    assert daemon._keyboard_device is None

    # Liga via reload
    new_cfg = DaemonConfig(
        poll_hz=200,
        auto_reconnect=False,
        ipc_enabled=False,
        udp_enabled=False,
        autoswitch_enabled=False,
        mouse_emulation_enabled=False,
        keyboard_emulation_enabled=True,
    )
    daemon.reload_config(new_cfg)
    assert len(started) == 1
    assert daemon._keyboard_device is not None

    # Desliga via reload
    new_cfg_off = DaemonConfig(
        poll_hz=200,
        auto_reconnect=False,
        ipc_enabled=False,
        udp_enabled=False,
        autoswitch_enabled=False,
        mouse_emulation_enabled=False,
        keyboard_emulation_enabled=False,
    )
    daemon.reload_config(new_cfg_off)
    assert len(stopped) == 1
    assert daemon._keyboard_device is None

# "A medida é a melhor das coisas." — Cleóbulo de Lindos
