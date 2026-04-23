"""Testes unitários do subsystem Mouse (isolamento).

Prova que:
  - MouseSubsystem.is_enabled segue config.mouse_emulation_enabled.
  - MouseSubsystem.stop é idempotente.
  - stop_mouse_emulation para e descarta o device.
  - dispatch_mouse chama device.dispatch com parâmetros corretos.
  - dispatch_mouse trata exceção silenciosamente.

Nota: start_mouse_emulation depende de UinputMouseDevice (uinput kernel),
portanto os testes de criação usam mocks via atributo direto do daemon.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hefesto.daemon.subsystems.mouse import (
    MouseSubsystem,
    dispatch_mouse,
    stop_mouse_emulation,
)


class TestMouseSubsystem:
    def _make_config(self, enabled: bool) -> MagicMock:
        cfg = MagicMock()
        cfg.mouse_emulation_enabled = enabled
        return cfg

    def test_is_enabled_true(self) -> None:
        subsystem = MouseSubsystem()
        assert subsystem.is_enabled(self._make_config(enabled=True)) is True

    def test_is_enabled_false(self) -> None:
        subsystem = MouseSubsystem()
        assert subsystem.is_enabled(self._make_config(enabled=False)) is False

    @pytest.mark.asyncio
    async def test_stop_idempotente_sem_device(self) -> None:
        subsystem = MouseSubsystem()
        await subsystem.stop()  # _device is None — não deve lançar

    @pytest.mark.asyncio
    async def test_stop_chama_device_stop(self) -> None:
        subsystem = MouseSubsystem()
        mock_dev = MagicMock()
        subsystem._device = mock_dev
        await subsystem.stop()
        mock_dev.stop.assert_called_once()
        assert subsystem._device is None


class TestStopMouseEmulation:
    def _make_daemon(self) -> MagicMock:
        daemon = MagicMock()
        daemon._mouse_device = None
        daemon.config = MagicMock()
        daemon.config.mouse_emulation_enabled = True
        return daemon

    def test_stop_descarta_device(self) -> None:
        daemon = self._make_daemon()
        mock_dev = MagicMock()
        daemon._mouse_device = mock_dev

        stop_mouse_emulation(daemon)

        mock_dev.stop.assert_called_once()
        assert daemon._mouse_device is None
        assert daemon.config.mouse_emulation_enabled is False

    def test_stop_noop_sem_device(self) -> None:
        daemon = self._make_daemon()
        daemon._mouse_device = None
        stop_mouse_emulation(daemon)  # não deve lançar


class TestDispatchMouse:
    def _make_state(self) -> MagicMock:
        state = MagicMock()
        state.raw_lx = 128
        state.raw_ly = 128
        state.raw_rx = 128
        state.raw_ry = 128
        state.l2_raw = 0
        state.r2_raw = 0
        return state

    def test_dispatch_chama_device_com_parametros_corretos(self) -> None:
        daemon = MagicMock()
        mock_dev = MagicMock()
        daemon._mouse_device = mock_dev
        state = self._make_state()
        buttons = frozenset({"cross"})

        dispatch_mouse(daemon, state, buttons)

        mock_dev.dispatch.assert_called_once_with(
            lx=128, ly=128, rx=128, ry=128, l2=0, r2=0, buttons=buttons
        )

    def test_dispatch_noop_sem_device(self) -> None:
        daemon = MagicMock()
        daemon._mouse_device = None
        state = self._make_state()
        dispatch_mouse(daemon, state, frozenset())  # não deve lançar

    def test_dispatch_trata_excecao(self) -> None:
        daemon = MagicMock()
        mock_dev = MagicMock()
        mock_dev.dispatch.side_effect = RuntimeError("falha dispatch")
        daemon._mouse_device = mock_dev
        state = self._make_state()

        dispatch_mouse(daemon, state, frozenset())  # não deve lançar
