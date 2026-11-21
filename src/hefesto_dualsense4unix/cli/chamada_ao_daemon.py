"""A chamada síncrona ao daemon que `controller`, `coop`, `gamepad` e `mouse` dividem.

O dono do corpo é `cli/chamada_ao_servico.chamar`: este só entrega o `console` de cada comando
(os testes trocam o `console` do módulo do comando para ler a saída). Códigos de saída: `2`
quando o prazo vence ou o daemon recusa o pedido, `3` com o serviço parado. O prazo vencido diz
que o daemon pode ter aplicado, nunca «nada mudou».
"""
from __future__ import annotations

from typing import Any

from rich.console import Console


def chamar_o_daemon(
    console: Console, method: str, params: dict[str, Any] | None = None
) -> Any:
    """Chama método IPC pelo invólucro único e devolve o resultado."""
    from hefesto_dualsense4unix.cli.chamada_ao_servico import chamar

    return chamar(method, params, console_do_comando=console)


__all__ = ["chamar_o_daemon"]
