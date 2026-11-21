"""O módulo da casa se reconhece pela cópia que o DKMS guarda, não pelo caminho.

O-MODULO-DA-CASA-SE-RECONHECE-EM-QUALQUER-DISTRO-01 (19/11/2026). O ``dkms`` 3.0.11 instala em
``/updates/dkms`` no Debian, no Ubuntu e no Arch, em ``/extra`` no Fedora e no RHEL e em
``/updates`` no openSUSE (``override_dest_module_location``). O dono, no Python
(``curas_da_casa.ko_da_casa``) e no shell (``dkms_ko_da_casa``), compara o ``.ko`` que o
``modinfo`` resolve com a cópia em ``<árvore>/hefesto-*/kernel-*/module/``, como o
``find_module_from_ko`` do próprio ``dkms``. TUDO É DE MENTIRA: a árvore, o ``modinfo`` e o
``/sys/module`` moram em ``tmp_path``.
"""
from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import curas_da_casa as cc
from tests.unit.dkms_de_mentira import ko_do_dkms

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"
KERNEL = "6.17.7-300.fc42.x86_64"
DESTINOS = ["extra", "updates", "updates/dkms"]


def _maquina(tmp_path: Path, ko: Path) -> cc.Maquina:
    dkms = tmp_path / "dkms"
    (dkms / "hefesto-hid-playstation" / "1.0.0").mkdir(parents=True, exist_ok=True)

    def comando(argv: Sequence[str]) -> str | None:
        if argv[0] == "modinfo" and argv[-1] == "hid_playstation":
            return f"filename:       {ko}\nsrcversion:     SRC\n"
        return None

    return cc.Maquina(sys_module=tmp_path / "sys-module", dkms=dkms, kernel=KERNEL,
                      comando=comando)


def _doctor(tmp_path: Path, ko: Path) -> str:
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (bin_ / "modinfo").write_text(f'#!/bin/sh\necho "{ko}"\n', encoding="utf-8")
    (bin_ / "modinfo").chmod(0o755)
    r = subprocess.run(
        [BASH, "-c", f'source "{DOCTOR}"; check_hefesto_hid_playstation_dkms'],
        env={"PATH": f"{bin_}:/usr/bin:/bin", "HOME": str(tmp_path),
             "HEFESTO_DOCTOR_KERNEL": KERNEL,
             "HEFESTO_SYS_MODULE": str(tmp_path / "sys-module"),
             "HEFESTO_EFIVARS_ROOT": str(tmp_path / "sem-efi"),
             "HEFESTO_DKMS_TREE": str(tmp_path / "dkms")},
        capture_output=True, text=True, timeout=60, check=False,
    )
    return r.stdout + r.stderr


@pytest.mark.parametrize("destino", DESTINOS)
def test_o_ko_do_dkms_vale_em_todo_destino(tmp_path: Path, destino: str) -> None:
    """D-1911-O-MODULO-DA-CASA-E-A-COPIA-QUE-O-DKMS-GUARDA: vale onde o dkms o pôs."""
    ko = ko_do_dkms(tmp_path, tmp_path / "dkms", "hefesto-hid-playstation",
                    "hid-playstation.ko.zst", destino=destino, kernel=KERNEL)
    assert cc.driver_do_dualsense(_maquina(tmp_path, ko)).estado == cc.VALE
    (tmp_path / "sys-module").mkdir()
    saida = _doctor(tmp_path, ko)
    assert "o do Hefesto entra na próxima conexão" in saida, saida


def test_o_de_fabrica_cai_mesmo_com_o_do_dkms_guardado(tmp_path: Path) -> None:
    ko_do_dkms(tmp_path, tmp_path / "dkms", "hefesto-hid-playstation", "hid-playstation.ko.zst",
               destino="extra", kernel=KERNEL)
    fabrica = tmp_path / "lib" / "modules" / KERNEL / "kernel/drivers/hid/hid-playstation.ko.zst"
    fabrica.parent.mkdir(parents=True)
    fabrica.write_bytes(b"o de fabrica")
    cura = cc.driver_do_dualsense(_maquina(tmp_path, fabrica))
    assert (cura.estado, cura.dica) == (cc.CAIU, cc.RODE_O_INSTALADOR)
    assert cura.frase == f"O driver do DualSense é o de fábrica no kernel {KERNEL}"
    (tmp_path / "sys-module").mkdir()
    saida = _doctor(tmp_path, fabrica)
    assert "o do Hefesto entra" not in saida, saida
