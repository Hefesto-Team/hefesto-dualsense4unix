"""O vigia do Wi-Fi USB roda como root sem enxergar casa nenhuma."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
UNIT = RAIZ / "assets" / "systemd" / "hefesto-wifi-usb-vigia.service"
SCRIPT = RAIZ / "scripts" / "wifi_usb.sh"


def _diretivas(texto: str) -> list[str]:
    return [
        linha.strip()
        for linha in texto.splitlines()
        if linha.strip() and not linha.lstrip().startswith("#")
    ]


def test_a_unit_nao_enxerga_casa() -> None:
    assert "ProtectHome=yes" in _diretivas(UNIT.read_text(encoding="utf-8"))


def test_o_script_nao_le_casa() -> None:
    codigo = "\n".join(
        linha
        for linha in SCRIPT.read_text(encoding="utf-8").splitlines()
        if not linha.lstrip().startswith("#")
    )
    achados = re.findall(r"\$\{?HOME\b|\$\{?XDG_[A-Z_]+|/home/|/root\b|/run/user|~/", codigo)
    assert not achados, (
        f"o wifi_usb.sh passou a ler casa ({sorted(set(achados))}), e a unit dele tem "
        "ProtectHome=yes: sob o systemd ele ficaria cego calado"
    )


@pytest.mark.skipif(shutil.which("systemd-analyze") is None, reason="sem systemd-analyze")
def test_o_systemd_aceita_a_unit(tmp_path: Path) -> None:
    """O `verify` lê a unit como o systemd lê; o ExecStart vai para o script do"""
    copia = tmp_path / UNIT.name
    copia.write_text(
        UNIT.read_text(encoding="utf-8").replace(
            "ExecStart=/usr/local/lib/hefesto-dualsense4unix/wifi_usb.sh", f"ExecStart={SCRIPT}"
        ),
        encoding="utf-8",
    )
    r = subprocess.run(
        ["systemd-analyze", "verify", str(copia)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    sobre_ela = [linha for linha in r.stderr.splitlines() if copia.name in linha]
    assert r.returncode == 0 and not sobre_ela, r.stderr
