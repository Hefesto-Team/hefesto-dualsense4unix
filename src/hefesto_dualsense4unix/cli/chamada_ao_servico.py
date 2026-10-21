"""A chamada síncrona da linha de comando ao serviço, com o prazo do método.

Os verbos novos (`freestyle`, `rumble`, `mic canal`, `mic volume`, `gamepad
mask`) falam com o serviço pelo mesmo cliente do IPC da janela e esperam o mesmo
prazo por método (`app/ipc_bridge.teto_da_linha_de_comando`). O prazo vencido
diz que o serviço pode ter aplicado, nunca «nada mudou»: o método que muda
estado pode ter chegado depois do prazo.

Códigos de saída, os mesmos de `mouse` e `gamepad`: `2` quando o prazo vence ou
o serviço recusa o pedido, `3` com o serviço fora do ar.
"""
from __future__ import annotations

from typing import Any

import typer
from rich.console import Console

console = Console()


def chamar(metodo: str, params: dict[str, Any] | None = None) -> Any:
    """Chama o método e converte a falha em recado e código de saída."""
    from hefesto_dualsense4unix.app.ipc_bridge import (
        FRASE_DO_PRAZO_VENCIDO,
        _run_call,
        prazo_vencido,
        teto_da_linha_de_comando,
    )
    from hefesto_dualsense4unix.cli.ipc_client import IpcError

    try:
        return _run_call(metodo, params, timeout=teto_da_linha_de_comando(metodo))
    except IpcError as exc:
        if prazo_vencido(exc):
            console.print(f"[yellow]{FRASE_DO_PRAZO_VENCIDO}[/yellow]")
            raise typer.Exit(code=2) from None
        console.print(f"[red]o serviço recusou o pedido:[/red] {exc.message}")
        raise typer.Exit(code=2) from None
    except (FileNotFoundError, ConnectionError, OSError) as exc:
        console.print(f"[red]serviço fora do ar[/red] (socket IPC inacessível): {exc}")
        raise typer.Exit(code=3) from None


__all__ = ["chamar", "console"]
