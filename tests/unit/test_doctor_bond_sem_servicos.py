"""BT-SDP-VAZIO-01 — o doctor acusa bond COM pareamento e SEM perfil HID."""
from __future__ import annotations

import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCTOR = ROOT / "scripts" / "doctor.sh"

_HID_UUID = "00001124-0000-1000-8000-00805f9b34fb"
_PATH_FAKE = "/org/bluez/hci0/dev_AA_BB_CC_00_00_11"


def _busctl_fake(tmp_path: Path, uuids: str, *, paired: str = "true") -> Path:
    """Um `busctl` de mentira com UM gamepad pareado e os UUIDs que eu mandar."""
    fake_bin = tmp_path / "fakebin"
    fake_bin.mkdir(exist_ok=True)
    alvo = fake_bin / "busctl"
    alvo.write_text(
        "#!/usr/bin/env bash\n"
        'case "$1 $2" in\n'
        f'  "tree org.bluez") echo "{_PATH_FAKE}" ;;\n'
        '  "get-property org.bluez")\n'
        '    case "$5" in\n'
        '      Alias) echo \'s "Wireless Controller"\' ;;\n'
        f'      Paired) echo "b {paired}" ;;\n'
        "      Connected) echo 'b false' ;;\n"
        "      Trusted) echo 'b true' ;;\n"
        f'      UUIDs) echo \'{uuids}\' ;;\n'
        "      *) echo '' ;;\n"
        "    esac ;;\n"
        "esac\n"
        "exit 0\n",
        encoding="utf-8",
    )
    alvo.chmod(alvo.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return fake_bin


def _rodar_check_bt_radio(fake_bin: Path) -> str:
    res = subprocess.run(
        ["bash", "-c", 'set --; source "$DOCTOR_SH"; check_bt_radio'],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={"PATH": f"{fake_bin}:/usr/bin:/bin", "DOCTOR_SH": str(DOCTOR)},
    )
    return res.stdout


def test_bond_sem_perfil_hid_e_acusado(tmp_path: Path) -> None:
    """O caso do 8BitDo: pareado, com bond, e UUIDs VAZIOS."""
    saida = _rodar_check_bt_radio(_busctl_fake(tmp_path, "as 0"))

    assert "[FAIL]" in saida, saida
    assert "NENHUM perfil HID" in saida, saida
    assert "RemoveDevice" in saida, saida
    assert "cache" in saida, saida


def test_bond_com_perfil_hid_fica_quieto(tmp_path: Path) -> None:
    """E o controle são não é acusado — senão o aviso vira ruído e ninguém lê."""
    saida = _rodar_check_bt_radio(
        _busctl_fake(tmp_path, f'as 2 "{_HID_UUID}" "00001200-0000-1000-8000-00805f9b34fb"')
    )

    assert "NENHUM perfil HID" not in saida, saida


def test_device_nao_pareado_nao_e_acusado(tmp_path: Path) -> None:
    """Device só VISTO num scan não tem por que ter perfil registrado."""
    saida = _rodar_check_bt_radio(_busctl_fake(tmp_path, "as 0", paired="false"))

    assert "NENHUM perfil HID" not in saida, saida
