"""O `uhid` patchado só se constrói nos kernels conferidos — GOVERNADOR-DO-RADIO-01.

O `uhid` é o dono de TODO HID por Bluetooth da máquina. O DKMS da
contrapressão (RADIO-AFOGADO-02) o substitui por um `uhid.c` do v7.1 com duas
linhas a mais; construído contra um kernel cujo `uhid.c` de fábrica mudou, ele
COMPILA LIMPO e devolve o arquivo velho — a correção do upstream perdida em
silêncio. O estudo de 23/09 pediu o pino (`BUILD_EXCLUSIVE_KERNEL`), e esta
régua cobra três coisas:

1. o pino existe, e a lista do `dkms.conf` é a MESMA do `patch/BASELINE`
   (`KERNELS_VALIDADOS`), nos dois sentidos — a forma do `rtw88-usb`;
2. um kernel que ninguém conferiu fica de fora;
3. a procedência: o `uhid.c` da pasta é o `SHA256_PATCHED_C`, e o
   `patch -R` devolve o `SHA256_VANILLA_C`.

A MORDIDA, feita em 23/09/2026: tirar a linha ``BUILD_EXCLUSIVE_KERNEL`` do
``dkms.conf`` faz ``test_o_dkms_do_uhid_tem_pino_de_kernel`` reprovar; tirar um
build da regex faz ``test_cada_kernel_validado_casa_o_pino`` reprovar.
Devolvido o arquivo, md5 conferido.
"""

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


def test_o_pino_nao_aceita_kernel_que_ninguem_conferiu() -> None:
    validados = set(_baseline()["KERNELS_VALIDADOS"].split())
    pino = _pino()
    for build in ("7.2.0-76070200", "7.1.6-76070106", "6.17.9-76061709", "7.1.5-1"):
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
