"""Subcomando `hefesto-dualsense4unix gamepad ...` (FEAT-DSX-GAMEPAD-FLAVOR-01).

Liga/desliga o gamepad virtual NO DAEMON (via IPC `gamepad.emulation.set`),
não como processo avulso — assim há UM leitor do controle (sem input dobrado
do antigo `emulate xbox360`). A máscara (`flavor`) define o que o jogo vê:

    hefesto-dualsense4unix gamepad on  [--flavor dualsense|xbox]
    hefesto-dualsense4unix gamepad off
    hefesto-dualsense4unix gamepad status [--json]

`dualsense` (default) → prompts de PlayStation; `xbox` → fallback p/ jogos
XInput-only. Erros de IPC (daemon offline) viram mensagem clara sem traceback.
"""
from __future__ import annotations

from typing import Any

import typer
from rich.console import Console

from hefesto_dualsense4unix.cli.ipc_client import IpcError

app = typer.Typer(
    name="gamepad",
    help="Gamepad virtual (DualSense/Xbox) pelo daemon — máscara p/ os jogos.",
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
def cmd_on(
    flavor: str | None = typer.Option(
        None,
        "--flavor",
        "-f",
        help=(
            "Como o jogo vê o controle: xbox (a vibração funciona em mais jogos) "
            "| dualsense (botões de PlayStation). Sem esta opção, mantém a que já "
            "está configurada."
        ),
    ),
) -> None:
    """Liga o gamepad virtual no daemon.

    HARM-08: o default era `dualsense` HARDCODED aqui, enquanto o daemon e a GUI
    já usavam `xbox` — então um `gamepad on` sem argumento TROCAVA a máscara de
    quem tinha Xbox configurado e matava o rumble in-game, em silêncio. Sem
    `--flavor` não mandamos o campo: o daemon mantém a máscara atual.
    """
    params: dict[str, Any] = {"enabled": True}
    if flavor is not None:
        params["flavor"] = flavor
    result = _call_sync("gamepad.emulation.set", params)
    ok = isinstance(result, dict) and bool(result.get("enabled"))
    active = result.get("flavor") if isinstance(result, dict) else None
    if ok:
        console.print(f"[green]gamepad virtual ligado[/green] (máscara: {active})")
    else:
        console.print(
            "[yellow]daemon respondeu sem habilitar (uinput disponível?)[/yellow]"
        )
        raise typer.Exit(code=1)


@app.command("off")
def cmd_off() -> None:
    """Desliga o gamepad virtual no daemon (libera o grab do controle)."""
    _call_sync("gamepad.emulation.set", {"enabled": False})
    console.print("[green]gamepad virtual desligado[/green]")


@app.command("status")
def cmd_status(
    as_json: bool = typer.Option(False, "--json", help="Saída como JSON (scripts)."),
) -> None:
    """Mostra o estado atual do gamepad virtual no daemon."""
    state = _call_sync("daemon.state_full")
    gp = state.get("gamepad_emulation") if isinstance(state, dict) else None
    if not isinstance(gp, dict):
        gp = {"enabled": None, "flavor": None}

    if as_json:
        console.print_json(data=gp)
        return

    enabled = gp.get("enabled")
    flavor = gp.get("flavor")
    if enabled is None:
        console.print(
            "[yellow]estado indisponível — daemon não expõe estado do gamepad.[/yellow]"
        )
        raise typer.Exit(code=1)

    label = "[green]ligado[/green]" if enabled else "[dim]desligado[/dim]"
    console.print(f"gamepad virtual: {label}")
    if flavor:
        console.print(f"máscara (flavor): {flavor}")


__all__ = ["app"]
