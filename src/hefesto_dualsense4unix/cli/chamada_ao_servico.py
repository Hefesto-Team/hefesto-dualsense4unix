"""A chamada síncrona da linha de comando ao serviço, com o prazo do método.

Todo verbo que fala com o serviço espera o prazo do método
(`app/ipc_bridge.teto_da_linha_de_comando`). O prazo vencido diz que o serviço pode ter
aplicado, nunca «nada mudou».

Códigos de saída, os de `docs/usage/cli.md`: `1` quando o prazo vence, `2` quando o
serviço recusa o pedido, `3` com o serviço parado (socket ausente ou conexão recusada,
a prova de `app/ipc_bridge.pedir_ao_servico`), com a frase `FRASE_DO_SERVICO_PARADO`; o
erro do socket vai ao diário.
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

    A recusa que vem no corpo da resposta volta a quem chama, que a lê.
    ``console_do_comando`` é o console de quem chama (os testes trocam o do módulo do comando).
    """
    saida = console_do_comando or console
    from hefesto_dualsense4unix.app.ipc_bridge import PARADO, RECUSOU, pedir_ao_servico

    desfecho = pedir_ao_servico(metodo, params)
    if desfecho.estado == PARADO:
        from hefesto_dualsense4unix.utils.logging_config import get_logger

        get_logger(__name__).info("servico_parado", metodo=metodo, erro=desfecho.motivo)
        saida.print(f"[red]{FRASE_DO_SERVICO_PARADO}[/red]")
        raise typer.Exit(code=3)
    if desfecho.estado != RECUSOU or desfecho.corpo is None:
        sair_se_o_servico_vive(saida, desfecho)
    return desfecho.corpo


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
