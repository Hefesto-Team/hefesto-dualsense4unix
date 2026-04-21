"""Subcomando `hefesto test ...`.

Operação direta no controle (não pelo daemon). Útil para exercitar
efeitos sem precisar do daemon rodando. Se quiser operar via daemon
rodando, envie trigger.set/led.set pelo IPC.
"""
from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import Any, Literal

import typer
from rich.console import Console

from hefesto.core.controller import IController
from hefesto.core.led_control import hex_to_rgb
from hefesto.core.trigger_effects import build_from_name

app = typer.Typer(name="test", help="Exercita efeitos direto no hardware.", no_args_is_help=True)
console = Console()


def _parse_params(raw: str | None) -> list[int]:
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    try:
        return [int(p) for p in parts]
    except ValueError as exc:
        raise typer.BadParameter(f"params: inteiros separados por virgula. Erro: {exc}") from None


@app.command("trigger")
def cmd_trigger(
    side: str = typer.Option(..., help="left ou right"),
    mode: str = typer.Option(..., help="Nome do preset (Rigid, Galloping, ...)."),
    params: str | None = typer.Option(None, help="CSV de inteiros: '0,9,7,7,10'"),
    raw: bool = typer.Option(
        False, "--raw", help="mode e valor inteiro (0-255); params sao 7 bytes HID."
    ),
) -> None:
    if side not in ("left", "right"):
        raise typer.BadParameter("side deve ser left ou right")
    side_literal: Literal["left", "right"] = "left" if side == "left" else "right"

    params_list = _parse_params(params)

    if raw:
        from hefesto.core.controller import TriggerEffect

        try:
            mode_int = int(mode)
        except ValueError:
            raise typer.BadParameter("modo --raw exige inteiro em --mode") from None
        if len(params_list) != 7:
            raise typer.BadParameter("modo --raw exige 7 valores em --params")
        effect = TriggerEffect(
            mode=mode_int,
            forces=(
                params_list[0], params_list[1], params_list[2], params_list[3],
                params_list[4], params_list[5], params_list[6],
            ),
        )
    else:
        effect = build_from_name(mode, params_list)

    _apply_on_hardware(lambda c: c.set_trigger(side_literal, effect))
    console.print(f"[green]trigger aplicado: {side_literal} {mode} {params_list}[/green]")


@app.command("led")
def cmd_led(
    color: str = typer.Option(..., help="Cor em hex (#FF0080) ou nome r,g,b."),
) -> None:
    rgb = hex_to_rgb(color) if color.startswith("#") or len(color) == 6 else _parse_rgb_csv(color)
    _apply_on_hardware(lambda c: c.set_led(rgb))
    console.print(f"[green]lightbar: rgb={rgb}[/green]")


@app.command("rumble")
def cmd_rumble(
    weak: int = typer.Option(0, min=0, max=255),
    strong: int = typer.Option(0, min=0, max=255),
) -> None:
    _apply_on_hardware(lambda c: c.set_rumble(weak=weak, strong=strong))
    console.print(f"[green]rumble: weak={weak} strong={strong}[/green]")


def _parse_rgb_csv(value: str) -> tuple[int, int, int]:
    parts = [int(p.strip()) for p in value.split(",")]
    if len(parts) != 3:
        raise typer.BadParameter("formato: R,G,B (3 valores 0-255)")
    for idx, b in enumerate(parts):
        if not (0 <= b <= 255):
            raise typer.BadParameter(f"rgb[{idx}] fora de 0-255")
    return (parts[0], parts[1], parts[2])


def _apply_on_hardware(action: Callable[[IController], Any]) -> None:
    from hefesto.core.backend_pydualsense import PyDualSenseController

    controller = PyDualSenseController()
    try:
        controller.connect()
        action(controller)
    finally:
        with contextlib.suppress(Exception):
            controller.disconnect()


__all__ = ["app"]
