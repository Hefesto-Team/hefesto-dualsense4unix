"""N-IGUAL-A-UM-01 — o doctor pergunta ao adaptador CERTO, não ao primeiro."""
from __future__ import annotations

import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCTOR = ROOT / "scripts" / "doctor.sh"

_HID_UUID = "00001124-0000-1000-8000-00805f9b34fb"
_DEV_EM_HCI1 = "/org/bluez/hci1/dev_AA_BB_CC_00_00_11"


def _busctl_fake(tmp_path: Path, *, uuids: str) -> Path:
    """`busctl` de mentira: DOIS adaptadores, o controle no SEGUNDO."""
    fake_bin = tmp_path / "fakebin"
    fake_bin.mkdir(exist_ok=True)
    alvo = fake_bin / "busctl"
    alvo.write_text(
        "#!/usr/bin/env bash\n"
        'case "$1 $2" in\n'
        '  "tree org.bluez")\n'
        '    echo "/org/bluez/hci0"\n'
        '    echo "/org/bluez/hci1"\n'
        f'    echo "{_DEV_EM_HCI1}" ;;\n'
        '  "get-property org.bluez")\n'
        '    case "$3" in\n'
        '      /org/bluez/hci0)\n'
        '        [[ "$5" == Discovering ]] && echo "b false" || echo "" ;;\n'
        '      /org/bluez/hci1)\n'
        '        [[ "$5" == Discovering ]] && echo "b true" || echo "" ;;\n'
        '      *)\n'
        '        case "$5" in\n'
        "          Alias) echo 's \"Wireless Controller\"' ;;\n"
        '          Paired) echo "b true" ;;\n'
        '          Connected) echo "b true" ;;\n'
        '          Trusted) echo "b true" ;;\n'
        f'          UUIDs) echo \'{uuids}\' ;;\n'
        "          *) echo '' ;;\n"
        "        esac ;;\n"
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


def test_o_discovering_do_segundo_adaptador_e_visto(tmp_path: Path) -> None:
    """O controle está em `hci1` e é `hci1` que procura — o aviso tem de sair."""
    saida = _rodar_check_bt_radio(_busctl_fake(tmp_path, uuids=f"as 1 \"{_HID_UUID}\""))
    assert "modo de busca" in saida, saida
    assert "hci1" in saida, saida


def test_a_cura_do_bond_sem_sdp_aponta_para_o_adaptador_do_controle(
    tmp_path: Path,
) -> None:
    """A linha de cura é para ela COPIAR — tem de citar o adaptador certo."""
    saida = _rodar_check_bt_radio(_busctl_fake(tmp_path, uuids="as 0"))
    assert "SDP vazio" in saida, saida
    assert "org.bluez /org/bluez/hci1 org.bluez.Adapter1 RemoveDevice" in saida, saida
    assert "/org/bluez/hci0 org.bluez.Adapter1 RemoveDevice" not in saida, saida
