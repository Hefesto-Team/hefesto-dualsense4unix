"""A chamada síncrona ao daemon que `controller`, `coop`, `gamepad` e `mouse` dividem.

Antes cada um carregava a sua cópia byte a byte. O dono é este, e cada comando só passa o
próprio `console` (os testes trocam o `console` do módulo do comando para ler a saída).

Códigos de saída: `2` quando o prazo vence ou o daemon recusa o pedido, `3` com o daemon
fora do ar. O prazo vencido diz que o daemon pode ter aplicado, nunca «nada mudou».
"""
from __future__ import annotations

from typing import Any

import typer
from rich.console import Console

from hefesto_dualsense4unix.cli.ipc_client import IpcError


def chamar_o_daemon(
    console: Console, method: str, params: dict[str, Any] | None = None
) -> Any:
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


__all__ = ["chamar_o_daemon"]
