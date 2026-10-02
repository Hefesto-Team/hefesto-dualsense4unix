"""Testar o microfone como o Discord: fala três segundos e ouve de volta."""

from __future__ import annotations

import os
import shutil
import subprocess

import structlog

logger = structlog.get_logger(__name__)

__all__ = ["fonte_do_controle"]


def fonte_do_controle(uniq: str, *, saida_pactl: str = "") -> str | None:
    """O nó de captura DAQUELE controle — ``None`` quando não dá para saber."""
    from hefesto_dualsense4unix.integrations import retrato_do_som
    from hefesto_dualsense4unix.integrations.fontes_de_captura import (
        escolher_fonte,
        fontes_dualsense,
    )

    saida = saida_pactl
    lista = ["pactl", "list", "short", "sources"]
    do_retrato = retrato_do_som.responder(lista) if not saida else None
    if do_retrato is not None:
        saida = do_retrato if isinstance(do_retrato, str) else ""
    elif not saida:
        if shutil.which("pactl") is None:
            return None
        ambiente = dict(os.environ)
        ambiente["LC_ALL"] = "C"
        try:
            saida = subprocess.run(
                lista,
                capture_output=True,
                text=True,
                timeout=5,
                env=ambiente,
                check=False,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return None
    if not saida:
        return None
    return escolher_fonte(fontes_dualsense(saida), str(uniq), [str(uniq)])
