from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "subir-mudanca-pequena.sh"
REGISTRA = (
    '#!/bin/bash\necho "$(basename "$0") $*" >> "$HEFESTO_REGISTRO"\n'
    'exit "${RC_DO_RAPIDO:-0}"\n'
)


def _ambiente(casa: Path, **extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", HOME=str(casa),
               HEFESTO_REGISTRO=str(casa / "registro"), **extra)
    return env


def git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=repo, env=_ambiente(repo.parent),
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "mesa"
    (repo / "scripts").mkdir(parents=True)
    git(repo, "init", "-q", "-b", "dev")
    git(repo, "config", "user.name", "Pessoa Um")
    git(repo, "config", "user.email", "um@casa.test")
    git(repo, "config", "commit.gpgsign", "false")
    for nome in ("install.sh", "scripts/portoes.sh"):
        (repo / nome).write_text(REGISTRA)
        (repo / nome).chmod(0o755)
    for i in range(7):
        (repo / f"a{i}.txt").write_text("um\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "chore: base")
    return repo


def subir(repo: Path, *args: str, **extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", str(SCRIPT), *args], cwd=repo,
                          env=_ambiente(repo.parent, **extra), capture_output=True, text=True)


def registro(repo: Path) -> list[str]:
    alvo = repo.parent / "registro"
    return alvo.read_text().splitlines() if alvo.exists() else []


def test_dois_arquivos_sobem_e_o_terceiro_sujo_fica_fora(repo: Path) -> None:
    for i in range(3):
        (repo / f"a{i}.txt").write_text("dois\n")
    p = subir(repo, "a0.txt", "a1.txt", "-m", "fix: dois", "--origem", "D-X")
    assert p.returncode == 0, p.stdout + p.stderr
    assert git(repo, "show", "--name-only", "--format=", "HEAD").split() == ["a0.txt", "a1.txt"]
    assert "Origem: D-X" in git(repo, "log", "-1", "--format=%B")
    assert git(repo, "status", "--porcelain") == "M a2.txt"
    assert registro(repo) == ["portoes.sh --rapido", "install.sh --yes --dev"]
    assert "parede: commit" in p.stdout
    assert list((repo / ".git" / "hefesto-pista-curta").glob("*.log"))


@pytest.mark.parametrize("caso", ["seis-arquivos", "151-linhas", "install"])
def test_o_grande_e_o_de_risco_recusam_antes_do_commit(repo: Path, caso: str) -> None:
    antes = git(repo, "rev-parse", "HEAD")
    if caso == "seis-arquivos":
        nomes = [f"a{i}.txt" for i in range(6)]
        for n in nomes:
            (repo / n).write_text("dois\n")
    elif caso == "151-linhas":
        nomes = ["a0.txt"]
        (repo / "a0.txt").write_text("x\n" * 150)
    else:
        nomes = ["install.sh"]
        (repo / "install.sh").write_text(REGISTRA + "\n")
    p = subir(repo, *nomes)
    assert p.returncode == 2
    assert "isto é do fecho" in p.stderr
    assert git(repo, "rev-parse", "HEAD") == antes
    assert registro(repo) == []


def test_rapido_vermelho_nao_chama_o_install(repo: Path) -> None:
    (repo / "a0.txt").write_text("dois\n")
    p = subir(repo, "a0.txt", RC_DO_RAPIDO="1")
    assert p.returncode == 1
    assert registro(repo) == ["portoes.sh --rapido"]
    assert "sem install" in p.stdout


def test_integracao_a_frente_do_dev_recusa(repo: Path) -> None:
    integra = repo.parent / "integra"
    git(repo, "worktree", "add", "-q", "-b", "integra/x", str(integra), "dev")
    (integra / "b.txt").write_text("b\n")
    git(integra, "add", "b.txt")
    git(integra, "commit", "-q", "-m", "chore: na integração")
    antes = git(repo, "rev-parse", "HEAD")
    (repo / "a0.txt").write_text("dois\n")
    p = subir(repo, "a0.txt")
    assert p.returncode == 2
    assert "fora do dev" in p.stderr
    assert git(repo, "rev-parse", "HEAD") == antes


def test_integracao_igual_ao_dev_anda_junto(repo: Path) -> None:
    integra = repo.parent / "integra"
    git(repo, "worktree", "add", "-q", "-b", "integra/x", str(integra), "dev")
    (repo / "a0.txt").write_text("dois\n")
    assert subir(repo, "a0.txt").returncode == 0
    assert git(integra, "rev-parse", "HEAD") == git(repo, "rev-parse", "HEAD")


def test_o_commit_de_agente_sobe_por_cherry_pick(repo: Path) -> None:
    git(repo, "switch", "-q", "-c", "voo/x")
    (repo / "a0.txt").write_text("dois\n")
    git(repo, "commit", "-q", "-am", "fix: do voo")
    sha = git(repo, "rev-parse", "HEAD")
    git(repo, "switch", "-q", "dev")
    assert subir(repo, "--de", sha).returncode == 0
    assert git(repo, "log", "-1", "--format=%s") == "fix: do voo"
    assert git(repo, "rev-parse", "dev") == git(repo, "rev-parse", "HEAD")
    assert registro(repo)[-1] == "install.sh --yes --dev"
