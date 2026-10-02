"""Testes unitários do subsystem IPC (isolamento)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from hefesto_dualsense4unix.daemon.subsystems import ipc as modulo
from hefesto_dualsense4unix.daemon.subsystems.ipc import IpcSubsystem


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
        await subsystem.stop()

    @pytest.mark.asyncio
    async def test_stop_chama_server_stop(self) -> None:
        subsystem = IpcSubsystem()
        mock_server = MagicMock()
        mock_server.stop = AsyncMock()
        subsystem._server = mock_server
        await subsystem.stop()
        mock_server.stop.assert_called_once()
        assert subsystem._server is None


class TestODesligarTemUmDonoSo:
    """O `shutdown` de `daemon/connection.py` derruba `_ipc_server` em linha."""

    def test_a_utilitaria_de_desligar_nao_volta(self) -> None:
        assert not hasattr(modulo, "stop_ipc")
        assert "stop_ipc" not in modulo.__all__
