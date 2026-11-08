#!/usr/bin/env python3
"""Ensaia o `preparar-o-fonte.py` de cada pacote DKMS contra um kernel que ainda não está instalado.

Recebe os pacotes de headers e de módulos do kernel candidato, já baixados por quem roda
(sem root, num diretório vazio), extrai tudo num diretório temporário e roda o preparador de
cada `assets/dkms/<pacote>/` contra essa árvore. A saída é o veredito que o DKMS gravaria
(`cache` ou `fabrica` quando vale; `sem-fonte`, `sem-fabrica`, `nao-aplica` ou `sem-serie`
quando cai) e a frase. Nada é instalado, e nada é escrito fora do diretório temporário.

Como baixar, sem root, no diretório `pacotes/`:

    apt-get download linux-headers-<v> linux-headers-<v>-generic linux-modules-<v>-generic
    dnf download kernel-core kernel-devel kernel-modules-core
    pacman -Sw --cachedir pacotes linux linux-headers

    o_kernel_candidato_sem_instalar.py pacotes/
    o_kernel_candidato_sem_instalar.py pacotes/ --sem-rede
    o_kernel_candidato_sem_instalar.py pacotes/ --sem-pasta-nova
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

RAIZ = Path(__file__).resolve().parents[2]
DKMS = RAIZ / "assets" / "dkms"
BEM = ("cache", "fabrica")
SEM_REDE = "http://127.0.0.1:9/{tag}/{caminho}"
SEM_FONTE_DA_DISTRO = "/nao-existe/linux-source-*/linux-source-*.tar.*"
SUFIXOS = (".deb", ".rpm", ".pkg.tar.zst", ".pkg.tar.xz", ".pkg.tar.gz", ".pkg.tar")


@dataclass
class Veredito:
    pacote: str
    estado: str
    frase: str

    @property
    def vale(self) -> bool:
        return self.estado in BEM

    def linha(self) -> str:
        return f"  {self.pacote:<16} {self.estado:<12} {self.frase}"


def _roda(comando: list[str], **kwargs: object) -> None:
    feito = subprocess.run(
        comando, capture_output=True, text=True, check=False, timeout=900, **kwargs  # type: ignore[call-overload]
    )
    if feito.returncode != 0:
        raise RuntimeError(f"{' '.join(comando[:2])} falhou: {feito.stderr.strip()[:300]}")


def extrair(pacote: Path, destino: Path) -> None:
    nome = pacote.name
    if nome.endswith(".deb"):
        _roda(["dpkg-deb", "-x", str(pacote), str(destino)])
    elif nome.endswith(".rpm"):
        cpio = subprocess.run(
            ["rpm2cpio", str(pacote)], capture_output=True, check=True, timeout=900
        ).stdout
        subprocess.run(
            ["cpio", "-idm", "--quiet"],
            input=cpio,
            cwd=destino,
            capture_output=True,
            check=True,
            timeout=900,
        )
    elif ".pkg.tar" in nome:
        _roda(["tar", "-xf", str(pacote), "-C", str(destino)])
    else:
        raise ValueError(f"pacote de formato desconhecido: {nome}")


def pacotes_da_pasta(pasta: Path) -> list[Path]:
    return sorted(p for p in pasta.iterdir() if p.is_file() and p.name.endswith(SUFIXOS))


@dataclass
class Kernel:
    kver: str
    ksrc: Path
    modulos: Path


def achar_o_kernel(raiz: Path) -> Kernel:
    modulos = raiz / "lib" / "modules"
    if not modulos.is_dir():
        modulos = raiz / "usr" / "lib" / "modules"
    versoes = sorted(p.name for p in modulos.iterdir() if p.is_dir()) if modulos.is_dir() else []
    if len(versoes) != 1:
        raise ValueError(f"esperava um kernel em {modulos}, achei {versoes}")
    kver = versoes[0]
    sufixo = re.sub(r"-generic$", "", kver)
    candidatos = [
        *sorted((raiz / "usr" / "src").glob(f"linux-headers-{kver}")),
        *sorted((raiz / "usr" / "src").glob(f"linux-headers-{sufixo}-generic")),
        *sorted((raiz / "usr" / "src").glob("kernels/*")),
        *sorted((raiz / "usr" / "src").glob("linux-headers-*")),
        *sorted(modulos.glob(f"{kver}/build")),
    ]
    ksrc = next((c for c in candidatos if (c / "Makefile").is_file()), None)
    if ksrc is None:
        raise ValueError("os pacotes de headers não trouxeram a árvore com Makefile")
    return Kernel(kver, ksrc, modulos)


@contextmanager
def _ambiente(modulos: Path, sem_rede: bool) -> Iterator[None]:
    novo = {
        "HEFESTO_DKMS_MODULES_ROOT": str(modulos),
        "HEFESTO_DKMS_FONTE_DA_DISTRO": SEM_FONTE_DA_DISTRO,
    }
    if sem_rede:
        novo["HEFESTO_DKMS_STABLE_URL"] = SEM_REDE
    antes = {chave: os.environ.get(chave) for chave in novo}
    os.environ.update(novo)
    try:
        yield
    finally:
        for chave, valor in antes.items():
            if valor is None:
                os.environ.pop(chave, None)
            else:
                os.environ[chave] = valor


def _carregar(pacote: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"preparar_{pacote.name.replace('-', '_')}", pacote / "preparar-o-fonte.py"
    )
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _sem_a_pasta_nova(pacote: Path, kver: str) -> None:
    build = kver.rsplit("-", 1)[0] if kver.endswith("-generic") else kver
    shutil.rmtree(pacote / "fonte-por-kernel" / build, ignore_errors=True)
    (pacote / "main-por-kernel" / f"main-{build}.h").unlink(missing_ok=True)
    raiz = pacote / "fonte-por-kernel" / "raiz.txt"
    if raiz.is_file():
        raiz.write_text(
            "".join(f"{b}\n" for b in raiz.read_text().split() if b != build), encoding="utf-8"
        )


def ensaiar_pacote(
    pacote: Path, kernel: Kernel, *, sem_rede: bool = False, sem_pasta_nova: bool = False
) -> Veredito:
    with tempfile.TemporaryDirectory(prefix="kernel-candidato-") as tmp:
        copia = Path(tmp) / pacote.name
        shutil.copytree(pacote, copia)
        if sem_pasta_nova:
            _sem_a_pasta_nova(copia, kernel.kver)
        destino = Path(tmp) / "destino"
        destino.mkdir()
        with _ambiente(kernel.modulos, sem_rede):
            preparador = _carregar(copia)
            modulo = preparador._conf("BUILT_MODULE_NAME[0]")
            estado, frase = preparador._decidir(kernel.kver, str(kernel.ksrc), modulo, destino)
    return Veredito(pacote.name, estado, frase)


def pacotes_dkms() -> list[Path]:
    return sorted(p.parent for p in DKMS.glob("*/preparar-o-fonte.py"))


def ensaiar(
    pasta_de_pacotes: Path, *, sem_rede: bool = False, sem_pasta_nova: bool = False
) -> tuple[Kernel, list[Veredito]]:
    with tempfile.TemporaryDirectory(prefix="kernel-candidato-raiz-") as tmp:
        raiz = Path(tmp)
        achados = pacotes_da_pasta(pasta_de_pacotes)
        if not achados:
            raise ValueError(f"nenhum pacote de kernel em {pasta_de_pacotes}")
        for pacote in achados:
            extrair(pacote, raiz)
        kernel = achar_o_kernel(raiz)
        vereditos = [
            ensaiar_pacote(p, kernel, sem_rede=sem_rede, sem_pasta_nova=sem_pasta_nova)
            for p in pacotes_dkms()
        ]
    return kernel, vereditos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pacotes", type=Path, help="pasta com os pacotes já baixados")
    parser.add_argument("--sem-rede", action="store_true", help="corta o stable do kernel.org")
    parser.add_argument(
        "--sem-pasta-nova",
        action="store_true",
        help="tira a pasta `fonte-por-kernel/<build>` do kernel ensaiado: o caminho da rede",
    )
    args = parser.parse_args(argv)
    try:
        kernel, vereditos = ensaiar(
            args.pacotes, sem_rede=args.sem_rede, sem_pasta_nova=args.sem_pasta_nova
        )
    except (ValueError, RuntimeError, OSError) as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 2
    print(f"kernel candidato: {kernel.kver}")
    for veredito in vereditos:
        print(veredito.linha())
    return 0 if all(v.vale for v in vereditos) else 1


if __name__ == "__main__":
    sys.exit(main())
