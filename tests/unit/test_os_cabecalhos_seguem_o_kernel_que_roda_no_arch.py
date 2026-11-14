from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
LIB = RAIZ / "scripts" / "dkms_lib.sh"


def _binario(pasta: Path, nome: str, corpo: str) -> None:
    caminho = pasta / nome
    caminho.write_text(f"#!/bin/sh\n{corpo}\n", encoding="utf-8")
    caminho.chmod(0o755)


def _pacman_de_mentira(pasta: Path, dono: str | None) -> Path:
    head = shutil.which("head")
    assert head
    (pasta / "head").symlink_to(head)
    if dono is None:
        _binario(pasta, "pacman", "echo 'erro: nenhum pacote possui o arquivo' >&2\nexit 1")
    else:
        _binario(
            pasta,
            "pacman",
            '[ "$1" = "-Qqo" ] || exit 2\n'
            f'case "$2" in /usr/lib/modules/*/vmlinuz) echo {dono} ;; *) exit 1 ;; esac',
        )
    return pasta


def _bash(pasta: Path, script: str, *args: str) -> str:
    feito = subprocess.run(
        [BASH, "-c", f'source "{LIB}"; {script}', "_", *args],
        env={
            "PATH": str(pasta),
            "HEFESTO_EFIVARS_ROOT": "/nao-existe/efivars",
            "HEFESTO_DKMS_MODULES_ROOT": str(pasta / "kernels"),
        },
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    return feito.stdout.strip()


@pytest.mark.parametrize(
    ("dono", "kver", "esperado"),
    [
        ("linux-cachyos", "7.3.3-1-cachyos", "linux-cachyos-headers"),
        ("linux-cachyos-lts", "6.12.40-1-cachyos-lts", "linux-cachyos-lts-headers"),
        ("linux-zen", "7.3.3-zen1-1-zen", "linux-zen-headers"),
        ("linux-lts", "6.12.40-1-lts", "linux-lts-headers"),
        ("linux612", "6.12.40-1-MANJARO", "linux612-headers"),
        ("linux", "7.3.3-arch1-1", "linux-headers"),
    ],
)
def test_o_cabecalho_e_o_do_pacote_dono_do_kernel(
    tmp_path: Path, dono: str, kver: str, esperado: str
) -> None:
    pasta = _pacman_de_mentira(tmp_path, dono)
    assert _bash(pasta, 'cabecalhos_do_kernel_no_pacman "$1"', kver) == esperado


def test_kernel_sem_dono_no_pacman_cai_no_linux_headers(tmp_path: Path) -> None:
    pasta = _pacman_de_mentira(tmp_path, None)
    assert _bash(pasta, 'cabecalhos_do_kernel_no_pacman "$1"', "7.3.3-proprio") == (
        "linux-headers"
    )


@pytest.mark.parametrize(
    ("gerenciador", "dkms", "cabecalhos"),
    [
        ("apt-get", "sudo apt install dkms", "sudo apt install linux-headers-7.3.3-1-cachyos"),
        ("dnf", "sudo dnf install dkms", "sudo dnf install kernel-devel-7.3.3-1-cachyos"),
        ("pacman", "sudo pacman -S --needed dkms", "sudo pacman -S --needed linux-cachyos-headers"),
    ],
)
def test_a_cura_do_aviso_fala_o_gerenciador_da_maquina(
    tmp_path: Path, gerenciador: str, dkms: str, cabecalhos: str
) -> None:
    pasta = _pacman_de_mentira(tmp_path, "linux-cachyos") if gerenciador == "pacman" else tmp_path
    if gerenciador != "pacman":
        _binario(pasta, gerenciador, "exit 0")
    escondidos = tmp_path / "vazia"
    escondidos.mkdir()
    feito = subprocess.run(
        [
            BASH,
            "-c",
            f'source "{LIB}"; _dkms_como_instalar dkms; echo; '
            '_dkms_como_instalar cabecalhos 7.3.3-1-cachyos',
        ],
        env={"PATH": f"{pasta}:{escondidos}", "HEFESTO_EFIVARS_ROOT": "/nao-existe"},
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    assert feito.stdout.splitlines() == [dkms, cabecalhos]


def test_no_arch_o_aviso_de_cabecalhos_ausentes_nao_manda_o_apt(tmp_path: Path) -> None:
    pasta = _pacman_de_mentira(tmp_path, "linux-cachyos")
    _binario(pasta, "dkms", "exit 0")
    _binario(pasta, "uname", "echo 7.3.3-1-cachyos")
    saida = _bash(
        pasta,
        "dkms_install_patched_module hefesto-teste 9.9.9 /caminho/inexistente hid-teste",
    )
    assert "sudo pacman -S --needed linux-cachyos-headers" in saida
    assert "apt install" not in saida
