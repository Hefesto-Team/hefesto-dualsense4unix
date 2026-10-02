"""O BlueZ sem as curas avisa também fora do dpkg — B2 da O-PRODUTO."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
BASELINE = RAIZ / "assets" / "bluez-backport" / "BASELINE"


def _marcas() -> dict[str, str]:
    return dict(
        re.findall(r"^MARCA_([^=]+)=(.*)$", BASELINE.read_text(encoding="utf-8"), re.MULTILINE)
    )


def _doctor_sem_dpkg(tmp_path: Path, marcas: list[str]) -> str:
    todas = _marcas()
    binario = tmp_path / "bluetoothd"
    binario.write_bytes(b"\x00".join(todas[m].encode() for m in marcas) + b"\x00")
    r = subprocess.run(
        [BASH, "-c", f'source "{RAIZ / "scripts" / "doctor.sh"}"; check_bluez_curas_do_backport'],
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            "HEFESTO_DOCTOR_BLUETOOTHD": str(binario),
            "HEFESTO_DOCTOR_DPKG": "dpkg-que-nao-existe",
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return r.stdout + r.stderr


def test_sem_o_0002_e_sem_dpkg_avisa_o_efeito(tmp_path: Path) -> None:
    saida = _doctor_sem_dpkg(tmp_path, ["hefesto-0001"])
    assert "[WARN]" in saida, saida
    assert "hefesto-0002" in saida and "EAGAIN" in saida, saida
    assert "três ou mais controles pelo rádio" in saida, saida


def test_o_bluez_de_fabrica_de_outra_distro_avisa(tmp_path: Path) -> None:
    """Sem marca nenhuma: o 5.8x do Fedora ou do Arch."""
    saida = _doctor_sem_dpkg(tmp_path, [])
    assert "[WARN]" in saida and "hefesto-0001" in saida and "hefesto-0002" in saida, saida


def test_com_as_curas_passa_mesmo_sem_dpkg(tmp_path: Path) -> None:
    """Quem construiu o BlueZ com os patches à mão não recebe aviso à toa."""
    saida = _doctor_sem_dpkg(tmp_path, ["hefesto-0001", "hefesto-0002"])
    assert "[ OK ] o bluetoothd em execução traz as curas" in saida, saida
    assert "[WARN]" not in saida, saida
