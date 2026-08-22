"""N-IGUAL-A-UM-01 — o doctor pergunta ao adaptador CERTO, não ao primeiro.

O caso MEDIDO na bancada dela em 22/08/2026: três adaptadores Bluetooth, cinco
controles distribuídos 1/2/2. O `check_bt_radio` do doctor perguntava
`Discovering` a um `/org/bluez/hci0` literal e mandava a cura de bond sem SDP
apontando para `/org/bluez/hci0` — mesmo quando o controle em questão mora em
`hci1`. Quatro dos cinco controles dela ficavam fora do radar do aviso, e o
comando de cura que o doctor imprime falharia com "Does Not Exist" na mão dela.

A cicatriz já estava escrita a vinte linhas de distância, em
`scripts/bt_health_watchdog.sh:158` — *"Concatenar 'hci0' fazia a vigia virar
no-op MUDO num adaptador hci1"* —, e não tinha sido generalizada. Numa máquina
com UM adaptador só que enumerou como `hci1` (a numeração inverte entre boots,
`GUIA-RADIO-DA-SALA.md` §6.1) os dois defeitos batem juntos.

COMO ESTE TESTE MORDE: o controle FAKE mora em `hci1`, e é `hci1` que está em
modo de busca. Com o `hci0` literal de volta no lugar, o aviso de Discovering
some (o `hci0` do fake responde `false`) e a linha de cura volta a citar
`hci0` — as duas asserções reprovam.

Padrão hermético dos irmãos (`test_doctor_bond_sem_servicos.py`): `busctl`
FAKE no PATH, nada do sistema real é tocado.
"""
from __future__ import annotations

import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCTOR = ROOT / "scripts" / "doctor.sh"

_HID_UUID = "00001124-0000-1000-8000-00805f9b34fb"
#: MAC sintético da casa (faixa `aa:bb:cc`, octetos 4 e 5 zerados).
_DEV_EM_HCI1 = "/org/bluez/hci1/dev_AA_BB_CC_00_00_11"


def _busctl_fake(tmp_path: Path, *, uuids: str) -> Path:
    """`busctl` de mentira: DOIS adaptadores, o controle no SEGUNDO.

    - `hci0` existe, está vazio e responde `Discovering: false`;
    - `hci1` hospeda o controle conectado e responde `Discovering: true`.

    É a bancada dela em miniatura: quem procura no primeiro adaptador não acha
    nada e conclui que está tudo bem.
    """
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
    """O controle está em `hci1` e é `hci1` que procura — o aviso tem de sair.

    Com o `/org/bluez/hci0` literal de volta, o doctor lê o adaptador vazio,
    recebe `false` e cala: a bancada dela inteira ficava sem este aviso.
    """
    saida = _rodar_check_bt_radio(_busctl_fake(tmp_path, uuids=f"as 1 \"{_HID_UUID}\""))
    assert "modo de busca" in saida, saida
    assert "hci1" in saida, saida


def test_a_cura_do_bond_sem_sdp_aponta_para_o_adaptador_do_controle(
    tmp_path: Path,
) -> None:
    """A linha de cura é para ela COPIAR — tem de citar o adaptador certo.

    `RemoveDevice` num adaptador que não hospeda o device devolve
    `org.freedesktop.DBus.Error.InvalidArgs`. Um comando de cura que falha na
    mão dela é pior que nenhum: ela conclui que o diagnóstico estava errado.
    """
    saida = _rodar_check_bt_radio(_busctl_fake(tmp_path, uuids="as 0"))
    assert "SDP vazio" in saida, saida
    assert "org.bluez /org/bluez/hci1 org.bluez.Adapter1 RemoveDevice" in saida, saida
    assert "/org/bluez/hci0 org.bluez.Adapter1 RemoveDevice" not in saida, saida
