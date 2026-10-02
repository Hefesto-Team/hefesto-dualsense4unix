"""Os dois buracos do `scripts/check_endereco_de_radio.py`, medidos em 26/08/2026."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_REL = "scripts/check_endereco_de_radio.py"

_OUI_DE_MENTIRA = "06:DE:AD"
_SUFIXO_DE_MENTIRA = "BE:EF:01"
MAC_DE_MENTIRA = f"{_OUI_DE_MENTIRA}:{_SUFIXO_DE_MENTIRA}"


@pytest.fixture
def repo_falso(tmp_path: Path) -> Path:
    """Repo de mentira com o portão copiado e um `git init` de verdade."""
    origem = Path(__file__).resolve().parents[2] / SCRIPT_REL
    if not origem.exists():
        pytest.skip(f"{SCRIPT_REL} não encontrado no repo")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "docs").mkdir()
    shutil.copy2(origem, tmp_path / SCRIPT_REL)
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "test"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    return tmp_path


def rodar(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, SCRIPT_REL],
        cwd=repo, capture_output=True, text=True, check=False,
    )


def test_arquivo_novo_sem_git_add_e_pego(repo_falso: Path) -> None:
    """O portão enxerga o arquivo NOVO, antes de qualquer `git add`."""
    (repo_falso / "docs" / "ja-revisado.md").write_text(
        "nada de endereço aqui\n", encoding="utf-8"
    )
    subprocess.run(["git", "add", "."], cwd=repo_falso, check=True, capture_output=True)

    (repo_falso / "docs" / "recem-colado.md").write_text(
        f"adaptador: {MAC_DE_MENTIRA}\n", encoding="utf-8"
    )

    r = rodar(repo_falso)
    assert r.returncode == 1, (
        "arquivo novo com endereço passou VERDE: a listagem voltou a olhar só "
        f"o índice.\nsaída:\n{r.stdout}"
    )
    assert "recem-colado.md" in r.stdout, r.stdout


def test_arquivo_que_o_gitignore_manda_ignorar_nao_reprova(repo_falso: Path) -> None:
    """A outra metade: `--exclude-standard` não pode ser esquecido."""
    (repo_falso / ".gitignore").write_text("lixo/\n", encoding="utf-8")
    (repo_falso / "lixo").mkdir()
    (repo_falso / "lixo" / "captura.txt").write_text(
        f"adaptador: {MAC_DE_MENTIRA}\n", encoding="utf-8"
    )

    r = rodar(repo_falso)
    assert r.returncode == 0, (
        "o portão acusou o que o `.gitignore` manda ignorar — sem "
        f"`--exclude-standard` ele grita falso.\nsaída:\n{r.stdout}"
    )


def test_svg_e_varrido(repo_falso: Path) -> None:
    """SVG é texto, e mesmo COMMITADO o endereço dentro dele passava."""
    (repo_falso / "docs" / "diagrama.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">'
        f"<text>adaptador {MAC_DE_MENTIRA}</text></svg>\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=repo_falso, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "svg"],
        cwd=repo_falso, check=True, capture_output=True,
    )

    r = rodar(repo_falso)
    assert r.returncode == 1, (
        "endereço dentro de um SVG COMMITADO passou verde: `.svg` voltou ao "
        f"EXCLUIR_SUFIXO.\nsaída:\n{r.stdout}"
    )
    assert "diagrama.svg" in r.stdout, r.stdout
