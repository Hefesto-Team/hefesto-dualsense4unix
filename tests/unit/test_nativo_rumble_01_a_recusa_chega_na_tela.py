"""NATIVO-RUMBLE-01, a metade da GUI: a recusa do daemon chega aos olhos dela."""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.daemon.subsystems.rumble import (
    MOTIVO_MODO_NATIVO_MANDA_NOS_MOTORES,
    RUMBLE_RECUSADO_MODO_NATIVO,
)

RESPOSTA_DE_RECUSA: dict[str, Any] = {
    "status": "recusado",
    "desfecho": RUMBLE_RECUSADO_MODO_NATIVO,
    "motivo": MOTIVO_MODO_NATIVO_MANDA_NOS_MOTORES,
    "weak": 0,
    "strong": 0,
    "passthrough": True,
}

RESPOSTA_DE_ACEITE: dict[str, Any] = {
    "status": "ok",
    "desfecho": "aplicado",
    "weak": 160,
    "strong": 220,
}


class TestRumbleSetChecked:
    """A ponte de IPC distingue "recusou" de "aplicou" e de "não respondeu"."""

    def test_recusa_no_corpo_vira_motivo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            ipc_bridge, "_safe_call", lambda *a, **k: (True, RESPOSTA_DE_RECUSA)
        )
        ok, motivo = ipc_bridge.rumble_set_checked(160, 220)
        assert ok is False, "recusa do daemon não pode voltar como sucesso"
        assert motivo == MOTIVO_MODO_NATIVO_MANDA_NOS_MOTORES

    def test_aceite_nao_inventa_motivo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            ipc_bridge, "_safe_call", lambda *a, **k: (True, RESPOSTA_DE_ACEITE)
        )
        assert ipc_bridge.rumble_set_checked(160, 220) == (True, None)

    def test_daemon_mudo_continua_sem_motivo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Transporte caído é (False, None) — a UI aí SIM fala do daemon."""
        monkeypatch.setattr(ipc_bridge, "_safe_call", lambda *a, **k: (False, None))
        assert ipc_bridge.rumble_set_checked(160, 220) == (False, None)

    def test_daemon_velho_sem_o_campo_status_nao_quebra(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O daemon vivo é mais velho que o código: resposta sem `status` vale."""
        monkeypatch.setattr(
            ipc_bridge, "_safe_call", lambda *a, **k: (True, {"weak": 160, "strong": 220})
        )
        assert ipc_bridge.rumble_set_checked(160, 220) == (True, None)
