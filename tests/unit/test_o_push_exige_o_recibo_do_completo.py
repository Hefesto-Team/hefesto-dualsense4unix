from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PORTOES = """#!/bin/bash
[ "${1:-}" = --interpretador ] && exit 0
echo completo >> "$HEFESTO_REGISTRO"
c="$(mktemp)"
"$HEFESTO_PY" scripts/recibo_da_medida.py abrir portoes-completo --corrida "$c" --raiz .
"$HEFESTO_PY" -m mypy --cache-dir=/dev/null src/m.py
rc=$?
"$HEFESTO_PY" scripts/recibo_da_medida.py fechar portoes-completo "$rc" --corrida "$c" --raiz .
exit "$rc"
"""


def _ambiente(casa: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "AUTORIA_"))}
    falso = casa / "bin"
    falso.mkdir(exist_ok=True)
    (falso / "shellcheck").write_text("#!/bin/sh\n")
    (falso / "shellcheck").chmod(0o755)
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", HOME=str(casa),
               AUTORIA_VEDADOS="1 termoquenaoexiste\n", HEFESTO_PY=sys.executable,
               HEFESTO_REGISTRO=str(casa / "registro"), PATH=f"{falso}:{env['PATH']}")
    return env


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, env=_ambiente(repo.parent),
                          capture_output=True, text=True)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "mesa"
    (repo / "scripts").mkdir(parents=True)
    (repo / "src").mkdir()
    ganchos = tmp_path / "ganchos"
    ganchos.mkdir()
    shutil.copy2(RAIZ / "scripts" / "hooks" / "pre-push", ganchos / "pre-push")
    for nome in ("check_autoria.py", "recibo_da_medida.py"):
        shutil.copy2(RAIZ / "scripts" / nome, repo / "scripts" / nome)
    (repo / "scripts" / "portoes.sh").write_text(PORTOES)
    (repo / ".mailmap").write_text("Pessoa Um <um@casa.test>\n")
    (repo / ".gitignore").write_text("__pycache__/\n")
    (repo / "src" / "m.py").write_text('x: int = "texto"\n')
    nu = tmp_path / "nu.git"
    for args in (["init", "-q", "-b", "dev"], ["config", "user.name", "Pessoa Um"],
                 ["config", "user.email", "um@casa.test"],
                 ["config", "core.hooksPath", str(ganchos)],
                 ["init", "-q", "--bare", str(nu)], ["remote", "add", "origin", str(nu)],
                 ["add", "."], ["commit", "-q", "-m", "chore: base"]):
        assert git(repo, *args).returncode == 0
    return repo


def registro(repo: Path) -> str:
    alvo = repo.parent / "registro"
    return alvo.read_text() if alvo.exists() else ""


def test_sem_recibo_o_push_roda_o_completo_e_o_vermelho_barra(repo: Path) -> None:
    p = git(repo, "push", "origin", "dev:refs/heads/dev")
    assert p.returncode != 0, p.stdout + p.stderr
    assert registro(repo) == "completo\n"
    assert "o completo não deixou recibo" in p.stdout + p.stderr
    assert git(repo, "ls-remote", "origin").stdout == ""


def test_sem_recibo_o_completo_verde_deixa_o_recibo_e_o_push_sai(repo: Path) -> None:
    (repo / "src" / "m.py").write_text("x: int = 1\n")
    assert git(repo, "commit", "-qam", "fix: o tipo").returncode == 0
    p = git(repo, "push", "origin", "dev:refs/heads/dev")
    assert p.returncode == 0, p.stdout + p.stderr
    assert registro(repo) == "completo\n"


def test_com_o_recibo_da_mesma_arvore_sai_sem_rodar(repo: Path) -> None:
    arvore = git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
    pasta = repo / ".git" / "hefesto-recibos"
    pasta.mkdir()
    (pasta / f"{arvore}.portoes-completo").write_text("medida: portoes-completo\n")
    p = git(repo, "push", "origin", "dev:refs/heads/dev")
    assert p.returncode == 0, p.stdout + p.stderr
    assert registro(repo) == ""


def test_outro_ramo_nao_pede_recibo(repo: Path) -> None:
    p = git(repo, "push", "origin", "dev:refs/heads/fecho/x")
    assert p.returncode == 0, p.stdout + p.stderr
    assert registro(repo) == ""
