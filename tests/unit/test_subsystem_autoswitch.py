"""Testes unitários do Autoswitch na lista de subsystems (isolamento)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon.subsystems import SUBSYSTEM_REGISTRY
from hefesto_dualsense4unix.daemon.subsystems import autoswitch as modulo

_PASSO = next(p for p in SUBSYSTEM_REGISTRY if p.nome == "autoswitch")


class TestAutoswitchNaLista:
    def test_o_gate_da_lista_segue_a_config(self) -> None:
        assert _PASSO.quando is not None
        assert _PASSO.quando(SimpleNamespace(autoswitch_enabled=True)) is True
        assert _PASSO.quando(SimpleNamespace(autoswitch_enabled=False)) is False

    @pytest.mark.asyncio
    async def test_parada_idempotente_sem_autoswitch(self) -> None:
        assert _PASSO.parada is not None
        daemon = SimpleNamespace(_autoswitch=None)
        await _PASSO.parada(daemon)
        assert daemon._autoswitch is None

    @pytest.mark.asyncio
    async def test_parada_chama_autoswitch_stop_e_zera(self) -> None:
        assert _PASSO.parada is not None
        trocador = MagicMock()
        daemon = SimpleNamespace(_autoswitch=trocador)
        await _PASSO.parada(daemon)
        trocador.stop.assert_called_once()
        assert daemon._autoswitch is None


class TestODesligarTemUmDonoSo:
    """A parada de `_autoswitch` mora na lista (`SUBSYSTEM_REGISTRY`), não em função do módulo."""

    def test_a_utilitaria_de_desligar_nao_volta(self) -> None:
        assert not hasattr(modulo, "stop_autoswitch")
        assert "stop_autoswitch" not in modulo.__all__
