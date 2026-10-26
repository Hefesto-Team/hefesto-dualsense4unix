#!/usr/bin/env python3
"""check_o_ignorado_fica_fora_do_indice.py — nada que o `.gitignore` exclui entra no repositório.

O `.gitignore` só segura o `git add` comum: o `git add -f` passa por cima dele, e o arquivo entra no índice, desce
no merge e sai no push. Medido em 09/10/2026: um estudo de `docs/process/` (que o `.gitignore` exclui desde 15/09,
porque o repositório carrega só o produto) entrou com `git add -f` numa branch de trabalho, e nenhum portão
perguntou, porque as réguas que listam a árvore pedem `--cached --others`, nunca o versionado que casa regra de
ignorado.

A pergunta é sobre o ÍNDICE, não sobre o disco: `git ls-files --cached --ignored`. Ela responde igual num clone do
CI (que não tem ignorado no disco) e na árvore de quem trabalha. Cada achado sai com a regra que ele casa
(`git check-ignore --no-index -v`), que é o que diz a quem lê se o erro é o arquivo ou a regra.

As regras são só as dos `.gitignore` do repositório (`--exclude-per-directory=.gitignore`), nunca as de quem roda
(13/10/2026, na conferência): com `--exclude-standard` entravam o `core.excludesFile` e o `.git/info/exclude` da
máquina, e um `*.md` no ignore pessoal de alguém reprovava o README versionado e mandava tirá-lo do índice. O
contrato é o `.gitignore`; o ignore pessoal não é do repositório, e o CI não o tem.

Sem `.git` não há índice a perguntar: sai «NÃO MEDIDO» na primeira linha, que o `portoes.sh` não conta como verde.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

RAIZ_PADRAO = Path(__file__).resolve().parents[1]

ISENTOS: dict[str, str] = {}


class SemIndice(Exception):
    """A árvore não responde ao git: não há índice a medir."""


def _git(raiz: Path, *args: str) -> str:
    try:
        feito = subprocess.run(
            ["git", "-C", str(raiz), *args],
            capture_output=True, text=True, check=False,
        )
    except OSError as erro:
        raise SemIndice(str(erro)) from erro
    if feito.returncode not in (0, 1):
        raise SemIndice(feito.stderr.strip() or f"git {' '.join(args)} saiu {feito.returncode}")
    return feito.stdout


def versionados_ignorados(raiz: Path) -> list[str]:
    """Os caminhos do índice que casam uma regra de ignorado."""
    saida = _git(raiz, "ls-files", "-z", "--cached", "--ignored",
                 "--exclude-per-directory=.gitignore")
    return sorted(c for c in saida.split("\0") if c)


def regra_de(raiz: Path, caminho: str) -> str:
    """A regra que o caminho casa, `origem:linha:padrão`, perguntada sem olhar o índice."""
    saida = _git(raiz, "check-ignore", "--no-index", "-v", "--", caminho).strip()
    regra, _, _ = saida.partition("\t")
    return regra or "(a regra não respondeu)"


def achados(raiz: Path, isentos: dict[str, str] | None = None) -> list[tuple[str, str]]:
    """(caminho, regra) de cada ignorado no índice que não está isento."""
    dispensa = ISENTOS if isentos is None else isentos
    return [(c, regra_de(raiz, c)) for c in versionados_ignorados(raiz) if c not in dispensa]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="nada que o .gitignore exclui entra no repositório")
    ap.add_argument("--raiz", type=Path, default=RAIZ_PADRAO, help="a árvore a medir (padrão: esta)")
    args = ap.parse_args(argv)
    try:
        _git(args.raiz, "rev-parse", "--git-dir")
        lista = achados(args.raiz)
    except SemIndice as erro:
        print(f"NÃO MEDIDO: {args.raiz} não responde ao git ({erro}); sem índice não há o que perguntar")
        return 0
    if not lista:
        print("o índice não carrega nada que o .gitignore exclui")
        return 0
    print(f"{len(lista)} arquivo(s) no índice casam regra de ignorado (entraram com `git add -f`):")
    for caminho, regra in lista:
        print(f"  {caminho}  <- {regra}")
    print("Tire do índice com `git rm --cached <caminho>` (o arquivo fica no disco) ou, se ele é do produto, "
          "corrija a regra; isenção só datada, em ISENTOS.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
