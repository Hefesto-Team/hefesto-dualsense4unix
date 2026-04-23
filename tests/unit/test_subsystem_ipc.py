"""Testes unitários do subsystem IPC (isolamento).

Prova que:
  - IpcSubsystem.is_enabled segue config.ipc_enabled.
  - IpcSubsystem.stop é idempotente (não lança em _server=None).
  - IpcSubsystem.stop chama server.stop() quando server existe.
  - stop_ipc é noop quando daemon._ipc_server is None.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from hefesto.daemon.subsystems.ipc import IpcSubsystem, stop_ipc


class TestIpcSubsystem:
    def _make_config(self, ipc_enabled: bool) -> MagicMock:
        cfg = MagicMock()
        cfg.ipc_enabled = ipc_enabled
        return cfg

    def test_is_enabled_true(self) -> None:
        subsystem = IpcSubsystem()
        assert subsystem.is_enabled(self._make_config(ipc_enabled=True)) is True

    def test_is_enabled_false(self) -> None:
        subsystem = IpcSubsystem()
        assert subsystem.is_enabled(self._make_config(ipc_enabled=False)) is False

    @pytest.mark.asyncio
    async def test_stop_idempotente_sem_server(self) -> None:
        """stop() sem _server atribuído não lança exceção."""
        subsystem = IpcSubsystem()
        await subsystem.stop()  # _server is None — não deve lançar

    @pytest.mark.asyncio
    async def test_stop_chama_server_stop(self) -> None:
        subsystem = IpcSubsystem()
        mock_server = MagicMock()
        mock_server.stop = AsyncMock()
        subsystem._server = mock_server
        await subsystem.stop()
        mock_server.stop.assert_called_once()
        assert subsystem._server is None


class TestStopIpc:
    @pytest.mark.asyncio
    async def test_stop_ipc_noop_sem_server(self) -> None:
        daemon = MagicMock()
        daemon._ipc_server = None
        await stop_ipc(daemon)  # não deve lançar

    @pytest.mark.asyncio
    async def test_stop_ipc_chama_stop_e_zera_referencia(self) -> None:
        daemon = MagicMock()
        mock_server = MagicMock()
        mock_server.stop = AsyncMock()
        daemon._ipc_server = mock_server
        await stop_ipc(daemon)
        mock_server.stop.assert_called_once()
        assert daemon._ipc_server is None
