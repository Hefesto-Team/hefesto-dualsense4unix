"""O pacman pede os cabeçalhos do kernel que roda.

No CachyOS o kernel que roda é o ``linux-cachyos``, e o ``linux-headers`` do Arch puro não serve ao
dkms; o mesmo vale para o ``linux-zen`` e o ``linux-lts``. O instalador pergunta ao pacman quem é o
dono do ``vmlinuz`` do kernel que roda e pede os cabeçalhos dele. O ``pacman`` aqui é de mentira,
no ``PATH`` de um ``tmp_path``.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.unit.test_install_garante_deps_em_qualquer_familia import _roda


def _pacman_que_responde(tmp_path: Path, corpo: str) -> dict[str, str]:
    binario = tmp_path / "bin"
    binario.mkdir()
    alvo = binario / "pacman"
    alvo.write_text("#!/usr/bin/env bash\n" + corpo, encoding="utf-8")
    alvo.chmod(0o755)
    return {"HEFESTO_FAMILIA_PACOTES": "pacman", "PATH": f"{binario}:{os.environ['PATH']}"}


@pytest.mark.parametrize("kernel", ["linux-cachyos", "linux-zen", "linux-lts", "linux"])
def test_o_pacman_pede_os_cabecalhos_do_dono_do_kernel(tmp_path: Path, kernel: str) -> None:
    env = _pacman_que_responde(
        tmp_path, f'[[ "$1" == "-Qqo" && "$2" == /usr/lib/modules/*/vmlinuz ]] && echo {kernel}\n')
    proc = _roda("_pkg_nome kernel-headers", env=env)
    assert proc.stdout.strip() == f"{kernel}-headers", proc.stdout + proc.stderr


@pytest.mark.parametrize("corpo", [
    "echo 'error: No package owns /usr/lib/modules/x/vmlinuz' >&2; exit 1\n",
    "echo 'linux; rm -rf ~'\n",
    "printf 'linux\\nlinux-zen\\n'\n",
])
def test_sem_resposta_clara_cai_no_linux_headers(tmp_path: Path, corpo: str) -> None:
    proc = _roda("_pkg_nome kernel-headers", env=_pacman_que_responde(tmp_path, corpo))
    assert proc.stdout.strip() == "linux-headers", proc.stdout + proc.stderr


def test_as_outras_familias_nao_perguntam_ao_pacman(tmp_path: Path) -> None:
    env = _pacman_que_responde(tmp_path, 'touch "$MARCA"; echo linux-zen\n')
    env["MARCA"] = str(tmp_path / "perguntou")
    for familia, esperado in (("apt", "linux-headers-"), ("dnf", "kernel-devel")):
        proc = _roda("_pkg_nome kernel-headers", env={**env, "HEFESTO_FAMILIA_PACOTES": familia})
        assert proc.stdout.strip().startswith(esperado), proc.stdout + proc.stderr
    assert not (tmp_path / "perguntou").exists()
