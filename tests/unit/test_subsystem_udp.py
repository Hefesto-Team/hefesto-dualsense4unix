"""Testes unitários do subsystem UDP (isolamento)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from hefesto_dualsense4unix.daemon.subsystems import udp as modulo
from hefesto_dualsense4unix.daemon.subsystems.udp import UdpSubsystem


class TestUdpSubsystem:
    def _make_config(self, udp_enabled: bool) -> MagicMock:
        cfg = MagicMock()
        cfg.udp_enabled = udp_enabled
        return cfg

    def test_is_enabled_true(self) -> None:
        subsystem = UdpSubsystem()
        assert subsystem.is_enabled(self._make_config(udp_enabled=True)) is True

    def test_is_enabled_false(self) -> None:
        subsystem = UdpSubsystem()
        assert subsystem.is_enabled(self._make_config(udp_enabled=False)) is False

    @pytest.mark.asyncio
    async def test_stop_idempotente_sem_server(self) -> None:
        subsystem = UdpSubsystem()
        await subsystem.stop()

    @pytest.mark.asyncio
    async def test_stop_chama_server_stop(self) -> None:
        subsystem = UdpSubsystem()
        mock_server = MagicMock()
        mock_server.stop = AsyncMock()
        subsystem._server = mock_server
        await subsystem.stop()
        mock_server.stop.assert_called_once()
        assert subsystem._server is None


class TestODesligarTemUmDonoSo:
    """O `shutdown` de `daemon/connection.py` derruba `_udp_server` em linha."""

    def test_a_utilitaria_de_desligar_nao_volta(self) -> None:
        assert not hasattr(modulo, "stop_udp")
        assert "stop_udp" not in modulo.__all__
