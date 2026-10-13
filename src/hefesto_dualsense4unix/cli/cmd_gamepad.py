"""Subcomando `hefesto-dualsense4unix gamepad ...` (FEAT-DSX-GAMEPAD-FLAVOR-01)."""
from __future__ import annotations

from typing import Any

import typer
from rich.console import Console

from hefesto_dualsense4unix.cli.cmd_steam import app as steam_input_app
from hefesto_dualsense4unix.cli.ipc_client import IpcError

app = typer.Typer(
    name="gamepad",
    help="Gamepad virtual (DualSense/Xbox) pelo daemon — máscara p/ os jogos.",
    no_args_is_help=True,
)
console = Console()

app.add_typer(steam_input_app, name="steam-input")


def _call_sync(method: str, params: dict[str, Any] | None = None) -> Any:
    """Chama método IPC e converte IpcError/OSError em mensagem amigável."""
    from hefesto_dualsense4unix.app.ipc_bridge import (
        FRASE_DO_PRAZO_VENCIDO,
        _run_call,
        prazo_vencido,
        teto_da_linha_de_comando,
    )

    try:
        return _run_call(method, params, timeout=teto_da_linha_de_comando(method))
    except IpcError as exc:
        if prazo_vencido(exc):
            console.print(f"[yellow]{FRASE_DO_PRAZO_VENCIDO}[/yellow]")
            raise typer.Exit(code=2) from None
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
            "| dualsense (botões de PlayStation) | nintendo (botões da Nintendo; "
            "os gatilhos viram botão). Sem esta opção, mantém a que já está "
            "configurada."
        ),
    ),
) -> None:
    """Liga o gamepad virtual no daemon."""
    params: dict[str, Any] = {"enabled": True}
    if flavor is not None:
        params["flavor"] = flavor
    params["origin"] = "manual"
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
    _call_sync("gamepad.emulation.set", {"enabled": False, "origin": "manual"})
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


@app.command("mask")
def cmd_mask(
    sabor: str | None = typer.Argument(
        None,
        help=(
            "A máscara que este controle veste para o jogo (xbox, dualsense, nintendo…). "
            "O serviço recusa o nome que não conhece."
        ),
    ),
    uniq: str = typer.Option(
        ..., "--uniq", help="O controle (o MAC normalizado): a máscara é de UM aparelho."
    ),
    limpar: bool = typer.Option(
        False, "--limpar", help="Sem máscara própria: o controle volta a herdar a do perfil."
    ),
) -> None:
    """Troca a máscara de UM controle: `gamepad mask xbox --uniq <endereço>`."""
    if (sabor is None) == (not limpar):
        console.print(
            "[red]diga a máscara ou use --limpar[/red] — "
            "`gamepad mask <sabor> --uniq <endereço>`."
        )
        raise typer.Exit(code=2)
    result = _call_sync("gamepad.mask.set", {"uniq": uniq, "flavor": "" if limpar else sabor})
    corpo = result if isinstance(result, dict) else {}
    if corpo.get("motivo") == "aparelho_nao_vestiu":
        console.print(
            "[yellow]o controle não vestiu a máscara pedida; ficou a de antes[/yellow]"
        )
        raise typer.Exit(code=1)
    flavor = corpo.get("flavor")
    if flavor:
        console.print(f"[green]máscara do controle:[/green] {flavor}")
    else:
        console.print("[green]máscara do controle:[/green] a do perfil")
    if corpo.get("gravado") is False:
        console.print(
            "[dim]vale agora; o perfil não guardou a escolha[/dim]"
        )


__all__ = ["app"]
