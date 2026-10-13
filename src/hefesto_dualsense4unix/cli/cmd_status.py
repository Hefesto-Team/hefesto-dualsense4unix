"""Subcomandos `hefesto-dualsense4unix status` e `hefesto-dualsense4unix battery`."""
from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from hefesto_dualsense4unix.cli.ipc_client import IpcClient, IpcError
from hefesto_dualsense4unix.utils import identidade

console = Console()

_ROTULOS_DE_CAMPO: dict[str, str] = {
    "active_profile": "active_profile (em vigor agora)",
}


class DaemonNaoRespondeuError(RuntimeError):
    """O serviço aceitou a conexão e não respondeu no prazo (parado ou travado)."""


async def _daemon_status_via_ipc() -> dict[str, Any] | None:
    """O ``daemon.status``; ``None`` com o serviço fora do ar.

    Serviço que ATENDE a conexão e não responde não é «fora do ar»: levanta
    :class:`DaemonNaoRespondeuError`, e quem chama diz isso (e não abre o aparelho,
    que o serviço travado ainda segura).
    """
    from hefesto_dualsense4unix.app.ipc_bridge import prazo_vencido

    try:
        async with IpcClient.connect() as client:
            result = await client.call("daemon.status")
            if isinstance(result, dict):
                return result
            return None
    except IpcError as exc:
        if prazo_vencido(exc):
            raise DaemonNaoRespondeuError(exc.message) from exc
        return None
    except (FileNotFoundError, ConnectionError):
        return None


def _status_ou_sair() -> dict[str, Any] | None:
    """O status do serviço, ou ``None`` fora do ar; serviço mudo sai com rc 1."""
    try:
        return asyncio.run(_daemon_status_via_ipc())
    except DaemonNaoRespondeuError as exc:
        console.print(f"[red]{exc}[/red] — confira o serviço: `hefesto-dualsense4unix doctor`")
        raise typer.Exit(code=1) from exc


def status_cmd() -> None:
    """Tabela com bateria + perfil + conexão + transporte."""
    data = _status_ou_sair()
    if data is None:
        console.print("[yellow]daemon offline — mostrando leitura direta do hardware[/yellow]")
        data = _fallback_hardware_read()

    table = Table(title=f"{identidade.atual().nome_longo} — Status")
    table.add_column("Campo", style="cyan")
    table.add_column("Valor")
    for key in ("connected", "transport", "active_profile", "battery_pct"):
        value = data.get(key)
        rotulo = _ROTULOS_DE_CAMPO.get(key, key)
        table.add_row(rotulo, str(value) if value is not None else "[dim]n/d[/dim]")
    console.print(table)


def battery_cmd() -> None:
    """Mostra só o percentual de bateria."""
    data = _status_ou_sair()
    if data is None:
        data = _fallback_hardware_read()
    if data.get("connected") is False:
        console.print("[red]nenhum controle ao alcance[/red]")
        raise typer.Exit(code=1)
    battery = data.get("battery_pct")
    if battery is None:
        console.print("[red]bateria desconhecida[/red]")
        raise typer.Exit(code=1)
    color = "green" if battery > 40 else "yellow" if battery > 15 else "red"
    console.print(f"[{color}]{battery}%[/{color}]")


def _fallback_hardware_read() -> dict[str, Any]:
    """A leitura direta do aparelho. Sem controle aberto, devolve ``None`` em tudo o que
    o aparelho diria: o backend de um posto vago responde bateria 0 e transporte USB,
    e repassar isso seria inventar um controle."""
    sem_controle: dict[str, Any] = {
        "connected": False, "transport": None, "active_profile": None, "battery_pct": None,
    }
    try:
        from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

        controller = PyDualSenseController()
        controller.connect()
        try:
            if not controller.is_connected():
                return sem_controle
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
        return sem_controle


__all__ = ["DaemonNaoRespondeuError", "battery_cmd", "status_cmd"]
