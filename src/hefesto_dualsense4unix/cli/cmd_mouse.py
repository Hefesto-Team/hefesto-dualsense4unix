"""Subcomando `hefesto-dualsense4unix mouse ...` (FEAT-CLI-PARITY-01).

Paridade CLI com a aba Mouse da GUI. Tudo via IPC (`mouse.emulation.set`
e `daemon.state_full`), não duplica lógica do daemon.

Subcomandos:
    hefesto-dualsense4unix mouse on  [--speed N] [--scroll-speed N]
    hefesto-dualsense4unix mouse off
    hefesto-dualsense4unix mouse status [--json]

Erros de IPC (daemon offline, timeout) viram mensagem clara sem traceback.
"""
from __future__ import annotations

from typing import Any

import typer
from rich.console import Console

from hefesto_dualsense4unix.cli.ipc_client import IpcError

app = typer.Typer(
    name="mouse",
    help="Emulação de mouse+teclado pelo DualSense (via daemon).",
    no_args_is_help=True,
)
console = Console()


def _call_sync(method: str, params: dict[str, Any] | None = None) -> Any:
    """Chama método IPC e converte IpcError/OSError em mensagem amigável.

    Reutiliza `_run_call` do `ipc_bridge` (módulo que NÃO importa GTK no
    topo — a importação de `GLib` é adiada para `call_async`). Portanto
    seguro de usar na CLI sem puxar dependência de GTK.
    """
    from hefesto_dualsense4unix.app.ipc_bridge import _run_call

    try:
        return _run_call(method, params, timeout=1.0)
    except IpcError as exc:
        console.print(f"[red]daemon recusou chamada:[/red] {exc.message}")
        raise typer.Exit(code=2) from None
    except (FileNotFoundError, ConnectionError, OSError) as exc:
        console.print(
            f"[red]daemon offline[/red] (socket IPC inacessível): {exc}"
        )
        raise typer.Exit(code=3) from None


@app.command("on")
def cmd_on(
    speed: int | None = typer.Option(
        None, "--speed", min=1, max=12, help="Velocidade do cursor (1-12)."
    ),
    scroll_speed: int | None = typer.Option(
        None, "--scroll-speed", min=1, max=5, help="Velocidade de scroll (1-5)."
    ),
) -> None:
    """Liga a emulação de mouse no daemon."""
    params: dict[str, Any] = {"enabled": True}
    if speed is not None:
        params["speed"] = speed
    if scroll_speed is not None:
        params["scroll_speed"] = scroll_speed

    result = _call_sync("mouse.emulation.set", params)
    ok = isinstance(result, dict) and bool(result.get("enabled"))
    if ok:
        console.print("[green]emulação de mouse ligada[/green]")
    else:
        console.print(
            "[yellow]daemon respondeu sem habilitar (uinput disponível?)[/yellow]"
        )
        raise typer.Exit(code=1)


@app.command("off")
def cmd_off() -> None:
    """Desliga a emulação de mouse no daemon."""
    _call_sync("mouse.emulation.set", {"enabled": False})
    console.print("[green]emulação de mouse desligada[/green]")


@app.command("status")
def cmd_status(
    as_json: bool = typer.Option(
        False, "--json", help="Saída como JSON (para scripts)."
    ),
) -> None:
    """Mostra estado atual da emulação de mouse no daemon."""
    state = _call_sync("daemon.state_full")
    mouse = state.get("mouse_emulation") if isinstance(state, dict) else None
    if not isinstance(mouse, dict):
        # Daemon antigo (pré-paridade): não expõe estado do mouse.
        mouse = {"enabled": None, "speed": None, "scroll_speed": None}

    if as_json:
        console.print_json(data=mouse)
        return

    enabled = mouse.get("enabled")
    speed = mouse.get("speed")
    scroll = mouse.get("scroll_speed")
    if enabled is None:
        console.print(
            "[yellow]estado indisponível — daemon não expõe estado do mouse.[/yellow]"
        )
        console.print("[dim]atualize o daemon para versão com mouse_emulation no state_full.[/dim]")
        raise typer.Exit(code=1)

    label = "[green]ligada[/green]" if enabled else "[dim]desligada[/dim]"
    console.print(f"emulação: {label}")
    if speed is not None:
        console.print(f"velocidade (cursor): {speed}")
    if scroll is not None:
        console.print(f"velocidade (scroll): {scroll}")


__all__ = ["app"]

# Nota de implementação:
# - `mouse.emulation.set` já existe em ipc_server (FEAT-MOUSE-01).
# - `daemon.state_full` é estendido nesta sprint (FEAT-CLI-PARITY-01) para
#   incluir bloco `mouse_emulation` com {enabled, speed, scroll_speed}.
#   Sem isso, `status` mostra "indisponível" sem estourar traceback.
