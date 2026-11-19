"""A venv doente se recria com o motivo dito — A-VENV-DOENTE-SE-RECRIA-COM-O-MOTIVO-DITO-01.

O passo 2 do `install.sh` de verdade (o trecho entre a escolha do Python e a criação da venv),
sob `set -euo pipefail`, sobre quatro venvs doentes forjadas: sem `pyvenv.cfg`, sem
`bin/python`, com o python num link quebrado, e a do Python de antes da atualização da distro,
com o python em link para o do sistema.

AS MORDIDAS: devolva a comparação pelo executável e a quarta passa calada; tire a guarda do
`pyvenv.cfg` e o rc mudo volta.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
INSTALL = RAIZ / "install.sh"
SAUDE = RAIZ / "scripts/lib/saude_da_venv.sh"
RUN = RAIZ / "run.sh"
SISTEMA = sys.version_info[:2]
VERSAO_DE_ANTES = f"{SISTEMA[0]}.{SISTEMA[1] - 1}.9"


def _passo_2() -> str:
    texto = INSTALL.read_text(encoding="utf-8")
    inicio = texto.index('_VENV_PYTHON="$(python_do_sistema)"')
    fim = texto.index('if [[ "${DRY_RUN:-0}" -eq 1 ]] && [[ ! -d "${VENV_DIR}" ]]; then')
    return texto[inicio:fim]


def _venv(tmp_path: Path, caso: str) -> Path:
    venv = tmp_path / ".venv"
    (venv / "bin").mkdir(parents=True)
    cfg = venv / "pyvenv.cfg"
    cfg.write_text(f"home = /usr/bin\nversion = {SISTEMA[0]}.{SISTEMA[1]}.0\n", encoding="utf-8")
    python = venv / "bin/python"
    if caso == "sem-pyvenv-cfg":
        cfg.unlink()
        python.symlink_to(sys.executable)
    elif caso == "link-quebrado":
        python.symlink_to(tmp_path / "python-que-sumiu")
    elif caso == "python-de-antes":
        cfg.write_text(f"home = /usr/bin\nversion = {VERSAO_DE_ANTES}\n", encoding="utf-8")
        (venv / "lib" / f"python{SISTEMA[0]}.{SISTEMA[1] - 1}").mkdir(parents=True)
        python.symlink_to(sys.executable)
    elif caso == "python-de-fora":
        cfg.write_text(f"home = /opt/python/bin\nversion = {SISTEMA[0]}.{SISTEMA[1]}.0\n",
                       encoding="utf-8")
        python.symlink_to(sys.executable)
    elif caso == "saudavel":
        python.symlink_to(sys.executable)
    return venv


def _rodar_o_passo_2(tmp_path: Path, venv: Path) -> subprocess.CompletedProcess[str]:
    roteiro = "\n".join([
        "set -euo pipefail",
        f'source "{SAUDE}"' if SAUDE.exists() else ":",
        '_faria() { printf "FARIA %s\\n" "$*"; }',
        _passo_2(),
        'printf "passou do passo 2\\n"',
    ])
    return subprocess.run(
        ["bash", "-c", roteiro], capture_output=True, text=True, check=False, timeout=60,
        env={**os.environ, "VENV_DIR": str(venv), "DRY_RUN": "0"},
    )


@pytest.mark.parametrize(
    "caso", ["sem-pyvenv-cfg", "sem-python", "link-quebrado", "python-de-antes", "python-de-fora"],
)
def test_a_venv_doente_se_recria_com_o_motivo(tmp_path: Path, caso: str) -> None:
    """D-1911-A-VENV-DOENTE-SE-RECRIA-COM-O-MOTIVO: recria e diz por quê, nunca rc mudo."""
    venv = _venv(tmp_path, caso)
    feito = _rodar_o_passo_2(tmp_path, venv)
    assert feito.returncode == 0, feito.stdout + feito.stderr
    assert "passou do passo 2" in feito.stdout
    assert "recriando" in feito.stdout, feito.stdout
    assert not venv.exists(), "a venv doente fica, e o pip seguinte cai na venv quebrada"


def test_a_venv_saudavel_fica(tmp_path: Path) -> None:
    venv = _venv(tmp_path, "saudavel")
    feito = _rodar_o_passo_2(tmp_path, venv)
    assert feito.returncode == 0, feito.stdout + feito.stderr
    assert "recriando" not in feito.stdout
    assert venv.exists()


def test_o_motivo_da_versao_diz_as_duas(tmp_path: Path) -> None:
    venv = _venv(tmp_path, "python-de-antes")
    feito = subprocess.run(
        ["bash", "-c", f'source "{SAUDE}"; venv_doente "$1" "$2"', "_", str(venv),
         sys.executable],
        capture_output=True, text=True, check=False, timeout=30,
    )
    assert feito.returncode == 0
    assert VERSAO_DE_ANTES.rsplit(".", 1)[0] in feito.stdout
    assert f"{SISTEMA[0]}.{SISTEMA[1]}" in feito.stdout


def test_o_run_diz_rode_o_install_em_vez_de_cair_no_import(tmp_path: Path) -> None:
    arvore = tmp_path / "arvore"
    (arvore / "scripts/lib").mkdir(parents=True)
    (arvore / "run.sh").write_text(RUN.read_text(encoding="utf-8"), encoding="utf-8")
    (arvore / "scripts/lib/saude_da_venv.sh").write_text(SAUDE.read_text(encoding="utf-8"),
                                                         encoding="utf-8")
    _venv(arvore, "link-quebrado")
    feito = subprocess.run(["bash", str(arvore / "run.sh"), "--smoke"], capture_output=True,
                           text=True, check=False, timeout=30)
    assert feito.returncode != 0
    assert "./install.sh" in feito.stdout + feito.stderr


def test_a_venv_de_outro_python_que_roda_abre_pelo_run(tmp_path: Path) -> None:
    """MORDIDA: o `home` de fora do sistema dentro do `venv_doente` fecha o run.sh e o doctor."""
    arvore = tmp_path / "arvore"
    (arvore / "scripts/lib").mkdir(parents=True)
    (arvore / "run.sh").write_text(RUN.read_text(encoding="utf-8"), encoding="utf-8")
    (arvore / "scripts/lib/saude_da_venv.sh").write_text(SAUDE.read_text(encoding="utf-8"),
                                                         encoding="utf-8")
    venv = _venv(arvore, "python-de-fora")
    falso = tmp_path / "falso"
    falso.mkdir()
    (falso / "python3").write_text("#!/bin/bash\necho abriu\n", encoding="utf-8")
    (falso / "python3").chmod(0o755)
    (venv / "bin/activate").write_text(f'PATH="{falso}:$PATH"\n', encoding="utf-8")
    feito = subprocess.run(["bash", str(arvore / "run.sh"), "--tray"], capture_output=True,
                           text=True, check=False, timeout=30)
    assert feito.returncode == 0, feito.stdout + feito.stderr
    assert feito.stdout.strip() == "abriu"


def test_o_doctor_reprova_a_venv_doente_da_arvore(tmp_path: Path) -> None:
    doctor = (RAIZ / "scripts/doctor.sh").read_text(encoding="utf-8")
    inicio = doctor.index("check_venv_da_arvore() {")
    funcao = doctor[inicio:doctor.index("\n}\n", inicio) + 3]
    arvore = tmp_path / "arvore"
    (arvore / "scripts/lib").mkdir(parents=True)
    (arvore / "install.sh").touch()
    (arvore / "scripts/lib/saude_da_venv.sh").write_text(SAUDE.read_text(encoding="utf-8"),
                                                         encoding="utf-8")
    _venv(arvore, "python-de-antes")
    roteiro = "\n".join([
        'pass() { echo "[PASS] $*"; }', 'fail() { echo "[FAIL] $*"; }',
        'esta_instalacao_e_um_checkout() { [[ -f "${ROOT_DIR}/install.sh" ]]; }',
        "conselho_de_instalacao() { printf 'rode ./install.sh'; }",
        funcao, "check_venv_da_arvore",
    ])
    saida = subprocess.run(["bash", "-c", roteiro], capture_output=True, text=True, check=False,
                           timeout=30, env={**os.environ, "ROOT_DIR": str(arvore)}).stdout
    assert "[FAIL]" in saida and "./install.sh" in saida, saida
