"""Testes da flag `--brightness` em `hefesto-dualsense4unix led` (FEAT-CLI-PARITY-01).

Mocka o IPC via monkeypatch de `_run_call` do `ipc_bridge`. Não toca
hardware real nem daemon real.
"""
from __future__ import annotations

from typing import Any

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli.app import app

runner = CliRunner()


@pytest.fixture
def ipc_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    """Intercepta `_run_call` e registra chamadas; simula daemon online respondendo OK."""
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_run_call(
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        calls.append((method, dict(params or {})))
        return {"status": "ok"}

    import hefesto_dualsense4unix.app.ipc_bridge as bridge

    monkeypatch.setattr(bridge, "_run_call", fake_run_call)
    return calls


@pytest.fixture
def ipc_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simula daemon offline: `_run_call` levanta FileNotFoundError."""

    def fake_run_call(
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        raise FileNotFoundError("socket inexistente")

    import hefesto_dualsense4unix.app.ipc_bridge as bridge

    monkeypatch.setattr(bridge, "_run_call", fake_run_call)


def test_led_sem_brightness_via_ipc(ipc_calls: list[tuple[str, dict[str, Any]]]) -> None:
    result = runner.invoke(app, ["led", "--color", "#ff8800"])
    assert result.exit_code == 0, result.output
    assert ipc_calls == [("led.set", {"rgb": [255, 136, 0]})]
    assert "via daemon" in result.output


def test_led_com_brightness_via_ipc(ipc_calls: list[tuple[str, dict[str, Any]]]) -> None:
    result = runner.invoke(app, ["led", "--color", "#ff8800", "--brightness", "50"])
    assert result.exit_code == 0, result.output
    assert ipc_calls == [
        ("led.set", {"rgb": [255, 136, 0], "brightness": 50})
    ]
    assert "brightness=50" in result.output


def test_led_brightness_invalido_baixo() -> None:
    result = runner.invoke(app, ["led", "--color", "#ff8800", "--brightness", "-1"])
    assert result.exit_code != 0
    # Typer deve rejeitar por estar abaixo do min=0.


def test_led_brightness_invalido_alto() -> None:
    result = runner.invoke(app, ["led", "--color", "#ff8800", "--brightness", "101"])
    assert result.exit_code != 0


def test_led_offline_fallback_escala_rgb(
    monkeypatch: pytest.MonkeyPatch,
    ipc_offline: None,
) -> None:
    """Sem daemon: aplica no hardware via `_apply_on_hardware` escalando RGB."""
    applied: list[tuple[int, int, int]] = []

    def fake_apply(action: Any) -> None:
        class FakeController:
            def set_led(self, rgb: tuple[int, int, int]) -> None:
                applied.append(rgb)

        action(FakeController())

    import hefesto_dualsense4unix.cli.cmd_test as cmd_test

    monkeypatch.setattr(cmd_test, "_apply_on_hardware", fake_apply)

    result = runner.invoke(app, ["led", "--color", "#ff8800", "--brightness", "50"])
    assert result.exit_code == 0, result.output
    # 50% de 255 = 127.5 -> round(.) = 128 (banker); 50% de 136 = 68; 50% de 0 = 0.
    assert applied == [(128, 68, 0)]
    assert "hardware" in result.output


def test_led_offline_sem_brightness_preserva_rgb(
    monkeypatch: pytest.MonkeyPatch,
    ipc_offline: None,
) -> None:
    applied: list[tuple[int, int, int]] = []

    def fake_apply(action: Any) -> None:
        class FakeController:
            def set_led(self, rgb: tuple[int, int, int]) -> None:
                applied.append(rgb)

        action(FakeController())

    import hefesto_dualsense4unix.cli.cmd_test as cmd_test

    monkeypatch.setattr(cmd_test, "_apply_on_hardware", fake_apply)

    result = runner.invoke(app, ["led", "--color", "#ff8800"])
    assert result.exit_code == 0, result.output
    assert applied == [(255, 136, 0)]
