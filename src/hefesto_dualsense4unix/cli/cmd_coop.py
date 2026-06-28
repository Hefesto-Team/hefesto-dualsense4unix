"""Subcomando `hefesto-dualsense4unix coop ...` (FEAT-DSX-COOP-LOCAL-01).

Liga/desliga o CO-OP LOCAL no daemon (via IPC `coop.set`). Com o co-op ligado,
cada controle físico vira um jogador SEPARADO (P1, P2, …) com seu próprio
gamepad virtual — ao contrário do modo padrão "N controles, 1 player" (todos
recebem o mesmo output e só o primário envia input).

    hefesto-dualsense4unix coop on
    hefesto-dualsense4unix coop off
    hefesto-dualsense4unix coop status [--json]

Pré-requisitos para 2 pessoas jogarem: gamepad virtual ligado
(`hefesto-dualsense4unix gamepad on`) + 2+ controles conectados. Erros de IPC
(daemon offline) viram mensagem clara sem traceback.
"""
from __future__ import annotations

from typing import Any

import typer
from rich.console import Console

from hefesto_dualsense4unix.cli.ipc_client import IpcError

app = typer.Typer(
    name="coop",
    help="Co-op local: cada controle vira um jogador (P1, P2, …).",
    no_args_is_help=True,
)
console = Console()


def _call_sync(method: str, params: dict[str, Any] | None = None) -> Any:
    """Chama método IPC e converte IpcError/OSError em mensagem amigável."""
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
    """Liga o co-op local (cada controle = um jogador)."""
    result = _call_sync("coop.set", {"enabled": True})
    players = result.get("players") if isinstance(result, dict) else None
    console.print("[green]co-op local ligado[/green]")
    if isinstance(players, int):
        console.print(f"jogadores ativos agora: {players}")
    console.print(
        "[dim]lembre: precisa do gamepad virtual ligado (hefesto-dualsense4unix "
        "gamepad on) + 2+ controles.[/dim]"
    )


@app.command("off")
def cmd_off() -> None:
    """Desliga o co-op local (volta ao modo 'N controles, 1 player')."""
    _call_sync("coop.set", {"enabled": False})
    console.print("[green]co-op local desligado[/green]")


@app.command("status")
def cmd_status(
    as_json: bool = typer.Option(False, "--json", help="Saída como JSON (scripts)."),
) -> None:
    """Mostra o estado atual do co-op local no daemon."""
    state = _call_sync("daemon.state_full")
    coop = state.get("coop") if isinstance(state, dict) else None
    if not isinstance(coop, dict):
        coop = {"enabled": None, "players": None}

    if as_json:
        console.print_json(data=coop)
        return

    enabled = coop.get("enabled")
    players = coop.get("players")
    if enabled is None:
        console.print(
            "[yellow]estado indisponível — daemon não expõe estado do co-op.[/yellow]"
        )
        raise typer.Exit(code=1)

    label = "[green]ligado[/green]" if enabled else "[dim]desligado[/dim]"
    console.print(f"co-op local: {label}")
    if isinstance(players, int):
        console.print(f"jogadores ativos: {players}")


__all__ = ["app"]
