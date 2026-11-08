"""O ajudante root do atualizador: verbos fechados, nenhum argumento livre, e a soma conferida.

O-HEFESTO-SE-ATUALIZA-INTEIRO-01, volta 1 (08/11/2026). O script roda como quem testa, nunca como
root: sem root ele só age com as pastas desviadas por ``HEFESTO_ATUALIZADOR_*``, e o ``apt-get``,
o ``dpkg-query``, o ``dkms``, o ``curl`` e o ``bootctl`` são dublês num ``PATH`` próprio que
anotam a chamada.

AS MORDIDAS (feitas na sprint, com a cura devolvida): a regra com curinga reprova o caso da regra;
o dkms_lib.sh sem o chown reprova o caso do fonte só do root;
o grupo livre aceito reprova o caso do grupo; o DKMS refeito com fonte que não é só do dono
reprova o caso do fonte; o MangoHud instalado sem conferir o digest reprova o caso da soma errada.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import pwd
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
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
        self.casa = base / "casa"
        self.casa.mkdir()
        self.api = ""
        for nome in ("apt-get", "dkms", "bootctl", "update-initramfs"):
            self.duble(nome)
        self.duble("dpkg-query", 'printf "nvidia-driver-595\\tii \\nlibnvidia-gl-595\\tii \\n'
                                 'linux-system76\\tii \\nlinux-image-7.2.15\\tii \\n'
                                 'curl\\tii \\n"')

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
                    "HEFESTO_ATUALIZADOR_CASA": str(self.casa),
                    "HEFESTO_ATUALIZADOR_API": self.api, **env}
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
        "apt-instalar kernel", "apt-baixar sistema", "apt-instalar sistema", "apt-limpar",
        "dkms-refazer", "mangohud-instalar", "mangohud-voltar", "kernel-anterior")]
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
                 ("apt-instalar", "nvidia", "x"), ("dkms-refazer", "--force"), ()):
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
    apt = [linha for linha in lar.lidas() if linha.startswith("apt-get")]
    assert apt[0].endswith("-d install --only-upgrade nvidia-driver-595 libnvidia-gl-595")
    assert apt[1].endswith("install --only-upgrade linux-system76")
    assert apt[2].endswith("full-upgrade")
    assert apt[3].endswith("autoremove --purge")
    assert all("APT::Status-Fd=1" in linha for linha in apt)


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
    feito = lar.rodar("dkms-refazer")
    assert feito.returncode != 0
    assert not [linha for linha in lar.lidas() if linha.startswith("dkms install")]


def _tar_do_mangohud(lar: Lar, nome: str = "MangoHud-0.8.5.r0.tar.gz") -> Path:
    pasta = lar.casa / ".cache" / "hefesto-dualsense4unix" / "atualizador" / "mangohud"
    pasta.mkdir(parents=True)
    setup = f'#!/bin/sh\necho "setup $*" >> "{lar.chamadas}"\n'.encode()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo("MangoHud/mangohud-setup.sh")
        info.size, info.mode = len(setup), 0o755
        tar.addfile(info, io.BytesIO(setup))
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
    assert "setup install" in lar.lidas()
    assert (lar.cache / "mangohud" / "atual.tar.gz").read_bytes() == arq.read_bytes()


def test_o_mangohud_volta_ao_anterior(lar: Lar) -> None:
    assert lar.rodar("mangohud-voltar").returncode == 2
    arq = _tar_do_mangohud(lar)
    _api(lar, arq.name, hashlib.sha256(arq.read_bytes()).hexdigest())
    assert lar.rodar("mangohud-instalar").returncode == 0
    (lar.cache / "mangohud" / "anterior.tar.gz").write_bytes(arq.read_bytes())
    assert lar.rodar("mangohud-voltar").returncode == 0
    assert lar.lidas().count("setup install") == 2


def test_o_kernel_anterior_vale_no_proximo_inicio(lar: Lar) -> None:
    assert lar.rodar("kernel-anterior").returncode == 2
    (lar.entradas / "Pop_OS-oldkern.conf").write_text("", encoding="utf-8")
    assert lar.rodar("kernel-anterior").returncode == 0
    assert "bootctl set-default Pop_OS-oldkern.conf" in lar.lidas()


def test_o_fonte_do_dkms_fica_so_do_root_antes_do_build(tmp_path: Path) -> None:
    from tests.unit.test_o_secure_boot_se_le_sem_mokutil import _instalar

    _saida, chamadas = _instalar(tmp_path, ligado=False, inscrita=False)
    linhas = chamadas.splitlines()
    destino = tmp_path / "usr-src" / "hefesto-hid-playstation-1.0.0"
    dono = linhas.index(f"sudo chown -R root:root {destino}")
    escrita = linhas.index(f"sudo chmod -R go-w {destino}")
    assert dono < escrita < linhas.index("sudo dkms add hefesto-hid-playstation/1.0.0")
