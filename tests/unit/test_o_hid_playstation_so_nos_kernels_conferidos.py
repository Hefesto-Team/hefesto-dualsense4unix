"""O cache do `hid-playstation`: cada kernel conferido tem o seu fonte, de fábrica mais a série."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PASTA = RAIZ / "assets" / "dkms" / "hid-playstation"
DKMS_CONF = PASTA / "dkms.conf"
BASELINE = PASTA / "patch" / "BASELINE"
POR_KERNEL = PASTA / "fonte-por-kernel"
DRIVER = "hid-playstation"


def _baseline() -> dict[str, str]:
    saida: dict[str, str] = {}
    for linha in BASELINE.read_text(encoding="utf-8").splitlines():
        if linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        if chave.strip() in ("PATCH", "POR_KERNEL"):
            continue
        saida[chave.strip()] = valor.strip()
    return saida


def _serie() -> list[str]:
    return [
        linha.partition("=")[2].strip()
        for linha in BASELINE.read_text(encoding="utf-8").splitlines()
        if linha.startswith("PATCH=")
    ]


def _por_kernel() -> dict[str, dict[str, str]]:
    """As linhas `POR_KERNEL=<build> CHAVE=valor …` do BASELINE, por build."""
    saida: dict[str, dict[str, str]] = {}
    for linha in BASELINE.read_text(encoding="utf-8").splitlines():
        if linha.startswith("POR_KERNEL="):
            campos = dict(par.split("=", 1) for par in linha.split())
            saida[campos.pop("POR_KERNEL")] = campos
    return saida


def _da_raiz() -> set[str]:
    return set((POR_KERNEL / "raiz.txt").read_text(encoding="utf-8").split())


def _sha(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def _desfaz_a_serie(fonte: Path, pasta_da_serie: Path, destino: Path) -> str:
    """Desfaz a série, na ordem inversa e sem fuzz, e devolve o sha do que sobrou."""
    destino.write_bytes(fonte.read_bytes())
    for nome in reversed(_serie()):
        resultado = subprocess.run(
            ["patch", "-R", "-p3", "-F0", "-s", str(destino)],
            input=(pasta_da_serie / nome).read_bytes(),
            capture_output=True,
            timeout=30,
            check=False,
        )
        assert resultado.returncode == 0, (nome, resultado.stdout, resultado.stderr)
    return _sha(destino)


def test_a_base_e_o_stable_de_cada_kernel_pinado() -> None:
    """O `.c` de base é o da versão EXATA de cada kernel do cache, a da raiz ou a da pasta dele."""
    base = _baseline()
    por_kernel = _por_kernel()
    for build in base["KERNELS_VALIDADOS"].split():
        kernel_base = por_kernel.get(build, base)["KERNEL_BASE"]
        assert build.split("-", 1)[0] == kernel_base.removeprefix("v"), (
            f"{build} está no cache sobre a base {kernel_base}: o "
            "`hid-playstation.c` de fábrica dele é o do stable daquela versão"
        )
    assert base["KERNEL_TESTED"].removesuffix("-generic") in base["KERNELS_VALIDADOS"].split()


def test_cada_build_conferido_tem_um_fonte_e_so_um() -> None:
    pastas = {p.name for p in POR_KERNEL.iterdir() if p.is_dir()}
    raiz = _da_raiz()
    assert not raiz & pastas, f"build com dois fontes: {sorted(raiz & pastas)}"
    assert raiz | pastas == set(_baseline()["KERNELS_VALIDADOS"].split())
    assert pastas == set(_por_kernel()), "cada pasta de fonte-por-kernel/ tem a linha POR_KERNEL"


@pytest.mark.parametrize("build", sorted(_por_kernel()))
def test_o_fonte_de_cada_kernel_e_o_de_fabrica_dele_mais_a_serie(
    build: str, tmp_path: Path
) -> None:
    if shutil.which("patch") is None:  # pragma: no cover
        pytest.skip("sem o patch(1) nesta máquina")
    campos = _por_kernel()[build]
    pasta = POR_KERNEL / build
    assert _sha(pasta / f"{DRIVER}.c") == campos["SHA256_PATCHED_C"]
    assert _sha(pasta / "hid-ids.h") == campos["SHA256_HID_IDS_H"]
    assert sorted(p.name for p in (pasta / "patch").glob("*.patch")) == sorted(_serie())
    desfeito = _desfaz_a_serie(pasta / f"{DRIVER}.c", pasta / "patch", tmp_path / "x.c")
    assert desfeito == campos["SHA256_VANILLA_C"], (
        f"a série de {build} desfeita não devolve o de fábrica do kernel dele"
    )


def test_o_fonte_do_7_2_6_guarda_o_edge_do_kernel_e_a_guarda_do_microfone() -> None:
    fonte = (POR_KERNEL / "7.2.6-76070206" / f"{DRIVER}.c").read_text(encoding="utf-8")
    assert "ds->is_edge = true;" in fonte, "os botões de trás do Edge, do 7.2, sumiram"
    assert "BTN_TRIGGER_HAPPY4" in fonte
    assert "module_param(mic_frames_ignored, bool, 0444);" in fonte
    assert "if (data[1] & DS_INPUT_BT_FLAG_AUDIO)" in fonte


def test_o_c_da_pasta_e_o_patchado_do_baseline() -> None:
    fonte = (PASTA / "hid-playstation.c").read_bytes()
    assert hashlib.sha256(fonte).hexdigest() == _baseline()["SHA256_PATCHED_C"]


def test_a_serie_desfeita_devolve_o_de_fabrica(tmp_path: Path) -> None:
    if shutil.which("patch") is None:  # pragma: no cover
        pytest.skip("sem o patch(1) nesta máquina")
    copia = tmp_path / "hid-playstation.c"
    copia.write_bytes((PASTA / "hid-playstation.c").read_bytes())
    for nome in reversed(_serie()):
        resultado = subprocess.run(
            ["patch", "-R", "-p3", "-s", str(copia)],
            input=(PASTA / "patch" / nome).read_bytes(),
            capture_output=True,
            timeout=30,
            check=False,
        )
        assert resultado.returncode == 0, (nome, resultado.stderr)
    assert hashlib.sha256(copia.read_bytes()).hexdigest() == _baseline()["SHA256_VANILLA_C"]


def test_a_marca_do_0003_e_so_de_leitura() -> None:
    """A marca não se escreve pelo sysfs, e o `.c` e o patch dizem a mesma coisa."""
    fonte = (PASTA / "hid-playstation.c").read_text(encoding="utf-8")
    remendo = next((PASTA / "patch").glob("0003-*.patch")).read_text(encoding="utf-8")
    assert "module_param(mic_frames_ignored, bool, 0444);" in fonte
    assert "+module_param(mic_frames_ignored, bool, 0444);" in remendo
    assert "static bool mic_frames_ignored = true;" in fonte
    assert "if (data[1] & DS_INPUT_BT_FLAG_AUDIO)" in fonte


def test_o_srcversion_do_0003_sem_a_marca_e_o_mesmo_no_daemon() -> None:
    """Uma lista, dois lugares: o `BASELINE` mede, o daemon consulta."""
    from hefesto_dualsense4unix.daemon.subsystems import bt_mic

    medido = set(_baseline()["SRCVERSION_DO_0003_SEM_A_MARCA"].split())
    assert all(re.fullmatch(r"[0-9A-F]{23}", v) for v in medido), medido
    assert medido == set(bt_mic.SRCVERSION_DO_0003_SEM_A_MARCA)
