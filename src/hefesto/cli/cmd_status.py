"""Subcomandos `hefesto status` e `hefesto battery`.

Falam com o daemon via IPC para apresentar informação atual ao usuário.
Se o daemon estiver parado, tenta ler o controle direto como fallback.
"""
from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from hefesto.cli.ipc_client import IpcClient, IpcError

console = Console()


async def _daemon_status_via_ipc() -> dict[str, Any] | None:
    try:
        async with IpcClient.connect() as client:
            result = await client.call("daemon.status")
            if isinstance(result, dict):
                return result
            return None
    except (FileNotFoundError, ConnectionError, IpcError):
        return None


def status_cmd() -> None:
    """Tabela com bateria + perfil + conexão + transporte."""
    data = asyncio.run(_daemon_status_via_ipc())
    if data is None:
        console.print("[yellow]daemon offline — mostrando leitura direta do hardware[/yellow]")
        data = _fallback_hardware_read()

    table = Table(title="Hefesto — Status")
    table.add_column("Campo", style="cyan")
    table.add_column("Valor")
    for key in ("connected", "transport", "active_profile", "battery_pct"):
        value = data.get(key)
        table.add_row(key, str(value) if value is not None else "[dim]n/d[/dim]")
    console.print(table)


def battery_cmd() -> None:
    """Mostra só o percentual de bateria."""
    data = asyncio.run(_daemon_status_via_ipc())
    if data is None:
        data = _fallback_hardware_read()
    battery = data.get("battery_pct")
    if battery is None:
        console.print("[red]bateria desconhecida[/red]")
        raise typer.Exit(code=1)
    color = "green" if battery > 40 else "yellow" if battery > 15 else "red"
    console.print(f"[{color}]{battery}%[/{color}]")


def _fallback_hardware_read() -> dict[str, Any]:
    try:
        from hefesto.core.backend_pydualsense import PyDualSenseController

        controller = PyDualSenseController()
        controller.connect()
        try:
            state = controller.read_state()
            return {
                "connected": state.connected,
                "transport": state.transport,
                "active_profile": None,
                "battery_pct": state.battery_pct,
            }
        finally:
            with contextlib.suppress(Exception):
                controller.disconnect()
    except Exception as exc:
        console.print(f"[red]sem controle disponivel: {exc}[/red]")
        return {"connected": False, "transport": None, "active_profile": None, "battery_pct": None}


__all__ = ["battery_cmd", "status_cmd"]
