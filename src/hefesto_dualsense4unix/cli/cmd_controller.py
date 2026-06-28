"""Subcomando `hefesto-dualsense4unix controller ...` (FEAT-DSX-CONTROLLER-SELECTOR-01).

Escolhe o ALVO das ações de output (lightbar, gatilhos, player-LED, rumble,
mic-LED) quando há 2+ controles conectados. Por padrão o output é broadcast (vai
para TODOS) — por isso, com 2 controles, ambos mostram o Player 1. Com um alvo
selecionado, as ações miram SÓ aquele controle (seleciono o Controle 2 → seto o
LED dele como Player 2).

    hefesto-dualsense4unix controller list
    hefesto-dualsense4unix controller target 2      # mira o Controle 2
    hefesto-dualsense4unix controller target all    # volta ao broadcast (padrão)

A numeração é 1-based e bate com a coluna "Controle N" da listagem (Controle 1 =
primário). Erros de IPC (daemon offline) viram mensagem clara sem traceback.
"""
from __future__ import annotations

from typing import Any

import typer
from rich.console import Console

from hefesto_dualsense4unix.cli.ipc_client import IpcError

app = typer.Typer(
    name="controller",
    help="Seletor de controle: mira as ações de output num controle específico.",
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


@app.command("target")
def cmd_target(
    alvo: str = typer.Argument(
        ...,
        metavar="<n|all>",
        help="Número do controle (1-based, 1=primário) ou 'all' para broadcast.",
    ),
) -> None:
    """Mira as ações de output em UM controle (ou em todos com 'all')."""
    raw = alvo.strip().lower()
    if raw in ("all", "todos", "*"):
        index: int | None = None
    else:
        try:
            n = int(raw)
        except ValueError:
            console.print(
                f"[red]alvo inválido:[/red] '{alvo}' — use um número (1, 2, …) ou 'all'."
            )
            raise typer.Exit(code=2) from None
        if n < 1:
            console.print("[red]alvo inválido:[/red] o número do controle começa em 1.")
            raise typer.Exit(code=2)
        index = n - 1
    result = _call_sync("controller.target.set", {"index": index})
    effective = result.get("target_index") if isinstance(result, dict) else None
    if effective is None:
        console.print("[green]alvo de output: todos os controles[/green] (broadcast)")
    else:
        console.print(f"[green]alvo de output: Controle {int(effective) + 1}[/green]")


@app.command("list")
def cmd_list(
    as_json: bool = typer.Option(False, "--json", help="Saída como JSON (scripts)."),
) -> None:
    """Lista os controles conectados e qual é o alvo de output atual."""
    state = _call_sync("daemon.state_full")
    controllers = state.get("controllers") if isinstance(state, dict) else None
    target_index = state.get("output_target_index") if isinstance(state, dict) else None
    if not isinstance(controllers, list):
        controllers = []
    conectados = [c for c in controllers if isinstance(c, dict) and c.get("connected")]

    if as_json:
        console.print_json(
            data={"controllers": conectados, "output_target_index": target_index}
        )
        return

    if not conectados:
        console.print("[yellow]nenhum controle conectado.[/yellow]")
        raise typer.Exit(code=1)

    alvo_label = (
        "todos (broadcast)" if target_index is None else f"Controle {int(target_index) + 1}"
    )
    console.print(f"alvo de output: [cyan]{alvo_label}[/cyan]")
    for c in conectados:
        idx = int(c.get("index", 0))
        transporte = (c.get("transport") or "?").upper()
        marcas: list[str] = []
        if c.get("is_primary"):
            marcas.append("primário")
        if target_index is not None and idx == target_index:
            marcas.append("alvo")
        sufixo = f" [{', '.join(marcas)}]" if marcas else ""
        console.print(f"  Controle {idx + 1} — {transporte}{sufixo}")


__all__ = ["app"]
