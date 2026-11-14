from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

BASH = shutil.which("bash") or "/bin/bash"
PKGBUILD = Path(__file__).resolve().parents[2] / "packaging" / "arch" / "PKGBUILD"


def _lista(nome: str) -> list[str]:
    feito = subprocess.run(
        [BASH, "-c", f'source "{PKGBUILD}" >/dev/null 2>&1; printf "%s\\n" "${{{nome}[@]}}"'],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    return [linha.split(":", 1)[0].strip() for linha in feito.stdout.splitlines() if linha]


def test_o_bwrap_da_caixa_das_extensoes_e_dependencia_dura() -> None:
    assert "bubblewrap" in _lista("depends")


def test_o_dmidecode_do_censo_do_gabinete_fica_nomeado() -> None:
    assert "dmidecode" in _lista("optdepends")
