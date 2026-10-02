#!/usr/bin/env python3
"""O CONSENTIMENTO DE DOIS TEMPOS — o relógio único sobre a Steam dela."""
from __future__ import annotations

import time
from typing import Any

#: ``steam_launch_options.with_steam_closed`` EXIGE de quem a chama, na forma
SEGUNDOS_PARA_CONFIRMAR = 20.0

ARMADO: dict[str, Any] = {}


def chave(*partes: object) -> str:
    """A chave do que se arma: as partes juntas, e a página na frente."""
    return ":".join(str(p) for p in partes)


def armado_agora() -> str:
    """A chave armada NESTE instante, ou ``""`` — e ela desarma sozinha no tempo."""
    if ARMADO and time.monotonic() >= float(ARMADO.get("ate") or 0.0):
        ARMADO.clear()
    return str(ARMADO.get("gesto") or "")


def armar(chave_: str) -> None:
    """Arma ``chave_`` por :data:`SEGUNDOS_PARA_CONFIRMAR`, desarmando o resto."""
    ARMADO.clear()
    ARMADO.update(gesto=chave_, ate=time.monotonic() + SEGUNDOS_PARA_CONFIRMAR)


def desarmar() -> None:
    """Nada fica armado. É o que o clique de confirmação faz ANTES de agir."""
    ARMADO.clear()
