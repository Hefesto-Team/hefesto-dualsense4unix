"""O install e o uninstall recusam rodar como root.

O-INSTALL-E-O-UNINSTALL-RECUSAM-RODAR-COMO-ROOT-01: os dois scripts de verdade, copiados sozinhos
para uma árvore de mentira, com um `id` que responde 0 e um lar de mentira. Sem a guarda, a
cópia sozinha para logo adiante (o install na recusa da distro sem systemd, o uninstall no
`source` que falta), então a mordida nunca roda uma instalação de verdade.

A MORDIDA: tire a guarda do começo de um dos dois e a frase some.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
FRASE = "não rode com sudo na frente"


def _rodar(tmp_path: Path, script: str, *args: str, **env: str) -> subprocess.CompletedProcess[str]:
    binarios = tmp_path / "bin"
    binarios.mkdir()
    (binarios / "id").write_text(
        '#!/bin/bash\n[[ "$1" == -u ]] && { echo 0; exit 0; }\nexec /usr/bin/id "$@"\n',
        encoding="utf-8",
    )
    (binarios / "id").chmod(0o755)
    arvore = tmp_path / "arvore"
    arvore.mkdir()
    shutil.copy(RAIZ / script, arvore / script)
    lar = tmp_path / "lar"
    lar.mkdir()
    feito = subprocess.run(
        ["bash", str(arvore / script), *args], capture_output=True, text=True, check=False,
        timeout=60,
        env={**os.environ, "PATH": f"{binarios}:{os.environ['PATH']}", "HOME": str(lar),
             "XDG_STATE_HOME": str(lar / "estado"), "XDG_CONFIG_HOME": str(lar / "config"),
             "HEFESTO_RAIZ_DO_SISTEMA": str(tmp_path / "sem-systemd"), **env},
    )
    assert not any(lar.iterdir()), "nada se escreve no lar antes da recusa"
    return feito


@pytest.mark.parametrize("script", ["install.sh", "uninstall.sh"])
def test_como_root_o_script_recusa_com_a_frase(tmp_path: Path, script: str) -> None:
    """D-1911-O-INSTALL-E-O-UNINSTALL-RECUSAM-ROOT: com sudo na frente, para antes de escrever."""
    feito = _rodar(tmp_path, script, "--yes")
    assert feito.returncode != 0
    assert FRASE in feito.stderr, feito.stdout + feito.stderr


@pytest.mark.parametrize("script", ["install.sh", "uninstall.sh"])
@pytest.mark.parametrize("como", ["ensaio", "conteiner"])
def test_o_ensaio_e_o_conteiner_passam_da_guarda(tmp_path: Path, script: str, como: str) -> None:
    args = ("--dry-run",) if como == "ensaio" else ("--yes",)
    env = {"HEFESTO_INSTALL_EM_CONTEINER": "1"} if como == "conteiner" else {}
    feito = _rodar(tmp_path, script, *args, **env)
    assert FRASE not in feito.stdout + feito.stderr


@pytest.mark.parametrize("script", ["install.sh", "uninstall.sh"])
def test_a_ajuda_passa_da_guarda(tmp_path: Path, script: str) -> None:
    feito = _rodar(tmp_path, script, "--help")
    assert feito.returncode == 0
    assert FRASE not in feito.stdout + feito.stderr
