"""A página do desenho se espera pelos sinais de desenhada, nunca pela rede quieta.

Os sinais têm um dono só, o retratista (``interface/olhar.py``, ``abrir_pronta``): o ``load``,
o ``document.fonts.ready``, dois quadros pintados e, quando a régua lê um seletor, ele no DOM.
Aqui o sinal que faltou vira a falha da régua, com o nome dele.
"""
from __future__ import annotations

import pathlib
from typing import Any

from hefesto_dualsense4unix.interface.olhar import (
    PRAZO_DE_CADA_SINAL_MS,
    PaginaNaoFicouProntaError,
    abrir_pronta,
)

PRAZO_MS = PRAZO_DE_CADA_SINAL_MS


def abrir(pg: Any, alvo: pathlib.Path | str, *, seletor: str | None = None,
          prazo_ms: int = PRAZO_MS) -> None:
    """Abre ``alvo`` em ``pg`` e só volta com a página desenhada; senão, diz o sinal que faltou."""
    try:
        abrir_pronta(pg, alvo, seletor=seletor, prazo_ms=prazo_ms)
    except PaginaNaoFicouProntaError as exc:
        raise AssertionError(str(exc)) from None
