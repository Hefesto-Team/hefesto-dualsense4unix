"""O doctor sabe dizer se a contrapressão do uhid, quando pedida, está de pé.

INSTALL-E-UNINSTALL-DO-RADIO-01 (23/09/2026), os pedidos P-1 e P-7: o uhid com
contrapressão é opt-in (`--uhid-contrapressao`), o uninstall o desliga a quente
e os dois instaladores o rearmam — e o doctor não dizia nada. O pedido é a conf
em /etc/modprobe.d; o que vale é o parâmetro do módulo CARREGADO; e o DKMS só
constrói nos kernels do `patch/BASELINE` (`KERNELS_VALIDADOS`), que o doctor
lê em vez de digitar.

A MORDIDA, medida: tirar o laço dos kernels conferidos (todo kernel vira
«próximo boot») reprova o caso do kernel fora da lista; trocar o `warn` do
parâmetro desligado por `pass`, o dele.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"
BASELINE = RAIZ / "assets" / "dkms" / "uhid" / "patch" / "BASELINE"


def _kernel_conferido() -> str:
    achado = re.search(r"^KERNELS_VALIDADOS=(\S+)", BASELINE.read_text(encoding="utf-8"), re.M)
    assert achado, "o BASELINE do uhid perdeu KERNELS_VALIDADOS"
    return achado.group(1).split(",")[0] + "-generic"


def _doctor(tmp_path: Path, *, pedido: bool, param: str | None, kernel: str) -> str:
    conf = tmp_path / "hefesto-uhid.conf"
    if pedido:
        conf.write_text("options uhid backpressure=1\n", encoding="utf-8")
    parametro = tmp_path / "backpressure"
    if param is not None:
        parametro.write_text(param + "\n", encoding="utf-8")
    r = subprocess.run(
        [BASH, "-c", f'source "{DOCTOR}"; check_uhid_contrapressao'],
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            "HEFESTO_DOCTOR_UHID_CONF": str(conf),
            "HEFESTO_DOCTOR_UHID_PARAM": str(parametro),
            "HEFESTO_DOCTOR_KERNEL": kernel,
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return r.stdout + r.stderr


def test_sem_o_pedido_nao_ha_o_que_conferir(tmp_path: Path) -> None:
    assert _doctor(tmp_path, pedido=False, param="1", kernel=_kernel_conferido()).strip() == ""


def test_pedida_e_ligada_passa(tmp_path: Path) -> None:
    saida = _doctor(tmp_path, pedido=True, param="1", kernel=_kernel_conferido())
    assert "[ OK ] contrapressão do uhid ligada" in saida, saida


def test_pedida_e_desligada_a_quente_avisa_com_o_gesto(tmp_path: Path) -> None:
    saida = _doctor(tmp_path, pedido=True, param="0", kernel=_kernel_conferido())
    assert "[WARN]" in saida and "DESLIGADA" in saida and "sudo tee" in saida, saida


def test_de_fabrica_num_kernel_conferido_e_o_proximo_boot(tmp_path: Path) -> None:
    saida = _doctor(tmp_path, pedido=True, param=None, kernel=_kernel_conferido())
    assert "PRÓXIMO BOOT" in saida and "[WARN]" not in saida, saida


def test_de_fabrica_fora_da_lista_nao_vale(tmp_path: Path) -> None:
    saida = _doctor(tmp_path, pedido=True, param=None, kernel="6.9.0-1-generic")
    assert "[WARN]" in saida and "não está entre os conferidos" in saida, saida


def test_o_main_pergunta() -> None:
    assert "\n    check_uhid_contrapressao\n" in DOCTOR.read_text(encoding="utf-8")
