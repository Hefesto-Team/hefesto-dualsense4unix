"""Testes unitários do IPC na lista de subsystems (isolamento)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from hefesto_dualsense4unix.daemon.subsystems import SUBSYSTEM_REGISTRY
from hefesto_dualsense4unix.daemon.subsystems import ipc as modulo

_PASSO = next(p for p in SUBSYSTEM_REGISTRY if p.nome == "ipc")


class TestIpcNaLista:
    def test_o_gate_da_lista_segue_a_config(self) -> None:
        assert _PASSO.quando is not None
        assert _PASSO.quando(SimpleNamespace(ipc_enabled=True)) is True
        assert _PASSO.quando(SimpleNamespace(ipc_enabled=False)) is False

    @pytest.mark.asyncio
    async def test_parada_idempotente_sem_server(self) -> None:
        assert _PASSO.parada is not None
        daemon = SimpleNamespace(_ipc_server=None)
        await _PASSO.parada(daemon)
        assert daemon._ipc_server is None

    @pytest.mark.asyncio
    async def test_parada_chama_server_stop_e_zera(self) -> None:
        assert _PASSO.parada is not None
        servidor = MagicMock()
        servidor.stop = AsyncMock()
        daemon = SimpleNamespace(_ipc_server=servidor)
        await _PASSO.parada(daemon)
        servidor.stop.assert_called_once()
        assert daemon._ipc_server is None


class TestODesligarTemUmDonoSo:
    """A parada de `_ipc_server` mora na lista (`SUBSYSTEM_REGISTRY`), não em função do módulo."""

    def test_a_utilitaria_de_desligar_nao_volta(self) -> None:
        assert not hasattr(modulo, "stop_ipc")
        assert "stop_ipc" not in modulo.__all__
