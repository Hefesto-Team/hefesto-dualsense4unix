"""Subcomando `hefesto-dualsense4unix metrics ...`."""
from __future__ import annotations

import typer
from rich.console import Console

app = typer.Typer(
    name="metrics",
    help="Liga e desliga as métricas Prometheus do daemon (desligadas por padrão).",
    no_args_is_help=True,
)

console = Console()


@app.command("ligar")
def cmd_ligar() -> None:
    """Liga as métricas na próxima subida do daemon (127.0.0.1, porta 9090)."""
    from hefesto_dualsense4unix.utils.session import save_metrics_enabled

    if not save_metrics_enabled(True):
        console.print("[red]Não consegui gravar a escolha na pasta de configuração.[/red]")
        raise typer.Exit(code=1)
    console.print(
        "Métricas ligadas. Valem quando o serviço do Hefesto subir de novo, "
        "em http://127.0.0.1:9090/metrics."
    )


@app.command("desligar")
def cmd_desligar() -> None:
    """Desliga as métricas na próxima subida do daemon (o padrão)."""
    from hefesto_dualsense4unix.utils.session import save_metrics_enabled

    if not save_metrics_enabled(False):
        console.print("[red]Não consegui gravar a escolha na pasta de configuração.[/red]")
        raise typer.Exit(code=1)
    console.print("Métricas desligadas. Vale quando o serviço do Hefesto subir de novo.")


__all__ = ["app"]
