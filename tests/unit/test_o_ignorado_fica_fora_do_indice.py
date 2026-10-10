"""Nada que o `.gitignore` exclui entra no repositório: o portão pergunta ao índice, não ao disco."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "check_o_ignorado_fica_fora_do_indice.py"


def _carrega():
    spec = importlib.util.spec_from_file_location("check_o_ignorado_fica_fora_do_indice", SCRIPT)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _git(raiz: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(raiz), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    raiz = tmp_path / "repo"
    raiz.mkdir()
    _git(raiz, "init", "-q")
    _git(raiz, "config", "user.email", "teste@exemplo.invalid")
    _git(raiz, "config", "user.name", "teste")
    (raiz / ".gitignore").write_text("*.pyc\ndocs/process/\n", encoding="utf-8")
    (raiz / "README.md").write_text("produto\n", encoding="utf-8")
    (raiz / "docs" / "process").mkdir(parents=True)
    (raiz / "docs" / "process" / "x.md").write_text("estudo\n", encoding="utf-8")
    _git(raiz, "add", ".gitignore", "README.md")
    return raiz


def _roda(raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--raiz", str(raiz)],
        capture_output=True, text=True, check=False,
    )


def test_limpo_sai_verde(repo: Path) -> None:
    feito = _roda(repo)
    assert feito.returncode == 0, feito.stdout + feito.stderr
    assert "docs/process/x.md" not in feito.stdout


def test_ignorado_no_disco_sem_indice_nao_reprova(repo: Path) -> None:
    """O ignorado que mora só no disco é o caso certo: ele não é achado."""
    (repo / "lixo.pyc").write_bytes(b"\0")
    feito = _roda(repo)
    assert feito.returncode == 0, feito.stdout


def test_o_add_forcado_reprova_nomeando_o_arquivo_e_a_regra(repo: Path) -> None:
    _git(repo, "add", "-f", "docs/process/x.md")
    feito = _roda(repo)
    assert feito.returncode == 1, feito.stdout + feito.stderr
    assert "docs/process/x.md" in feito.stdout
    # a regra sai com a origem e a linha: `.gitignore:2:docs/process/`
    assert ".gitignore:2:docs/process/" in feito.stdout, feito.stdout


def test_o_add_forcado_ja_commitado_reprova(repo: Path) -> None:
    _git(repo, "add", "-f", "docs/process/x.md")
    _git(repo, "commit", "-q", "-m", "base")
    feito = _roda(repo)
    assert feito.returncode == 1, feito.stdout


def test_git_rm_cached_devolve_o_verde_e_deixa_o_disco(repo: Path) -> None:
    _git(repo, "add", "-f", "docs/process/x.md")
    _git(repo, "rm", "-q", "--cached", "docs/process/x.md")
    assert (repo / "docs" / "process" / "x.md").is_file()
    assert _roda(repo).returncode == 0


def test_a_isencao_dispensa_so_o_caminho_dela(repo: Path) -> None:
    modulo = _carrega()
    _git(repo, "add", "-f", "docs/process/x.md")
    assert [c for c, _ in modulo.achados(repo, {})] == ["docs/process/x.md"]
    assert modulo.achados(repo, {"docs/process/x.md": "10/10/2026, teste: isenção datada"}) == []


def test_a_isencao_nasce_vazia() -> None:
    assert _carrega().ISENTOS == {}


def test_sem_git_nao_sai_verde(tmp_path: Path) -> None:
    """Sem índice não há medida: a primeira linha diz NÃO MEDIDO, que o `portoes.sh` não conta como verde."""
    nada = tmp_path / "sem-git"
    nada.mkdir()
    feito = subprocess.run(
        [sys.executable, str(SCRIPT), "--raiz", str(nada)],
        capture_output=True, text=True, check=False,
        env={"PATH": "/usr/bin:/bin", "GIT_CEILING_DIRECTORIES": str(tmp_path)},
    )
    assert feito.stdout.startswith("NÃO MEDIDO"), feito.stdout + feito.stderr


def test_o_portao_esta_na_lista_e_no_ci() -> None:
    linha = "rapido|o-ignorado-fica-fora-do-indice|py|scripts/check_o_ignorado_fica_fora_do_indice.py|@head"
    assert linha in (RAIZ / "scripts" / "portoes.sh").read_text(encoding="utf-8")
    assert "scripts/check_o_ignorado_fica_fora_do_indice.py" in (
        RAIZ / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
