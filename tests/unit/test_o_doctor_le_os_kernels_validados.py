#!/usr/bin/env python3
"""A RÉGUA DO AVISO DE DRIFT: o doctor LÊ os kernels validados, não os digita.

O QUE ELE DIZIA, E ERA FALSO — medido em 01/09/2026, na máquina dela, minutos
depois de o `rtw88-usb` ser revalidado para o kernel 7.1.5-76070105:

    [WARN] kernel atual (7.1.5-76070105-generic) != kernel testado dos patches
           DKMS (7.0.11-76070011-generic) — (…) o módulo do hefesto pode estar
           MASCARANDO um in-tree mais novo (…) ou 'sudo dkms remove' para voltar
           ao in-tree

O módulo tinha sido medido contra ESTE kernel: fonte baixado, patch conferido,
`main.h` próprio, CRCs comparados com o `Module.symvers` do alvo. O aviso estava
alarmando sobre a cura recém-validada — e o conselho era ARRANCÁ-LA.

A FORMA É A QUE ESTA CASA JÁ NOMEOU ONZE VEZES NUMA LEVA SÓ: *a régua digitava o
que devia LER*. O `HEFESTO_DKMS_KERNEL_TESTED` era um literal no `doctor.sh`, e
o fato mudou de lugar sem ele.

O DONO DO FATO é `assets/dkms/rtw88-usb/patch/BASELINE:KERNELS_VALIDADOS` — o
mesmo que o `dkms.conf` usa no `BUILD_EXCLUSIVE_KERNEL`. Se o dkms CONSTRÓI para
um kernel, o doctor não pode chamar esse kernel de não-testado.

A MORDIDA: tire a leitura da BASELINE e o primeiro caso reprova; acrescente um
kernel à BASELINE sem pô-lo no `dkms.conf` (ou o contrário) e o terceiro reprova.
"""
from __future__ import annotations

import pathlib
import re
import subprocess

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"
BASELINE = RAIZ / "assets" / "dkms" / "rtw88-usb" / "patch" / "BASELINE"
DKMS_CONF = RAIZ / "assets" / "dkms" / "rtw88-usb" / "dkms.conf"


def _validados() -> list[str]:
    linha = re.search(r"^KERNELS_VALIDADOS=(.+)$", BASELINE.read_text(encoding="utf-8"), re.M)
    assert linha, "KERNELS_VALIDADOS sumiu da BASELINE"
    return linha.group(1).split()


def test_o_doctor_le_a_baseline_em_vez_de_digitar() -> None:
    fonte = DOCTOR.read_text(encoding="utf-8")
    assert "_dkms_kernels_validados" in fonte, (
        "o doctor voltou a comparar só com o literal `HEFESTO_DKMS_KERNEL_TESTED` "
        "— e vai chamar de não-testado um kernel que a BASELINE validou"
    )
    assert "KERNELS_VALIDADOS" in fonte, (
        "o doctor não lê mais a chave `KERNELS_VALIDADOS` do BASELINE"
    )


def test_o_aviso_nao_dispara_para_kernel_validado() -> None:
    """A prova de COMPORTAMENTO: roda a função com cada build validado.

    Ler o texto do script provaria que a leitura existe; isto prova que ela
    RESPONDE. O `uname -r` é dublado, então o caso vale em qualquer máquina.
    """
    for build in _validados():
        roteiro = f"""
        set -uo pipefail
        ROOT_DIR="{RAIZ}"
        HEFESTO_DKMS_KERNEL_TESTED="nao-e-este"
        WARNS=0
        pass() {{ printf 'PASS %s\\n' "$*"; }}
        warn() {{ printf 'WARN %s\\n' "$*"; }}
        uname() {{ printf '%s-generic\\n' "{build}"; }}
        source <(sed -n '/^_dkms_kernels_validados()/,/^}}/p' "{DOCTOR}")
        source <(sed -n '/^_check_dkms_kernel_drift()/,/^}}/p' "{DOCTOR}")
        _check_dkms_kernel_drift
        """
        r = subprocess.run(["bash", "-c", roteiro], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert r.stdout.startswith("PASS"), (
            f"o doctor avisou drift sobre {build}, que a BASELINE declara "
            f"validado:\n{r.stdout}{r.stderr}"
        )


def test_o_aviso_dispara_para_kernel_nao_validado() -> None:
    """A outra metade: um kernel de fora TEM de acender o aviso.

    Sem este caso, apagar a função inteira passaria — e o doctor deixaria de
    avisar quando o módulo REALMENTE está mascarando um in-tree mais novo.
    """
    roteiro = f"""
    set -uo pipefail
    ROOT_DIR="{RAIZ}"
    HEFESTO_DKMS_KERNEL_TESTED="nao-e-este"
    WARNS=0
    pass() {{ printf 'PASS %s\\n' "$*"; }}
    warn() {{ printf 'WARN %s\\n' "$*"; }}
    uname() {{ printf '9.9.9-99999999-generic\\n'; }}
    source <(sed -n '/^_dkms_kernels_validados()/,/^}}/p' "{DOCTOR}")
    source <(sed -n '/^_check_dkms_kernel_drift()/,/^}}/p' "{DOCTOR}")
    _check_dkms_kernel_drift
    """
    r = subprocess.run(["bash", "-c", roteiro], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith("WARN"), (
        f"um kernel FORA da lista não acendeu o aviso — o doctor deixou de "
        f"proteger contra o módulo de safra antiga mascarar o in-tree:\n{r.stdout}"
    )


@pytest.mark.parametrize("build", _validados())
def test_a_baseline_e_o_dkms_conf_concordam(build: str) -> None:
    """Um kernel validado na BASELINE e ausente do pino é cura que não constrói.

    E o inverso — no pino sem estar na BASELINE — é ABI que ninguém mediu. Os
    dois lados são o mesmo defeito visto de pontas opostas.
    """
    pino = re.search(
        r'^BUILD_EXCLUSIVE_KERNEL="(.+)"$', DKMS_CONF.read_text(encoding="utf-8"), re.M
    )
    assert pino, "BUILD_EXCLUSIVE_KERNEL sumiu do dkms.conf"
    assert build.replace(".", r"\.") in pino.group(1), (
        f"{build} está em KERNELS_VALIDADOS e não no BUILD_EXCLUSIVE_KERNEL — "
        f"o doctor vai dizer 'validado' sobre um kernel para o qual o dkms PULA "
        f"o build"
    )
