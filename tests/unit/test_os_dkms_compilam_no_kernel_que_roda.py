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
EXCLUSIVO = (
    'BUILD_EXCLUSIVE_KERNEL="$("${BASH_SOURCE[0]%/*}/preparar-o-fonte.py" --exclusivo '
    '"$kernelver" "${kernel_source_dir}" "${dkms_tree}/${PACKAGE_NAME}/${PACKAGE_VERSION}")"'
)
GUARDA_DO_AUTOINSTALL = (
    "if declare -F autoinstall >/dev/null && ! declare -f autoinstall | grep -qw 77; then"
)
KERNEL_NOVO = "7.9.1-1-generic"
PULA = 77
NENHUM_KERNEL = "^/"


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
    antes = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(modulo)
    finally:
        sys.dont_write_bytecode = antes
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
        linhas = conf.splitlines()
        assert PRE_BUILD in linhas, f"{pacote}: o dkms.conf não chama o preparador"
        assert EXCLUSIVO in linhas, f"{pacote}: o dkms.conf não decide o pulo ao ser lido"
        assert GUARDA_DO_AUTOINSTALL in linhas, (
            f"{pacote}: o DKMS que reprova o 77 no autoinstall quebraria o kernel novo"
        )
        assert [linha for linha in linhas if linha.startswith("BUILD_EXCLUSIVE_KERNEL=")] == [
            EXCLUSIVO
        ], f"{pacote}: o dkms.conf voltou a prender o build a uma lista de kernels"


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
    def __init__(self, raiz: Path, srcversion: str, versao_dos_headers: str = "") -> None:
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
        make = self.bin / "make"
        make.write_text(
            "#!/bin/sh\n"
            "for a; do case $a in\n"
            f"  kernelversion) echo {versao_dos_headers}; exit 0 ;;\n"
            '  M=*) : > "${a#M=}/uhid.ko" ;;\n'
            "esac; done\nexit 0\n",
            encoding="utf-8",
        )
        make.chmod(0o755)
        if versao_dos_headers:
            (self.ksrc / "Makefile").write_text("kernelversion:\n", encoding="utf-8")
        self.stable = raiz / "stable"

    def rodar(self, kver: str = KERNEL_NOVO, *antes: str) -> subprocess.CompletedProcess[str]:
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
                *antes,
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
        linhas = (self.veredito / f"fonte-{kver}.txt").read_text(encoding="utf-8").split("\n")
        return linhas[0], linhas[1].strip()

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


@pytest.mark.parametrize(("estado", "fica"), [("cache", True), ("sem-fonte", False)])
def test_o_dkms_lib_esquece_so_o_veredito_que_falhou(
    tmp_path: Path, estado: str, fica: bool
) -> None:
    arvore = tmp_path / "dkms"
    pasta = arvore / "hefesto-uhid" / "1.0.0"
    pasta.mkdir(parents=True)
    texto = pasta / f"fonte-{KERNEL_NOVO}.txt"
    guardado = pasta / f"fonte-{KERNEL_NOVO}.tar"
    texto.write_text(f"{estado}\na frase\nchave\n", encoding="utf-8")
    guardado.write_bytes(b"")
    falso = tmp_path / "bin"
    falso.mkdir()
    sudo = falso / "sudo"
    sudo.write_text('#!/bin/sh\nexec "$@"\n', encoding="utf-8")
    sudo.chmod(0o755)
    rodou = subprocess.run(
        [
            BASH,
            "-c",
            f"source '{REPO / 'scripts' / 'dkms_lib.sh'}'\n"
            f"_dkms_esquecer_o_veredito_que_falhou hefesto-uhid 1.0.0 {KERNEL_NOVO}",
        ],
        capture_output=True,
        text=True,
        check=False,
        env={
            **os.environ,
            "HEFESTO_DKMS_TREE": str(arvore),
            "PATH": f"{falso}:{os.environ['PATH']}",
        },
    )
    assert rodou.returncode == 0, rodou.stderr
    assert texto.exists() is fica
    assert guardado.exists() is fica


def _uhid_sem_srcversion(kernel: Kernel) -> None:
    modinfo = kernel.bin / "modinfo"
    modinfo.write_text(
        '#!/bin/sh\n[ "$2" = alias ] && echo uhid:devname\nexit 0\n', encoding="utf-8"
    )


def test_sem_srcversion_so_o_stable_da_versao_dos_headers_se_confere(tmp_path: Path) -> None:
    kver = "7.9.0-3-amd64"
    kernel = Kernel(tmp_path, "", versao_dos_headers="7.9.4")
    _uhid_sem_srcversion(kernel)
    ko = kernel.modulos / kver / "kernel" / "drivers" / "hid" / "uhid.ko"
    ko.parent.mkdir(parents=True)
    ko.write_bytes(b"")
    _uhid_de_fabrica(kernel.stable / "v7.9")
    _uhid_de_fabrica(kernel.stable / "v7.9.4")
    feito = kernel.rodar(kver)
    assert feito.returncode == 0, feito.stderr
    estado, frase = kernel.lido(kver)
    assert estado == "fabrica"
    assert "o stable v7.9.4 do kernel.org" in frase, frase
    assert "pelos alias e parâmetros no stable da versão que os headers declaram" in frase, frase


def test_sem_srcversion_e_sem_a_versao_dos_headers_o_stable_nao_entra(tmp_path: Path) -> None:
    kver = "7.9.0-3-amd64"
    kernel = Kernel(tmp_path, "")
    _uhid_sem_srcversion(kernel)
    ko = kernel.modulos / kver / "kernel" / "drivers" / "hid" / "uhid.ko"
    ko.parent.mkdir(parents=True)
    ko.write_bytes(b"")
    _uhid_de_fabrica(kernel.stable / "v7.9")
    feito = kernel.rodar(kver)
    assert feito.returncode == PULA, feito.stderr
    estado, frase = kernel.lido(kver)
    assert estado == "sem-fonte"
    assert "os headers não dizem a versão exata" in frase, frase
    assert "o stable v7.9 " not in frase, frase


def test_o_include_da_pasta_de_cima_entra_no_fecho_e_fica_fora_do_srcversion() -> None:
    preparador = _preparador("uhid")
    arvore = {
        "drivers/g/function/f_x.c": b'#include "u_x.h"\n#include "u_f.h"\nint a;\n',
        "drivers/g/function/u_x.h": b"int b;\n",
        "drivers/g/u_f.h": b"int c;\n",
    }
    faltou: list[str] = []
    arquivos = preparador._fecho("drivers/g/function/f_x.c", arvore.get, faltou)
    assert arquivos == arvore and not faltou
    so_da_pasta = {k: v for k, v in arvore.items() if "/function/" in k}
    assert preparador.srcversion(arquivos) == preparador.srcversion(so_da_pasta)
    del arvore["drivers/g/u_f.h"]
    assert preparador._fecho("drivers/g/function/f_x.c", arvore.get, faltou) is None
    assert faltou == ["drivers/g/function/u_f.h"]


def test_o_exclusivo_pula_quando_o_de_fabrica_fica_e_nao_toca_o_fonte(tmp_path: Path) -> None:
    kernel = Kernel(tmp_path, "0123456789ABCDEF0123456", versao_dos_headers="7.9.1")
    _uhid_de_fabrica(kernel.ksrc)
    makefile = (kernel.pacote / "Makefile").read_bytes()
    antes = kernel.uhid_c()
    feito = kernel.rodar(KERNEL_NOVO, "--exclusivo")
    assert feito.returncode == 0, feito.stderr
    assert feito.stdout == f"{NENHUM_KERNEL}\n"
    estado, frase = kernel.lido()
    assert estado == "sem-fonte", frase
    assert (kernel.pacote / "Makefile").read_bytes() == makefile
    assert kernel.uhid_c() == antes
    assert not (kernel.veredito / f"fonte-{KERNEL_NOVO}.tar").exists()


def test_o_exclusivo_prepara_e_o_pre_build_usa_o_guardado(tmp_path: Path) -> None:
    kernel = Kernel(tmp_path, _fabrica(), versao_dos_headers="7.9.1")
    _uhid_de_fabrica(kernel.ksrc)
    antes = kernel.uhid_c()
    feito = kernel.rodar(KERNEL_NOVO, "--exclusivo")
    assert feito.returncode == 0, feito.stderr
    assert feito.stdout == "\n"
    assert kernel.lido()[0] == "fabrica"
    assert (kernel.veredito / f"fonte-{KERNEL_NOVO}.tar").is_file()
    assert kernel.uhid_c() == antes
    shutil.rmtree(kernel.ksrc / "drivers")
    feito = kernel.rodar()
    assert feito.returncode == 0, feito.stderr
    assert kernel.uhid_c() == _baseline("uhid", "SHA256_PATCHED_C")


def test_o_exclusivo_nao_decide_sem_headers_nem_no_kernel_ja_construido(tmp_path: Path) -> None:
    kernel = Kernel(tmp_path, "0123456789ABCDEF0123456")
    feito = kernel.rodar(KERNEL_NOVO, "--exclusivo")
    assert (feito.returncode, feito.stdout) == (0, "\n"), feito.stderr
    assert not (kernel.veredito / f"fonte-{KERNEL_NOVO}.txt").exists()
    (kernel.ksrc / "Makefile").write_text("kernelversion:\n", encoding="utf-8")
    (kernel.veredito / KERNEL_NOVO).mkdir()
    feito = kernel.rodar(KERNEL_NOVO, "--exclusivo")
    assert (feito.returncode, feito.stdout) == (0, "\n"), feito.stderr
    assert not (kernel.veredito / f"fonte-{KERNEL_NOVO}.txt").exists()


@pytest.mark.parametrize(
    ("autoinstall", "esperado"),
    [('[ "$s" = 77 ]', "yes"), ('[ "$s" = 0 ]', ""), (None, "yes")],
)
def test_o_dkms_conf_lido_pelo_dkms_pula_e_tira_o_autoinstall_que_reprova_o_77(
    tmp_path: Path, autoinstall: str | None, esperado: str
) -> None:
    kernel = Kernel(tmp_path, "0123456789ABCDEF0123456", versao_dos_headers="7.9.1")
    _uhid_de_fabrica(kernel.ksrc)
    funcao = f"autoinstall() {{ {autoinstall}; }}\n" if autoinstall else ""
    lido = subprocess.run(
        [
            BASH,
            "-c",
            f"{funcao}kernelver={KERNEL_NOVO}\nkernel_source_dir='{kernel.ksrc}'\n"
            f"dkms_tree='{kernel.arvore_dkms}'\n"
            f". '{kernel.pacote / 'dkms.conf'}'\n"
            'printf "%s|%s" "$BUILD_EXCLUSIVE_KERNEL" "$AUTOINSTALL"',
        ],
        capture_output=True,
        text=True,
        check=False,
        env={
            **os.environ,
            "PATH": f"{kernel.bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "HEFESTO_DKMS_MODULES_ROOT": str(kernel.modulos),
            "HEFESTO_DKMS_FONTE_DA_DISTRO": str(tmp_path / "sem-distro-*.tar.xz"),
            "HEFESTO_DKMS_STABLE_URL": f"file://{kernel.stable}/{{tag}}/{{caminho}}",
        },
    )
    assert lido.returncode == 0, lido.stderr
    assert lido.stdout == f"{NENHUM_KERNEL}|{esperado}", lido.stderr
    assert kernel.lido()[0] == "sem-fonte"
