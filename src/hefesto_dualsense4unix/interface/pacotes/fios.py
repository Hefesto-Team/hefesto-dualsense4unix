"""Os fios da interface nascem aqui, com nome (O-FIO-DA-JANELA-NUNCA-ESPERA-01).

O fio da janela é o do GTK: o que espera ali (subprocesso, `/sys`, IPC) congela a
janela inteira. O trabalho que espera vem para um fio daqui, e a resposta volta pelo
escaninho de quem pediu (o tique seguinte a lê) ou por `GLib.idle_add`.

Ficam fora os dois fios com o endereço no nome (`mesa_viva`, `a05_vibracao`): a régua 4
de `test_o_registro_copiado_nao_entrega_o_endereco.py` os lê por `Thread(name=mascarar(…))`.
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any


def soltar(nome: str, alvo: Callable[..., Any], *args: Any) -> threading.Thread:
    """Roda `alvo(*args)` num fio `daemon` chamado `nome`, já de pé.

    O alvo vai como veio, sem embrulho: a régua que troca `threading.Thread`
    por um fio na hora (ou o anota) continua vendo o `target` de quem pediu.
    """
    if not nome:
        raise ValueError("fio sem nome: diga o que ele faz")
    fio = threading.Thread(target=alvo, args=args, name=nome, daemon=True)
    fio.start()
    return fio
