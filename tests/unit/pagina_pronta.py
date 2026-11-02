"""A página do desenho se espera pelos sinais de desenhada, nunca pela rede quieta.

Os sinais têm um dono só, o retratista (``interface/olhar.py``, ``abrir_pronta``): o ``load``,
o ``document.fonts.ready``, dois quadros pintados e, quando a régua lê um seletor, ele no DOM.
O ``goto`` é de quem chama: o do retratista só abre ``file://`` de página do repositório, e o
daqui abre o endereço que a régua pede. O sinal que faltou vira a falha da régua, com o nome dele.
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


def _endereco(alvo: pathlib.Path | str) -> str:
    if isinstance(alvo, pathlib.Path):
        return alvo.resolve().as_uri()
    return alvo if "://" in alvo else pathlib.Path(alvo).resolve().as_uri()


def abrir(pg: Any, alvo: pathlib.Path | str, *, seletor: str | None = None,
          prazo_ms: int = PRAZO_MS) -> None:
    """Abre ``alvo`` em ``pg`` e só volta com a página desenhada; senão, diz o sinal que faltou."""
    try:
        endereco = _endereco(alvo)
        abrir_pronta(pg, endereco, lambda **ir: pg.goto(endereco, **ir),
                     seletor=seletor, prazo_ms=prazo_ms)
    except PaginaNaoFicouProntaError as exc:
        raise AssertionError(str(exc)) from None
