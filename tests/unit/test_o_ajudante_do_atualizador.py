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
reprova a segunda volta dele.
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
INSTALADOS = (("nvidia-driver-595", "595.104.02-0ubuntu1"),
              ("libnvidia-gl-595", "595.104.02-0ubuntu1"), ("linux-system76", "7.2.15.76070215"),
              ("linux-image-7.2.15", "7.2.15-1"),
              ("curl", "8.5.0-2ubuntu10"), ("bluez", "5.87-0ubuntu0.1~hefesto24.04.5"),
              ("pipewire", "1.6.9-0~hefesto24.04.1"),
              ("xdg-desktop-portal-cosmic", "1.0.0~1780000000+0~hefesto1"))


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
        self.api = ""
        for nome in ("apt-get", "dkms", "bootctl", "update-initramfs"):
            self.duble(nome)
        self.duble("uname", 'echo 7.2.15-generic')
        self.duble("apt-mark", f'[ "$1" = showhold ] && cat "{self.segurados}"; exit 0')
        linhas = "".join(f"{p}\\tii \\t{v}\\n" for p, v in INSTALADOS)
        self.duble("dpkg-query", f'printf "{linhas}"')

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
        "dkms-refazer", "mangohud-instalar", "mangohud-voltar",
        *(f"backport-{v} {p}" for p in ("bluez", "pipewire", "portal")
          for v in ("construir", "instalar", "voltar")),
        "kernel-anterior")]
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
    feito = lar.rodar("dkms-refazer", HEFESTO_ATUALIZADOR_DONO="root")
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
    assert lar.lidas().count("setup install") == 3
    segunda = lar.rodar("mangohud-voltar")
    assert segunda.returncode == 2 and "sem versão anterior" in segunda.stderr
    assert lar.lidas().count("setup install") == 3


def test_o_mangohud_nao_volta_de_pasta_que_outro_escreve(lar: Lar) -> None:
    _instalar_mangohud(lar, "MangoHud-0.8.4.r0.tar.gz")
    _instalar_mangohud(lar, "MangoHud-0.8.5.r0.tar.gz")
    (lar.cache / "mangohud").chmod(0o777)
    feito = lar.rodar("mangohud-voltar")
    assert feito.returncode == 2 and "não é só do root" in feito.stderr
    assert lar.lidas().count("setup install") == 2


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
    assert ordem[0] == "apt-mark hold bluez xdg-desktop-portal-cosmic", ordem
    assert ordem[1].startswith("apt-get")
    assert ordem[-1] == "apt-mark unhold bluez xdg-desktop-portal-cosmic", ordem
    assert not any("pipewire" in x for x in ordem), "o que já estava segurado não se solta"


def test_a_subida_que_falha_solta_os_da_casa_igual(lar: Lar) -> None:
    lar.duble("apt-get", "exit 100")
    feito = lar.rodar("apt-instalar", "sistema")
    assert feito.returncode != 0
    assert _ordem(lar)[-1] == "apt-mark unhold bluez xdg-desktop-portal-cosmic"


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
    feito = lar.rodar("apt-limpar")
    assert feito.returncode == 0, feito.stderr
    ordem = _ordem(lar)
    assert ordem[0] == "apt-mark hold bluez xdg-desktop-portal-cosmic", ordem
    assert "autoremove" in ordem[1]
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
