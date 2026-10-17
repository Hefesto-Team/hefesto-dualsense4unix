#!/usr/bin/env python3
"""A RÉGUA DO AVISO DE DRIFT: o doctor LÊ os kernels validados, não os digita."""
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
    """A prova de COMPORTAMENTO: roda a função com cada build validado."""
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
    """A outra metade: um kernel de fora TEM de acender o aviso."""
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
    """Um kernel validado na BASELINE e ausente do pino é cura que não constrói."""
    pino = re.search(
        r'^BUILD_EXCLUSIVE_KERNEL="(.+)"$', DKMS_CONF.read_text(encoding="utf-8"), re.M
    )
    assert pino, "BUILD_EXCLUSIVE_KERNEL sumiu do dkms.conf"
    assert build.replace(".", r"\.") in pino.group(1), (
        f"{build} está em KERNELS_VALIDADOS e não no BUILD_EXCLUSIVE_KERNEL — "
        f"o doctor vai dizer 'validado' sobre um kernel para o qual o dkms PULA "
        f"o build"
    )


_DKMS = RAIZ / "assets" / "dkms"
_PACOTES = ("hid-nintendo", "usb-f-hid", "uhid", "rtw88-usb")


def _validados_de(pacote: str) -> set[str]:
    texto = (_DKMS / pacote / "patch" / "BASELINE").read_text(encoding="utf-8")
    linha = re.search(r"^KERNELS_VALIDADOS=(.+)$", texto, re.M)
    assert linha, f"KERNELS_VALIDADOS sumiu da BASELINE do {pacote}"
    return set(linha.group(1).replace(",", " ").split())


def _pino_de(pacote: str) -> re.Pattern[str]:
    texto = (_DKMS / pacote / "dkms.conf").read_text(encoding="utf-8")
    casou = re.search(r'^BUILD_EXCLUSIVE_KERNEL="(.+)"$', texto, re.M)
    assert casou, f"BUILD_EXCLUSIVE_KERNEL sumiu do dkms.conf do {pacote}"
    return re.compile(casou.group(1))


@pytest.mark.parametrize("pacote", _PACOTES)
def test_os_modulos_acompanham_o_kernel_que_o_hid_playstation_ja_valida(pacote: str) -> None:
    """Um módulo que fica para trás no kernel novo some calado: o de fábrica assume.

    O `hid-playstation` é o molde de cada kernel que o sistema trouxe. Os outros
    quatro módulos DKMS têm de validar os mesmos builds que ele valida (cada um
    com o fonte de fábrica DELE medido), e a lista da BASELINE, o doctor e o pino do
    `dkms.conf` têm de dizer o mesmo.
    """
    molde = _validados_de("hid-playstation")
    assert "7.2.6-76070206" in molde
    faltam = {b for b in molde if b not in _validados_de(pacote)}
    assert not faltam, f"{pacote} não valida {sorted(faltam)}, que o hid-playstation valida"
    pino = _pino_de(pacote)
    for build in _validados_de(pacote):
        assert pino.match(f"{build}-generic"), f"{pacote}: o pino não constrói {build}"


def _doctor_em(tmp_path: pathlib.Path, checagem: str, kernel: str) -> str:
    """Roda uma checagem do doctor com o kernel dado, sem tocar no da máquina."""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    em_fabrica = "/lib/modules/k/kernel/drivers/usb/gadget/function/usb_f_hid.ko.zst"
    (bin_ / "modinfo").write_text(f'#!/bin/sh\necho "{em_fabrica}"\n', encoding="utf-8")
    (bin_ / "dkms").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    for nome in ("modinfo", "dkms"):
        (bin_ / nome).chmod(0o755)
    (tmp_path / "sys-module" / "usb_f_hid" / "parameters").mkdir(parents=True)
    (tmp_path / "efivars-vazia").mkdir()
    pedido = tmp_path / "hefesto-uhid.conf"
    pedido.write_text("options uhid backpressure=1\n", encoding="utf-8")
    r = subprocess.run(
        ["bash", "-c", f'source "{DOCTOR}"; {checagem}'],
        env={
            "PATH": f"{bin_}:/usr/bin:/bin",
            "HOME": str(tmp_path),
            "HEFESTO_DOCTOR_KERNEL": kernel,
            "HEFESTO_DOCTOR_SYS_MODULE": str(tmp_path / "sys-module"),
            "HEFESTO_EFIVARS_ROOT": str(tmp_path / "efivars-vazia"),
            "HEFESTO_DOCTOR_UHID_CONF": str(pedido),
            "HEFESTO_DOCTOR_UHID_PARAM": str(tmp_path / "sem-o-parametro"),
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return r.stdout + r.stderr


@pytest.mark.parametrize(
    ("pacote", "checagem"),
    [("usb-f-hid", "check_hefesto_usb_f_hid_dkms"), ("uhid", "check_uhid_contrapressao")],
)
def test_o_doctor_chama_de_conferido_cada_kernel_da_baseline(
    tmp_path: pathlib.Path, pacote: str, checagem: str
) -> None:
    """A prova de COMPORTAMENTO dos dois: o doctor lê a lista, com vírgula ou espaço.

    Com o de fábrica carregado num kernel da BASELINE, o doctor manda instalar
    (usb-f-hid) ou espera o próximo boot (uhid); nunca diz «não está entre os
    conferidos», que é a frase do kernel que ninguém mediu.
    """
    for build in sorted(_validados_de(pacote)):
        kernel = f"{build}-generic"
        (tmp_path / build).mkdir()
        saida = _doctor_em(tmp_path / build, checagem, kernel)
        assert "não está entre os conferidos" not in saida, f"{pacote} em {kernel}:\n{saida}"
        esperado = (
            f"não está instalada para o kernel {kernel}" if pacote == "usb-f-hid"
            else "PRÓXIMO BOOT"
        )
        assert esperado in saida, f"{pacote} em {kernel}:\n{saida}"
