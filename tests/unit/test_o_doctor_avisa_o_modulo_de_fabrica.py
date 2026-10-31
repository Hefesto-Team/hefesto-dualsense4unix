"""O doctor avisa quando o módulo de fábrica assume e o microfone pelo rádio cai.

O-MODULO-DO-CONTROLE-SEGUE-O-KERNEL-NOVO-E-O-DOCTOR-AVISA-QUANDO-ELE-CAI-01, refeita por
OS-DKMS-COMPILAM-NO-KERNEL-QUE-RODA-01. O `hid-playstation` do Hefesto compila no kernel que
roda; quando não compila, o `preparar-o-fonte.py` grava o motivo no veredito da árvore do dkms,
e o `check_hefesto_hid_playstation_dkms` o repete no aviso. Sem veredito, o aviso manda
instalar para aquele kernel.

A MORDIDA: tirar o ramo do veredito (`elif [[ -n "${pulo}" ]]`) reprova
`test_o_motivo_do_pre_build_vira_o_aviso`; trocar o `warn` do de fábrica por `info` reprova
`test_o_de_fabrica_em_kernel_novo_avisa`.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests.unit.test_o_microfone_do_radio_pergunta_ao_driver import (
    _POPEN_DE_VERDADE,
    _RUN_DE_VERDADE,
    _sys_do_modulo,
)

RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"
DE_FABRICA = "A74F93FE20FF36683AF7614"
PACOTE = "hefesto-hid-playstation"
VERSAO = "1.0.0"

KERNELS_NOVOS = [
    "7.2.7-76070207-generic",
    "7.2.11-arch1-1",
    "7.3.0-76070300-generic",
]


def _doctor(
    tmp_path: Path,
    *,
    modulo: Path,
    staged: bool,
    kernel: str,
    veredito: tuple[str, str] | None = None,
) -> str:
    bin_ = tmp_path / "bin-doctor"
    bin_.mkdir()
    arquivo = (
        "/lib/modules/k/updates/dkms/hid-playstation.ko.zst"
        if staged
        else "/lib/modules/k/kernel/drivers/hid/hid-playstation.ko.zst"
    )
    (bin_ / "modinfo").write_text(f'#!/bin/sh\necho "{arquivo}"\n', encoding="utf-8")
    (bin_ / "dkms").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    for nome in ("modinfo", "dkms"):
        (bin_ / nome).chmod(0o755)
    raiz = tmp_path / "sys-module-doctor"
    raiz.mkdir()
    os.symlink(modulo, raiz / "hid_playstation")
    efivars = tmp_path / "efivars-vazia"
    efivars.mkdir()
    arvore = tmp_path / "arvore-do-dkms"
    if veredito is not None:
        pasta = arvore / PACOTE / VERSAO
        pasta.mkdir(parents=True)
        (pasta / f"fonte-{kernel}.txt").write_text("\n".join(veredito) + "\n", encoding="utf-8")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(subprocess, "run", _RUN_DE_VERDADE)
        mp.setattr(subprocess, "Popen", _POPEN_DE_VERDADE)
        r = subprocess.run(
            ["bash", "-c", f'source "{DOCTOR}"; check_hefesto_hid_playstation_dkms'],
            env={
                "PATH": f"{bin_}:/usr/bin:/bin",
                "HOME": str(tmp_path),
                "HEFESTO_DOCTOR_KERNEL": kernel,
                "HEFESTO_DOCTOR_SYS_MODULE": str(raiz),
                "HEFESTO_EFIVARS_ROOT": str(efivars),
                "HEFESTO_DKMS_TREE": str(arvore),
            },
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    return r.stdout + r.stderr


@pytest.mark.parametrize("kernel", KERNELS_NOVOS)
def test_o_de_fabrica_em_kernel_novo_avisa(tmp_path: Path, kernel: str) -> None:
    modulo = _sys_do_modulo(tmp_path, srcversion=DE_FABRICA)
    saida = _doctor(tmp_path, modulo=modulo, staged=False, kernel=kernel)
    assert "[WARN]" in saida, saida
    assert "microfone do DualSense pelo rádio" in saida, saida
    assert f"não está instalado para o kernel {kernel}" in saida, saida
    assert "[ OK ]" not in saida, saida


def test_o_motivo_do_pre_build_vira_o_aviso(tmp_path: Path) -> None:
    """O veredito que o `preparar-o-fonte.py` deixou é o motivo que o aviso dá."""
    frase = "hefesto-hid-playstation: nenhuma série guardada aplica no de fábrica de 7.2.11-arch1-1"
    modulo = _sys_do_modulo(tmp_path, srcversion=DE_FABRICA)
    saida = _doctor(
        tmp_path,
        modulo=modulo,
        staged=False,
        kernel=KERNELS_NOVOS[1],
        veredito=("nao-aplica", frase),
    )
    assert "[WARN]" in saida and frase in saida, saida
    assert "não está instalado para o kernel" not in saida, saida


@pytest.mark.parametrize("estado", ["cache", "fabrica"])
def test_o_veredito_de_quem_compilou_nao_e_motivo(tmp_path: Path, estado: str) -> None:
    modulo = _sys_do_modulo(tmp_path, srcversion=DE_FABRICA)
    saida = _doctor(
        tmp_path,
        modulo=modulo,
        staged=False,
        kernel=KERNELS_NOVOS[1],
        veredito=(estado, "hefesto-hid-playstation: o de fábrica veio do stable"),
    )
    assert "o de fábrica veio do stable" not in saida, saida
    assert "não está instalado para o kernel" in saida, saida


@pytest.mark.parametrize(
    "kernel", ["7.1.5-76070105-generic", "7.2.6-76070206-generic", *KERNELS_NOVOS]
)
def test_com_a_copia_do_hefesto_o_aviso_some(tmp_path: Path, kernel: str) -> None:
    modulo = _sys_do_modulo(tmp_path, marca="Y")
    saida = _doctor(tmp_path, modulo=modulo, staged=True, kernel=kernel)
    assert "[WARN]" not in saida, saida
    assert "[ OK ]" in saida and "descarta o áudio do microfone" in saida, saida
