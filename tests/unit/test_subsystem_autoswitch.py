"""Testes unitários do subsystem Autoswitch (isolamento).

Prova que:
  - AutoswitchSubsystem.is_enabled segue config.autoswitch_enabled.
  - AutoswitchSubsystem.stop é idempotente.
  - AutoswitchSubsystem.stop chama autoswitch.stop() quando existe.
  - o desligar do daemon tem um dono só: a utilitária `stop_autoswitch` não volta.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon.subsystems import autoswitch as modulo
from hefesto_dualsense4unix.daemon.subsystems.autoswitch import AutoswitchSubsystem


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


class TestODesligarTemUmDonoSo:
    """O `shutdown` de `daemon/connection.py` derruba `_autoswitch` em linha.

    A utilitária `stop_autoswitch` fazia o mesmo e só a suíte a chamava: duas
    cópias do desligar, que divergiriam na primeira mudança de uma delas.
    Ela saiu em 28/09/2026 (O-CODIGO-SEM-CHAMADOR-LIGA-OU-SAI-01). Quem prova
    o desligar é `tests/unit/test_daemon_shutdown.py`, que sobe o daemon e
    confere `_autoswitch` zerado depois do `shutdown`.
    """

    def test_a_utilitaria_de_desligar_nao_volta(self) -> None:
        assert not hasattr(modulo, "stop_autoswitch")
        assert "stop_autoswitch" not in modulo.__all__
