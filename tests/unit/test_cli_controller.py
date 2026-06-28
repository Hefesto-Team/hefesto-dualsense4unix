"""Testes do subcomando `controller target/list` (FEAT-DSX-CONTROLLER-SELECTOR-01)."""
from __future__ import annotations

from typing import Any

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli.app import app

runner = CliRunner()


@pytest.fixture
def mock_ipc(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Mocka `_run_call` com registro de chamadas e resposta configurável."""
    registry: dict[str, Any] = {"calls": [], "response": {"status": "ok"}, "raise": None}

    def fake_run_call(
        method: str, params: dict[str, Any] | None = None, timeout: float | None = None
    ) -> Any:
        registry["calls"].append((method, dict(params or {})))
        if registry["raise"] is not None:
            raise registry["raise"]
        resp = registry["response"]
        if callable(resp):
            return resp(method, params)
        return resp

    import hefesto_dualsense4unix.app.ipc_bridge as bridge

    monkeypatch.setattr(bridge, "_run_call", fake_run_call)
    return registry


def test_target_numero_mapeia_para_indice_zero_based(mock_ipc: dict[str, Any]) -> None:
    mock_ipc["response"] = {"status": "ok", "target_index": 1}
    result = runner.invoke(app, ["controller", "target", "2"])
    assert result.exit_code == 0, result.output
    # CLI 1-based "2" → IPC index 1.
    assert mock_ipc["calls"] == [("controller.target.set", {"index": 1})]
    assert "Controle 2" in result.output


def test_target_all_vira_broadcast(mock_ipc: dict[str, Any]) -> None:
    mock_ipc["response"] = {"status": "ok", "target_index": None}
    result = runner.invoke(app, ["controller", "target", "all"])
    assert result.exit_code == 0, result.output
    assert mock_ipc["calls"] == [("controller.target.set", {"index": None})]
    assert "todos" in result.output.lower()


def test_target_nao_numerico_falha(mock_ipc: dict[str, Any]) -> None:
    result = runner.invoke(app, ["controller", "target", "xyz"])
    assert result.exit_code == 2
    assert mock_ipc["calls"] == []  # nem chega no IPC


def test_target_zero_invalido(mock_ipc: dict[str, Any]) -> None:
    result = runner.invoke(app, ["controller", "target", "0"])
    assert result.exit_code == 2
    assert mock_ipc["calls"] == []


def test_list_mostra_controles_e_alvo(mock_ipc: dict[str, Any]) -> None:
    mock_ipc["response"] = {
        "controllers": [
            {"index": 0, "connected": True, "transport": "bt", "is_primary": True},
            {"index": 1, "connected": True, "transport": "usb", "is_primary": False},
        ],
        "output_target_index": 1,
    }
    result = runner.invoke(app, ["controller", "list"])
    assert result.exit_code == 0, result.output
    assert mock_ipc["calls"] == [("daemon.state_full", {})]
    assert "Controle 1" in result.output
    assert "Controle 2" in result.output
    assert "alvo" in result.output.lower()


def test_list_json(mock_ipc: dict[str, Any]) -> None:
    mock_ipc["response"] = {
        "controllers": [
            {"index": 0, "connected": True, "transport": "usb", "is_primary": True},
        ],
        "output_target_index": None,
    }
    result = runner.invoke(app, ["controller", "list", "--json"])
    assert result.exit_code == 0, result.output
    assert '"output_target_index"' in result.output


def test_list_sem_controles(mock_ipc: dict[str, Any]) -> None:
    mock_ipc["response"] = {"controllers": [], "output_target_index": None}
    result = runner.invoke(app, ["controller", "list"])
    assert result.exit_code == 1
    assert "nenhum controle" in result.output.lower()
