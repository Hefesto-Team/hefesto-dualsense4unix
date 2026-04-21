"""Subcomando `hefesto emulate xbox360 [--on|--off]`.

Cria um gamepad virtual Xbox360 via uinput e fica em primeiro plano,
repassando o input do DualSense físico até Ctrl+C.

Em modo `--on` (default quando rodado), o daemon fica lendo o controle
real e emitindo no virtual. `--off` simplesmente aborta (sem stato
persistente ainda; em integração futura com daemon, manda IPC).
"""
from __future__ import annotations

import asyncio
import contextlib

import typer
from rich.console import Console

console = Console()

app = typer.Typer(
    name="emulate",
    help="Gamepad virtual pra jogos que só reconhecem Xbox.",
    no_args_is_help=True,
)


@app.command("xbox360")
def cmd_xbox360(
    on: bool = typer.Option(True, "--on/--off", help="Ligar/desligar emulação."),
    poll_hz: int = typer.Option(
        60, "--poll-hz", min=10, max=250, help="Taxa de forward em Hz."
    ),
) -> None:
    """Cria device Xbox360 virtual e retransmite input do controle físico."""
    if not on:
        console.print("[yellow]--off sem daemon rodando: nada pra parar[/yellow]")
        raise typer.Exit(code=0)

    try:
        asyncio.run(_run_emulation(poll_hz=poll_hz))
    except KeyboardInterrupt:
        console.print("[dim]emulação interrompida[/dim]")


async def _run_emulation(poll_hz: int) -> None:
    from hefesto.core.backend_pydualsense import PyDualSenseController
    from hefesto.integrations.uinput_gamepad import UinputGamepad

    controller = PyDualSenseController()
    controller.connect()

    gamepad = UinputGamepad()
    if not gamepad.start():
        controller.disconnect()
        console.print("[red]falha ao criar gamepad virtual (uinput)[/red]")
        raise typer.Exit(code=3)

    console.print(
        f"[green]gamepad virtual ativo[/green] — polling {poll_hz}Hz. "
        "Ctrl+C pra encerrar."
    )

    period = 1.0 / poll_hz
    try:
        while True:
            state = controller.read_state()
            snap = (
                controller._evdev.snapshot()
                if controller._evdev.is_available()
                else None
            )
            gamepad.forward_analog(
                lx=state.raw_lx,
                ly=state.raw_ly,
                rx=state.raw_rx,
                ry=state.raw_ry,
                l2=state.l2_raw,
                r2=state.r2_raw,
            )
            if snap is not None:
                gamepad.forward_buttons(snap.buttons_pressed)
            await asyncio.sleep(period)
    finally:
        gamepad.stop()
        with contextlib.suppress(Exception):
            controller.disconnect()


__all__ = ["app"]
