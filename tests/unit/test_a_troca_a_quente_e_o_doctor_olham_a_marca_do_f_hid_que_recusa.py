"""A troca a quente e o doctor pedem TODAS as marcas do `usb_f_hid` curado.

A-TROCA-A-QUENTE-E-O-DOCTOR-OLHAM-A-MARCA-DO-F-HID-QUE-RECUSA-01 (03/11/2026). O `0002`
acrescenta a marca `get_report_refuses`; com o `0001` carregado (só `get_report_sized`) a troca
dizia «nada a trocar» e o doctor dava verde sobre o módulo velho. A lista mora num dono só,
`DKMS_MARCAS_DO_USB_F_HID` em `scripts/dkms_lib.sh`. Tudo roda num `/sys/module` de mentira.

A MORDIDA: a lista do dono voltar a ser só `get_report_sized` reprova
`test_so_a_marca_velha_troca_a_quente` e `test_o_doctor_reprova_o_modulo_sem_a_marca_nova`.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
CAMADA = RAIZ / "scripts" / "lib" / "camada_de_maquina.sh"
DOCTOR = RAIZ / "scripts" / "doctor.sh"
DKMS_LIB = RAIZ / "scripts" / "dkms_lib.sh"
VELHA = "get_report_sized"
NOVA = "get_report_refuses"


def _sys_module(tmp_path: Path, marcas: tuple[str, ...] | None, refcnt: int = 0) -> Path:
    raiz = tmp_path / "sys-module"
    raiz.mkdir()
    if marcas is not None:
        modulo = raiz / "usb_f_hid"
        (modulo / "parameters").mkdir(parents=True)
        (modulo / "refcnt").write_text(f"{refcnt}\n", encoding="ascii")
        for nome in marcas:
            (modulo / "parameters" / nome).write_text("Y\n", encoding="ascii")
    return raiz


def _sudo(tmp_path: Path, sys_module: Path, traz: tuple[str, ...]) -> Path:
    """O `modprobe usb_f_hid` de mentira carrega um módulo com as marcas `traz`."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    modulo = sys_module / "usb_f_hid"
    ecos = "".join(f' echo Y > "{modulo}/parameters/{m}";' for m in traz)
    (bin_ / "sudo").write_text(
        "#!/bin/sh\n"
        f'echo "sudo $*" >> "{tmp_path}/chamadas.log"\n'
        'case "$*" in\n'
        f'  "modprobe -r usb_f_hid") rm -rf "{modulo}";;\n'
        f'  "modprobe usb_f_hid") mkdir -p "{modulo}/parameters"; echo 0 > "{modulo}/refcnt";'
        f"{ecos};\n"
        "esac\n"
        "exit 0\n",
        encoding="utf-8",
    )
    (bin_ / "systemctl").write_text("#!/bin/sh\nexit 3\n", encoding="utf-8")
    for nome in ("sudo", "systemctl"):
        (bin_ / nome).chmod(0o755)
    return bin_


def _trocar(
    tmp_path: Path, marcas: tuple[str, ...] | None, traz: tuple[str, ...] = (VELHA, NOVA)
) -> tuple[str, list[str], Path]:
    sys_module = _sys_module(tmp_path, marcas)
    bin_ = _sudo(tmp_path, sys_module, traz)
    gadgets = tmp_path / "usb_gadget"
    gadgets.mkdir()
    (tmp_path / "proc").mkdir()
    script = "\n".join(
        (
            "set -euo pipefail",
            f"ROOT_DIR='{RAIZ}'",
            'warn() { printf "WARN: %s\\n" "$*"; }',
            f"source '{CAMADA}'",
            "trocar_usb_f_hid_a_quente",
            'printf "PENDENTE: %s\\n" "${_REINICIO_PENDENTE[@]}"',
        )
    )
    r = subprocess.run(
        [BASH, "-c", script], capture_output=True, text=True, timeout=60, check=False,
        env={
            "PATH": f"{bin_}:/usr/bin:/bin",
            "HOME": str(tmp_path),
            "LC_ALL": "C.UTF-8",
            "HEFESTO_SYS_MODULE": str(sys_module),
            "HEFESTO_USB_GADGET_ROOT": str(gadgets),
            "HEFESTO_USB_F_HID_PRAZO_S": "1",
            "HEFESTO_RAIZ_PROC": str(tmp_path / "proc"),
        },
    )
    assert r.returncode == 0, r.stderr
    log = tmp_path / "chamadas.log"
    chamadas = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return r.stdout, chamadas, sys_module


def _doctor(
    tmp_path: Path, marcas: tuple[str, ...] | None, *, staged: bool, doctor: Path = DOCTOR
) -> str:
    bin_ = tmp_path / "bin-doctor"
    bin_.mkdir()
    arquivo = (
        "/lib/modules/k/updates/dkms/usb_f_hid.ko.zst" if staged
        else "/lib/modules/k/kernel/drivers/usb/gadget/function/usb_f_hid.ko.zst"
    )
    (bin_ / "modinfo").write_text(f'#!/bin/sh\necho "{arquivo}"\n', encoding="utf-8")
    (bin_ / "dkms").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    for nome in ("modinfo", "dkms"):
        (bin_ / nome).chmod(0o755)
    efivars = tmp_path / "efivars-vazia"
    efivars.mkdir()
    r = subprocess.run(
        [BASH, "-c", f'source "{doctor}"; check_hefesto_usb_f_hid_dkms'],
        env={
            "PATH": f"{bin_}:/usr/bin:/bin",
            "HOME": str(tmp_path),
            "HEFESTO_DOCTOR_KERNEL": "7.1.5-76070105-generic",
            "HEFESTO_DOCTOR_SYS_MODULE": str(_sys_module(tmp_path, marcas)),
            "HEFESTO_EFIVARS_ROOT": str(efivars),
            "HEFESTO_DKMS_TREE": str(tmp_path / "arvore-do-dkms"),
        },
        capture_output=True, text=True, timeout=30, check=False,
    )
    return r.stdout + r.stderr


def test_a_lista_do_dono_e_a_das_marcas_do_fonte() -> None:
    """Cada `module_param` booleano 0444 do `f_hid.c` do DKMS é uma marca da lista, e só eles."""
    fonte = (RAIZ / "assets" / "dkms" / "usb-f-hid" / "f_hid.c").read_text(encoding="utf-8")
    do_fonte = re.findall(r"module_param\((\w+), bool, 0444\)", fonte)
    r = subprocess.run(
        [BASH, "-c", f'source "{DKMS_LIB}"; printf "%s\\n" "${{DKMS_MARCAS_DO_USB_F_HID[@]}}"'],
        capture_output=True, text=True, timeout=30, check=True,
    )
    assert r.stdout.split() == do_fonte, (r.stdout, do_fonte)
    assert NOVA in do_fonte and VELHA in do_fonte


def test_so_a_marca_velha_troca_a_quente(tmp_path: Path) -> None:
    """O `0001` carregado e o `0002` staged: a troca troca, sem esperar o boot."""
    saida, chamadas, sys_module = _trocar(tmp_path, (VELHA,))
    assert chamadas == ["sudo modprobe -r usb_f_hid", "sudo modprobe usb_f_hid"], chamadas
    assert f"sem {NOVA}" in saida and "trocado a quente" in saida, saida
    assert (sys_module / "usb_f_hid" / "parameters" / NOVA).exists()
    assert "nada a trocar" not in saida, saida
    assert saida.rstrip().endswith("PENDENTE:"), saida


def test_com_todas_as_marcas_nada_a_trocar(tmp_path: Path) -> None:
    saida, chamadas, _ = _trocar(tmp_path, (VELHA, NOVA))
    assert chamadas == [], chamadas
    assert "nada a trocar" in saida, saida


def test_sem_marca_nenhuma_troca_como_hoje(tmp_path: Path) -> None:
    saida, chamadas, _ = _trocar(tmp_path, ())
    assert chamadas == ["sudo modprobe -r usb_f_hid", "sudo modprobe usb_f_hid"], chamadas
    assert f"sem {VELHA} {NOVA}" in saida and "trocado a quente" in saida, saida


def test_descarregado_nao_toca(tmp_path: Path) -> None:
    saida, chamadas, _ = _trocar(tmp_path, None)
    assert chamadas == [], chamadas
    assert "próximo carregamento" in saida, saida


def test_o_modulo_que_volta_sem_a_marca_nova_pede_o_boot(tmp_path: Path) -> None:
    """O staged ainda é o `0001`: a troca não anuncia cura, e o boot fica pendente."""
    saida, chamadas, _ = _trocar(tmp_path, (VELHA,), traz=(VELHA,))
    assert "sudo modprobe usb_f_hid" in chamadas, chamadas
    assert "trocado a quente" not in saida, saida
    assert f"segue sem {NOVA}" in saida, saida
    assert "PENDENTE: a função HID dos pads USB virtuais (usb_f_hid)" in saida, saida


@pytest.mark.parametrize("staged", [True, False])
def test_o_doctor_reprova_o_modulo_sem_a_marca_nova(tmp_path: Path, staged: bool) -> None:
    saida = _doctor(tmp_path, (VELHA,), staged=staged)
    assert "[FAIL]" in saida and "[ OK ]" not in saida, saida
    assert f"sem a marca {NOVA}" in saida, saida
    assert "de fábrica" not in saida, saida
    assert "install.sh" in saida, saida
    if staged:
        assert "não foi trocada" in saida, saida


def test_o_doctor_com_todas_as_marcas_passa(tmp_path: Path) -> None:
    saida = _doctor(tmp_path, (VELHA, NOVA), staged=True)
    assert "[ OK ]" in saida and "[FAIL]" not in saida, saida


def test_o_doctor_sem_marca_nenhuma_e_a_de_fabrica(tmp_path: Path) -> None:
    saida = _doctor(tmp_path, (), staged=False)
    assert "[FAIL]" in saida, saida
    assert "o jogo no Proton espera 5 s por pedido de feature" in saida, saida


def test_o_doctor_descarregado_nao_reclama(tmp_path: Path) -> None:
    saida = _doctor(tmp_path, None, staged=True)
    assert "[FAIL]" not in saida and "[WARN]" not in saida, saida
    assert "próximo carregamento" in saida, saida


def test_o_doctor_sem_o_dono_nao_da_verde(tmp_path: Path) -> None:
    """Sem o `dkms_lib.sh` ao lado, o doctor diz que não sabe; nunca passa calado."""
    copia = tmp_path / "raiz" / "scripts" / "doctor.sh"
    copia.parent.mkdir(parents=True)
    shutil.copy(DOCTOR, copia)
    saida = _doctor(tmp_path, (VELHA, NOVA), staged=True, doctor=copia)
    assert "[ OK ]" not in saida, saida
    assert "não sei conferir as marcas" in saida, saida


def test_nenhum_script_le_a_marca_fora_do_dono() -> None:
    """A pergunta «é o curado?» não volta a morar num `parameters/get_report_*` solto."""
    soltos = []
    for arquivo in [RAIZ / "install.sh", *sorted((RAIZ / "scripts").rglob("*.sh"))]:
        if arquivo == DKMS_LIB:
            continue
        texto = arquivo.read_text(encoding="utf-8", errors="replace")
        if re.search(r"parameters/get_report_\w+", texto):
            soltos.append(str(arquivo.relative_to(RAIZ)))
    assert soltos == [], soltos
