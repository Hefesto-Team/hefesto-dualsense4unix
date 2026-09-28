"""O subcomando do básico medido — o protocolo, achado na instalação que roda.

O-BASICO-MEDIDO-01 (28/09/2026). O gesto é o nome do protocolo seguido do
subcomando: `hefesto-dualsense4unix basico retrato` (noqa-acento: o nome).
O protocolo mora em `scripts/o_basico.py`, e não aqui, porque ele é bancada:
lê o `/proc`, o `/sys`, o diário e o daemon vivo, roda os ensaios da pasta
`scripts/ensaios/` e, nos subcomandos que
escrevem, reserva a bancada e confere a volta. Este comando só o ACHA na
instalação que está rodando — pelo mesmo dono que acha o `doctor.sh`
(`utils/repo_files.encontrar_arquivo_do_repo`) — e o roda com o interpretador
do produto, que é o que enxerga o pacote.

Os argumentos passam inteiros, inclusive o `--help`: quem os entende é o
protocolo. O código de saída também passa inteiro — 0 verde, 1 vermelho,
2 recusado, 3 «não sei» —, e «o protocolo não veio nesta instalação» é 3,
porque sem ele nada foi medido.
"""
from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import typer

from hefesto_dualsense4unix.utils.repo_files import encontrar_arquivo_do_repo

#: O caminho do protocolo, relativo à raiz da instalação.
CAMINHO_DO_PROTOCOLO = "scripts/o_basico.py"

#: O código de «não sei»: sem o protocolo, nada foi medido.
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
