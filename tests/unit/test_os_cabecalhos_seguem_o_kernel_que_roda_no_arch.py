from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
LIB = RAIZ / "scripts" / "lib" / "cabecalhos_do_kernel.sh"


def _pacman_de_mentira(pasta: Path, dono: str | None) -> Path:
    binario = pasta / "pacman"
    if dono is None:
        corpo = "#!/bin/sh\necho 'erro: nenhum pacote possui o arquivo' >&2\nexit 1\n"
    else:
        corpo = (
            "#!/bin/sh\n"
            '[ "$1" = "-Qqo" ] || exit 2\n'
            f'case "$2" in /usr/lib/modules/*/vmlinuz) echo {dono} ;; *) exit 1 ;; esac\n'
        )
    binario.write_text(corpo, encoding="utf-8")
    binario.chmod(0o755)
    return pasta


def _cabecalhos(pasta: Path, kver: str) -> str:
    feito = subprocess.run(
        [BASH, "-c", f'source "{LIB}"; cabecalhos_do_kernel_no_pacman "$1"', "_", kver],
        env={"PATH": f"{pasta}:/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    return feito.stdout.strip()


@pytest.mark.parametrize(
    ("dono", "kver", "esperado"),
    [
        ("linux-cachyos", "7.3.3-1-cachyos", "linux-cachyos-headers"),
        ("linux-cachyos-lts", "6.12.40-1-cachyos-lts", "linux-cachyos-lts-headers"),
        ("linux-zen", "7.3.3-zen1-1-zen", "linux-zen-headers"),
        ("linux-lts", "6.12.40-1-lts", "linux-lts-headers"),
        ("linux612", "6.12.40-1-MANJARO", "linux612-headers"),
        ("linux", "7.3.3-arch1-1", "linux-headers"),
    ],
)
def test_o_cabecalho_e_o_do_pacote_dono_do_kernel(
    tmp_path: Path, dono: str, kver: str, esperado: str
) -> None:
    assert _cabecalhos(_pacman_de_mentira(tmp_path, dono), kver) == esperado


def test_kernel_sem_dono_no_pacman_cai_no_linux_headers(tmp_path: Path) -> None:
    assert _cabecalhos(_pacman_de_mentira(tmp_path, None), "7.3.3-proprio") == "linux-headers"
