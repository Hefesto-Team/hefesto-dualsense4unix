"""`hefesto-dualsense4unix gamepad on/off` — a máscara não pode mudar sozinha.

HARM-08 (auditoria de harmonia, 2026-07-15): o `--flavor` tinha default
``"dualsense"`` HARDCODED no comando, enquanto o daemon e a GUI já usavam
``xbox`` (`DEFAULT_FLAVOR`) desde o SPRINT-GAME-RUMBLE-01. Resultado: um
`gamepad on` sem argumento — o gesto mais natural que existe — **trocava** a
máscara de quem tinha Xbox configurado e **matava o rumble in-game**, em
silêncio. O mesmo gesto ligava máscaras diferentes conforme a porta de entrada
(GUI/applet/CLI).

O contrato do daemon (`ipc_handlers._handle_gamepad_emulation_set`) sempre foi
"flavor é opcional; mantém o atual se ausente" — a CLI é que não o respeitava.
"""
from __future__ import annotations

from typing import Any

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli.app import app

runner = CliRunner()


@pytest.fixture
def mock_ipc(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    registry: dict[str, Any] = {
        "calls": [],
        "response": {"status": "ok", "enabled": True, "flavor": "xbox"},
    }

    def fake_run_call(
        method: str, params: dict[str, Any] | None = None, timeout: float | None = None
    ) -> Any:
        registry["calls"].append((method, dict(params or {})))
        return registry["response"]

    import hefesto_dualsense4unix.app.ipc_bridge as bridge

    monkeypatch.setattr(bridge, "_run_call", fake_run_call)
    return registry


def test_on_sem_flavor_nao_manda_o_campo(mock_ipc: dict[str, Any]) -> None:
    """Sem o campo, o daemon preserva a máscara já configurada."""
    result = runner.invoke(app, ["gamepad", "on"])

    assert result.exit_code == 0
    (method, params), = mock_ipc["calls"]
    assert method == "gamepad.emulation.set"
    assert params == {"enabled": True}
    assert "flavor" not in params


def test_on_sem_flavor_nao_derruba_xbox_configurado(mock_ipc: dict[str, Any]) -> None:
    """O caso real: quem tinha Xbox (rumble ok) rodava `gamepad on` e perdia a vibração."""
    mock_ipc["response"] = {"status": "ok", "enabled": True, "flavor": "xbox"}

    result = runner.invoke(app, ["gamepad", "on"])

    (_method, params), = mock_ipc["calls"]
    assert params.get("flavor") != "dualsense"
    assert "xbox" in result.stdout


@pytest.mark.parametrize("flavor", ["xbox", "dualsense"])
def test_on_com_flavor_explicito_manda_o_campo(
    mock_ipc: dict[str, Any], flavor: str
) -> None:
    mock_ipc["response"] = {"status": "ok", "enabled": True, "flavor": flavor}

    result = runner.invoke(app, ["gamepad", "on", "--flavor", flavor])

    assert result.exit_code == 0
    (_method, params), = mock_ipc["calls"]
    assert params == {"enabled": True, "flavor": flavor}


def test_on_forma_curta_tambem_manda(mock_ipc: dict[str, Any]) -> None:
    runner.invoke(app, ["gamepad", "on", "-f", "xbox"])

    (_method, params), = mock_ipc["calls"]
    assert params["flavor"] == "xbox"


def test_off_nao_menciona_mascara(mock_ipc: dict[str, Any]) -> None:
    mock_ipc["response"] = {"status": "ok", "enabled": False}

    result = runner.invoke(app, ["gamepad", "off"])

    assert result.exit_code == 0
    (_method, params), = mock_ipc["calls"]
    assert params == {"enabled": False}


def test_daemon_sem_habilitar_falha_com_codigo(mock_ipc: dict[str, Any]) -> None:
    mock_ipc["response"] = {"status": "ok", "enabled": False, "flavor": None}

    result = runner.invoke(app, ["gamepad", "on"])

    assert result.exit_code == 1


def test_help_orienta_pela_consequencia_nao_pelo_jargao() -> None:
    """O help dizia 'XInput-only'/'prompts PS' e não contava o que importa."""
    result = runner.invoke(app, ["gamepad", "on", "--help"])

    saida = result.stdout.lower()
    assert "vibra" in saida
    assert "xinput-only" not in saida
