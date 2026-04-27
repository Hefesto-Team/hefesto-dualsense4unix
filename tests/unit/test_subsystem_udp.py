"""Testes unitários do subsystem UDP (isolamento).

Prova que:
  - UdpSubsystem.is_enabled segue config.udp_enabled.
  - UdpSubsystem.stop é idempotente.
  - UdpSubsystem.stop chama server.stop() quando server existe.
  - stop_udp é noop quando daemon._udp_server is None.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from hefesto_dualsense4unix.daemon.subsystems.udp import UdpSubsystem, stop_udp


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
        await subsystem.stop()  # _server is None — não deve lançar

    @pytest.mark.asyncio
    async def test_stop_chama_server_stop(self) -> None:
        subsystem = UdpSubsystem()
        mock_server = MagicMock()
        mock_server.stop = AsyncMock()
        subsystem._server = mock_server
        await subsystem.stop()
        mock_server.stop.assert_called_once()
        assert subsystem._server is None


class TestStopUdp:
    @pytest.mark.asyncio
    async def test_stop_udp_noop_sem_server(self) -> None:
        daemon = MagicMock()
        daemon._udp_server = None
        await stop_udp(daemon)  # não deve lançar

    @pytest.mark.asyncio
    async def test_stop_udp_chama_stop_e_zera_referencia(self) -> None:
        daemon = MagicMock()
        mock_server = MagicMock()
        mock_server.stop = AsyncMock()
        daemon._udp_server = mock_server
        await stop_udp(daemon)
        mock_server.stop.assert_called_once()
        assert daemon._udp_server is None
