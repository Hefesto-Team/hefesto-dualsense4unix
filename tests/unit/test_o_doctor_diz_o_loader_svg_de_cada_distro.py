from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
DOCTOR = Path(__file__).resolve().parents[2] / "scripts" / "doctor.sh"


@pytest.mark.parametrize(
    ("gerenciador", "esperado"),
    [
        ("apt-get", "sudo apt install librsvg2-common"),
        ("dnf", "sudo dnf install librsvg2"),
        ("pacman", "sudo pacman -S librsvg"),
        ("", "librsvg no Arch"),
    ],
)
def test_o_loader_svg_sai_pelo_gerenciador_da_maquina(
    tmp_path: Path, gerenciador: str, esperado: str
) -> None:
    if gerenciador:
        (tmp_path / gerenciador).write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        (tmp_path / gerenciador).chmod(0o755)
    feito = subprocess.run(
        [BASH, "-c", f"source '{DOCTOR}'; _pacote_do_loader_svg"],
        env={"PATH": str(tmp_path), "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert feito.stdout.strip().endswith(esperado), feito.stdout + feito.stderr
