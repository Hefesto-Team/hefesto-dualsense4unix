"""Testes unitários do subsystem Autoswitch (isolamento).

Prova que:
  - AutoswitchSubsystem.is_enabled segue config.autoswitch_enabled.
  - AutoswitchSubsystem.stop é idempotente.
  - AutoswitchSubsystem.stop chama autoswitch.stop() quando existe.
  - stop_autoswitch é noop quando daemon._autoswitch is None.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon.subsystems.autoswitch import (
    AutoswitchSubsystem,
    stop_autoswitch,
)


class TestAutoswitchSubsystem:
    def _make_config(self, autoswitch_enabled: bool) -> MagicMock:
        cfg = MagicMock()
        cfg.autoswitch_enabled = autoswitch_enabled
        return cfg

    def test_is_enabled_true(self) -> None:
        subsystem = AutoswitchSubsystem()
        assert subsystem.is_enabled(self._make_config(autoswitch_enabled=True)) is True

    def test_is_enabled_false(self) -> None:
        subsystem = AutoswitchSubsystem()
        assert subsystem.is_enabled(self._make_config(autoswitch_enabled=False)) is False

    @pytest.mark.asyncio
    async def test_stop_idempotente_sem_autoswitch(self) -> None:
        subsystem = AutoswitchSubsystem()
        await subsystem.stop()  # _autoswitch is None — não deve lançar

    @pytest.mark.asyncio
    async def test_stop_chama_autoswitch_stop(self) -> None:
        subsystem = AutoswitchSubsystem()
        mock_sw = MagicMock()
        subsystem._autoswitch = mock_sw
        await subsystem.stop()
        mock_sw.stop.assert_called_once()
        assert subsystem._autoswitch is None


class TestStopAutoswitch:
    @pytest.mark.asyncio
    async def test_stop_autoswitch_noop_sem_autoswitch(self) -> None:
        daemon = MagicMock()
        daemon._autoswitch = None
        await stop_autoswitch(daemon)  # não deve lançar

    @pytest.mark.asyncio
    async def test_stop_autoswitch_chama_stop(self) -> None:
        daemon = MagicMock()
        mock_sw = MagicMock()
        daemon._autoswitch = mock_sw
        await stop_autoswitch(daemon)
        mock_sw.stop.assert_called_once()
        assert daemon._autoswitch is None
