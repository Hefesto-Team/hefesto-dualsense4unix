"""O diário escreve o traceback puro, sem desenhar os locais de cada quadro.

Origem: D-1310-O-DIARIO-ESCREVE-O-TRACEBACK-SEM-OS-LOCAIS. O ``ConsoleRenderer``
com o rich instalado desenha o ``repr`` de todo local; o ``IpcServer`` inteiro
entrava no desenho, e o laço do daemon parava mais que o prazo de 1 s do cliente.
"""
from __future__ import annotations

import io
import logging

import structlog

from hefesto_dualsense4unix.utils import logging_config


class _LocalQueConta:
    """Um local que anota quem pediu o ``repr`` dele."""

    def __init__(self) -> None:
        self.pedidos = 0

    def __repr__(self) -> str:
        self.pedidos += 1
        return "LOCAL-DESENHADO"


def _cai(local: _LocalQueConta) -> None:
    raise RuntimeError(f"queda com {id(local)}")


def test_a_queda_sai_com_o_traceback_e_sem_o_desenho_dos_locais() -> None:
    """D-1310-O-DIARIO-ESCREVE-O-TRACEBACK-SEM-OS-LOCAIS."""
    buf = io.StringIO()
    log = structlog.wrap_logger(
        structlog.PrintLogger(file=buf),
        processors=logging_config.cadeia_do_diario("console", buf),
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
    )
    local = _LocalQueConta()
    try:
        _cai(local)
    except RuntimeError:
        log.exception("ipc_handler_error", method="daemon.status")
    saida = buf.getvalue()
    assert "Traceback (most recent call last)" in saida
    assert "RuntimeError: queda com" in saida
    assert "LOCAL-DESENHADO" not in saida
    assert local.pedidos == 0
