"""O ajudante root do atualizador: verbos fechados, nenhum argumento livre, e a soma conferida.

O-HEFESTO-SE-ATUALIZA-INTEIRO-01, volta 1 (08/11/2026). O script roda como quem testa, nunca como
root: sem root ele só age com as pastas desviadas por ``HEFESTO_ATUALIZADOR_*``, e o ``apt-get``,
o ``dpkg-query``, o ``dkms``, o ``curl`` e o ``bootctl`` são dublês num ``PATH`` próprio que
anotam a chamada.

AS MORDIDAS (feitas na sprint, com a cura devolvida): a regra com curinga reprova o caso da regra;
o dkms_lib.sh sem o chown reprova o caso do fonte só do root;
o grupo livre aceito reprova o caso do grupo; o DKMS refeito com fonte que não é só do dono
reprova o caso do fonte; o MangoHud instalado sem conferir o digest reprova o caso da soma errada;
a subida do apt sem segurar os pacotes da casa reprova o caso dos backports; o voltar do kernel
sem o registro (o de antes, que ia ao «oldkern» de qualquer jeito) reprova o caso do kernel; o
registro que não se apaga reprova a segunda volta; o voltar do MangoHud que troca as duas versões
reprova a segunda volta dele. Em 20/11/2026: o hold dos da casa e o dpkg do conserto sem a saída
da espera reprovam o caso de quem esbarra na trava; o apt sem essa saída, o caso da trava ocupada.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import pwd
import re
import shutil
import subprocess
import tarfile
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
INSTALADOS = (("nvidia-driver-595", "595.104.02-0ubuntu1"),
              ("libnvidia-gl-595", "595.104.02-0ubuntu1"), ("linux-system76", "7.2.15.76070215"),
              ("linux-image-7.2.15", "7.2.15-1"),
              ("curl", "8.5.0-2ubuntu10"), ("bluez", "5.87-0ubuntu0.1~hefesto24.04.5"),
              ("pipewire", "1.6.9-0~hefesto24.04.1"),
              ("xdg-desktop-portal-cosmic", "1.0.0~1780000000+0~hefesto1"))


DEPENDE_POP = ("linux-system76\tii \tlinux-image-7.2.15-76070215-generic, "
               "linux-headers-7.2.15-76070215-generic\n"
               "linux-image-7.2.15-76070215-generic\tii \tlinux-modules-7.2.15-76070215-generic\n"
               "linux-firmware\tii \t\n")
DEPENDE_UBUNTU_HWE = (
    "linux-generic-hwe-24.04\tii \tlinux-image-generic-hwe-24.04 (= 6.14.0-37.37~24.04.1), "
    "linux-headers-generic-hwe-24.04 (= 6.14.0-37.37~24.04.1)\n"
    "linux-image-generic-hwe-24.04\tii \tlinux-image-6.14.0-37-generic | "
    "linux-image-unsigned-6.14.0-37-generic, linux-firmware\n"
    "linux-headers-generic-hwe-24.04\tii \tlinux-headers-6.14.0-37-generic\n"
    "linux-image-6.14.0-37-generic\tii \tlinux-modules-6.14.0-37-generic\n"
    "linux-libc-dev\tii \tlibc6\n")
DEPENDE_DEBIAN = ("linux-image-amd64\tii \tlinux-image-6.12.57+deb13-amd64 (= 6.12.57-1)\n"
                  "linux-headers-amd64\tii \tlinux-headers-6.12.57+deb13-amd64 (= 6.12.57-1)\n"
                  "linux-image-6.12.57+deb13-amd64\tii \tkmod, linux-base\n"
                  "linux-base\tii \tdebconf\n")


def sufixos_dos_backports() -> list[str]:
    """Os ``SUFIXO=`` de cada ``assets/*-backport/BASELINE``, como o install os grava."""
    achados = []
    for baseline in sorted(RAIZ.glob("assets/*-backport/BASELINE")):
        for linha in baseline.read_text(encoding="utf-8").splitlines():
            if linha.startswith("SUFIXO="):
                achados.append(linha.split("=", 1)[1])
    return sorted(set(achados))
SCRIPT = RAIZ / "scripts" / "hefesto_atualizador_raiz.sh"
ALVO = "/usr/local/lib/hefesto-dualsense4unix/atualizador-raiz"


class Lar:
    def __init__(self, base: Path) -> None:
        self.base = base
        self.bin = base / "bin"
        self.bin.mkdir()
        self.chamadas = base / "chamadas.log"
        self.cache = base / "cache"
        self.cache.mkdir()
        self.src = base / "src"
        self.src.mkdir()
        self.modulos = base / "modules"
        self.entradas = base / "entries"
        self.entradas.mkdir()
        self.esp = base / "esp"
        self.esp.mkdir()
        self.boot = base / "boot"
        self.boot.mkdir()
        self.casa = base / "casa"
        self.casa.mkdir()
        self.estado = base / "estado"
        self.segurados = base / "segurados"
        self.segurados.write_text("pipewire\n", encoding="utf-8")
        self.sufixos = base / "sufixos-da-casa"
        self.sufixos.write_text("".join(f"{x}\n" for x in sufixos_dos_backports()),
                                encoding="utf-8")
        self.sufixos.chmod(0o644)
        self.depende = base / "depende"
        self.api = ""
        for nome in ("apt-get", "dkms", "bootctl", "update-initramfs"):
            self.duble(nome)
        self.duble("uname", 'echo 7.2.15-generic')
        self.duble("ldconfig")
        self.dpkg = base / "dpkg"
        (self.dpkg / "updates").mkdir(parents=True)
        self.auditoria = base / "auditoria"
        real = shutil.which("dpkg") or "/usr/bin/dpkg"
        self.duble("dpkg", f'case "$1" in --audit) cat "{self.auditoria}" 2>/dev/null; exit 0;;'
                           f' --force-confdef) exit 0;; esac\nexec "{real}" "$@"')
        self.destino = base / "raiz"
        self.destino.mkdir()
        self.duble("apt-mark", f'[ "$1" = showhold ] && cat "{self.segurados}"; exit 0')
        linhas = "".join(f"{p}\\tii \\t{v}\\n" for p, v in INSTALADOS)
        self.duble("dpkg-query", f'case "$*" in *Depends*) cat "{self.depende}"; exit 0;; esac\n'
                                 f'printf "{linhas}"')
        self.dependencias(DEPENDE_POP)

    def dependencias(self, linhas: str) -> None:
        self.depende.write_text(linhas, encoding="utf-8")

    def duble(self, nome: str, corpo: str = "") -> None:
        arq = self.bin / nome
        arq.write_text(f'#!/bin/sh\necho "{nome} $*" >> "{self.chamadas}"\n{corpo}\n',
                       encoding="utf-8")
        arq.chmod(0o755)

    def rodar(self, *args: str, root: bool = True, **env: str) -> subprocess.CompletedProcess:
        ambiente = {"PATH": f"{self.bin}:{os.environ['PATH']}", "HOME": str(self.casa),
                    "HEFESTO_ATUALIZADOR_SRC": str(self.src),
                    "HEFESTO_ATUALIZADOR_MODULOS": str(self.modulos),
                    "HEFESTO_ATUALIZADOR_ENTRADAS": str(self.entradas),
                    "HEFESTO_ATUALIZADOR_ESP": str(self.esp),
                    "HEFESTO_ATUALIZADOR_BOOT": str(self.boot),
                    "HEFESTO_ATUALIZADOR_CASA": str(self.casa),
                    "HEFESTO_ATUALIZADOR_ESTADO": str(self.estado),
                    "HEFESTO_ATUALIZADOR_SUFIXOS": str(self.sufixos),
                    "HEFESTO_ATUALIZADOR_DONO": pwd.getpwuid(os.getuid()).pw_name,
                    "HEFESTO_ATUALIZADOR_API": self.api,
                    "HEFESTO_ATUALIZADOR_DESTINO": str(self.destino),
                    "HEFESTO_ATUALIZADOR_DPKG": str(self.dpkg), **env}
        if root:
            ambiente["HEFESTO_ATUALIZADOR_CACHE"] = str(self.cache)
        return subprocess.run(["bash", str(SCRIPT), *args], env=ambiente, capture_output=True,
                              text=True, timeout=60, check=False)

    def lidas(self) -> list[str]:
        if not self.chamadas.exists():
            return []
        return self.chamadas.read_text(encoding="utf-8").splitlines()


@pytest.fixture
def lar(tmp_path: Path) -> Lar:
    if os.geteuid() == 0:
        pytest.skip("o ajudante como root usa os caminhos de verdade")
    return Lar(tmp_path)


def test_a_regra_lista_cada_verbo_sem_curinga(lar: Lar) -> None:
    feito = lar.rodar("regra-sudo", "fulana")
    assert feito.returncode == 0, feito.stderr
    regra = feito.stdout
    assert "*" not in regra.replace("# ", "")
    assert "fulana ALL=(root) NOPASSWD: HEFESTO_ATUALIZADOR" in regra
    verbos = [linha.strip().rstrip(", \\") for linha in regra.splitlines()
              if linha.strip().startswith(ALVO)]
    assert verbos == [f"{ALVO} {v}" for v in (
        "apt-lista", "apt-baixar nvidia", "apt-instalar nvidia", "apt-baixar kernel",
        "apt-instalar kernel", "apt-baixar sistema", "apt-instalar sistema",
        "apt-baixar-de-novo nvidia", "apt-reinstalar nvidia", "apt-baixar-de-novo kernel",
        "apt-reinstalar kernel", "apt-consertar", "apt-limpar",
        "dkms-refazer", "dkms-reinstalar", "mangohud-instalar", "mangohud-reinstalavel",
        "mangohud-reinstalar",
        "mangohud-voltar",
        *(f"backport-{v} {p}" for p in ("bluez", "pipewire", "portal")
          for v in ("construir", "instalar", "reinstalavel", "reinstalar", "voltar")),
        "kernel-metas", "kernel-anterior")]
    visudo = shutil.which("visudo") or "/usr/sbin/visudo"
    if Path(visudo).exists():
        arq = lar.base / "regra"
        arq.write_text(regra, encoding="utf-8")
        conferido = subprocess.run([visudo, "-cqf", str(arq)], capture_output=True, check=False)
        if conferido.returncode not in (0,) and b"ermission" not in conferido.stderr:
            pytest.fail(f"o visudo recusou a regra: {conferido.stderr!r}")
    for ruim in ("ALL", "root", "a b", "x;rm", ""):
        assert lar.rodar("regra-sudo", ruim).returncode == 2, ruim


def test_verbo_e_argumento_fora_da_lista_se_recusam(lar: Lar) -> None:
    for args in (("rm",), ("apt-baixar", "tudo"), ("apt-baixar",), ("apt-lista", "x"),
                 ("apt-instalar", "nvidia", "x"), ("dkms-refazer", "--force"), ("apt-limpar", "x"),
                 ("apt-limpar", "bluez"), ("kernel-anterior", "7.2.15"),
                 ("mangohud-voltar", "0.8.3"), ()):
        assert lar.rodar(*args).returncode == 2, args
    assert lar.lidas() == []


def test_sem_root_e_sem_o_desvio_nada_age(lar: Lar) -> None:
    feito = lar.rodar("apt-lista", root=False)
    assert feito.returncode == 1 and "requer root" in feito.stderr
    assert lar.lidas() == []


def test_o_grupo_do_apt_sobe_so_os_pacotes_dele(lar: Lar) -> None:
    assert lar.rodar("apt-baixar", "nvidia").returncode == 0
    assert lar.rodar("apt-instalar", "kernel").returncode == 0
    assert lar.rodar("apt-instalar", "sistema").returncode == 0
    assert lar.rodar("apt-limpar").returncode == 0
    apt = [linha for linha in lar.lidas() if linha.startswith("apt-get") and " -s " not in linha]
    assert apt[0].endswith("-d install --only-upgrade nvidia-driver-595 libnvidia-gl-595")
    assert apt[1].endswith("install --only-upgrade linux-system76")
    assert apt[2].endswith("full-upgrade")
    assert len(apt) == 3 and not any("--purge" in linha for linha in lar.lidas())
    assert all("APT::Status-Fd=1" in linha for linha in apt)


def _orfaos(lar: Lar, *nomes: str, alem: str = "") -> None:
    lista = lar.base / "orfaos"
    lista.write_text("".join(f"Remv {n} [1.0]\n" for n in nomes), encoding="utf-8")
    lar.duble("apt-get", f'case "$*" in "-s autoremove") cat "{lista}" ;;'
                         f' "-s remove "*) shift 2; for p; do echo "Remv $p [1.0]"; done;'
                         f' [ -n "{alem}" ] && echo "Remv {alem} [1.0]" ;; esac; exit 0')


def test_a_limpeza_tira_so_o_que_a_subida_deixou_orfao(lar: Lar) -> None:
    _orfaos(lar, "libvelha1")
    assert lar.rodar("apt-limpar").stdout.startswith("nada a remover")
    assert lar.rodar("apt-instalar", "sistema").returncode == 0
    _orfaos(lar, "libvelha1", "libtrocada2")
    feito = lar.rodar("apt-limpar")
    assert feito.returncode == 0, feito.stderr
    assert "removido: libtrocada2" in feito.stdout and "libvelha1" not in feito.stdout
    remove = [x for x in lar.lidas() if x.startswith("apt-get") and " remove " in x
              and " -s " not in x]
    assert len(remove) == 1 and remove[0].endswith(" remove libtrocada2"), remove
    assert "--purge" not in remove[0] and "allow-remove-essential=false" in remove[0]
    assert not (lar.estado / "orfaos-antes").exists()
    assert lar.rodar("apt-limpar").stdout.startswith("nada a remover")


def test_o_registro_dos_orfaos_de_uma_fila_que_morreu_nao_vale_para_a_seguinte(lar: Lar) -> None:
    _orfaos(lar)
    assert lar.rodar("apt-instalar", "nvidia").returncode == 0
    registro = lar.estado / "orfaos-antes"
    velho = time.time() - 3 * 3600
    os.utime(registro, (velho, velho))
    _orfaos(lar, "pipewire-build-deps")
    assert lar.rodar("apt-instalar", "sistema").returncode == 0
    _orfaos(lar, "pipewire-build-deps", "libtrocada2")
    feito = lar.rodar("apt-limpar")
    assert feito.returncode == 0, feito.stderr
    assert "removido: libtrocada2" in feito.stdout and "pipewire-build-deps" not in feito.stdout


def test_a_limpeza_que_tiraria_outro_pacote_nao_tira_nada(lar: Lar) -> None:
    _orfaos(lar, alem="pipewire-build-deps")
    assert lar.rodar("apt-instalar", "nvidia").returncode == 0
    _orfaos(lar, "libbluetooth-dev", alem="pipewire-build-deps")
    feito = lar.rodar("apt-limpar")
    assert feito.returncode == 2 and "pipewire-build-deps" in feito.stderr, feito.stderr
    assert not [x for x in lar.lidas() if " remove " in x and " -s " not in x]


def _fonte(lar: Lar) -> Path:
    pasta = lar.src / "hefesto-hid-playstation-1.0.0"
    pasta.mkdir()
    (pasta / "dkms.conf").write_text("PACKAGE_NAME=x\n", encoding="utf-8")
    (lar.modulos / "7.2.18-generic" / "build").mkdir(parents=True)
    return pasta


def test_o_dkms_so_se_refaz_com_o_fonte_do_dono(lar: Lar) -> None:
    pasta = _fonte(lar)
    pasta.chmod(0o775)
    feito = lar.rodar("dkms-refazer", HEFESTO_ATUALIZADOR_DONO=pwd.getpwuid(os.getuid()).pw_name)
    assert feito.returncode != 0 and "não é só do root" in feito.stderr
    assert not [linha for linha in lar.lidas() if linha.startswith("dkms install")]
    pasta.chmod(0o755)
    (pasta / "dkms.conf").chmod(0o644)
    feito = lar.rodar("dkms-refazer", HEFESTO_ATUALIZADOR_DONO=pwd.getpwuid(os.getuid()).pw_name)
    assert feito.returncode == 0, feito.stderr
    assert "dkms install -m hefesto-hid-playstation -v 1.0.0 -k 7.2.18-generic" in lar.lidas()
    assert any(linha.startswith("update-initramfs") for linha in lar.lidas())


def test_o_dkms_recusa_o_fonte_de_outro_dono(lar: Lar) -> None:
    _fonte(lar)
    feito = lar.rodar("dkms-refazer", HEFESTO_ATUALIZADOR_DONO="root")
    assert feito.returncode != 0
    assert not [linha for linha in lar.lidas() if linha.startswith("dkms install")]


PACOTE_DO_MANGOHUD = (
    (".", 0o755, b"", ""), ("usr/", 0o755, b"", ""), ("usr/bin/", 0o755, b"", ""),
    ("usr/bin/mangoplot", 0o755, b"#!/usr/bin/python3\n", ""),
    ("usr/bin/mangohud", 0o755, b"#!/bin/sh\n", ""),
    ("usr/lib/", 0o755, b"", ""), ("usr/lib/mangohud/", 0o755, b"", ""),
    ("usr/lib/mangohud/lib32/", 0o755, b"", ""),
    ("usr/lib/mangohud/lib32/libMangoHud.so", 0o755, b"ELF32", ""),
    ("usr/lib/mangohud/lib32/libMangoHud_opengl.so", 0o755, b"ELF32", ""),
    ("usr/lib/mangohud/lib32/libMangoHud_shim.so", 0o755, b"ELF32", ""),
    ("usr/lib/mangohud/lib64/", 0o755, b"", ""),
    ("usr/lib/mangohud/lib64/libMangoHud.so", 0o755, b"ELF64", ""),
    ("usr/lib/mangohud/lib64/libMangoHud_opengl.so", 0o755, b"ELF64", ""),
    ("usr/lib/mangohud/lib64/libMangoHud_shim.so", 0o755, b"ELF64", ""),
    ("usr/share/", 0o755, b"", ""), ("usr/share/man/", 0o755, b"", ""),
    ("usr/share/man/man1/", 0o755, b"", ""),
    ("usr/share/man/man1/mangohud.1", 0o644, b".TH\n", ""),
    ("usr/share/icons/", 0o755, b"", ""), ("usr/share/icons/hicolor/", 0o755, b"", ""),
    ("usr/share/icons/hicolor/scalable/", 0o755, b"", ""),
    ("usr/share/icons/hicolor/scalable/apps/", 0o755, b"", ""),
    ("usr/share/icons/hicolor/scalable/apps/io.github.flightlessmango.mangohud.svg", 0o644,
     b"<svg/>", ""),
    ("usr/share/vulkan/", 0o755, b"", ""), ("usr/share/vulkan/implicit_layer.d/", 0o755, b"", ""),
    ("usr/share/vulkan/implicit_layer.d/MangoHud.x86_64.json", 0o644, b"{}", ""),
    ("usr/share/vulkan/implicit_layer.d/MangoHud.x86.json", 0o644, b"{}", ""),
    ("usr/share/doc/", 0o755, b"", ""), ("usr/share/doc/mangohud/", 0o755, b"", ""),
    ("usr/share/doc/mangohud/MangoHud.conf.example", 0o644, b"fps\n", ""),
    ("usr/share/doc/mangohud/presets.conf.example", 0o644, b"[1]\n", ""),
    ("usr/share/metainfo/", 0o755, b"", ""),
    ("usr/share/metainfo/io.github.flightlessmango.mangohud.metainfo.xml", 0o644, b"<x/>", ""),
)


def _tar_do_mangohud(lar: Lar, nome: str = "MangoHud-0.8.5.r0.tar.gz",
                     membros: tuple[tuple[str, int, bytes, str], ...] = PACOTE_DO_MANGOHUD,
                     ) -> Path:
    """O tarball como a release o publica: o ``mangohud-setup.sh`` e o ``MangoHud-package.tar``
    com os destinos, na forma medida no ``MangoHud-0.8.4.r0.g992103e.tar.gz`` de 20/11/2026 (a
    pasta ``.``, as pastas, o ícone e o metainfo; nenhum link); o setup de mentira anota quando
    roda. O caminho que termina em ``/`` (e o ``.``) é pasta."""
    pasta = lar.casa / ".cache" / "hefesto-dualsense4unix" / "atualizador" / "mangohud"
    pasta.mkdir(parents=True, exist_ok=True)
    interno = io.BytesIO()
    with tarfile.open(fileobj=interno, mode="w") as pacote:
        for caminho, modo, dado, alvo in membros:
            info = tarfile.TarInfo("." if caminho == "." else f"./{caminho.rstrip('/')}")
            info.mode = modo
            if caminho == "." or caminho.endswith("/"):
                info.type = tarfile.DIRTYPE
                pacote.addfile(info)
            elif alvo:
                info.type, info.linkname = tarfile.SYMTYPE, alvo
                pacote.addfile(info)
            else:
                info.size = len(dado)
                pacote.addfile(info, io.BytesIO(dado))
    setup = f'#!/bin/sh\necho "setup $*" >> "{lar.chamadas}"\n'.encode()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for caminho, dado, modo in (("MangoHud/mangohud-setup.sh", setup, 0o755),
                                    ("MangoHud/MangoHud-package.tar", interno.getvalue(), 0o644)):
            info = tarfile.TarInfo(caminho)
            info.size, info.mode = len(dado), modo
            tar.addfile(info, io.BytesIO(dado))
    arq = pasta / nome
    arq.write_bytes(buf.getvalue())
    return arq


def _api(lar: Lar, nome: str, sha: str) -> None:
    release = {"assets": [{"name": nome, "digest": f"sha256:{sha}"}]}
    resposta = lar.base / "release.json"
    resposta.write_text(json.dumps(release), encoding="utf-8")
    lar.duble("curl", f'cat "{resposta}"')
    lar.api = "https://exemplo.invalid/release"


def test_o_mangohud_so_entra_com_a_soma_publicada(lar: Lar) -> None:
    arq = _tar_do_mangohud(lar)
    _api(lar, arq.name, "0" * 64)
    feito = lar.rodar("mangohud-instalar")
    assert feito.returncode == 2 and "não é o publicado" in feito.stderr
    assert not any(linha.startswith("setup") for linha in lar.lidas())
    _api(lar, arq.name, hashlib.sha256(arq.read_bytes()).hexdigest())
    feito = lar.rodar("mangohud-instalar")
    assert feito.returncode == 0, feito.stderr
    assert "ldconfig " in lar.lidas()
    assert (lar.destino / "usr/lib/mangohud/lib64/libMangoHud.so").read_bytes() == b"ELF64"
    assert (lar.cache / "mangohud" / "atual.tar.gz").read_bytes() == arq.read_bytes()


def _instalar_mangohud(lar: Lar, nome: str) -> bytes:
    pasta = lar.casa / ".cache" / "hefesto-dualsense4unix" / "atualizador" / "mangohud"
    if pasta.exists():
        shutil.rmtree(pasta)
    arq = _tar_do_mangohud(lar, nome)
    _api(lar, arq.name, hashlib.sha256(arq.read_bytes()).hexdigest())
    assert lar.rodar("mangohud-instalar").returncode == 0
    return arq.read_bytes()


def test_o_mangohud_volta_uma_vez_so_ao_que_o_ajudante_trocou(lar: Lar) -> None:
    assert lar.rodar("mangohud-voltar").returncode == 2
    velho = _instalar_mangohud(lar, "MangoHud-0.8.4.r0.tar.gz")
    novo = _instalar_mangohud(lar, "MangoHud-0.8.5.r0.tar.gz")
    pasta = lar.cache / "mangohud"
    assert (pasta / "anterior.tar.gz").read_bytes() == velho
    assert (pasta / "atual.tar.gz").read_bytes() == novo
    assert lar.rodar("mangohud-voltar").returncode == 0
    assert (pasta / "atual.tar.gz").read_bytes() == velho
    assert lar.lidas().count("ldconfig ") == 3
    segunda = lar.rodar("mangohud-voltar")
    assert segunda.returncode == 2 and "sem versão anterior" in segunda.stderr
    assert lar.lidas().count("ldconfig ") == 3


def test_o_mangohud_nao_volta_de_pasta_que_outro_escreve(lar: Lar) -> None:
    _instalar_mangohud(lar, "MangoHud-0.8.4.r0.tar.gz")
    _instalar_mangohud(lar, "MangoHud-0.8.5.r0.tar.gz")
    (lar.cache / "mangohud").chmod(0o777)
    feito = lar.rodar("mangohud-voltar")
    assert feito.returncode == 2 and "não é só do root" in feito.stderr
    assert lar.lidas().count("ldconfig ") == 2


def _kernels(lar: Lar, *versoes: str, velho: str = "") -> None:
    for versao in versoes:
        (lar.modulos / versao).mkdir(parents=True, exist_ok=True)
        (lar.boot / f"vmlinuz-{versao}").write_bytes(f"imagem {versao}".encode())
    (lar.esp / "vmlinuz-previous.efi").write_bytes(f"imagem {velho or versoes[0]}".encode())
    (lar.entradas / "Pop_OS-current.conf").write_text("linux /vmlinuz.efi\n", encoding="utf-8")
    (lar.entradas / "Pop_OS-oldkern.conf").write_text("linux /vmlinuz-previous.efi\n",
                                                      encoding="utf-8")


def _apt_que_traz_o_kernel(lar: Lar, novo: str) -> None:
    lar.duble("apt-get", f'case "$*" in *install*) mkdir -p "{lar.modulos}/{novo}" ;; esac')


def test_o_kernel_so_volta_ao_que_o_ajudante_trocou_e_uma_vez(lar: Lar) -> None:
    _kernels(lar, "7.2.15-generic")
    feito = lar.rodar("kernel-anterior")
    assert feito.returncode == 2 and "nenhuma subida" in feito.stderr
    assert not [x for x in lar.lidas() if x.startswith("bootctl")]
    assert lar.rodar("apt-instalar", "kernel").returncode == 0
    assert not (lar.estado / "kernel-anterior").exists()
    _apt_que_traz_o_kernel(lar, "7.2.18-generic")
    assert lar.rodar("apt-instalar", "kernel").returncode == 0
    registro = lar.estado / "kernel-anterior"
    assert registro.read_text(encoding="utf-8").strip() == "7.2.15-generic"
    assert oct(registro.stat().st_mode & 0o777) == "0o600"
    feito = lar.rodar("kernel-anterior")
    assert feito.returncode == 0, feito.stderr
    assert "bootctl set-default Pop_OS-oldkern.conf" in lar.lidas()
    assert not registro.exists()
    segunda = lar.rodar("kernel-anterior")
    assert segunda.returncode == 2
    assert [x for x in lar.lidas() if x.startswith("bootctl")] == [
        "bootctl set-default Pop_OS-oldkern.conf"]


def test_o_kernel_registrado_que_saiu_ou_registro_de_outro_nao_volta(lar: Lar) -> None:
    _kernels(lar, "7.2.15-generic")
    _apt_que_traz_o_kernel(lar, "7.2.18-generic")
    assert lar.rodar("apt-instalar", "kernel").returncode == 0
    registro = lar.estado / "kernel-anterior"
    registro.chmod(0o666)
    assert lar.rodar("kernel-anterior").returncode == 2
    registro.chmod(0o600)
    (lar.modulos / "7.2.15-generic").rmdir()
    feito = lar.rodar("kernel-anterior")
    assert feito.returncode == 2 and "não está mais instalado" in feito.stderr
    assert not [x for x in lar.lidas() if x.startswith("bootctl")]


def test_a_entrada_com_a_versao_no_nome_vence_o_oldkern(lar: Lar) -> None:
    _kernels(lar, "7.2.15-generic")
    (lar.entradas / "maquina-7.2.15-generic.conf").write_text("", encoding="utf-8")
    _apt_que_traz_o_kernel(lar, "7.2.18-generic")
    assert lar.rodar("apt-instalar", "kernel").returncode == 0
    assert lar.rodar("kernel-anterior").returncode == 0
    assert "bootctl set-default maquina-7.2.15-generic.conf" in lar.lidas()


def test_os_sufixos_saem_de_cada_backport_da_casa() -> None:
    baselines = sorted(RAIZ.glob("assets/*-backport/BASELINE"))
    assert len(baselines) >= 3
    for baseline in baselines:
        texto = baseline.read_text(encoding="utf-8")
        sufixos = [x.split("=", 1)[1] for x in texto.splitlines() if x.startswith("SUFIXO=")]
        assert len(sufixos) == 1 and "~hefesto" in sufixos[0], baseline
    pipewire = (RAIZ / "assets/pipewire-backport/BASELINE").read_text(encoding="utf-8")
    for chave in ("PW_REVISAO", "WP_REVISAO"):
        valor = next(x for x in pipewire.splitlines() if x.startswith(f"{chave}="))
        assert "~hefesto24.04." in valor
    camada = (RAIZ / "scripts/lib/camada_de_maquina.sh").read_text(encoding="utf-8")
    assert "grep -h '^SUFIXO=' \"${ROOT_DIR}\"/assets/*-backport/BASELINE" in camada


def _ordem(lar: Lar) -> list[str]:
    return [x for x in lar.lidas() if x.startswith(("apt-get", "apt-mark hold", "apt-mark unhold"))]


@pytest.mark.parametrize("grupo", ["sistema", "nvidia", "kernel"])
def test_a_subida_do_apt_nao_troca_os_backports_da_casa(lar: Lar, grupo: str) -> None:
    feito = lar.rodar("apt-instalar", grupo)
    assert feito.returncode == 0, feito.stderr
    ordem = _ordem(lar)
    segura = "bluez xdg-desktop-portal-cosmic" + (
        " linux-system76 nvidia-driver-595 libnvidia-gl-595" if grupo == "sistema" else "")
    assert ordem[0] == f"apt-mark hold {segura}", ordem
    assert ordem[1].startswith("apt-get")
    assert ordem[-1] == f"apt-mark unhold {segura}", ordem
    assert not any("pipewire" in x for x in ordem), "o que já estava segurado não se solta"


def test_a_subida_que_falha_solta_os_da_casa_igual(lar: Lar) -> None:
    lar.duble("apt-get", "exit 100")
    feito = lar.rodar("apt-instalar", "sistema")
    assert feito.returncode != 0
    assert _ordem(lar)[-1] == ("apt-mark unhold bluez xdg-desktop-portal-cosmic linux-system76 "
                               "nvidia-driver-595 libnvidia-gl-595")


def test_sem_a_lista_dos_sufixos_nenhum_pacote_sobe(lar: Lar) -> None:
    lar.sufixos.unlink()
    feito = lar.rodar("apt-instalar", "sistema")
    assert feito.returncode == 2 and "sufixos da casa" in feito.stderr
    assert not [x for x in lar.lidas() if x.startswith("apt-get")]
    lar.sufixos.write_text("~hefesto24.04.\n", encoding="utf-8")
    lar.sufixos.chmod(0o666)
    assert lar.rodar("apt-instalar", "sistema").returncode == 2
    assert not [x for x in lar.lidas() if x.startswith("apt-get")]


def test_o_fonte_do_dkms_fica_so_do_root_antes_do_build(tmp_path: Path) -> None:
    from tests.unit.test_o_secure_boot_se_le_sem_mokutil import _instalar

    _saida, chamadas = _instalar(tmp_path, ligado=False, inscrita=False)
    linhas = chamadas.splitlines()
    destino = tmp_path / "usr-src" / "hefesto-hid-playstation-1.0.0"
    dono = linhas.index(f"sudo chown -R root:root {destino}")
    escrita = linhas.index(f"sudo chmod -R go-w {destino}")
    assert dono < escrita < linhas.index("sudo dkms add hefesto-hid-playstation/1.0.0")


def _plantar_no_find(lar: Lar, plantado: Path) -> None:
    real = shutil.which("find") or "/usr/bin/find"
    lar.duble("find", f'case "$*" in *MangoHud-*) echo "{plantado}"; exit 0 ;; esac\n'
                      f'exec "{real}" "$@"')


def test_o_mangohud_trocado_por_link_depois_da_busca_nao_se_le(lar: Lar) -> None:
    arq = _tar_do_mangohud(lar)
    _api(lar, arq.name, hashlib.sha256(arq.read_bytes()).hexdigest())
    fora = lar.base / "fora.tar.gz"
    arq.replace(fora)
    arq.symlink_to(fora)
    _plantar_no_find(lar, arq)
    feito = lar.rodar("mangohud-instalar")
    assert feito.returncode == 2 and "não li" in feito.stderr, feito.stderr
    assert not any(linha.startswith("setup") for linha in lar.lidas())
    assert not (lar.cache / "mangohud" / "novo.tar.gz").exists()


def test_o_mangohud_trocado_por_fifo_nao_trava_o_root(lar: Lar) -> None:
    arq = _tar_do_mangohud(lar)
    _api(lar, arq.name, hashlib.sha256(arq.read_bytes()).hexdigest())
    arq.unlink()
    os.mkfifo(arq)
    _plantar_no_find(lar, arq)
    feito = lar.rodar("mangohud-instalar")
    assert feito.returncode == 2 and "não é um arquivo comum" in feito.stderr, feito.stderr
    assert not any(linha.startswith("setup") for linha in lar.lidas())


def test_sem_saber_o_que_ja_esta_segurado_nada_sobe(lar: Lar) -> None:
    lar.duble("apt-mark", '[ "$1" = showhold ] && exit 1; exit 0')
    feito = lar.rodar("apt-instalar", "sistema")
    assert feito.returncode == 2 and "já segurados" in feito.stderr, feito.stderr
    assert not [x for x in lar.lidas() if x.startswith(("apt-get", "apt-mark hold"))]


def test_a_limpeza_tambem_segura_os_da_casa(lar: Lar) -> None:
    assert lar.rodar("apt-instalar", "nvidia").returncode == 0
    _orfaos(lar, "libtrocada2")
    lar.chamadas.unlink()
    feito = lar.rodar("apt-limpar")
    assert feito.returncode == 0, feito.stderr
    ordem = _ordem(lar)
    assert ordem[0] == "apt-mark hold bluez xdg-desktop-portal-cosmic", ordem
    assert ordem[-2].endswith(" remove libtrocada2"), ordem
    assert ordem[-1] == "apt-mark unhold bluez xdg-desktop-portal-cosmic", ordem


def _funcao_do_install(nome: str) -> str:
    corpo = (RAIZ / "scripts/lib/camada_de_maquina.sh").read_text(encoding="utf-8")
    inicio = corpo.index(f"{nome}() {{")
    return corpo[inicio:corpo.index("\n}\n", inicio) + 3]


def test_o_visudo_so_se_chama_no_ajudante_que_grava_toda_regra() -> None:
    corpo = (RAIZ / "scripts/lib/camada_de_maquina.sh").read_text(encoding="utf-8")
    assert corpo.count("visudo -cqf") == 1
    assert "visudo -cqf" in _funcao_do_install("_gravar_regra_do_sudo")
    for rotina in ("install_atualizador_raiz_host", "install_placa_acordada_host",
                   "install_bt_ponte_privilegiada_host"):
        assert "_gravar_regra_do_sudo " in _funcao_do_install(rotina), rotina


@pytest.mark.parametrize(("rotina", "regra"), [
    ("install_atualizador_raiz_host", "49-hefesto-atualizador"),
    ("install_placa_acordada_host", "49-hefesto-placa"),
    ("install_bt_ponte_privilegiada_host", "49-hefesto-bt-ponte"),
])
def test_o_install_confere_a_regra_ja_do_root_antes_de_valer(tmp_path: Path, rotina: str,
                                                             regra: str) -> None:
    lib, regras = tmp_path / "lib", tmp_path / "sudoers.d"
    lib.mkdir()
    regras.mkdir()
    codigo = _funcao_do_install("_gravar_regra_do_sudo") + _funcao_do_install(rotina)
    if rotina == "install_atualizador_raiz_host":
        codigo = _funcao_do_install("_instalar_as_receitas_do_atualizador") + codigo
    codigo = codigo.replace("/usr/local/lib/hefesto-dualsense4unix", str(lib)) \
        .replace("/etc/sudoers.d", str(regras))
    log, bin_ = tmp_path / "sudo.log", tmp_path / "bin"
    bin_.mkdir()
    (bin_ / "sudo").write_text(
        "#!/bin/bash\n"
        f'echo "$*" >> "{log}"\n'
        '[[ "$1" == -n ]] && shift\n'
        '[[ "$1" == true || "$1" == -l || "$1" == chown ]] && exit 0\n'
        'if [[ "$1" == visudo ]]; then\n'
        f'  echo "visudo-viu $(stat -c %a "${{@: -1}}") ${{@: -1}}" >> "{log}"; exit 0\n'
        'fi\n'
        'if [[ "$1" == install ]]; then\n'
        '  args=(); for a in "${@:2}"; do [[ "$a" == -o || "$a" == -g || "$a" == root ]] '
        '|| args+=("$a"); done\n'
        '  exec install "${args[@]}"\n'
        'fi\n'
        'exec "$@"\n', encoding="utf-8")
    (bin_ / "sudo").chmod(0o755)
    (bin_ / "visudo").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (bin_ / "visudo").chmod(0o755)
    roteiro = tmp_path / "roda.sh"
    roteiro.write_text(f'warn() {{ echo "AVISO $*"; }}\nROOT_DIR="{RAIZ}"\n'
                       "_garantir_a_conta_no_grupo_hefesto() { return 0; }\n"
                       f"{codigo}\nset -euo pipefail\n{rotina}\n", encoding="utf-8")
    feito = subprocess.run(["bash", str(roteiro)], capture_output=True, text=True, timeout=60,
                           env={**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}",
                                "SUDO_USER": "fulana", "TMPDIR": str(tmp_path)},
                           check=False)
    assert feito.returncode == 0 and "AVISO" not in feito.stdout, feito.stdout + feito.stderr
    viu = [x for x in log.read_text(encoding="utf-8").splitlines() if x.startswith("visudo-viu")]
    assert len(viu) == 1
    modo, caminho = viu[0].split()[1:]
    assert Path(caminho).parent == regras and Path(caminho).name.startswith("."), viu
    assert modo == "440", "o visudo confere o arquivo que só o root escreve, não o rascunho"
    final = regras / regra
    assert "fulana" in final.read_text(encoding="utf-8")
    if rotina == "install_atualizador_raiz_host":
        receitas = lib / "receitas"
        assert (receitas / "scripts" / "hefesto_receita_nova.py").is_file()
        assert (receitas / "assets" / "bluez-backport" / "BASELINE").is_file()
        assert not any(c.stat().st_mode & 0o022 for c in receitas.rglob("*")), (
            "o ajudante recusa receita que outro escreve")
    assert sorted(p.name for p in regras.iterdir()) == [regra]
    assert not list(tmp_path.glob("tmp.*")), "o rascunho de quem usa não sobra"


def test_o_oldkern_que_nao_e_o_kernel_registrado_nao_vira_volta(lar: Lar) -> None:
    _kernels(lar, "7.2.15-generic", velho="7.2.6-generic")
    _apt_que_traz_o_kernel(lar, "7.2.18-generic")
    assert lar.rodar("apt-instalar", "kernel").returncode == 0
    feito = lar.rodar("kernel-anterior")
    assert feito.returncode == 2 and "não é o kernel 7.2.15-generic" in feito.stderr, feito.stderr
    assert not [x for x in lar.lidas() if x.startswith("bootctl")]
    assert (lar.estado / "kernel-anterior").exists(), "a volta recusada não gasta o registro"
    (lar.entradas / "Pop_OS-oldkern.conf").write_text("linux /../../etc/shadow\n",
                                                      encoding="utf-8")
    assert lar.rodar("kernel-anterior").returncode == 2
    assert not [x for x in lar.lidas() if x.startswith("bootctl")]


def _o_que_o_root_grava() -> set[str]:
    camada = (RAIZ / "scripts/lib/camada_de_maquina.sh").read_text(encoding="utf-8")
    inicio = camada.index("_instalar_as_receitas_do_atualizador() {")
    fim = camada.index("install_censo_do_gabinete_host() {")
    gravados = set(re.findall(r"/usr/local/lib/hefesto-dualsense4unix/[\w.-]+", camada[inicio:fim]))
    ajudante = (RAIZ / "scripts/hefesto_atualizador_raiz.sh").read_text(encoding="utf-8")
    cache = re.search(r"^\s+CACHE=(/\S+)$", ajudante, re.M)
    estado = re.search(r"^\s+ESTADO=(/\S+)$", ajudante, re.M)
    assert cache and estado, "o ajudante mudou a forma das pastas do root"
    gravados |= {f"{cache.group(1)}/{sub}"
                 for sub in set(re.findall(r"\$\{CACHE\}/([a-z]+)", ajudante))}
    gravados.add(estado.group(1))
    pecas = re.search(r'^BACKPORTS="([^"]+)"', ajudante, re.M)
    assert pecas, "o ajudante mudou a lista das peças da casa"
    gravados |= {f"/var/cache/{p}hefesto-backport-{b}"
                 for b in pecas.group(1).split() for p in ("", "private/")}
    return gravados


def test_o_uninstall_leva_tudo_que_o_install_e_o_ajudante_gravam_como_root() -> None:
    """O ajudante, os sufixos, as receitas, as entregas dos backports, o MangoHud guardado, o
    registro do kernel e a caixa da construção saem no uninstall."""
    removidos = set()
    for linha in (RAIZ / "uninstall.sh").read_text(encoding="utf-8").splitlines():
        if re.match(r"\s*sudo rm -[a-z]*f", linha):
            removidos |= set(re.findall(r"(/[\w./-]+)", linha))
    gravados = _o_que_o_root_grava()
    assert {"/usr/local/lib/hefesto-dualsense4unix/receitas",
            "/var/cache/hefesto-dualsense4unix/backports"} <= gravados
    assert not gravados - removidos, sorted(gravados - removidos)


@pytest.mark.parametrize(("depende", "metas"), [
    (DEPENDE_POP, ["linux-system76"]),
    (DEPENDE_UBUNTU_HWE, ["linux-generic-hwe-24.04", "linux-headers-generic-hwe-24.04",
                          "linux-image-generic-hwe-24.04"]),
    (DEPENDE_DEBIAN, ["linux-headers-amd64", "linux-image-amd64"]),
    (DEPENDE_DEBIAN.replace("6.12.57", "6.12.63"), ["linux-headers-amd64", "linux-image-amd64"]),
])
def test_o_ajudante_acha_as_metas_do_kernel_de_cada_distro(lar: Lar, depende: str,
                                                           metas: list[str]) -> None:
    lar.dependencias(depende)
    lido = lar.rodar("kernel-metas", root=False)
    assert lido.returncode == 0 and lido.stdout.split() == metas, lido
    assert lar.rodar("apt-instalar", "kernel").returncode == 0
    subida = [x for x in lar.lidas() if x.startswith("apt-get") and "--only-upgrade" in x]
    assert subida[-1].endswith("install --only-upgrade " + " ".join(metas))


def test_o_grupo_sem_nada_instalado_sai_com_nove(lar: Lar) -> None:
    lar.dependencias("linux-firmware\tii \t\n")
    feito = lar.rodar("apt-instalar", "kernel")
    assert feito.returncode == 9 and "nada instalado no grupo kernel" in feito.stdout


def _apt_que_sobe(lar: Lar) -> list[str]:
    return [linha for linha in lar.lidas()
            if linha.startswith("apt-get") and " -s " not in linha and " -f install" not in linha]


@pytest.mark.parametrize("marca", ["auditoria", "updates"])
def test_o_dpkg_interrompido_se_conserta_antes_da_subida(lar: Lar, marca: str) -> None:
    """D-1911-O-APT-CONSERTA-O-DPKG-E-ESPERA-A-TRAVA: o dpkg a meio se conserta antes de subir."""
    if marca == "auditoria":
        lar.auditoria.write_text("O pacote a seguir está apenas meio configurado:\n bluez\n",
                                 encoding="utf-8")
    else:
        (lar.dpkg / "updates" / "0001").write_text("x", encoding="utf-8")
    feito = lar.rodar("apt-instalar", "sistema")
    assert feito.returncode == 0, feito.stderr
    lidas = lar.lidas()
    conserto = lidas.index("dpkg --force-confdef --force-confold --configure -a")
    reparo = next(i for i, x in enumerate(lidas) if x.startswith("apt-get") and "-f install" in x)
    simulacao = next(i for i, x in enumerate(lidas) if x.startswith("apt-get -s"))
    subida = next(i for i, x in enumerate(lidas) if x.endswith("full-upgrade"))
    segura = next(i for i, x in enumerate(lidas) if x.startswith("apt-mark hold "))
    assert segura < conserto < reparo < simulacao < subida, lidas
    assert "parou no meio" in feito.stdout


def test_o_dpkg_inteiro_nao_chama_o_conserto(lar: Lar) -> None:
    assert lar.rodar("apt-instalar", "sistema").returncode == 0
    assert not [x for x in lar.lidas() if "--configure" in x or "-f install" in x]


def test_o_conserto_que_falha_tem_frase_propria_e_nada_sobe(lar: Lar) -> None:
    lar.auditoria.write_text("meio configurado\n", encoding="utf-8")
    lar.duble("apt-get", 'case "$*" in *"-f install"*) exit 100;; esac; exit 0')
    feito = lar.rodar("apt-instalar", "nvidia")
    assert feito.returncode == 12
    assert "o conserto dos pacotes interrompidos falhou" in feito.stderr
    assert not [x for x in lar.lidas() if "--only-upgrade" in x]
    assert "apt-mark unhold bluez xdg-desktop-portal-cosmic" in lar.lidas()


def test_todo_apt_que_troca_leva_o_prazo_da_trava(lar: Lar) -> None:
    """D-1911-O-APT-CONSERTA-O-DPKG-E-ESPERA-A-TRAVA: todo apt que troca espera a trava."""
    lar.auditoria.write_text("meio configurado\n", encoding="utf-8")
    for verbo in (("apt-baixar", "nvidia"), ("apt-instalar", "kernel"),
                  ("apt-instalar", "sistema"), ("apt-reinstalar", "nvidia"), ("apt-consertar",)):
        assert lar.rodar(*verbo).returncode == 0, verbo
    trocam = [x for x in lar.lidas() if x.startswith("apt-get") and " -s " not in x]
    assert len(trocam) >= 6
    assert all("DPkg::Lock::Timeout=300" in x for x in trocam), trocam


def test_a_trava_ocupada_sai_com_codigo_proprio_e_vira_espera(
        lar: Lar, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-1911-O-APT-CONSERTA-O-DPKG-E-ESPERA-A-TRAVA: a trava ocupada é espera, não falha."""
    import fcntl

    from hefesto_dualsense4unix.app.actions import atualizador as at
    from hefesto_dualsense4unix.app.actions import pecas_do_atualizador as pa

    lar.duble("apt-get",
              'case "$*" in *full-upgrade*) echo "E: trava" >&2; exit 100;; esac; exit 0')
    trava = lar.dpkg / "lock-frontend"
    trava.write_text("", encoding="utf-8")
    livre = lar.rodar("apt-instalar", "sistema")
    assert livre.returncode == 100, "sem trava ocupada, a falha do apt fica falha"
    with trava.open("r+") as f:
        fcntl.lockf(f, fcntl.LOCK_EX)
        feito = lar.rodar("apt-instalar", "sistema")
    assert feito.returncode == pa.RC_TRAVA_OCUPADA
    assert pa.OUTRO_INSTALADOR in feito.stderr
    assert lar.lidas()[-1].startswith("apt-mark unhold bluez xdg-desktop-portal-cosmic")

    monkeypatch.setattr(pa, "AJUDANTE", lar.base / "chamadas.log")
    monkeypatch.setattr(pa, "_comando", lambda *_a, **_k: (feito.returncode, feito.stderr))
    with pytest.raises(at.EsperaError, match="outro instalador"):
        pa._raiz("apt-instalar", "sistema", passo=at.Passo())
    monkeypatch.setattr(pa, "_comando", lambda *_a, **_k: (100, "E: trava"))
    with pytest.raises(pa.RaizSaiuError):
        pa._raiz("apt-instalar", "sistema", passo=at.Passo())


def _esbarra_na_trava(lar: Lar, quem: str, trava: Path) -> None:
    """O ``apt-mark`` e o ``dpkg`` de verdade não esperam a trava de outro instalador: saem com
    erro enquanto a trava está presa."""
    presa = lar.bin / "trava-presa"
    presa.write_text("#!/usr/bin/env python3\nimport fcntl, os, struct, sys\n"
                     "fd = os.open(sys.argv[1], os.O_RDONLY)\n"
                     "pedido = struct.pack('@hhqqi', fcntl.F_WRLCK, 0, 0, 0, 0)\n"
                     "tipo = struct.unpack('@hhqqi', fcntl.fcntl(fd, fcntl.F_GETLK, pedido))[0]\n"
                     "sys.exit(0 if tipo != fcntl.F_UNLCK else 1)\n", encoding="utf-8")
    presa.chmod(0o755)
    esbarra = f'"{presa}" "{trava}" && {{ echo "E: Could not get lock {trava}" >&2; exit 100; }}'
    if quem == "apt-mark":
        lar.duble("apt-mark", f'[ "$1" = showhold ] && {{ cat "{lar.segurados}"; exit 0; }}\n'
                              f'{esbarra}\nexit 0')
    else:
        real = shutil.which("dpkg") or "/usr/bin/dpkg"
        lar.duble("dpkg", f'case "$1" in --audit) cat "{lar.auditoria}"; exit 0;;'
                          f' --force-confdef) {esbarra}; exit 0;; esac\nexec "{real}" "$@"')


@pytest.mark.parametrize("quem", ["apt-mark", "dpkg"])
def test_quem_esbarra_na_trava_de_outro_instalador_tambem_espera(lar: Lar, quem: str) -> None:
    """D-1911-O-APT-CONSERTA-O-DPKG-E-ESPERA-A-TRAVA: segurar e consertar também esperam.

    O ``apt-mark hold`` dos da casa vem antes de todo apt, e o ``dpkg --configure -a`` do conserto
    não tem prazo de trava: com outro instalador na trava, os dois saem com o código da espera."""
    import fcntl

    from hefesto_dualsense4unix.app.actions import pecas_do_atualizador as pa

    trava = lar.dpkg / "lock-frontend"
    trava.write_text("", encoding="utf-8")
    lar.auditoria.write_text("meio configurado\n", encoding="utf-8")
    _esbarra_na_trava(lar, quem, trava)
    with trava.open("r+") as f:
        fcntl.lockf(f, fcntl.LOCK_EX)
        feito = lar.rodar("apt-instalar", "sistema")
    assert feito.returncode == pa.RC_TRAVA_OCUPADA, feito.stderr
    assert pa.OUTRO_INSTALADOR in feito.stderr
    assert not [x for x in lar.lidas() if x.endswith("full-upgrade")]


@pytest.mark.parametrize("apt_falha", [False, True])
def test_os_pacotes_do_sistema_nao_levam_o_kernel_nem_a_nvidia(lar: Lar, apt_falha: bool) -> None:
    """D-1911-O-SISTEMA-NAO-LEVA-KERNEL-NEM-NVIDIA: o kernel e a Nvidia ficam segurados durante a
    subida do sistema e se soltam no fim, também com o apt falhando."""
    if apt_falha:
        lar.duble("apt-get", 'case "$*" in *full-upgrade*) exit 100;; esac; exit 0')
    feito = lar.rodar("apt-instalar", "sistema")
    assert feito.returncode == (100 if apt_falha else 0), feito.stderr
    lidas = lar.lidas()
    segura = next(x for x in lidas if x.startswith("apt-mark hold "))
    for pacote in ("linux-system76", "nvidia-driver-595", "libnvidia-gl-595"):
        assert f" {pacote}" in f" {segura} ", segura
    subida = next(i for i, x in enumerate(lidas) if x.endswith("full-upgrade"))
    assert lidas.index(segura) < subida
    solta = [x for x in lidas[subida:] if x.startswith("apt-mark unhold ")]
    assert solta and set(solta[0].split()[2:]) == set(segura.split()[2:]), (segura, solta)
    assert not (lar.estado / "segurados-pelo-ajudante").exists()


def test_o_grupo_kernel_e_o_nvidia_nao_se_seguram(lar: Lar) -> None:
    for grupo in ("kernel", "nvidia"):
        assert lar.rodar("apt-instalar", grupo).returncode == 0
    segurados = " ".join(x for x in lar.lidas() if x.startswith("apt-mark hold "))
    assert "linux-system76" not in segurados and "nvidia-driver" not in segurados
