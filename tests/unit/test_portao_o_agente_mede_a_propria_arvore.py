"""O PORTÃO DA ARMADILHA DO EDITABLE INSTALL — o agente mede a PRÓPRIA árvore."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
DESPACHANTE = RAIZ / "scripts" / "despachar-agente.sh"

LE_O_DESPACHANTE = pytest.mark.insumo_fora_do_git("scripts/despachar-agente.sh")

_IMPRIME = "import hefesto_dualsense4unix as m; print(m.__file__)"


def env_do_despachante(wt: Path) -> dict[str, str]:
    """O que o ``.envrc-voo`` DO DESPACHANTE exportaria para este worktree."""
    texto = DESPACHANTE.read_text(encoding="utf-8")
    m = re.search(r'cat > "\$WT/\.envrc-voo" <<ENV\n(.*?)\nENV\n', texto, flags=re.S)
    assert m, "não achei o bloco que escreve o .envrc-voo em despachar-agente.sh"
    variaveis: dict[str, str] = {}
    for linha in m.group(1).splitlines():
        mv = re.match(r'export ([A-Z_]+)="(.*)"$', linha.strip())
        if mv:
            variaveis[mv.group(1)] = mv.group(2).replace("${WT}", str(wt)).replace("$WT", str(wt))
    return variaveis


@pytest.fixture
def worktree(tmp_path: Path):
    """Um worktree DESTACADO da árvore de verdade, e destacado de propósito."""
    destino = tmp_path / "arvore-duble"
    r = subprocess.run(
        ["git", "worktree", "add", "--detach", str(destino), "HEAD"],
        cwd=RAIZ, capture_output=True, text=True,
    )
    assert r.returncode == 0, "não consegui criar o worktree dublê:\n" + r.stderr
    try:
        yield destino
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(destino)],
            cwd=RAIZ, capture_output=True, text=True,
        )


def _importa(wt: Path, env_extra: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PYTEST_ADDOPTS", None)
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-c", _IMPRIME], cwd=wt, capture_output=True, text=True, env=env
    )


@LE_O_DESPACHANTE
def test_com_o_envrc_do_despachante_o_import_cai_dentro_da_arvore_do_agente(
    worktree: Path,
) -> None:
    variaveis = env_do_despachante(worktree)

    r = _importa(worktree, variaveis)
    if r.returncode == 0:
        onde = Path(r.stdout.strip()).resolve()
        assert str(onde).startswith(str(worktree.resolve())), (
            f"o agente importou {onde}, que NÃO é a árvore dele ({worktree}). "
            "É a armadilha do install editable: o .pth do venv guarda um caminho "
            "ABSOLUTO para a árvore principal, e o import escapa do worktree. "
            "Confira a linha de PYTHONPATH do .envrc-voo em despachar-agente.sh; "
            f"o que ele escreveu foi: {variaveis}"
        )
    else:
        raise AssertionError(
            "o import nem rodou de dentro do worktree, com o ambiente que o "
            f"despachante escreveria ({variaveis}):\n{r.stderr}"
        )


@LE_O_DESPACHANTE
def test_o_pythonpath_aponta_para_o_src_do_proprio_worktree(worktree: Path) -> None:
    variaveis = env_do_despachante(worktree)
    assert variaveis["PYTHONPATH"] == str(worktree / "src"), (
        "o PYTHONPATH do .envrc-voo não é o src DESTE worktree: "
        + variaveis["PYTHONPATH"]
    )


def test_sem_a_variavel_o_import_escapa_da_arvore(worktree: Path) -> None:
    """O dublê tem de saber RECUSAR, ou a régua acima não prova nada."""
    r = _importa(worktree, {})
    if r.returncode != 0:
        assert "hefesto_dualsense4unix" in r.stderr
        return
    onde = Path(r.stdout.strip()).resolve()
    assert not str(onde).startswith(str(worktree.resolve())), (
        "sem PYTHONPATH o import caiu DENTRO do worktree — então esta bancada "
        "não reproduz a armadilha, e a régua de cima passaria de qualquer jeito. "
        "Confira se o venv ainda tem o editable install."
    )


@LE_O_DESPACHANTE
def test_o_despachante_ignora_o_envrc_pelo_exclude_local() -> None:
    """O `.envrc-voo` guarda o caminho ABSOLUTO da máquina: ele não pode sujar o `git status`."""
    texto = DESPACHANTE.read_text(encoding="utf-8")
    assert "info/exclude" in texto, (
        "o despachante não ignora o .envrc-voo pelo exclude LOCAL do worktree. "
        "Sem isso, ou ele suja todo `git status` de agente, ou um `git add -A` o "
        "commita com o caminho da máquina dela dentro."
    )


def test_o_envrc_nao_e_versionado_e_nao_viaja_no_merge() -> None:
    """Ele guarda o caminho ABSOLUTO da máquina; versioná-lo o levaria ao merge."""
    versionados = subprocess.run(
        ["git", "ls-files", ".envrc-voo"], cwd=RAIZ, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert versionados == "", "o .envrc-voo foi versionado: " + versionados
