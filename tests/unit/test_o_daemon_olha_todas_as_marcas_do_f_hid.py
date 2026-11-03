"""O daemon só chama de curado o `usb_f_hid` que tem todas as marcas do `f_hid.c` do DKMS.

O-DAEMON-OLHA-TODAS-AS-MARCAS-DO-F-HID-01 (03/11/2026). O `0001` carregado tem só a
`get_report_sized`; o `0002` acrescenta a `get_report_refuses`. O daemon perguntava pela primeira,
e o módulo pela metade passava por curado: o aviso calava e o estado dizia «curado». Tudo roda num
`/sys/module` de mentira.

A MORDIDA: o `marcas_do_f_hid_que_faltam` olhar só a `get_report_sized` reprova
`test_so_a_marca_velha_nao_e_curado_e_o_aviso_diz_a_que_falta`.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import ipc_handlers
from hefesto_dualsense4unix.integrations import pad_usb, uhid_gamepad

RAIZ = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash") or "/bin/bash"
VELHA, NOVA = "get_report_sized", "get_report_refuses"


def _parametros(tmp_path: Path, *marcas: str, carregado: bool = True) -> str:
    pasta = tmp_path / "sys-module" / "usb_f_hid" / "parameters"
    if carregado:
        pasta.mkdir(parents=True)
        for marca in marcas:
            (pasta / marca).write_text("Y\n", encoding="ascii")
    return str(pasta)


@pytest.fixture
def avisos(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    linhas: list[dict[str, Any]] = []
    monkeypatch.setattr(
        uhid_gamepad.logger, "warning", lambda evento, **kw: linhas.append({"evento": evento, **kw})
    )
    monkeypatch.setattr(uhid_gamepad, "_F_HID_SEM_MARCA_AVISADO", [])
    monkeypatch.setattr(pad_usb, "_MARCAS_QUE_FALTAM", [None])
    return linhas


def _estado() -> dict[str, Any]:
    result: dict[str, Any] = {"gamepad_emulation": {"enabled": True}}
    ipc_handlers._com_a_marca_do_f_hid(result)
    emulacao = result["gamepad_emulation"]
    assert isinstance(emulacao, dict)
    return emulacao


def test_so_a_marca_velha_nao_e_curado_e_o_aviso_diz_a_que_falta(
    tmp_path: Path, avisos: list[dict[str, Any]]
) -> None:
    parametros = _parametros(tmp_path, VELHA)
    assert pad_usb.marcas_do_f_hid_que_faltam(parametros) == (NOVA,)
    assert pad_usb.f_hid_fecha_a_resposta(parametros) is False
    assert pad_usb.medir_a_marca_do_f_hid(parametros) is False
    uhid_gamepad._avisar_o_f_hid_sem_marca()
    uhid_gamepad._avisar_o_f_hid_sem_marca()
    assert [linha["evento"] for linha in avisos] == ["pad_usb_f_hid_de_fabrica"]
    assert avisos[0]["faltam"] == [NOVA]
    assert _estado() == {
        "enabled": True,
        "get_report_sized": False,
        "f_hid_marcas_que_faltam": [NOVA],
    }


def test_as_duas_marcas_e_curado(tmp_path: Path, avisos: list[dict[str, Any]]) -> None:
    parametros = _parametros(tmp_path, VELHA, NOVA)
    assert pad_usb.marcas_do_f_hid_que_faltam(parametros) == ()
    assert pad_usb.f_hid_fecha_a_resposta(parametros) is True
    assert pad_usb.medir_a_marca_do_f_hid(parametros) is True
    assert _estado() == {"enabled": True, "get_report_sized": True, "f_hid_marcas_que_faltam": []}


def test_o_de_fabrica_nao_tem_nenhuma(tmp_path: Path, avisos: list[dict[str, Any]]) -> None:
    parametros = _parametros(tmp_path)
    assert pad_usb.marcas_do_f_hid_que_faltam(parametros) == (VELHA, NOVA)
    assert pad_usb.medir_a_marca_do_f_hid(parametros) is False
    assert _estado()["f_hid_marcas_que_faltam"] == [VELHA, NOVA]


def test_sem_o_modulo_no_ar_e_none(tmp_path: Path, avisos: list[dict[str, Any]]) -> None:
    parametros = _parametros(tmp_path, carregado=False)
    assert pad_usb.marcas_do_f_hid_que_faltam(parametros) is None
    assert pad_usb.f_hid_fecha_a_resposta(parametros) is None
    assert pad_usb.medir_a_marca_do_f_hid(parametros) is None
    assert _estado() == {
        "enabled": True,
        "get_report_sized": None,
        "f_hid_marcas_que_faltam": None,
    }


def test_a_marca_com_outro_valor_falta(tmp_path: Path) -> None:
    parametros = _parametros(tmp_path, VELHA)
    Path(parametros, NOVA).write_text("N\n", encoding="ascii")
    assert pad_usb.marcas_do_f_hid_que_faltam(parametros) == (NOVA,)


def test_a_lista_do_daemon_e_a_do_fonte_e_a_do_shell() -> None:
    """Cada `module_param` booleano 0444 do `f_hid.c` é marca do daemon e do shell, e só eles."""
    fonte = (RAIZ / "assets" / "dkms" / "usb-f-hid" / "f_hid.c").read_text(encoding="utf-8")
    do_fonte = re.findall(r"module_param\((\w+), bool, 0444\)", fonte)
    do_shell = subprocess.run(
        [
            BASH,
            "-c",
            f'source "{RAIZ / "scripts" / "dkms_lib.sh"}"; '
            'printf "%s\\n" "${DKMS_MARCAS_DO_USB_F_HID[@]}"',
        ],
        capture_output=True, text=True, timeout=30, check=True,
    ).stdout.split()
    assert list(pad_usb.MARCAS_DO_F_HID) == do_fonte == do_shell, (
        pad_usb.MARCAS_DO_F_HID, do_fonte, do_shell
    )
