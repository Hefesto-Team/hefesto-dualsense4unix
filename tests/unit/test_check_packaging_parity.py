"""Testes de regressão da seção udev do scripts/check_packaging_parity.sh.

FIX-PACKAGING-SEED-PARITY-01: a checagem garante que CADA assets/NN-*.rules
está coberta pelos instaladores (install_udev.sh, install-host-udev.sh,
build_deb.sh) e pelo uninstall.sh — uma regra nova (como a 78) não pode
sumir de um instalador sem ninguém notar.

Mesmo padrão de tests/unit/test_check_anonymity.py: pytest + subprocess num
repo fake em tmp_path (sem bats-core, sem depender do estado do repo real).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT_REL_PATH = "scripts/check_packaging_parity.sh"

RULE = "79-teste-parity.rules"


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """Repo fake mínimo: só o script + uma regra 79 coberta em TODO lugar.

    Sem packaging/ nem flatpak/, as seções de applet COSMIC passam vazias —
    aqui o alvo é exclusivamente a seção de paridade udev.
    """
    repo_root = Path(__file__).resolve().parents[2]
    src_script = repo_root / SCRIPT_REL_PATH
    if not src_script.exists():
        pytest.skip(f"script {SCRIPT_REL_PATH} não encontrado no repo")

    (tmp_path / "scripts").mkdir()
    (tmp_path / "assets").mkdir()
    dst_script = tmp_path / SCRIPT_REL_PATH
    shutil.copy2(src_script, dst_script)
    dst_script.chmod(0o755)

    (tmp_path / "assets" / RULE).write_text("# regra de teste\n", encoding="utf-8")
    # Cobertura completa: nativo e host por nome; .deb por glob (como o real).
    (tmp_path / "scripts" / "install_udev.sh").write_text(
        f'sudo install -Dm644 "$ASSETS/{RULE}" /etc/udev/rules.d/{RULE}\n',
        encoding="utf-8",
    )
    (tmp_path / "scripts" / "install-host-udev.sh").write_text(
        f'RULES=("{RULE}")\n', encoding="utf-8"
    )
    (tmp_path / "scripts" / "build_deb.sh").write_text(
        'for rules_file in assets/79-*.rules; do cp "$rules_file" x; done\n',
        encoding="utf-8",
    )
    (tmp_path / "uninstall.sh").write_text(
        f"sudo rm -f /etc/udev/rules.d/{RULE}\n", encoding="utf-8"
    )
    return tmp_path


def run_check(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", SCRIPT_REL_PATH],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def test_regra_coberta_em_todos_passa(fake_repo: Path) -> None:
    result = run_check(fake_repo)
    assert result.returncode == 0, result.stdout
    assert f"[ OK ] {RULE}" in result.stdout


def test_regra_fora_do_install_host_falha_nomeando_o_furado(fake_repo: Path) -> None:
    (fake_repo / "scripts" / "install-host-udev.sh").write_text(
        'RULES=("70-outra.rules")\n', encoding="utf-8"
    )
    result = run_check(fake_repo)
    assert result.returncode == 1
    assert f"[FAIL] {RULE}" in result.stdout
    assert "scripts/install-host-udev.sh" in result.stdout


def test_regra_fora_do_build_deb_falha(fake_repo: Path) -> None:
    (fake_repo / "scripts" / "build_deb.sh").write_text(
        "# sem nenhuma regra\n", encoding="utf-8"
    )
    result = run_check(fake_repo)
    assert result.returncode == 1
    assert "scripts/build_deb.sh" in result.stdout


def test_regra_fora_do_uninstall_falha(fake_repo: Path) -> None:
    (fake_repo / "uninstall.sh").write_text("# nada\n", encoding="utf-8")
    result = run_check(fake_repo)
    assert result.returncode == 1
    assert "uninstall.sh" in result.stdout


def test_regra_opt_in_so_exige_uninstall(fake_repo: Path) -> None:
    """A 75 (opt-in) dispensa cobertura de instalação, mas exige uninstall."""
    optional = "75-ps5-controller-disable-usb-audio.rules"
    (fake_repo / "assets" / optional).write_text("# opt-in\n", encoding="utf-8")
    (fake_repo / "uninstall.sh").write_text(
        f"sudo rm -f /etc/udev/rules.d/{RULE} /etc/udev/rules.d/{optional}\n",
        encoding="utf-8",
    )
    result = run_check(fake_repo)
    assert result.returncode == 0, result.stdout
    assert f"[ OK ] {optional}" in result.stdout


def test_udev_parity_do_repo_real_esta_verde() -> None:
    """No repo REAL, a seção udev não pode ter [FAIL] (regressão de paridade).

    Não exige exit 0 do script inteiro: outras seções (applet COSMIC) têm
    achados próprios fora do escopo desta guarda.
    """
    repo_root = Path(__file__).resolve().parents[2]
    if not (repo_root / SCRIPT_REL_PATH).exists():
        pytest.skip(f"script {SCRIPT_REL_PATH} não encontrado no repo")
    result = subprocess.run(
        ["bash", SCRIPT_REL_PATH],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    udev_section = result.stdout.split("== paridade das regras udev", 1)
    assert len(udev_section) == 2, "seção udev ausente na saída do script"
    assert "[FAIL]" not in udev_section[1].split("═", 1)[0].split("─", 1)[0]
