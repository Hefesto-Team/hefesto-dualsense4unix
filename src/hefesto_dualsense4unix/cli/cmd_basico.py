"""O subcomando do básico medido — o protocolo, achado na instalação que roda."""
from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import typer

from hefesto_dualsense4unix.utils.repo_files import encontrar_arquivo_do_repo

CAMINHO_DO_PROTOCOLO = "scripts/o_basico.py"

RC_NAO_SEI = 3


def achar_o_protocolo() -> Path | None:
    """O `scripts/o_basico.py` desta instalação, ou None se ele não veio."""
    return encontrar_arquivo_do_repo(CAMINHO_DO_PROTOCOLO)


def basico_cmd(argumentos: Sequence[str]) -> int:
    """Roda o protocolo com `argumentos` e devolve o código de saída dele."""
    protocolo = achar_o_protocolo()
    if protocolo is None:
        typer.echo(
            f"{CAMINHO_DO_PROTOCOLO} não veio nesta instalação — nada foi medido.",
            err=True,
        )
        return RC_NAO_SEI
    return subprocess.run(
        [sys.executable, str(protocolo), *argumentos], check=False
    ).returncode
