"""Testes de regressão do scripts/check_anonymity.sh: a privacidade de aparelho.

O vocabulário (quem assina, os termos que não se publicam) saiu daqui e mora em
`scripts/check_autoria.py`, com os casos em `tests/unit/test_check_autoria.py`. Este
script ficou com o endereço de rádio e o número de série de fábrica.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT_REL_PATH = "scripts/check_anonymity.sh"
CANARIO = "zqcanario" + "autoria"

# Forma de série de fábrica, num prefixo FORJADO: o portão mede pela forma.
SERIAL_FORJADO = "Z99Z99" + "ABCDEFGHIJK"


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """Monta um repo fake mínimo com o script copiado."""
    repo_root = Path(__file__).resolve().parents[2]
    src_script = repo_root / SCRIPT_REL_PATH
    if not src_script.exists():
        pytest.skip(f"script {SCRIPT_REL_PATH} não encontrado no repo")

    (tmp_path / "scripts").mkdir()
    (tmp_path / "src" / "hefesto_dualsense4unix").mkdir(parents=True)

    dst_script = tmp_path / SCRIPT_REL_PATH
    shutil.copy2(src_script, dst_script)
    dst_script.chmod(0o755)
    return tmp_path


def run_check(repo: Path) -> subprocess.CompletedProcess[str]:
    """Executa o script no cwd do fake repo e captura o resultado."""
    return subprocess.run(
        ["bash", SCRIPT_REL_PATH],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def _git_de_mentira(repo: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, capture_output=True)


def test_repositorio_limpo_passa(fake_repo: Path) -> None:
    (fake_repo / "src/hefesto_dualsense4unix/a.py").write_text("# código limpo\n")
    result = run_check(fake_repo)
    assert result.returncode == 0, result.stdout
    assert "OK" in result.stdout


def test_o_script_nao_dispara_em_si_mesmo(fake_repo: Path) -> None:
    result = run_check(fake_repo)
    assert result.returncode == 0, result.stdout


def test_funciona_com_o_ramo_do_git(fake_repo: Path) -> None:
    _git_de_mentira(fake_repo)
    (fake_repo / "src/hefesto_dualsense4unix/a.py").write_text("# código limpo\n")
    subprocess.run(["git", "add", "."], cwd=fake_repo, check=True, capture_output=True)
    result = run_check(fake_repo)
    assert result.returncode == 0, result.stdout


def test_o_vocabulario_nao_e_mais_deste_script(fake_repo: Path) -> None:
    """A metade de vocabulário saiu: quem a mede é `check_autoria.py`, pela lista de fora."""
    (fake_repo / "src/hefesto_dualsense4unix/a.py").write_text(
        f"# {CANARIO}\n# written by someone\n# feito por fulano\n"
    )
    result = run_check(fake_repo)
    assert result.returncode == 0, result.stdout
    texto = (Path(__file__).resolve().parents[2] / SCRIPT_REL_PATH).read_text(encoding="utf-8")
    assert "FORBIDDEN" not in texto and "RUIDO_MEDIDO" not in texto


def test_serial_de_fabrica_reprova_e_a_saida_nao_o_republica(fake_repo: Path) -> None:
    _git_de_mentira(fake_repo)
    (fake_repo / "src/hefesto_dualsense4unix/a.py").write_text(f"# serial {SERIAL_FORJADO}\n")
    subprocess.run(["git", "add", "."], cwd=fake_repo, check=True, capture_output=True)
    result = run_check(fake_repo)
    assert result.returncode == 1, result.stdout
    assert "SERIAL DE FÁBRICA" in result.stdout
    assert SERIAL_FORJADO not in result.stdout, "o portão republicou o serial inteiro"
    assert SERIAL_FORJADO[:6] + "#" * 11 in result.stdout


def test_serial_em_arquivo_novo_ainda_sem_git_add_tambem_reprova(fake_repo: Path) -> None:
    _git_de_mentira(fake_repo)
    (fake_repo / "src/hefesto_dualsense4unix/novo.py").write_text(f"# {SERIAL_FORJADO}\n")
    result = run_check(fake_repo)
    assert result.returncode == 1, result.stdout
    assert "novo.py" in result.stdout


def test_arquivo_ignorado_pelo_gitignore_nao_e_medido(fake_repo: Path) -> None:
    _git_de_mentira(fake_repo)
    (fake_repo / ".gitignore").write_text("lixo/\n", encoding="utf-8")
    (fake_repo / "lixo").mkdir()
    (fake_repo / "lixo" / "gerado.py").write_text(f"# {SERIAL_FORJADO}\n")
    result = run_check(fake_repo)
    assert result.returncode == 0, result.stdout
