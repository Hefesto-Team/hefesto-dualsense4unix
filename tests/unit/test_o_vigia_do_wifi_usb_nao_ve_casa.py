"""O vigia do Wi-Fi USB roda como root sem enxergar casa nenhuma.

INSTALL-E-UNINSTALL-DO-RADIO-01 (23/09/2026), o pedido P-18: a unit veio do
self-heal do zsh dela (O-QUE-E-DO-HEFESTO-SAI-DO-ZSH-01) sem endurecimento, e o
`wifi_usb.sh` não lê casa nenhuma — só o /sys, o /dev do reset da porta, o
`wpa_cli` e o próprio estado em /run. O `ProtectHome=yes` custa zero a ele e
tira do alcance de um defeito dele o /home, o /root e o /run/user.

Duas perguntas, e a segunda é o que impede a primeira de virar mentira: a unit
tem o `ProtectHome=yes`, e o script continua sem ler casa (se um dia passar a
ler, a unit o cegaria calada — é o caso do watchdog e do `maquina.json`, que
pediu `ProtectHome=tmpfs` com um bind).

A MORDIDA, medida: tirar o `ProtectHome=yes` da unit reprova o primeiro teste;
pôr um `${HOME}` no código do `wifi_usb.sh`, o segundo.
"""

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
    """O `verify` lê a unit como o systemd lê; o ExecStart vai para o script do
    repositório, que existe aqui (o de /usr/local/lib pode não existir)."""
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
