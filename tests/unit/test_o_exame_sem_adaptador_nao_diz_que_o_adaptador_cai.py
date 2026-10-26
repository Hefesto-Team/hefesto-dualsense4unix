"""Sem adaptador BT ligado, o exame e o doctor dizem «não sei», nunca «o adaptador cai».

Os seis casos (conf sim ou não, com o parâmetro ``Y``, ``N`` ou ausente), no
Python e no `doctor.sh`, pelo mesmo critério: a atenção (e o `WARN`) só com o
parâmetro lido e ligado.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations.exame_da_mesa import (
    ESTADO_ATENCAO,
    ESTADO_CERTO,
    ESTADO_NAO_SEI,
    energia_do_radio,
)

RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"

CASOS = {
    (True, "Y"): (ESTADO_ATENCAO, "WARN"),
    (True, "N"): (ESTADO_CERTO, "PASS"),
    (True, None): (ESTADO_NAO_SEI, "INFO"),
    (False, "Y"): (ESTADO_ATENCAO, "WARN"),
    (False, "N"): (ESTADO_CERTO, "PASS"),
    (False, None): (ESTADO_NAO_SEI, "INFO"),
}


def _bancada(tmp_path: Path, com_conf: bool, valor: str | None) -> tuple[Path, Path]:
    parametro = tmp_path / "enable_autosuspend"
    if valor is not None:
        parametro.write_text(valor + "\n", encoding="utf-8")
    conf = tmp_path / "hefesto-btusb-no-autosuspend.conf"
    if com_conf:
        conf.write_text("options btusb enable_autosuspend=0\n", encoding="utf-8")
    return parametro, conf


def _doctor(parametro: Path, conf: Path) -> str:
    roteiro = f"""
    set -uo pipefail
    ROOT_DIR="{RAIZ}"
    QUIET=0; WARNS=0; FAILS=0
    pass() {{ printf 'PASS %s\\n' "$*"; }}
    warn() {{ printf 'WARN %s\\n' "$*"; }}
    info() {{ printf 'INFO %s\\n' "$*"; }}
    conselho_de_instalacao() {{ printf 'rode a instalação'; }}
    so_no_checkout() {{ :; }}
    source <(sed -n '/^check_btusb_autosuspend()/,/^}}/p' "{DOCTOR}")
    check_btusb_autosuspend
    """
    ambiente = {
        **os.environ,
        "HEFESTO_DOCTOR_BTUSB_CONF": str(conf),
        "HEFESTO_DOCTOR_BTUSB_PARAM": str(parametro),
    }
    r = subprocess.run(
        ["bash", "-c", roteiro], capture_output=True, text=True, env=ambiente
    )
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


@pytest.mark.parametrize(("com_conf", "valor"), list(CASOS))
def test_o_exame_responde_pelo_que_mediu(
    tmp_path: Path, com_conf: bool, valor: str | None
) -> None:
    parametro, conf = _bancada(tmp_path, com_conf, valor)
    item = energia_do_radio(parametro=parametro, conf=conf)

    assert item.estado == CASOS[(com_conf, valor)][0], (
        f"conf={com_conf} parâmetro={valor}: o exame deu {item.estado} "
        f"«{item.porque}»"
    )
    if valor is None:
        assert "cai" not in item.porque, (
            "sem adaptador ligado o exame afirma que o adaptador cai"
        )
        assert "nenhum adaptador" in item.porque
    if valor is None and not com_conf:
        assert "não está no lugar" in item.porque, (
            "o «não sei» sem a regra não diz que a regra falta"
        )
        assert item.cura and "instalação" in item.cura


@pytest.mark.parametrize(("com_conf", "valor"), list(CASOS))
def test_o_doctor_responde_pelo_mesmo_criterio(
    tmp_path: Path, com_conf: bool, valor: str | None
) -> None:
    parametro, conf = _bancada(tmp_path, com_conf, valor)
    saida = _doctor(parametro, conf)

    assert saida.splitlines()[0].split()[0] == CASOS[(com_conf, valor)][1], (
        f"conf={com_conf} parâmetro={valor}: o doctor disse\n{saida}"
    )
    assert "=?" not in saida, "o doctor escreveu um valor que não leu"
    if valor is None and not com_conf:
        assert "não carregado" in saida and "sem o conf" in saida
        assert "rode a instalação" in saida


def test_o_doctor_acompanha_o_desvio_da_regua() -> None:
    """Os ganchos têm de valer: sem eles a régua mediria o btusb de quem a roda."""
    fonte = DOCTOR.read_text(encoding="utf-8")
    assert "${HEFESTO_DOCTOR_BTUSB_CONF:-" in fonte
    assert "${HEFESTO_DOCTOR_BTUSB_PARAM:-" in fonte
