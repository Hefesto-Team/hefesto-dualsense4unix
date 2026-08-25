"""O PORTÃO DA ARMADILHA DO EDITABLE INSTALL — o agente mede a PRÓPRIA árvore.

É a Falha 2 escondida DENTRO do conserto da Falha 2, e por isso ela é o defeito
mais traiçoeiro desta leva: o worktree isola a árvore, e mesmo assim o
interpretador continua importando o código do vizinho.

MEDIDO EM 24/08/2026, e conferido por segunda mão. O install editable grava um
caminho **absoluto** em
``.venv/lib/python3.12/site-packages/_editable_impl_hefesto_dualsense4unix.pth``::

    /mnt/Apate/Desenvolvimento/hefesto-dualsense4unix/src

Rodado de dentro de um worktree::

    sem PYTHONPATH   -> /mnt/Apate/.../hefesto-dualsense4unix/src/...   a do VIZINHO
    com PYTHONPATH   -> <worktree>/src/hefesto_dualsense4unix/...       a PRÓPRIA

Um agente que não saiba disso **mede o código de outra pessoa e jura que mediu o
seu** -- e o relatório dele fica convincente, porque os números existem. É o
padrão "o instrumento mente mais que o produto", desta vez com o instrumento
sendo o próprio interpretador.

POR QUE É PORTÃO E NÃO NOTA NO DOCUMENTO: uma nota em prosa depende de alguém
lê-la antes de rodar o primeiro comando. Este portão pega a variável ONDE ELA
NASCE -- no ``.envrc-voo`` que o despachante escreve -- e por isso não há
ninguém para esquecer.

A MORDIDA: arranque a linha de ``PYTHONPATH`` do ``cat > "$WT/.envrc-voo"`` em
``scripts/despachar-agente.sh``. Este teste reprova **nomeando o caminho da
árvore que foi importada**, não com um "falhou". Devolva e ele volta ao verde.

O DUBLÊ SABE RECUSAR (armadilha A2): ``test_sem_a_variavel_o_import_escapa_da
_arvore`` exercita o lado SEM a variável e exige que o import NÃO caia dentro do
worktree. Régua que só sabe passar não é régua -- e no caso desta medição a
casa já pagou o preço contrário: as duas primeiras provas do ``flock``, em
24/08, foram falsos NEGATIVOS por dublê mal feito.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
DESPACHANTE = RAIZ / "scripts" / "despachar-agente.sh"

_IMPRIME = "import hefesto_dualsense4unix as m; print(m.__file__)"


def env_do_despachante(wt: Path) -> dict[str, str]:
    """O que o ``.envrc-voo`` DO DESPACHANTE exportaria para este worktree.

    Lê o bloco ``cat > "$WT/.envrc-voo" <<ENV ... ENV`` do script em vez de
    repetir o conteúdo aqui. É a diferença entre um teste que mede o produto e
    um que mede a própria cópia: se a linha sumir do despachante, ela some daqui
    também, e o teste reprova. Repetir o valor no teste seria uma segunda lista.
    """
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
    """Um worktree DESTACADO da árvore de verdade, e destacado de propósito.

    ``--detach`` não cria branch: não há nome para limpar depois, e nada colide
    com as branches ``voo/*`` dos agentes que estiverem em voo agora.
    """
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


# ---------------------------------------------------------------------------
# A régua
# ---------------------------------------------------------------------------


def test_com_o_envrc_do_despachante_o_import_cai_dentro_da_arvore_do_agente(
    worktree: Path,
) -> None:
    variaveis = env_do_despachante(worktree)

    # O IMPORT VEM PRIMEIRO, e a ordem é o produto desta régua: se ela conferisse
    # a variável antes, a reprovação diria "faltou PYTHONPATH" -- verdadeiro e
    # inútil. Reprovando pelo import, ela diz QUAL ÁRVORE foi medida, que é a
    # frase que faz alguém entender o que estava prestes a acontecer.
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


def test_o_pythonpath_aponta_para_o_src_do_proprio_worktree(worktree: Path) -> None:
    variaveis = env_do_despachante(worktree)
    assert variaveis["PYTHONPATH"] == str(worktree / "src"), (
        "o PYTHONPATH do .envrc-voo não é o src DESTE worktree: "
        + variaveis["PYTHONPATH"]
    )


def test_sem_a_variavel_o_import_escapa_da_arvore(worktree: Path) -> None:
    """O dublê tem de saber RECUSAR, ou a régua acima não prova nada.

    Duas saídas são aceitas, e as duas provam a mesma coisa -- que sem a
    variável o worktree NÃO se mede:
      - o import cai fora do worktree (é o caso desta bancada, com o `.pth` do
        editable apontando para a árvore principal);
      - o import falha (é o caso de um ambiente sem editable install: o layout
        é `src/`, e sem PYTHONPATH não há pacote nenhum a importar).
    """
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


def test_o_envrc_nao_e_versionado_e_nao_viaja_no_merge() -> None:
    """Ele guarda o caminho ABSOLUTO da máquina; versioná-lo o levaria ao merge."""
    texto = DESPACHANTE.read_text(encoding="utf-8")
    assert "info/exclude" in texto, (
        "o despachante não ignora o .envrc-voo pelo exclude LOCAL do worktree. "
        "Sem isso, ou ele suja todo `git status` de agente, ou um `git add -A` o "
        "commita com o caminho da máquina dela dentro."
    )
    versionados = subprocess.run(
        ["git", "ls-files", ".envrc-voo"], cwd=RAIZ, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert versionados == "", "o .envrc-voo foi versionado: " + versionados
