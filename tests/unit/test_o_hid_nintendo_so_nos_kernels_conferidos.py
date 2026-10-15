"""O `hid-nintendo` patchado só se constrói nos kernels conferidos, cada um com o seu fonte."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PASTA = RAIZ / "assets" / "dkms" / "hid-nintendo"
DKMS_CONF = PASTA / "dkms.conf"
BASELINE = PASTA / "patch" / "BASELINE"
POR_KERNEL = PASTA / "fonte-por-kernel"
ESCOLHER = PASTA / "escolher-o-fonte.sh"
DRIVER = "hid-nintendo"


def _linhas() -> list[str]:
    return BASELINE.read_text(encoding="utf-8").splitlines()


def _baseline() -> dict[str, str]:
    saida: dict[str, str] = {}
    for linha in _linhas():
        if linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        if chave in ("PATCH", "POR_KERNEL"):
            continue
        saida[chave.strip()] = valor.strip()
    return saida


def _serie() -> list[str]:
    return [linha.partition("=")[2].strip() for linha in _linhas() if linha.startswith("PATCH=")]


def _por_kernel() -> dict[str, dict[str, str]]:
    """As linhas `POR_KERNEL=<build> CHAVE=valor …` do BASELINE, por build."""
    saida: dict[str, dict[str, str]] = {}
    for linha in _linhas():
        if not linha.startswith("POR_KERNEL="):
            continue
        campos = dict(par.split("=", 1) for par in linha.split())
        saida[campos.pop("POR_KERNEL")] = campos
    return saida


def _regex() -> str:
    casou = re.search(
        r'^BUILD_EXCLUSIVE_KERNEL="([^"]+)"$', DKMS_CONF.read_text(encoding="utf-8"), re.M
    )
    assert casou, "o dkms.conf do hid-nintendo perdeu o BUILD_EXCLUSIVE_KERNEL"
    return casou.group(1)


def _sha(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def _validados() -> list[str]:
    validados = _baseline()["KERNELS_VALIDADOS"].split()
    assert validados, "KERNELS_VALIDADOS vazio: o pino não teria dono"
    return validados


def _pastas() -> set[str]:
    return {p.name for p in POR_KERNEL.iterdir() if p.is_dir()}


def _da_raiz() -> set[str]:
    return set((POR_KERNEL / "raiz.txt").read_text(encoding="utf-8").split())


def test_o_dkms_do_hid_nintendo_tem_pino_e_escolhe_o_fonte() -> None:
    _regex()
    texto = DKMS_CONF.read_text(encoding="utf-8")
    assert re.search(r'^PRE_BUILD="\./escolher-o-fonte\.sh \$kernelver"$', texto, re.M), (
        "sem o PRE_BUILD, todo kernel do pino compila o `.c` da raiz"
    )


def test_a_regex_e_a_lista_dizem_o_mesmo_nos_dois_sentidos() -> None:
    validados = _validados()
    pino = re.compile(_regex())
    for build in validados:
        assert pino.match(f"{build}-generic"), (
            f"{build} está em KERNELS_VALIDADOS e o dkms.conf não o constrói"
        )
    alternativas = re.fullmatch(r"\^\((.+)\)-", _regex())
    assert alternativas, "a regex do pino deixou de ser a lista de builds exatos"
    da_regex = {alt.replace("\\.", ".") for alt in alternativas.group(1).split("|")}
    assert da_regex == set(validados), "a regex constrói um build que a lista não confere"


def test_o_pino_nao_aceita_kernel_que_ninguem_conferiu() -> None:
    validados = set(_validados())
    pino = re.compile(_regex())
    for build in ("9.9.9-99999999", "7.2.10-76070210", "7.3.0-76070300", "7.1.13-76070113"):
        assert build not in validados
        assert not pino.match(f"{build}-generic"), (
            f"o pino deixa passar {build}, que ninguém conferiu"
        )


def test_cada_build_conferido_tem_um_fonte_e_so_um() -> None:
    raiz, pastas = _da_raiz(), _pastas()
    assert not raiz & pastas, f"build com dois fontes: {sorted(raiz & pastas)}"
    assert raiz | pastas == set(_validados()), (
        "o raiz.txt e as pastas de fonte-por-kernel/ têm de cobrir KERNELS_VALIDADOS, e só ele"
    )
    assert pastas == set(_por_kernel()), "cada pasta de fonte-por-kernel/ tem a linha POR_KERNEL"


@pytest.mark.parametrize("build", sorted(_por_kernel()))
def test_o_fonte_de_cada_kernel_e_o_de_fabrica_dele_mais_a_serie(
    build: str, tmp_path: Path
) -> None:
    if shutil.which("patch") is None:  # pragma: no cover - a máquina da casa tem
        pytest.skip("sem o patch(1) nesta máquina")
    campos = _por_kernel()[build]
    pasta = POR_KERNEL / build
    assert _sha(pasta / f"{DRIVER}.c") == campos["SHA256_PATCHED_C"]
    assert _sha(pasta / "hid-ids.h") == campos["SHA256_HID_IDS_H"]
    assert sorted(p.name for p in (pasta / "patch").glob("*.patch")) == sorted(_serie())
    copia = tmp_path / f"{DRIVER}.c"
    copia.write_bytes((pasta / f"{DRIVER}.c").read_bytes())
    for nome in reversed(_serie()):
        resultado = subprocess.run(
            ["patch", "-R", "-p3", "-F0", "-s", str(copia)],
            input=(pasta / "patch" / nome).read_bytes(),
            capture_output=True,
            timeout=30,
            check=False,
        )
        assert resultado.returncode == 0, (nome, resultado.stdout, resultado.stderr)
    assert _sha(copia) == campos["SHA256_VANILLA_C"], (
        f"a série de {build} desfeita não devolve o de fábrica do kernel dele"
    )


def test_o_fonte_do_7_2_6_guarda_os_consertos_do_kernel_novo() -> None:
    fonte = (POR_KERNEL / "7.2.6-76070206" / f"{DRIVER}.c").read_text(encoding="utf-8")
    leitor = fonte[fonte.index("static int joycon_ctlr_read_handler(") :]
    leitor = leitor[: leitor.index("\n}\n")]
    assert "size >= sizeof(struct joycon_input_report)" in leitor, (
        "o conserto da leitura fora do buffer (34725ed47) sumiu"
    )
    assert "lic_procon_button_mappings" in fonte, "o HORI Wireless Switch Pad sumiu"
    assert "goto err_io_stop;" in fonte, "o 2e0d98dc8 (parar o IO antes do hid_hw_stop) sumiu"
    for parametro in ("bt_probe_retries", "usb_probe_degrade", "register_leds_on_set_failure"):
        assert f"module_param({parametro}," in fonte, f"a série perdeu o {parametro}"


def _pacote_como_no_usr_src(destino: Path) -> Path:
    """O pacote como o `dkms_lib.sh` o deixa em /usr/src: sem o `patch/` da raiz."""
    shutil.copytree(PASTA, destino)
    shutil.rmtree(destino / "patch")
    return destino


def _escolher(pasta: Path, kver: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(pasta / "escolher-o-fonte.sh"), kver],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_o_escolher_poe_o_fonte_do_build_exato(tmp_path: Path) -> None:
    pasta = _pacote_como_no_usr_src(tmp_path / "build")
    resultado = _escolher(pasta, "7.2.6-76070206-generic")
    assert resultado.returncode == 0, resultado.stderr
    campos = _por_kernel()["7.2.6-76070206"]
    assert _sha(pasta / f"{DRIVER}.c") == campos["SHA256_PATCHED_C"]
    assert _sha(pasta / "hid-ids.h") == campos["SHA256_HID_IDS_H"]


def test_o_escolher_deixa_a_raiz_nos_kernels_dela(tmp_path: Path) -> None:
    for build in sorted(_da_raiz()):
        pasta = _pacote_como_no_usr_src(tmp_path / build)
        resultado = _escolher(pasta, f"{build}-generic")
        assert resultado.returncode == 0, resultado.stderr
        assert _sha(pasta / f"{DRIVER}.c") == _baseline()["SHA256_PATCHED_C"]
        assert _sha(pasta / "hid-ids.h") == _baseline()["SHA256_HID_IDS_H"]


def test_o_escolher_recusa_o_build_sem_fonte(tmp_path: Path) -> None:
    pasta = _pacote_como_no_usr_src(tmp_path / "build")
    antes = _sha(pasta / f"{DRIVER}.c")
    resultado = _escolher(pasta, "9.9.9-99999999-generic")
    assert resultado.returncode != 0
    assert "9.9.9-99999999" in resultado.stderr
    assert _sha(pasta / f"{DRIVER}.c") == antes, "a recusa não pode trocar o fonte"
