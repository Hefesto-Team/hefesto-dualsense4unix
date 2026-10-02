"""Subcomando `hefesto-dualsense4unix coop ...` (FEAT-DSX-COOP-LOCAL-01)."""
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
    """Reconcilia o co-op local agora (cada controle = um jogador)."""
    result = _call_sync("coop.set", {"enabled": True})
    players = result.get("players") if isinstance(result, dict) else None
    console.print("[green]co-op local ligado[/green]")
    if isinstance(players, int):
        console.print(f"jogadores ativos agora: {players}")
    console.print(
        "[dim]lembre: precisa do gamepad virtual ligado (hefesto-dualsense4unix "
        "gamepad on) + 2+ controles.[/dim]"
    )


COOP_OFF_RECUSA = (
    "[yellow]o co-op local não desliga mais.[/yellow]\n"
    "cada controle conectado é um jogador — decisão da mantenedora "
    "(06/08/2026): ninguém conecta quatro controles no PC esperando que os "
    "quatro movam o mesmo personagem.\n"
    "[dim]quer um controle de reserva? deixe-o desconectado. O co-op também "
    "sai de cena sozinho nos jogos com Steam Input (exceção medida), e volta "
    "quando o jogo fecha.[/dim]"
)


@app.command("off")
def cmd_off() -> None:
    """RECUSADO: o co-op local não desliga mais — explica o porquê."""
    console.print(COOP_OFF_RECUSA)
    raise typer.Exit(code=2)


SEM_DADO = "—"

NOTA_QUEM_NUMERA = "(dentro do jogo, quem numera é o jogo)"


def _plural_externos(n: int) -> str:
    """`1 externo` / `2 externos` — o rótulo concorda com o número."""
    return "1 externo" if n == 1 else f"{n} externos"


def linhas_de_contagem(players: Any, externals: Any) -> list[str]:
    """As DUAS contagens do co-op, nomeadas — LUGAR-À-MESA-01/E0a."""
    jogadores = players if isinstance(players, int) and not isinstance(players, bool) else None
    ext = (
        externals
        if isinstance(externals, int) and not isinstance(externals, bool) and externals >= 0
        else None
    )
    linhas = [
        f"jogadores pelo Hefesto: {jogadores if jogadores is not None else SEM_DADO}"
    ]
    if jogadores is None or ext is None:
        linhas.append(f"controles na mesa: {SEM_DADO}")
        linhas.append("(este daemon não sabe dizer — atualize o daemon)")
        return linhas
    if ext == 0:
        linhas.append(f"controles na mesa: {jogadores} (nenhum externo)")
        return linhas
    linhas.append(f"controles na mesa: {jogadores + ext}, sendo {_plural_externos(ext)}")
    linhas.append(NOTA_QUEM_NUMERA)
    return linhas


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
    for linha in linhas_de_contagem(players, coop.get("externals")):
        console.print(linha, highlight=False)


__all__ = [
    "COOP_OFF_RECUSA",
    "NOTA_QUEM_NUMERA",
    "SEM_DADO",
    "app",
    "linhas_de_contagem",
]
