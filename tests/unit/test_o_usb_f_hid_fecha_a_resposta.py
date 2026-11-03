"""O `usb_f_hid` do Hefesto fecha a resposta do GET_REPORT — O-F-HID-FECHA-A-RESPOSTA.

O de fábrica responde todo pedido de feature com 64 bytes e sem o pacote vazio;
o Wine e o SDL pedem 128, e cada pedido volta ETIMEDOUT aos ~5 s. O fonte em
`assets/dkms/usb-f-hid/` é o stable v7.1.5 com a série de `patch/`, e esta régua cobra a
proveniência dele: o cache (`fonte-por-kernel/raiz.txt`) e os KERNELS_VALIDADOS dizem
o mesmo, o `.c` da pasta é o do BASELINE, a série desfeita devolve o de fábrica, as
marcas `get_report_sized` e `get_report_refuses` estão no fonte e todo kernel de OUTRA
versão do cache (o 7.2.6) tem o de fábrica dele medido igual ao da base.

A MORDIDA: trocar um byte do `f_hid.c`, tirar a marca, pôr no cache um kernel sem
medida ou mandar o módulo para `/kernel` em vez de `/updates/dkms` reprova pelo
menos uma régua daqui.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PASTA = RAIZ / "assets" / "dkms" / "usb-f-hid"
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


def _serie() -> list[str]:
    """Os `PATCH=` do BASELINE, na ordem em que se aplicam."""
    return [
        linha.split("=", 1)[1].strip()
        for linha in BASELINE.read_text(encoding="utf-8").splitlines()
        if linha.startswith("PATCH=")
    ]


def _conf(chave: str) -> str:
    casou = re.search(rf'^{chave}="([^"]*)"$', DKMS_CONF.read_text(encoding="utf-8"), re.M)
    assert casou, f"o dkms.conf do usb-f-hid perdeu o {chave}"
    return casou.group(1)


def test_o_cache_e_os_conferidos_dizem_o_mesmo() -> None:
    """Kernel no cache sem estar nos conferidos é fonte que ninguém mediu."""
    raiz = (PASTA / "fonte-por-kernel" / "raiz.txt").read_text(encoding="utf-8").split()
    validados = [v.strip() for v in _baseline()["KERNELS_VALIDADOS"].split(",")]
    assert raiz and sorted(raiz) == sorted(validados), (raiz, validados)
    assert "7.2.6-76070206" in raiz


def test_todo_kernel_de_outra_versao_tem_o_fabrica_medido_igual_a_base() -> None:
    """O passo 1 do ritual: o `f_hid.c` e o `u_hid.h` de fábrica dele SÃO os da base.

    Kernel de outra versão que a base entra sem fonte por kernel só se o de fábrica
    dele foi medido e deu o mesmo sha256 — nunca se acrescenta o kernel com o arquivo
    de outro.
    """
    base = _baseline()
    versao_da_base = base["KERNEL_BASE"].removeprefix("v")
    for build in base["KERNELS_VALIDADOS"].split(","):
        if build.split("-", 1)[0] == versao_da_base:
            continue
        sufixo = build.replace(".", "_").replace("-", "_")
        assert base.get(f"SHA256_FABRICA_C_{sufixo}") == base["SHA256_VANILLA_C"], (
            f"{build} entra sobre a base {base['KERNEL_BASE']} sem o `f_hid.c` de fábrica "
            "dele medido igual ao da base: o patch teria de ser refeito sobre o stable dele"
        )
        assert base.get(f"SHA256_FABRICA_U_HID_H_{sufixo}") == base["SHA256_U_HID_H"], (
            f"{build}: o `u_hid.h` de fábrica dele não foi medido igual ao da base"
        )
        assert re.fullmatch(r"[0-9a-f]{40}", base.get(f"POP_LINUX_COMMIT_{sufixo}", "")), (
            f"{build}: o commit do pop-os/linux que o pacote nomeia não está gravado"
        )


def test_o_modulo_vai_para_updates_dkms_com_o_nome_de_fabrica() -> None:
    """O curado vence o de fábrica no `modprobe` só se morar em `updates/` com o mesmo nome."""
    assert _conf(r"DEST_MODULE_LOCATION\[0\]") == "/updates/dkms"
    assert _conf(r"BUILT_MODULE_NAME\[0\]") == "usb_f_hid"
    assert _conf("PACKAGE_NAME") == "hefesto-usb-f-hid"
    makefile = (PASTA / "Makefile").read_text(encoding="utf-8")
    assert "obj-m := usb_f_hid.o" in makefile
    assert "usb_f_hid-y := f_hid.o" in makefile


def test_o_f_hid_da_pasta_e_o_patchado_do_baseline() -> None:
    fonte = (PASTA / "f_hid.c").read_bytes()
    assert hashlib.sha256(fonte).hexdigest() == _baseline()["SHA256_PATCHED_C"]


def test_o_u_hid_h_e_o_de_fabrica() -> None:
    fonte = (PASTA / "u_hid.h").read_bytes()
    assert hashlib.sha256(fonte).hexdigest() == _baseline()["SHA256_U_HID_H"]


def test_a_marca_esta_no_fonte() -> None:
    """Nada mais no sysfs separa o curado do de fábrica: o daemon e o doctor leem pela marca."""
    fonte = (PASTA / "f_hid.c").read_text(encoding="utf-8")
    assert "static bool get_report_sized = true;" in fonte
    assert "module_param(get_report_sized, bool, 0444);" in fonte
    assert "static bool get_report_refuses = true;" in fonte
    assert "module_param(get_report_refuses, bool, 0444);" in fonte


def _patch(*args: str, entrada: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["patch", *args], input=entrada, capture_output=True, timeout=30, check=False
    )


def test_o_patch_desfeito_devolve_o_de_fabrica_e_refeito_o_da_pasta(tmp_path: Path) -> None:
    if shutil.which("patch") is None:  # pragma: no cover
        pytest.skip("sem o patch(1) nesta máquina")
    base = _baseline()
    serie = [(PASTA / "patch" / nome).read_bytes() for nome in _serie()]
    assert sorted(_serie()) == sorted(p.name for p in (PASTA / "patch").glob("*.patch"))
    copia = tmp_path / "f_hid.c"
    copia.write_bytes((PASTA / "f_hid.c").read_bytes())
    for remendo in reversed(serie):
        desfeito = _patch("-R", "-p5", "-s", str(copia), entrada=remendo)
        assert desfeito.returncode == 0, desfeito.stderr.decode()
    assert hashlib.sha256(copia.read_bytes()).hexdigest() == base["SHA256_VANILLA_C"]
    for remendo in serie:
        refeito = _patch("-p5", "-s", str(copia), entrada=remendo)
        assert refeito.returncode == 0, refeito.stderr.decode()
    assert hashlib.sha256(copia.read_bytes()).hexdigest() == base["SHA256_PATCHED_C"]


def test_o_patch_traz_a_marca() -> None:
    """A marca nasce do patch, não de uma edição solta no `.c` da pasta."""
    primeiro, segundo = (
        (PASTA / "patch" / nome).read_text(encoding="utf-8") for nome in _serie()
    )
    assert "+module_param(get_report_sized, bool, 0444);" in primeiro
    assert "+module_param(get_report_refuses, bool, 0444);" in segundo
