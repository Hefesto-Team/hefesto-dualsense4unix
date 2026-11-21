"""A chamada síncrona da linha de comando ao serviço, com o prazo do método.

Os verbos novos (`freestyle`, `rumble`, `mic canal`, `mic volume`, `gamepad
mask`) falam com o serviço pelo mesmo cliente do IPC da janela e esperam o mesmo
prazo por método (`app/ipc_bridge.teto_da_linha_de_comando`). O prazo vencido
diz que o serviço pode ter aplicado, nunca «nada mudou»: o método que muda
estado pode ter chegado depois do prazo.

Códigos de saída: `2` quando o prazo vence ou o serviço recusa o pedido, `3` com o
serviço parado, com a frase `FRASE_DO_SERVICO_PARADO`; o erro do socket vai ao diário.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import typer
from rich.console import Console

if TYPE_CHECKING:
    from hefesto_dualsense4unix.app.ipc_bridge import Desfecho

console = Console()

FRASE_DO_SERVICO_PARADO = (
    "O serviço do Hefesto está parado. Suba com `hefesto-dualsense4unix daemon start`."
)


def chamar(
    metodo: str, params: dict[str, Any] | None = None, *, console_do_comando: Console | None = None
) -> Any:
    """Chama o método e converte a falha em recado e código de saída.

    ``console_do_comando`` é o console de quem chama (os testes trocam o do módulo do comando).
    """
    saida = console_do_comando or console
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
            saida.print(f"[yellow]{FRASE_DO_PRAZO_VENCIDO}[/yellow]")
            raise typer.Exit(code=2) from None
        saida.print(f"[red]o serviço recusou o pedido:[/red] {exc.message}")
        raise typer.Exit(code=2) from None
    except (FileNotFoundError, ConnectionError, OSError) as exc:
        from hefesto_dualsense4unix.utils.logging_config import get_logger

        get_logger(__name__).info("servico_parado", metodo=metodo, erro=str(exc))
        saida.print(f"[red]{FRASE_DO_SERVICO_PARADO}[/red]")
        raise typer.Exit(code=3) from None


def sair_se_o_servico_vive(console_do_comando: Console, desfecho: Desfecho) -> None:
    """A reserva direta só vale com o serviço comprovadamente parado.

    Recusa sai com a frase do motivo e rc 2; serviço que não respondeu, com a do prazo vencido
    e rc 1.
    ``atendeu`` e ``parado`` voltam: quem chama decide o que fazer com cada um.
    """
    from hefesto_dualsense4unix.app.ipc_bridge import FRASE_DO_PRAZO_VENCIDO, MUDO, RECUSOU

    if desfecho.estado == RECUSOU:
        motivo = desfecho.motivo or "sem motivo informado"
        console_do_comando.print(f"[red]o serviço recusou o pedido:[/red] {motivo}")
        raise typer.Exit(code=2)
    if desfecho.estado == MUDO:
        console_do_comando.print(f"[yellow]{FRASE_DO_PRAZO_VENCIDO}[/yellow]")
        raise typer.Exit(code=1)


__all__ = ["FRASE_DO_SERVICO_PARADO", "chamar", "console", "sair_se_o_servico_vive"]
