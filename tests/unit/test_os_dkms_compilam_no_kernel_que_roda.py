"""Os módulos DKMS compilam do de fábrica do kernel que roda, conferido pelo srcversion."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[2]
DKMS = REPO / "assets" / "dkms"
PACOTES = sorted(p.parent.name for p in DKMS.glob("*/dkms.conf"))
BASH = shutil.which("bash") or "/bin/bash"
PRE_BUILD = (
    'PRE_BUILD="./preparar-o-fonte.py $kernelver ${kernel_source_dir} '
    '${dkms_tree}/${PACKAGE_NAME}/${PACKAGE_VERSION}"'
)
KERNEL_NOVO = "7.9.1-1-generic"
PULA = 77


def _baseline(pacote: str, chave: str) -> str:
    texto = (DKMS / pacote / "patch" / "BASELINE").read_text(encoding="utf-8")
    achado = re.search(rf"^{chave}=(\S+)", texto, re.M)
    assert achado, f"{pacote}/patch/BASELINE não diz {chave}"
    return achado.group(1)


def _preparador(pacote: str) -> ModuleType:
    caminho = DKMS / pacote / "preparar-o-fonte.py"
    spec = importlib.util.spec_from_file_location(f"preparar_{pacote.replace('-', '_')}", caminho)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _desfazer(arvore: Path, serie: list[Path]) -> None:
    for patch in reversed(serie):
        subprocess.run(
            ["patch", "-s", "-R", "-p1", "-F0", "--batch", "-d", str(arvore), "-i", str(patch)],
            check=True,
            capture_output=True,
        )


def _uhid_de_fabrica(destino: Path) -> Path:
    arquivo = destino / "drivers" / "hid" / "uhid.c"
    arquivo.parent.mkdir(parents=True)
    shutil.copyfile(DKMS / "uhid" / "uhid.c", arquivo)
    _desfazer(destino, sorted((DKMS / "uhid" / "patch").glob("*.patch")))
    assert hashlib.sha256(arquivo.read_bytes()).hexdigest() == _baseline("uhid", "SHA256_VANILLA_C")
    return arquivo


def test_todo_pacote_traz_o_mesmo_preparador_no_pre_build() -> None:
    assert len(PACOTES) == 5, PACOTES
    referencia = (DKMS / "uhid" / "preparar-o-fonte.py").read_bytes()
    for pacote in PACOTES:
        preparador = DKMS / pacote / "preparar-o-fonte.py"
        assert preparador.read_bytes() == referencia, f"{pacote}: o preparador divergiu do uhid"
        assert os.access(preparador, os.X_OK), f"{pacote}: o preparador não é executável"
        conf = (DKMS / pacote / "dkms.conf").read_text(encoding="utf-8")
        assert PRE_BUILD in conf.splitlines(), f"{pacote}: o dkms.conf não chama o preparador"
        assert "BUILD_EXCLUSIVE_KERNEL=" not in conf, (
            f"{pacote}: o dkms.conf voltou a prender o build a uma lista de kernels"
        )


@pytest.mark.parametrize(
    ("pacote", "build", "esperado"),
    [
        ("uhid", None, _baseline("uhid", "SRCVERSION_DE_FABRICA").split(":")[1]),
        ("hid-playstation", "7.2.6-76070206", "EA0114B919E055190F87C71"),
    ],
)
def test_o_srcversion_do_preparador_e_o_do_modpost(
    tmp_path: Path, pacote: str, build: str | None, esperado: str
) -> None:
    preparador = _preparador(pacote)
    if build is None:
        _uhid_de_fabrica(tmp_path)
        principal = "drivers/hid/uhid.c"
    else:
        guardado = DKMS / pacote / "fonte-por-kernel" / build
        pasta = tmp_path / "drivers" / "hid"
        pasta.mkdir(parents=True)
        for arquivo in guardado.iterdir():
            if arquivo.is_file():
                shutil.copyfile(arquivo, pasta / arquivo.name)
        _desfazer(tmp_path, sorted((guardado / "patch").glob("*.patch")))
        principal = f"drivers/hid/{pacote}.c"
    arquivos = preparador._fecho(principal, preparador._da_arvore(tmp_path))
    assert arquivos, "o fecho dos includes locais não achou o fonte"
    assert preparador.srcversion(arquivos) == esperado


class Kernel:
    def __init__(self, raiz: Path, srcversion: str) -> None:
        self.raiz = raiz
        self.pacote = raiz / "pacote"
        shutil.copytree(DKMS / "uhid", self.pacote)
        self.ksrc = raiz / "ksrc"
        self.ksrc.mkdir()
        self.arvore_dkms = raiz / "dkms"
        self.veredito = self.arvore_dkms / "hefesto-uhid" / "1.0.0"
        self.veredito.mkdir(parents=True)
        self.modulos = raiz / "modules"
        ko = self.modulos / KERNEL_NOVO / "kernel" / "drivers" / "hid" / "uhid.ko"
        ko.parent.mkdir(parents=True)
        ko.write_bytes(b"")
        self.bin = raiz / "bin"
        self.bin.mkdir()
        modinfo = self.bin / "modinfo"
        modinfo.write_text(
            f'#!/bin/sh\n[ "$2" = srcversion ] && echo {srcversion}\nexit 0\n', encoding="utf-8"
        )
        modinfo.chmod(0o755)
        self.stable = raiz / "stable"

    def rodar(self, kver: str = KERNEL_NOVO) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env.update(
            PATH=f"{self.bin}{os.pathsep}{env.get('PATH', '')}",
            HEFESTO_DKMS_MODULES_ROOT=str(self.modulos),
            HEFESTO_DKMS_FONTE_DA_DISTRO=str(self.raiz / "sem-distro-*.tar.xz"),
            HEFESTO_DKMS_STABLE_URL=f"file://{self.stable}/{{tag}}/{{caminho}}",
        )
        return subprocess.run(
            [
                sys.executable,
                str(self.pacote / "preparar-o-fonte.py"),
                kver,
                str(self.ksrc),
                str(self.veredito),
            ],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

    def lido(self, kver: str = KERNEL_NOVO) -> tuple[str, str]:
        estado, frase = (
            (self.veredito / f"fonte-{kver}.txt").read_text(encoding="utf-8").split("\n", 1)
        )
        return estado, frase.strip()

    def uhid_c(self) -> str:
        return hashlib.sha256((self.pacote / "uhid.c").read_bytes()).hexdigest()


def _fabrica() -> str:
    return _baseline("uhid", "SRCVERSION_DE_FABRICA").split(":")[1]


def test_o_kernel_novo_compila_da_arvore_dele_conferida(tmp_path: Path) -> None:
    kernel = Kernel(tmp_path, _fabrica())
    _uhid_de_fabrica(kernel.ksrc)
    (kernel.pacote / "uhid.c").write_bytes(b"o arquivo de outro kernel\n")
    feito = kernel.rodar()
    assert feito.returncode == 0, feito.stderr
    estado, frase = kernel.lido()
    assert estado == "fabrica"
    assert "conferido pelo srcversion" in frase and "série de patch/ aplicou" in frase, frase
    assert kernel.uhid_c() == _baseline("uhid", "SHA256_PATCHED_C")


def test_o_kernel_novo_compila_do_stable_quando_a_arvore_nao_traz_o_fonte(
    tmp_path: Path,
) -> None:
    kernel = Kernel(tmp_path, _fabrica())
    _uhid_de_fabrica(kernel.stable / "v7.9.1")
    feito = kernel.rodar()
    assert feito.returncode == 0, feito.stderr
    estado, frase = kernel.lido()
    assert estado == "fabrica"
    assert "o stable v7.9.1 do kernel.org" in frase, frase
    assert kernel.uhid_c() == _baseline("uhid", "SHA256_PATCHED_C")


def test_fonte_que_nao_bate_com_o_srcversion_nao_compila(tmp_path: Path) -> None:
    kernel = Kernel(tmp_path, "0123456789ABCDEF0123456")
    _uhid_de_fabrica(kernel.ksrc)
    feito = kernel.rodar()
    assert feito.returncode == PULA, feito.stderr
    estado, frase = kernel.lido()
    assert estado == "sem-fonte"
    assert "não achei o fonte de fábrica de 7.9.1-1-generic" in frase, frase
    assert "instale a fonte do kernel da distro" in frase, frase
    assert (kernel.pacote / "Makefile").read_text(encoding="utf-8").startswith("$(error ")


def test_a_serie_que_nao_aplica_reprova_com_a_frase_certa(tmp_path: Path) -> None:
    kernel = Kernel(tmp_path, _fabrica())
    _uhid_de_fabrica(kernel.ksrc)
    patch = next((kernel.pacote / "patch").glob("*.patch"))
    texto = patch.read_text(encoding="utf-8")
    contexto = next(
        linha for linha in texto.splitlines() if linha.startswith(" ") and len(linha) > 8
    )
    patch.write_text(texto.replace(contexto, contexto + " quebrado", 1), encoding="utf-8")
    feito = kernel.rodar()
    assert feito.returncode == PULA, feito.stderr
    estado, frase = kernel.lido()
    assert estado == "nao-aplica"
    assert "nenhuma série guardada aplica no de fábrica de 7.9.1-1-generic" in frase, frase
    assert f"o {patch.name} deixa" in frase, frase
    assert "o ritual está em patch/BASELINE" in frase, frase
    assert (kernel.pacote / "Makefile").read_text(encoding="utf-8").startswith("$(error ")


def test_kernel_sem_o_modulo_de_fabrica_pula(tmp_path: Path) -> None:
    kernel = Kernel(tmp_path, _fabrica())
    _uhid_de_fabrica(kernel.ksrc)
    shutil.rmtree(kernel.modulos)
    feito = kernel.rodar()
    assert feito.returncode == PULA, feito.stderr
    estado, frase = kernel.lido()
    assert estado == "sem-fabrica"
    assert "não traz o uhid de fábrica" in frase, frase


def test_o_build_guardado_e_so_cache(tmp_path: Path) -> None:
    kernel = Kernel(tmp_path, "0123456789ABCDEF0123456")
    kver = "7.2.6-76070206-generic"
    feito = kernel.rodar(kver)
    assert feito.returncode == 0, feito.stderr
    estado, frase = kernel.lido(kver)
    assert estado == "cache"
    assert "o fonte da raiz serve a 7.2.6-76070206" in frase, frase
    assert kernel.uhid_c() == _baseline("uhid", "SHA256_PATCHED_C")


def test_o_dkms_lib_le_o_veredito_que_o_preparador_grava(tmp_path: Path) -> None:
    kernel = Kernel(tmp_path, "0123456789ABCDEF0123456")
    _uhid_de_fabrica(kernel.ksrc)
    kernel.rodar()
    lido = subprocess.run(
        [
            BASH,
            "-c",
            f"source '{REPO / 'scripts' / 'dkms_lib.sh'}'\n"
            f"dkms_veredito_do_fonte hefesto-uhid 1.0.0 {KERNEL_NOVO}",
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "HEFESTO_DKMS_TREE": str(kernel.arvore_dkms)},
    )
    assert lido.returncode == 0, lido.stderr
    estado, frase = lido.stdout.rstrip("\n").split("\t", 1)
    assert (estado, frase) == kernel.lido()
