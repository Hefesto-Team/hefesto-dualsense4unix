"""O `uhid` patchado só se constrói nos kernels conferidos — GOVERNADOR-DO-RADIO-01."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PASTA = RAIZ / "assets" / "dkms" / "uhid"
DKMS_CONF = PASTA / "dkms.conf"
BASELINE = PASTA / "patch" / "BASELINE"


def _baseline() -> dict[str, str]:
    saida: dict[str, str] = {}
    for linha in BASELINE.read_text(encoding="utf-8").splitlines():
        if linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        saida[chave.strip()] = valor.strip()
    return saida


def _pino() -> re.Pattern[str]:
    casou = re.search(
        r'^BUILD_EXCLUSIVE_KERNEL="([^"]+)"$', DKMS_CONF.read_text(encoding="utf-8"), re.M
    )
    assert casou, "o dkms.conf do uhid perdeu o BUILD_EXCLUSIVE_KERNEL"
    return re.compile(casou.group(1))


def test_o_dkms_do_uhid_tem_pino_de_kernel() -> None:
    _pino()


def test_cada_kernel_validado_casa_o_pino() -> None:
    validados = _baseline()["KERNELS_VALIDADOS"].split()
    assert validados, "KERNELS_VALIDADOS vazio: o pino não teria dono"
    pino = _pino()
    for build in validados:
        assert pino.match(f"{build}-generic"), (
            f"{build} está em KERNELS_VALIDADOS e o dkms.conf não o constrói"
        )


def test_a_regex_do_pino_e_os_conferidos_dizem_o_mesmo() -> None:
    """Os dois sentidos: build na regex e fora de KERNELS_VALIDADOS é kernel que ninguém mediu."""
    casou = re.search(
        r'^BUILD_EXCLUSIVE_KERNEL="([^"]+)"$', DKMS_CONF.read_text(encoding="utf-8"), re.M
    )
    assert casou, "o dkms.conf do uhid perdeu o BUILD_EXCLUSIVE_KERNEL"
    forma = re.fullmatch(r"\^\(?(.+?)\)?-", casou.group(1))
    assert forma, "o pino perdeu a forma `^(build|build)-`"
    na_regex = {alt.replace("\\.", ".") for alt in forma.group(1).split("|")}
    assert na_regex == set(_baseline()["KERNELS_VALIDADOS"].split())


def test_o_pino_nao_aceita_kernel_que_ninguem_conferiu() -> None:
    validados = set(_baseline()["KERNELS_VALIDADOS"].split())
    pino = _pino()
    for build in (
        "7.2.0-76070200", "7.1.6-76070106", "6.17.9-76061709", "7.1.5-1", "7.0.11-76070011",
    ):
        assert build not in validados
        assert not pino.match(f"{build}-generic"), (
            f"o pino deixa passar {build}, que ninguém conferiu"
        )


def test_o_uhid_da_pasta_e_o_patchado_do_baseline() -> None:
    fonte = (PASTA / "uhid.c").read_bytes()
    assert hashlib.sha256(fonte).hexdigest() == _baseline()["SHA256_PATCHED_C"]


def test_o_patch_desfeito_devolve_o_de_fabrica(tmp_path: Path) -> None:
    if shutil.which("patch") is None:  # pragma: no cover - a máquina da casa tem
        pytest.skip("sem o patch(1) nesta máquina")
    base = _baseline()
    copia = tmp_path / "uhid.c"
    copia.write_bytes((PASTA / "uhid.c").read_bytes())
    remendo = PASTA / "patch" / base["PATCH"]
    resultado = subprocess.run(
        ["patch", "-R", "-p0", "-s", str(copia)],
        input=remendo.read_bytes(),
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert hashlib.sha256(copia.read_bytes()).hexdigest() == base["SHA256_VANILLA_C"]


def test_a_base_e_o_stable_de_cada_kernel_pinado() -> None:
    """O `uhid.c` de base é o de fábrica de cada kernel pinado.

    Kernel da versão da base: o stable daquela versão. Kernel de OUTRA versão (o
    7.2.6): só com o `uhid.c` de fábrica dele medido e igual ao da base.
    """
    base = _baseline()
    versao_da_base = base["KERNEL_BASE"].removeprefix("v")
    for build in base["KERNELS_VALIDADOS"].split():
        if build.split("-", 1)[0] == versao_da_base:
            continue
        sufixo = build.replace(".", "_").replace("-", "_")
        assert base.get(f"SHA256_FABRICA_C_{sufixo}") == base["SHA256_VANILLA_C"], (
            f"{build} está pinado sobre a base {base['KERNEL_BASE']} sem o `uhid.c` de "
            "fábrica dele medido igual ao da base: o patch teria de ser refeito sobre "
            "o stable daquele kernel"
        )
        assert re.fullmatch(r"[0-9a-f]{40}", base.get(f"POP_LINUX_COMMIT_{sufixo}", "")), (
            f"{build}: o commit do pop-os/linux que o pacote nomeia não está gravado"
        )


def test_o_pino_aceita_o_7_2_6_que_o_sistema_trouxe() -> None:
    validados = _baseline()["KERNELS_VALIDADOS"].split()
    assert "7.2.6-76070206" in validados
    assert _pino().match("7.2.6-76070206-generic")
    assert not _pino().match("7.2.6-76070207-generic"), "o pino é pelo build exato"


def test_cada_kernel_pinado_tem_o_srcversion_de_fabrica_medido() -> None:
    """O terceiro passo do ritual: a medida que prova o pino fica escrita."""
    base = _baseline()
    medidos: dict[str, str] = {}
    for par in base.get("SRCVERSION_DE_FABRICA", "").split():
        build, _, srcversion = par.partition(":")
        assert re.fullmatch(r"[0-9A-F]{23}", srcversion), par
        medidos[build] = srcversion
    assert set(medidos) == set(base["KERNELS_VALIDADOS"].split()), (
        "kernel pinado sem o srcversion de fábrica medido, ou medida de um "
        "kernel que saiu do pino"
    )
