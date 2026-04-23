"""Subcomando `hefesto plugin ...`.

Comandos para inspecionar e recarregar plugins do daemon.

- `hefesto plugin list`   — lista plugins carregados (nome, perfis, estado).
- `hefesto plugin reload` — recarrega plugins do disco via IPC ou direto.

Nota: requer daemon em execução com plugins_enabled=True para operar
via IPC. Sem daemon, informa estado indisponivel.
"""
from __future__ import annotations

import asyncio
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="plugin",
    help="Gerencia plugins do daemon Hefesto.",
    no_args_is_help=True,
)

console = Console()


async def _ipc_call(method: str, params: dict[str, Any]) -> Any:
    """Executa uma chamada IPC async conectando ao daemon."""
    from hefesto.cli.ipc_client import IpcClient

    async with IpcClient.connect() as client:
        return await client.call(method, params)


@app.command("list")
def cmd_list() -> None:
    """Lista plugins carregados no daemon."""
    from hefesto.cli.ipc_client import IpcError

    try:
        resultado = asyncio.run(_ipc_call("plugin.list", {}))
    except IpcError as exc:
        console.print(f"[red]Erro IPC:[/red] {exc}")
        console.print("[dim]Daemon não acessivel ou plugins não habilitados.[/dim]")
        raise typer.Exit(code=1) from exc

    plugins = resultado if isinstance(resultado, list) else []

    if not plugins:
        console.print("[dim]Nenhum plugin carregado.[/dim]")
        return

    tabela = Table(title="Plugins carregados", show_header=True)
    tabela.add_column("Nome", style="cyan")
    tabela.add_column("Perfis", style="magenta")
    tabela.add_column("Estado", style="green")
    tabela.add_column("Classe")

    for p in plugins:
        nome = p.get("name", "?")
        perfis = ", ".join(p.get("profile_match", [])) or "[dim]todos[/dim]"
        estado = "[red]desativado[/red]" if p.get("disabled") else "[green]ativo[/green]"
        classe = p.get("classe", "")
        tabela.add_row(nome, perfis, estado, classe)

    console.print(tabela)


@app.command("reload")
def cmd_reload() -> None:
    """Recarrega plugins do disco no daemon em execução."""
    from hefesto.cli.ipc_client import IpcError

    try:
        resultado = asyncio.run(_ipc_call("plugin.reload", {}))
    except IpcError as exc:
        console.print(f"[red]Erro IPC:[/red] {exc}")
        console.print("[dim]Daemon não acessivel ou plugins não habilitados.[/dim]")
        raise typer.Exit(code=1) from exc

    total = resultado.get("total", 0) if isinstance(resultado, dict) else 0
    console.print(f"[green]Reload concluido:[/green] {total} plugin(s) carregado(s).")


__all__ = ["app"]
