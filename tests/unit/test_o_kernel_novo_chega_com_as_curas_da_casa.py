"""O 7.2.15 chega com as curas da casa: o fonte conferido de cada pacote mora no repositório."""

from __future__ import annotations

import hashlib
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).resolve().parents[2]
DKMS = RAIZ / "assets" / "dkms"
KERNEL = "7.2.15-76070215"
COMMIT_DO_POP = "d8e9a1a3852588f2fcebc4b730c3720ad2af524c"
PACOTES_COM_PASTA = ("hid-playstation", "hid-nintendo", "rtw88-usb")
SRCVERSION_DE_FABRICA = {
    "hid-playstation": "07657A261948C8834D0D66F",
    "hid-nintendo": "283B81807DB5B49E33E3E08",
    "rtw88-usb": "D87C7426A36E1E67721CC7F",
}
FABRICA_NO_DISCO = {
    "hid-playstation": "drivers/hid/hid-playstation",
    "hid-nintendo": "drivers/hid/hid-nintendo",
    "rtw88-usb": "drivers/net/wireless/realtek/rtw88/rtw88_usb",
}


def _carregar(nome: str, caminho: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(nome, caminho)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


ensaio = _carregar(
    "o_kernel_candidato_sem_instalar",
    RAIZ / "scripts" / "ensaios" / "o_kernel_candidato_sem_instalar.py",
)
ck = _carregar("conferir_o_kernel_novo_do_7_2_15", RAIZ / "scripts" / "conferir_o_kernel_novo.py")


def _linhas(pacote: str) -> list[str]:
    return (DKMS / pacote / "patch" / "BASELINE").read_text(encoding="utf-8").splitlines()


def _chaves(pacote: str) -> dict[str, str]:
    saida: dict[str, str] = {}
    for linha in _linhas(pacote):
        if linha.startswith("#") or "=" not in linha or linha.startswith(("PATCH", "POR_KERNEL")):
            continue
        chave, valor = linha.split("=", 1)
        saida[chave.strip()] = valor.strip()
    return saida


def _por_kernel(pacote: str) -> dict[str, str]:
    for linha in _linhas(pacote):
        if linha.startswith(f"POR_KERNEL={KERNEL} "):
            campos = dict(par.split("=", 1) for par in linha.split())
            campos.pop("POR_KERNEL")
            return campos
    return {}


def _sha(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def _validados(pacote: str) -> list[str]:
    return _chaves(pacote)["KERNELS_VALIDADOS"].split()


@pytest.mark.parametrize("pacote", PACOTES_COM_PASTA)
def test_o_kernel_novo_esta_entre_os_validados_e_tem_pasta(pacote: str) -> None:
    pasta = DKMS / pacote / "fonte-por-kernel" / KERNEL
    assert pasta.is_dir(), f"{pacote}: sem a pasta do {KERNEL}, o gancho do apt depende da rede"
    assert KERNEL in _validados(pacote)
    raiz = (DKMS / pacote / "fonte-por-kernel" / "raiz.txt").read_text().split()
    assert KERNEL not in raiz, "um build não serve da raiz e de uma pasta ao mesmo tempo"
    assert sorted(p.name for p in (pasta / "patch").glob("*.patch")) == sorted(
        p.name for p in (DKMS / pacote / "fonte-por-kernel" / "7.2.6-76070206" / "patch").iterdir()
    )


@pytest.mark.parametrize("pacote", ("hid-playstation", "hid-nintendo"))
def test_o_fonte_dos_hid_e_o_patchado_do_baseline(pacote: str) -> None:
    campos = _por_kernel(pacote)
    pasta = DKMS / pacote / "fonte-por-kernel" / KERNEL
    assert campos["KERNEL_BASE"] == "v7.2.15"
    assert campos["POP_LINUX_COMMIT"] == COMMIT_DO_POP
    assert _sha(pasta / f"{pacote}.c") == campos["SHA256_PATCHED_C"]
    assert _sha(pasta / "hid-ids.h") == campos["SHA256_HID_IDS_H"]


def test_o_fonte_do_rtw88_e_o_patchado_do_baseline() -> None:
    dados = _chaves("rtw88-usb")
    pasta = DKMS / "rtw88-usb" / "fonte-por-kernel" / KERNEL
    assert dados["POP_LINUX_COMMIT_7_2_15"] == COMMIT_DO_POP
    assert _sha(pasta / "usb.c") == dados["SHA256_PATCHED_C_7_2_15"]
    assert _sha(pasta / "rx.h") == dados["SHA256_RX_H_7_2_15"]
    main = DKMS / "rtw88-usb" / "main-por-kernel" / f"main-{KERNEL}.h"
    assert _sha(main) == dados["SHA256_MAIN_7_2_15_76070215"]
    assert dados["CRC_RTW_USB_PROBE_7_2_15"] != dados["CRC_RTW_USB_PROBE_7_2_6"], (
        "os CRCs dos exports mudaram no 7.2.15: o in-tree rtw88_8822bu carrega contra os novos"
    )


@pytest.mark.skipif(shutil.which("patch") is None, reason="sem o patch(1)")
@pytest.mark.parametrize("pacote", PACOTES_COM_PASTA)
def test_a_serie_da_pasta_desfeita_devolve_o_de_fabrica_do_kernel(pacote: str) -> None:
    bases = dict(ck._bases(pacote))
    da_pasta = bases[f"fonte-por-kernel/{KERNEL}"]
    if pacote == "rtw88-usb":
        esperado = _chaves(pacote)["SHA256_VANILLA_C_7_2_15"]
    else:
        esperado = _por_kernel(pacote)["SHA256_VANILLA_C"]
    principal = next(c for c in da_pasta if c.endswith(".c"))
    assert da_pasta[principal] == {esperado}


@pytest.mark.parametrize("pacote", PACOTES_COM_PASTA)
def test_o_srcversion_de_fabrica_do_kernel_novo_fica_ao_lado_da_serie(pacote: str) -> None:
    if pacote == "rtw88-usb":
        gravado = _chaves(pacote)["SRCVERSION_DE_FABRICA_7_2_15"]
    else:
        gravado = _por_kernel(pacote)["SRCVERSION_DE_FABRICA"]
    assert gravado == SRCVERSION_DE_FABRICA[pacote]


@pytest.mark.parametrize("pacote", PACOTES_COM_PASTA)
def test_o_srcversion_gravado_e_o_do_modulo_de_fabrica_desta_maquina(pacote: str) -> None:
    modulo = Path("/lib/modules") / f"{KERNEL}-generic" / "kernel" / FABRICA_NO_DISCO[pacote]
    arquivo = next(iter(sorted(modulo.parent.glob(f"{modulo.name}.ko*"))), None)
    if arquivo is None or shutil.which("modinfo") is None:
        pytest.skip(f"esta máquina não roda o {KERNEL}")
    feito = subprocess.run(
        ["modinfo", "-F", "srcversion", str(arquivo)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert feito.stdout.strip() == SRCVERSION_DE_FABRICA[pacote]


def _kernel_de_mentira(raiz: Path, pacote: str) -> object:
    preparador = ensaio._carregar(DKMS / pacote)
    principal = preparador._principal()
    modulo = preparador._conf("BUILT_MODULE_NAME[0]")
    kver = f"{KERNEL}-generic"
    fabrica = raiz / "modules" / kver / "kernel" / principal.rsplit("/", 1)[0] / f"{modulo}.ko"
    fabrica.parent.mkdir(parents=True)
    fabrica.write_bytes(b"")
    ksrc = raiz / "ksrc"
    ksrc.mkdir()
    return ensaio.Kernel(kver, ksrc, raiz / "modules")


@pytest.mark.parametrize("pacote", PACOTES_COM_PASTA)
def test_com_a_pasta_nova_o_veredito_e_cache_mesmo_sem_rede(pacote: str, tmp_path: Path) -> None:
    """D-0811-O-KERNEL-NOVO-CHEGA-COM-AS-CURAS-DA-CASA: a pasta no repositório dispensa a rede."""
    kernel = _kernel_de_mentira(tmp_path, pacote)
    veredito = ensaio.ensaiar_pacote(DKMS / pacote, kernel, sem_rede=True)
    assert veredito.estado == "cache", veredito.frase
    assert KERNEL in veredito.frase


@pytest.mark.parametrize("pacote", PACOTES_COM_PASTA)
def test_sem_a_pasta_nova_e_sem_rede_o_veredito_cai_com_a_frase(
    pacote: str, tmp_path: Path
) -> None:
    """D-0811-O-KERNEL-NOVO-CHEGA-COM-AS-CURAS-DA-CASA: sem a pasta e sem rede, cai com a frase."""
    kernel = _kernel_de_mentira(tmp_path, pacote)
    veredito = ensaio.ensaiar_pacote(DKMS / pacote, kernel, sem_rede=True, sem_pasta_nova=True)
    assert veredito.estado == "sem-fonte", veredito
    assert "o de fábrica assume" in veredito.frase


def test_o_ensaio_nao_escreve_no_pacote(tmp_path: Path) -> None:
    antes = sorted((p.relative_to(DKMS), _sha(p)) for p in DKMS.rglob("*") if p.is_file())
    kernel = _kernel_de_mentira(tmp_path, "hid-playstation")
    ensaio.ensaiar_pacote(DKMS / "hid-playstation", kernel, sem_rede=True, sem_pasta_nova=True)
    depois = sorted((p.relative_to(DKMS), _sha(p)) for p in DKMS.rglob("*") if p.is_file())
    assert depois == antes


def test_o_ensaio_acha_o_kernel_na_arvore_extraida(tmp_path: Path) -> None:
    (tmp_path / "lib" / "modules" / "9.9.9-1-generic").mkdir(parents=True)
    headers = tmp_path / "usr" / "src" / "linux-headers-9.9.9-1-generic"
    headers.mkdir(parents=True)
    (headers / "Makefile").write_text("", encoding="utf-8")
    kernel = ensaio.achar_o_kernel(tmp_path)
    assert (kernel.kver, kernel.ksrc) == ("9.9.9-1-generic", headers)
    (tmp_path / "lib" / "modules" / "9.9.8-1-generic").mkdir()
    with pytest.raises(ValueError, match="esperava um kernel"):
        ensaio.achar_o_kernel(tmp_path)


def test_o_fonte_do_kernel_viaja_byte_a_byte_pelo_commit() -> None:
    """D-0811-O-KERNEL-NOVO-CHEGA-COM-AS-CURAS-DA-CASA: o commit não troca palavra do fonte."""
    if shutil.which("git") is None or not (RAIZ / ".git").exists():
        pytest.skip("fora de uma árvore do git")
    fixados = sorted(
        str(p.relative_to(RAIZ))
        for p in DKMS.rglob("*")
        if p.is_file() and p.suffix in {".c", ".h", ".patch"}
    )
    assert fixados
    feito = subprocess.run(
        ["git", "-C", str(RAIZ), "check-attr", "ia-literal", "--", *fixados],
        capture_output=True,
        text=True,
        check=True,
    )
    soltos = [linha for linha in feito.stdout.splitlines() if not linha.endswith(": set")]
    assert not soltos, soltos
