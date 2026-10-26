"""A regra do btusb se lê onde o kmod lê, no exame e no doctor, pelo mesmo critério.

A-REGRA-DO-BTUSB-SE-LE-ONDE-O-KMOD-LE-01 (26/10/2026). O `.deb`, o `.rpm` e o
pacote do Arch põem o `hefesto-btusb-no-autosuspend.conf` em `/usr/lib/modprobe.d`,
e o exame e o doctor o procuravam só em `/etc/modprobe.d`: numa raiz com o conf
só onde o pacote o põe, os dois diziam que a regra faltava. Os diretórios abaixo
são os de `man modprobe.d`, escritos aqui e não importados: a lista do produto
que encolhe tem de reprovar esta régua.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations.exame_da_mesa import (
    ESTADO_ATENCAO,
    ESTADO_CERTO,
    ESTADO_NAO_SEI,
    REGRA_DO_BTUSB,
    Item,
    energia_do_radio,
)

RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"

ONDE_O_KMOD_LE = (
    "etc/modprobe.d",
    "run/modprobe.d",
    "usr/local/lib/modprobe.d",
    "usr/lib/modprobe.d",
    "lib/modprobe.d",
)
NIVEL_NO_DOCTOR = {ESTADO_CERTO: "PASS", ESTADO_ATENCAO: "WARN", ESTADO_NAO_SEI: "INFO"}


def _raiz(tmp_path: Path, *onde: str) -> Path:
    raiz = tmp_path / "raiz"
    raiz.mkdir()
    for diretorio in onde:
        (raiz / diretorio).mkdir(parents=True)
        (raiz / diretorio / REGRA_DO_BTUSB).write_text(
            "options btusb enable_autosuspend=0\n", encoding="utf-8"
        )
    return raiz


def _parametro(tmp_path: Path, valor: str | None) -> Path:
    parametro = tmp_path / "enable_autosuspend"
    if valor is not None:
        parametro.write_text(valor + "\n", encoding="utf-8")
    return parametro


def _doctor(raiz: Path, parametro: Path, python: str = sys.executable) -> str:
    roteiro = f"""
    set -uo pipefail
    ROOT_DIR="{RAIZ}"
    QUIET=0; WARNS=0; FAILS=0
    pass() {{ printf 'PASS %s\\n' "$*"; }}
    warn() {{ printf 'WARN %s\\n' "$*"; }}
    info() {{ printf 'INFO %s\\n' "$*"; }}
    conselho_de_instalacao() {{ printf 'rode a instalação'; }}
    so_no_checkout() {{ :; }}
    source <(sed -n '/^_regra_que_o_kmod_le()/,/^}}/p' "{DOCTOR}")
    source <(sed -n '/^check_btusb_autosuspend()/,/^}}/p' "{DOCTOR}")
    _python_do_produto() {{ printf '%s\\n' "{python}"; }}
    check_btusb_autosuspend
    """
    ambiente = {
        k: v for k, v in os.environ.items() if not k.startswith("HEFESTO_DOCTOR_BTUSB_")
    }
    ambiente["HEFESTO_DOCTOR_BTUSB_RAIZ"] = str(raiz)
    ambiente["HEFESTO_DOCTOR_BTUSB_PARAM"] = str(parametro)
    r = subprocess.run(
        ["bash", "-c", roteiro], capture_output=True, text=True, env=ambiente, check=False
    )
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def _os_dois(tmp_path: Path, valor: str | None, *onde: str) -> tuple[Item, str]:
    raiz = _raiz(tmp_path, *onde)
    parametro = _parametro(tmp_path, valor)
    return energia_do_radio(parametro=parametro, raiz=raiz), _doctor(raiz, parametro)


@pytest.mark.parametrize("pasta", ONDE_O_KMOD_LE)
@pytest.mark.parametrize("valor", ["Y", None])
def test_o_conf_em_qualquer_diretorio_do_kmod_vale_o_mesmo_que_em_etc(
    tmp_path: Path, pasta: str, valor: str | None
) -> None:
    (tmp_path / "aqui").mkdir()
    (tmp_path / "etc").mkdir()
    item, doctor = _os_dois(tmp_path / "aqui", valor, pasta)
    item_etc, doctor_etc = _os_dois(tmp_path / "etc", valor, "etc/modprobe.d")

    assert "está no lugar" in item.porque and "não está" not in item.porque, (
        f"o conf em /{pasta}: o exame disse «{item.porque}»"
    )
    assert (item.estado, item.porque) == (item_etc.estado, item_etc.porque)
    assert "modprobe.d do btusb instalado" in doctor, f"o conf em /{pasta}: {doctor}"
    assert doctor.split(" ", 1)[0] == doctor_etc.split(" ", 1)[0]


@pytest.mark.parametrize("valor", ["Y", None])
def test_o_conf_e_o_parametro_ligado_tem_o_mesmo_nivel_nos_dois(
    tmp_path: Path, valor: str | None
) -> None:
    item, doctor = _os_dois(tmp_path, valor, "usr/lib/modprobe.d")

    esperado = ESTADO_ATENCAO if valor == "Y" else ESTADO_NAO_SEI
    assert item.estado == esperado, item.porque
    assert doctor.split(" ", 1)[0] == NIVEL_NO_DOCTOR[esperado], doctor


def test_o_link_para_dev_null_em_etc_mascara_o_do_pacote(tmp_path: Path) -> None:
    raiz = _raiz(tmp_path, "usr/lib/modprobe.d")
    (raiz / "etc" / "modprobe.d").mkdir(parents=True)
    (raiz / "etc" / "modprobe.d" / REGRA_DO_BTUSB).symlink_to(os.devnull)
    parametro = _parametro(tmp_path, "Y")

    item = energia_do_radio(parametro=parametro, raiz=raiz)
    doctor = _doctor(raiz, parametro)

    assert "pode desligar o adaptador" in item.porque, item.porque
    assert "sem o conf do hefesto" in doctor, doctor


def test_sem_o_conf_em_lugar_nenhum_os_dois_dizem_que_falta(tmp_path: Path) -> None:
    item, doctor = _os_dois(tmp_path, None)

    assert "não está no lugar" in item.porque, item.porque
    assert "sem o conf do hefesto" in doctor, doctor


@pytest.mark.parametrize("python", ["", "/bin/false"])
def test_o_doctor_sem_o_python_do_produto_diz_que_nao_sabe(tmp_path: Path, python: str) -> None:
    raiz = _raiz(tmp_path, "usr/lib/modprobe.d")

    doctor = _doctor(raiz, _parametro(tmp_path, "Y"), python)

    assert doctor.startswith("INFO não consegui perguntar ao Hefesto"), doctor
    assert "enable_autosuspend=Y" in doctor, doctor
