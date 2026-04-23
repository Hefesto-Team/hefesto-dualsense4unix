"""Testes dos subcomandos `hefesto mouse on/off/status` (FEAT-CLI-PARITY-01)."""
from __future__ import annotations

import json
from typing import Any

import pytest
from typer.testing import CliRunner

from hefesto.cli.app import app
from hefesto.cli.ipc_client import IpcError

runner = CliRunner()


@pytest.fixture
def mock_ipc(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Mocka `_run_call` com um registro mutável e uma resposta configurável.

    - registry["calls"] -> lista de (method, params)
    - registry["response"] -> resposta padrão (override via atribuição)
    - registry["raise"] -> exceção pra levantar (caso != None)
    """
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

    import hefesto.app.ipc_bridge as bridge

    monkeypatch.setattr(bridge, "_run_call", fake_run_call)
    return registry


def test_mouse_on_sem_parametros(mock_ipc: dict[str, Any]) -> None:
    mock_ipc["response"] = {"status": "ok", "enabled": True}
    result = runner.invoke(app, ["mouse", "on"])
    assert result.exit_code == 0, result.output
    assert mock_ipc["calls"] == [("mouse.emulation.set", {"enabled": True})]
    assert "ligada" in result.output


def test_mouse_on_com_parametros(mock_ipc: dict[str, Any]) -> None:
    mock_ipc["response"] = {"status": "ok", "enabled": True}
    result = runner.invoke(app, ["mouse", "on", "--speed", "8", "--scroll-speed", "2"])
    assert result.exit_code == 0, result.output
    assert mock_ipc["calls"] == [
        ("mouse.emulation.set", {"enabled": True, "speed": 8, "scroll_speed": 2})
    ]


def test_mouse_on_daemon_nao_habilitou(mock_ipc: dict[str, Any]) -> None:
    mock_ipc["response"] = {"status": "failed", "enabled": False}
    result = runner.invoke(app, ["mouse", "on"])
    assert result.exit_code == 1
    assert "sem habilitar" in result.output


def test_mouse_off(mock_ipc: dict[str, Any]) -> None:
    mock_ipc["response"] = {"status": "ok", "enabled": False}
    result = runner.invoke(app, ["mouse", "off"])
    assert result.exit_code == 0, result.output
    assert mock_ipc["calls"] == [("mouse.emulation.set", {"enabled": False})]
    assert "desligada" in result.output


def test_mouse_status_humano(mock_ipc: dict[str, Any]) -> None:
    mock_ipc["response"] = {
        "connected": True,
        "mouse_emulation": {"enabled": True, "speed": 8, "scroll_speed": 3},
    }
    result = runner.invoke(app, ["mouse", "status"])
    assert result.exit_code == 0, result.output
    assert mock_ipc["calls"] == [("daemon.state_full", {})]
    assert "ligada" in result.output
    assert "8" in result.output
    assert "3" in result.output


def test_mouse_status_json(mock_ipc: dict[str, Any]) -> None:
    mock_ipc["response"] = {
        "connected": True,
        "mouse_emulation": {"enabled": False, "speed": 6, "scroll_speed": 1},
    }
    result = runner.invoke(app, ["mouse", "status", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload == {"enabled": False, "speed": 6, "scroll_speed": 1}


def test_mouse_status_daemon_antigo_sem_bloco(mock_ipc: dict[str, Any]) -> None:
    """Daemon pré-paridade: state_full não retorna `mouse_emulation`."""
    mock_ipc["response"] = {"connected": True}  # sem mouse_emulation
    result = runner.invoke(app, ["mouse", "status"])
    assert result.exit_code == 1
    assert "indisponível" in result.output


def test_mouse_daemon_offline_mensagem_clara(mock_ipc: dict[str, Any]) -> None:
    mock_ipc["raise"] = FileNotFoundError("no socket")
    result = runner.invoke(app, ["mouse", "on"])
    assert result.exit_code == 3
    assert "offline" in result.output


def test_mouse_ipc_error_mensagem_clara(mock_ipc: dict[str, Any]) -> None:
    mock_ipc["raise"] = IpcError(-32003, "enabled não eh bool")
    result = runner.invoke(app, ["mouse", "on"])
    assert result.exit_code == 2
    assert "recusou" in result.output
    assert "enabled" in result.output


def test_mouse_on_speed_fora_do_range() -> None:
    result = runner.invoke(app, ["mouse", "on", "--speed", "13"])
    assert result.exit_code != 0


def test_mouse_on_scroll_fora_do_range() -> None:
    result = runner.invoke(app, ["mouse", "on", "--scroll-speed", "6"])
    assert result.exit_code != 0
