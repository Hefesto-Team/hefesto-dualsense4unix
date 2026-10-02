"""O doctor resume as famílias do rádio perguntando ao dono do classificador."""

from __future__ import annotations

import datetime
import shutil
import subprocess
import sys
from pathlib import Path

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"


def _doctor(casa: Path, linhas: list[str]) -> str:
    estado = casa / ".local" / "state" / "hefesto-dualsense4unix"
    estado.mkdir(parents=True)
    (estado / "kernel.log").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    roteiro = (
        f'source "{DOCTOR}"\n'
        f'_python_do_produto() {{ printf "%s\\n" "{sys.executable}"; }}\n'
        "check_familias_do_radio\n"
    )
    r = subprocess.run(
        [BASH, "-c", roteiro],
        env={"PATH": "/usr/bin:/bin", "HOME": str(casa), "LC_ALL": "C.UTF-8"},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return r.stdout + r.stderr


def _dia(dias_atras: int) -> str:
    return (datetime.date.today() - datetime.timedelta(days=dias_atras)).isoformat()


def test_dentro_da_janela_avisa_e_fora_e_historico(tmp_path: Path) -> None:
    hoje, velho = _dia(0), _dia(30)
    saida = _doctor(
        tmp_path,
        [
            f"# {velho} 09:00:00 kernel-watch iniciado (padrões: USB-71 JOYCON BT-SOCKET "
            "FILA-CHEIA ENLACE-PARADO BT-TRAVADO CRC + contadores hci)",
            f"{velho}T09:10:00-03:00 [CRC] hid-playstation: DualSense input CRC's check failed",
            f"{hoje}T10:00:00-03:00 [BT-SOCKET] bluetoothd: bt socket write error",
        ],
    )
    assert "[WARN] rádio: rádio afogado [BT-SOCKET] — 1 vez(es) nos últimos 7 dias" in saida, saida
    assert "hefesto-0002" in saida
    linha_do_crc = next((linha for linha in saida.splitlines() if "[CRC]" in linha), "")
    assert "não aconteceu nos últimos 7 dias" in linha_do_crc, saida
    assert "[WARN]" not in linha_do_crc, (
        "um CRC de 30 dias atrás virou aviso no presente:\n" + saida
    )
    assert "não olhei" not in saida


def test_o_log_de_antes_das_familias_se_le_pelo_conteudo(tmp_path: Path) -> None:
    hoje = _dia(0)
    saida = _doctor(
        tmp_path,
        [
            f"# {hoje} 09:00:00 kernel-watch iniciado (padrões: USB-71 JOYCON BT-HCI XHCI "
            "+ contadores hci)",
            f"{hoje}T09:05:00-03:00 [BT-HCI] Bluetooth: hci1: command 0x0c03 tx timeout",
        ],
    )
    assert "adaptador travado [BT-TRAVADO] — 1 vez(es)" in saida, saida


def test_familia_nunca_procurada_e_nao_olhei(tmp_path: Path) -> None:
    hoje = _dia(0)
    saida = _doctor(
        tmp_path,
        [
            f"# {hoje} 09:00:00 kernel-watch iniciado (padrões: USB-71 JOYCON BT-HCI XHCI "
            "+ contadores hci)",
        ],
    )
    assert "ainda não procurava" in saida and "[FILA-CHEIA]" in saida, saida
    assert "[WARN]" not in saida


def test_o_doctor_nao_redigita_o_padrao() -> None:
    """Quem classifica é o storm_doctor; o doctor não carrega as palavras."""
    codigo = "\n".join(
        linha
        for linha in DOCTOR.read_text(encoding="utf-8").splitlines()
        if not linha.lstrip().startswith("#")
    ).lower()
    for palavra in ("output queue is full", "bt socket write error", "link tx timeout"):
        assert palavra not in codigo, f"o doctor redigitou o padrão «{palavra}»"
    assert "classificar_o_historico" in codigo
