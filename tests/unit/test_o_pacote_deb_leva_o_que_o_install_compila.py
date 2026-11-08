"""O pacote .deb leva todo módulo DKMS e o compila em cada kernel novo.

A sprint é a O-PACOTE-DEB-LEVA-O-QUE-O-INSTALL-COMPILA-01. Medido em 31/10/2026: o `build_deb.sh`
listava quatro pastas de `assets/dkms/` à mão, sem o `uhid`, e o `postinst` só dizia para rodar um
ajudante. No Debian 12 (dkms 3.0.10) o `dkms.conf` desliga o `AUTOINSTALL`, e um kernel novo ficava
no módulo de fábrica sem próximo install: o .deb não tem próximo install.

MORDIDAS (06/11/2026, executadas sobre a cura e devolvidas):

- a lista de quatro pastas devolvida ao `build_deb.sh` reprova
  `test_o_pacote_copia_toda_pasta_com_dkms_conf`;
- `dkms_do_pacote.sh` sem o `HEFESTO_DKMS_KERNEL` reprova `test_o_kernel_novo_recebe_cada_modulo`;
- o gancho fora do `build_deb.sh` reprova `test_o_gancho_do_kernel_entra_nos_dois_lugares`;
- o gancho sem o `|| true` reprova `test_o_gancho_nunca_derruba_a_instalacao_do_kernel`;
- a remoção do `hefesto-uhid` tirada do `prerm` reprova `test_a_remocao_desfaz_cada_modulo`;
- o `dkms_flush_initramfs` de volta só para o kernel que roda reprova
  `test_os_headers_que_chegam_depois_refazem_o_initramfs_do_kernel_novo`;
- o `--force` tirado do `dkms install` reprova
  `test_o_modulo_substitui_o_de_fabrica_mesmo_sem_versao_que_os_separe`.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
DKMS = RAIZ / "assets" / "dkms"
BUILD_DEB = RAIZ / "scripts" / "build_deb.sh"
GANCHO = RAIZ / "packaging" / "debian" / "kernel-postinst"
AJUDANTE = RAIZ / "scripts" / "dkms_do_pacote.sh"
KERNEL_NOVO = "6.1.0-99-amd64"


def _pastas() -> list[str]:
    return sorted(conf.parent.name for conf in DKMS.glob("*/dkms.conf"))


def _do_conf(pasta: str, campo: str) -> str:
    achado = re.search(rf'^{re.escape(campo)}="(.*)"$',
                       (DKMS / pasta / "dkms.conf").read_text(encoding="utf-8"), re.M)
    assert achado, f"{pasta}: sem {campo}"
    return achado.group(1)


def test_o_pacote_copia_toda_pasta_com_dkms_conf(tmp_path: Path) -> None:
    texto = BUILD_DEB.read_text(encoding="utf-8")
    achado = re.search(r"^for _conf in .*?^done$", texto, re.M | re.S)
    assert achado, "o build_deb.sh não copia as fontes DKMS por laço"
    subprocess.run(["bash", "-euc", achado.group(0)], cwd=RAIZ, check=True,
                   env={**os.environ, "STAGING": str(tmp_path)})
    levadas = sorted(p.parent.name for p in tmp_path.glob(
        "usr/share/hefesto-dualsense4unix/dkms/*/dkms.conf"))
    assert levadas == _pastas()
    assert "uhid" in levadas


def test_o_gancho_do_kernel_entra_nos_dois_lugares() -> None:
    """O `dkms` do Debian também olha os dois: os headers chegam depois da imagem do kernel."""
    texto = BUILD_DEB.read_text(encoding="utf-8")
    assert "/etc/kernel/postinst.d/hefesto-dualsense4unix" in texto
    assert "/etc/kernel/header_postinst.d/hefesto-dualsense4unix" in texto
    assert "scripts/dkms_do_pacote.sh" in texto


def _base_de_mentira(tmp_path: Path) -> tuple[dict[str, str], Path]:
    base = tmp_path / "pacote"
    (base / "scripts").mkdir(parents=True)
    (base / "scripts" / "dkms_lib.sh").write_bytes(
        (RAIZ / "scripts" / "dkms_lib.sh").read_bytes())
    for pasta in _pastas():
        destino = base / "dkms" / pasta
        destino.mkdir(parents=True)
        (destino / "dkms.conf").write_bytes((DKMS / pasta / "dkms.conf").read_bytes())
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    registro = tmp_path / "dkms.log"
    falsos = {
        "dkms": f'#!/bin/sh\necho "$*" >> {registro}\nexit 0\n',
        "sudo": '#!/bin/sh\nexec "$@"\n',
        "chown": f'#!/bin/sh\necho "chown $*" >> {registro}\n',
        "chmod": f'#!/bin/sh\necho "chmod $*" >> {registro}\n',
        "modinfo": "#!/bin/sh\nexit 1\n",
        "uname": "#!/bin/sh\necho 7.0.0-kernel-que-roda\n",
        "update-initramfs": f'#!/bin/sh\necho "update-initramfs $*" >> {registro}\n',
        "dracut": f'#!/bin/sh\necho "dracut $*" >> {registro}\n',
        "mkinitcpio": f'#!/bin/sh\necho "mkinitcpio $*" >> {registro}\n',
    }
    for nome, corpo in falsos.items():
        (bin_ / nome).write_text(corpo, encoding="utf-8")
        (bin_ / nome).chmod(0o755)
    for kernel in (KERNEL_NOVO, "7.0.0-kernel-que-roda"):
        (tmp_path / "modules" / kernel / "build").mkdir(parents=True)
    ambiente = {
        **os.environ,
        "PATH": f"{bin_}:{os.environ['PATH']}",
        "HEFESTO_PACOTE_BASE": str(base),
        "HEFESTO_DKMS_SRC_ROOT": str(tmp_path / "src"),
        "HEFESTO_DKMS_MODULES_ROOT": str(tmp_path / "modules"),
        "HEFESTO_DKMS_TREE": str(tmp_path / "arvore"),
        "HEFESTO_EFIVARS_ROOT": str(tmp_path / "sem-efi"),
        "COM_UHID_CONTRAPRESSAO": "1",
    }
    return ambiente, registro


def _rodar(ambiente: dict[str, str], *argumentos: str) -> None:
    feito = subprocess.run(["bash", str(AJUDANTE), *argumentos], env=ambiente,
                           capture_output=True, text=True, timeout=60)
    assert feito.returncode == 0, feito.stderr


def test_o_kernel_novo_recebe_cada_modulo(tmp_path: Path) -> None:
    ambiente, registro = _base_de_mentira(tmp_path)
    _rodar(ambiente, KERNEL_NOVO)
    chamadas = registro.read_text(encoding="utf-8")
    for pasta in _pastas():
        nome = f"{_do_conf(pasta, 'PACKAGE_NAME')}/{_do_conf(pasta, 'PACKAGE_VERSION')}"
        assert f"build {nome} -k {KERNEL_NOVO}" in chamadas, chamadas
        assert f"install {nome} -k {KERNEL_NOVO}" in chamadas, chamadas
    assert "7.0.0-kernel-que-roda" not in chamadas


def test_sem_argumento_o_kernel_e_o_que_roda(tmp_path: Path) -> None:
    ambiente, registro = _base_de_mentira(tmp_path)
    _rodar(ambiente)
    chamadas = registro.read_text(encoding="utf-8")
    assert "build hefesto-uhid/1.0.0 -k 7.0.0-kernel-que-roda" in chamadas, chamadas
    assert KERNEL_NOVO not in chamadas


def _com_initramfs(tmp_path: Path, ambiente: dict[str, str], *, ko_novo: bool) -> dict[str, str]:
    """O `.ko` do kernel novo e o initramfs dele, um mais novo que o outro."""
    ko, initrd = tmp_path / "updates" / "dkms" / "uhid.ko", tmp_path / "initrd"
    ko.parent.mkdir(parents=True)
    ko.write_bytes(b"")
    initrd.write_bytes(b"")
    os.utime(ko if ko_novo else initrd, (2_000_000_000, 2_000_000_000))
    os.utime(initrd if ko_novo else ko, (1_000_000_000, 1_000_000_000))
    modinfo = Path(ambiente["PATH"].split(":")[0]) / "modinfo"
    modinfo.write_text(
        f'#!/bin/sh\n[ "$1 $2" = "-k {KERNEL_NOVO}" ] || exit 1\necho {ko}\n', encoding="utf-8")
    return {**ambiente, "HEFESTO_INITRAMFS_PATH": str(initrd)}


def test_os_headers_que_chegam_depois_refazem_o_initramfs_do_kernel_novo(tmp_path: Path) -> None:
    """Instalados depois da imagem, o initramfs do kernel novo já nasceu sem o módulo do Hefesto.

    O `postinst.d/initramfs-tools` não roda de novo, e o boot carregaria a cópia de fábrica."""
    ambiente, registro = _base_de_mentira(tmp_path)
    _rodar(_com_initramfs(tmp_path, ambiente, ko_novo=True), KERNEL_NOVO)
    assert f"update-initramfs -u -k {KERNEL_NOVO}" in registro.read_text(encoding="utf-8")


def test_o_initramfs_mais_novo_que_o_modulo_fica(tmp_path: Path) -> None:
    ambiente, registro = _base_de_mentira(tmp_path)
    _rodar(_com_initramfs(tmp_path, ambiente, ko_novo=False), KERNEL_NOVO)
    assert "update-initramfs" not in registro.read_text(encoding="utf-8")


def test_a_imagem_do_kernel_sem_initramfs_ainda_deixa_para_o_gancho_dele(tmp_path: Path) -> None:
    """No `postinst.d` o gancho vem antes do `initramfs-tools`, que nasce com o módulo."""
    ambiente, registro = _base_de_mentira(tmp_path)
    com_initrd = _com_initramfs(tmp_path, ambiente, ko_novo=True)
    (tmp_path / "initrd").unlink()
    _rodar(com_initrd, KERNEL_NOVO)
    assert "update-initramfs" not in registro.read_text(encoding="utf-8")


def _dkms_que_diz(ambiente: dict[str, str], registro: Path, status: str) -> None:
    (Path(ambiente["PATH"].split(":")[0]) / "dkms").write_text(
        f'#!/bin/sh\necho "$*" >> {registro}\n[ "$1" = status ] && echo "{status}"\nexit 0\n',
        encoding="utf-8")


def test_o_modulo_substitui_o_de_fabrica_mesmo_sem_versao_que_os_separe(tmp_path: Path) -> None:
    """O kernel do Debian 12 não grava `srcversion`, e o `.ko` nosso também não tem `version`: o
    DKMS diz que «exactly matches», não copia nada e o status sai `installed`. Medido em 07/11/2026
    no `debian:12`, dkms 3.0.10. MORDIDA: tirar o `--force` do `dkms install`."""
    ambiente, registro = _base_de_mentira(tmp_path)
    _rodar(ambiente, KERNEL_NOVO)
    assert f"install hefesto-uhid/1.0.0 -k {KERNEL_NOVO} --force" in registro.read_text("utf-8")


@pytest.mark.parametrize("aviso", ["WARNING! Diff between built and installed module!",
                                   "Differences between built and installed modules"],
                         ids=["dkms-3.0", "dkms-3.4"])
def test_o_autoinstall_que_nao_substituiu_se_refaz(tmp_path: Path, aviso: str) -> None:
    """O `autoinstall` do DKMS não tem o `--force`: o aviso de diferença é o rastro dele, e cada
    série do DKMS o escreve de um jeito. MORDIDA: casar só a frase do 3.0 reprova o `dkms-3.4`."""
    ambiente, registro = _base_de_mentira(tmp_path)
    _dkms_que_diz(ambiente, registro, f"x, y, z: installed ({aviso})")
    _rodar(ambiente, KERNEL_NOVO)
    assert f"install hefesto-uhid/1.0.0 -k {KERNEL_NOVO}" in registro.read_text("utf-8")


def test_o_que_ja_esta_instalado_nao_se_reinstala(tmp_path: Path) -> None:
    ambiente, registro = _base_de_mentira(tmp_path)
    _dkms_que_diz(ambiente, registro, "x, y, z: installed")
    _rodar(ambiente, KERNEL_NOVO)
    assert f"install hefesto-uhid/1.0.0 -k {KERNEL_NOVO}" not in registro.read_text("utf-8")


def test_o_modulo_que_nao_chegou_ao_updates_nao_diz_ok(tmp_path: Path) -> None:
    """MORDIDA: voltar o `ok` incondicional para o kernel de fora do que roda."""
    ambiente, _ = _base_de_mentira(tmp_path)
    feito = subprocess.run(["bash", str(AJUDANTE), KERNEL_NOVO], env=ambiente,
                           capture_output=True, text=True, timeout=60)
    assert "NÃO aponta" in feito.stdout, feito.stdout
    assert "ok:" not in feito.stdout, feito.stdout


def _gancho_com(tmp_path: Path, corpo: str | None) -> subprocess.CompletedProcess[str]:
    ajudante = tmp_path / "ajudante"
    gancho = tmp_path / "gancho"
    texto = GANCHO.read_text(encoding="utf-8")
    assert "/usr/share/hefesto-dualsense4unix/scripts/dkms_do_pacote.sh" in texto
    gancho.write_text(texto.replace(
        "/usr/share/hefesto-dualsense4unix/scripts/dkms_do_pacote.sh", str(ajudante)),
        encoding="utf-8")
    if corpo is not None:
        ajudante.write_text(corpo, encoding="utf-8")
        ajudante.chmod(0o755)
    return subprocess.run(["sh", str(gancho), KERNEL_NOVO, "/boot/vmlinuz"], capture_output=True,
                          text=True, timeout=30)


@pytest.mark.parametrize("corpo", ["#!/bin/sh\nexit 1\n", None], ids=["falhou", "pacote-removido"])
def test_o_gancho_nunca_derruba_a_instalacao_do_kernel(tmp_path: Path, corpo: str | None) -> None:
    assert _gancho_com(tmp_path, corpo).returncode == 0


def test_o_gancho_passa_o_kernel_novo(tmp_path: Path) -> None:
    saida = tmp_path / "recebido"
    feito = _gancho_com(tmp_path, f'#!/bin/sh\necho "$*" > {saida}\n')
    assert feito.returncode == 0
    assert saida.read_text(encoding="utf-8").strip() == KERNEL_NOVO


@pytest.mark.parametrize("script", ["prerm", "postrm"])
def test_a_remocao_desfaz_cada_modulo(script: str) -> None:
    texto = (RAIZ / "packaging" / "debian" / script).read_text(encoding="utf-8")
    for pasta in _pastas():
        assert f'dkms remove "{_do_conf(pasta, "PACKAGE_NAME")}/' in texto, pasta


def test_o_control_declara_o_python_que_o_preparador_pede() -> None:
    """O preparador roda no `python3` do sistema, fora do venv, e o `zip(strict=True)` pede o 3.10.

    Medido em 06/11/2026 no `python:3.9`: `TypeError: zip() takes no keyword arguments`."""
    control = (RAIZ / "packaging" / "debian" / "control").read_text(encoding="utf-8")
    assert "python3 (>= 3.10)" in control
    assert 'requires-python = ">=3.10"' in (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    for pasta in _pastas():
        preparador = (DKMS / pasta / "preparar-o-fonte.py").read_text(encoding="utf-8")
        assert preparador.startswith("#!/usr/bin/env python3\n"), pasta
        assert "strict=True" in preparador, pasta


def test_o_github_nao_cita_a_fedora_que_saiu_da_matriz() -> None:
    citados = [c for c in (RAIZ / ".github").rglob("*.y*ml")
               if "fedora-40" in c.read_text(encoding="utf-8")]
    assert not citados, citados
