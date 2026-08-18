"""BT-SDP-VAZIO-01 — o doctor acusa bond COM pareamento e SEM perfil HID.

O caso que originou este arquivo, medido na máquina dela em 02/08/2026: o
8BitDo em modo PS4 tinha `[LinkKey]` no disco, `Paired`/`Bonded`/`Trusted`
todos `true` — e **zero UUIDs**. O `profiles/input/server.c` do BlueZ recusa
conexão ENTRANTE de quem não tem o perfil HID (`0x1124`) registrado
("Refusing connection: unknown device"), e o device entra num laço: o rádio
sobe, o perfil não, o link cai. Da poltrona, isso se parece com regressão do
Hefesto — e foi exatamente assim que a queixa chegou.

**Por que um check NOVO, se `check_bt_sdp_cache_envenenado` já existe.** Aquele
tem um filtro de elegibilidade que o torna cego a este caso, de propósito para
outro (SDP-CACHE-01):

    # Só device de perfil HID (0x1124 = HumanInterfaceDevice).
    grep -qi '^Services=.*00001124-...' "${info_f}" || continue

Ele **só examina quem já tem `Services=` no `info`**. Um device sem `Services=`
nenhum — o pior caso — é pulado antes de ser olhado. O check enxerga o device
meio-quebrado e é cego ao totalmente quebrado. Este arquivo trava a cura.

Padrão hermético dos irmãos (`test_doctor_radio_pareamento.py`): `busctl` FAKE
no PATH, nada do sistema real é tocado.
"""
from __future__ import annotations

import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCTOR = ROOT / "scripts" / "doctor.sh"

_HID_UUID = "00001124-0000-1000-8000-00805f9b34fb"
_PATH_FAKE = "/org/bluez/hci0/dev_AA_BB_CC_00_00_11"


def _busctl_fake(tmp_path: Path, uuids: str, *, paired: str = "true") -> Path:
    """Um `busctl` de mentira com UM gamepad pareado e os UUIDs que eu mandar.

    O alias tem de casar o filtro de nomes do `check_bt_radio`
    ('dualsense|wireless controller|...'), senão o device é descartado antes do
    trecho sob teste e o caso passaria por não ter sido exercitado.
    """
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
    """O caso do 8BitDo: pareado, com bond, e UUIDs VAZIOS.

    Sem este aviso o defeito é invisível ao diagnóstico inteiro — `Paired`,
    `Bonded` e `Trusted` ficam `true` o tempo todo, e nenhum outro check olha
    os UUIDs.

    Mordida: apagar o bloco do `check_bt_radio`, ou trocar o `fail` por `pass`.
    """
    saida = _rodar_check_bt_radio(_busctl_fake(tmp_path, "as 0"))

    assert "[FAIL]" in saida, saida
    assert "NENHUM perfil HID" in saida, saida
    # A cura tem de vir escrita, e com o cache junto: remover o device sem
    # remover `cache/<MAC>` faz o pareamento novo nascer igualmente quebrado
    # (SDP-CACHE-01 — já custou o quarto controle a esta casa).
    assert "RemoveDevice" in saida, saida
    assert "cache" in saida, saida


def test_bond_com_perfil_hid_fica_quieto(tmp_path: Path) -> None:
    """E o controle são não é acusado — senão o aviso vira ruído e ninguém lê.

    É o estado em que o 8BitDo ficou DEPOIS da cura de 02/08 (UUIDs com
    `0x1124` e `0x1200`).

    Mordida: inverter a condição (tirar o `!` do teste de `grep`).
    """
    saida = _rodar_check_bt_radio(
        _busctl_fake(tmp_path, f'as 2 "{_HID_UUID}" "00001200-0000-1000-8000-00805f9b34fb"')
    )

    assert "NENHUM perfil HID" not in saida, saida


def test_device_nao_pareado_nao_e_acusado(tmp_path: Path) -> None:
    """Device só VISTO num scan não tem por que ter perfil registrado.

    Sem a guarda de `Paired`, todo controle de vizinho que passasse num scan
    viraria uma linha vermelha no diagnóstico dela.

    Mordida: tirar o teste de `Paired == true` da condição.
    """
    saida = _rodar_check_bt_radio(_busctl_fake(tmp_path, "as 0", paired="false"))

    assert "NENHUM perfil HID" not in saida, saida
