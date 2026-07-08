"""Subcomando `hefesto-dualsense4unix native ...` (FEAT-NATIVE-MODE-01).

Modo Nativo: "release total" do controle — solta o DualSense para o jogo usar
os gatilhos adaptativos NATIVOS da Sony (Sackboy & cia), sem o hefesto no meio.
Tudo via IPC (`native.mode.set` e `daemon.state_full`).

Subcomandos:
    hefesto-dualsense4unix native on
    hefesto-dualsense4unix native off
    hefesto-dualsense4unix native status [--json]
"""
from __future__ import annotations

from typing import Any

import typer
from rich.console import Console

from hefesto_dualsense4unix.cli.ipc_client import IpcError

app = typer.Typer(
    name="native",
    help="Modo Nativo — solta o controle para o jogo (gatilhos nativos da Sony).",
    no_args_is_help=True,
)
console = Console()


def _call_sync(method: str, params: dict[str, Any] | None = None) -> Any:
    from hefesto_dualsense4unix.app.ipc_bridge import _run_call

    try:
        return _run_call(method, params, timeout=1.0)
    except IpcError as exc:
        console.print(f"[red]daemon recusou chamada:[/red] {exc.message}")
        raise typer.Exit(code=2) from None
    except (FileNotFoundError, ConnectionError, OSError) as exc:
        console.print(f"[red]daemon offline[/red] (socket IPC inacessível): {exc}")
        raise typer.Exit(code=3) from None


@app.command("on")
def cmd_on() -> None:
    """Liga o Modo Nativo — solta o controle para o jogo."""
    result = _call_sync("native.mode.set", {"enabled": True})
    ok = isinstance(result, dict) and bool(result.get("native_mode"))
    if ok:
        console.print("[green]Modo Nativo LIGADO[/green] — controle solto para o jogo.")
        console.print(
            "[dim]gatilhos, rumble e LEDs agora são do jogo; emulação desligada.[/dim]"
        )
    else:
        console.print("[yellow]daemon respondeu sem ligar o Modo Nativo[/yellow]")
        raise typer.Exit(code=1)


@app.command("off")
def cmd_off() -> None:
    """Desliga o Modo Nativo — o hefesto reassume (restaura o último perfil)."""
    _call_sync("native.mode.set", {"enabled": False})
    console.print("[green]Modo Nativo DESLIGADO[/green] — hefesto reassumiu o controle.")


@app.command("status")
def cmd_status(
    as_json: bool = typer.Option(False, "--json", help="Saída como JSON."),
) -> None:
    """Mostra se o Modo Nativo está ativo."""
    state = _call_sync("daemon.state_full")
    native = bool(state.get("native_mode")) if isinstance(state, dict) else False
    if as_json:
        console.print_json(data={"native_mode": native})
        return
    if native:
        console.print("Modo Nativo: [green]ligado[/green] (controle solto para o jogo)")
    else:
        console.print("Modo Nativo: [dim]desligado[/dim]")


__all__ = ["app"]
