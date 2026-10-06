#!/usr/bin/env python3
"""O item 3 do checklist de fim de leva, executável — FOTO-NO-GANCHO-01."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

FOTOS = "docs/usage/assets"

FOTOS_DA_VISTA = f"{FOTOS}/maximizada"

FAMILIAS_DE_FOTO = (FOTOS, FOTOS_DA_VISTA)

CODIGO_DA_TELA = (
    "src/hefesto_dualsense4unix/interface",
    "src/hefesto_dualsense4unix/app",
)

ARVORE_VAZIA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

EM_BRANCO = "em-branco"
"""Nada a cobrar: o commit não toca a tela e a história está em dia."""

EM_DIA = "em-dia"
"""O commit leva a prova junto. O caminho bom, e ele quita dívida herdada."""

CURA_EM_CURSO = "cura-em-curso"
"""Toca a tela, não leva a prova, mas as fotos estão sujas na árvore.

O mesmo perdão que `fotos_sendo_refeitas_agora` dá no portão da suíte: quem
acabou de rodar o retrato ainda não commitou as imagens. Avisa e deixa passar.
"""

BLOQUEADO = "bloqueado"
"""Toca a tela, não leva a prova, e não há foto nenhuma em curso."""

DIVIDA_HERDADA = "divida-herdada"
"""O commit não toca a tela, mas `HEAD` já está devendo foto.

É o caso da Onda 0: nove merges trouxeram interface, nenhum passou por gancho
nenhum, e o commit de fim de leva não toca `app/`. Sem isto, o gancho aprovaria
o commit que fecha a leva com a foto atrasada — que é o defeito inteiro.
"""


def _toca(caminho: str, prefixos: Iterable[str]) -> bool:
    return any(caminho == p or caminho.startswith(p + "/") for p in prefixos)


def familia_de(caminho: str) -> str | None:
    """A família de foto a que este caminho pertence — a MAIS INTERNA que o cobre."""
    cobrem = [f for f in FAMILIAS_DE_FOTO if _toca(caminho, (f,))]
    return max(cobrem, key=len) if cobrem else None


def _pathspec(familia: str) -> list[str]:
    """Os caminhos que são DESTA família e de nenhuma outra, para o `git log`."""
    return [familia] + [
        f":(exclude){outra}"
        for outra in FAMILIAS_DE_FOTO
        if outra != familia and outra.startswith(familia + "/")
    ]


def familias_sem_prova(no_indice: Iterable[str]) -> list[str]:
    """As famílias de foto que este commit NÃO carrega — o buraco de 11/09/2026."""
    com_prova = {familia_de(c) for c in no_indice} - {None}
    return [f for f in FAMILIAS_DE_FOTO if f not in com_prova]


def comando_da_familia(familia: str) -> str:
    """O gesto EXATO que refaz aquela pasta — sem ele o bloqueio não é acionável."""
    sufixo = " --vista dela" if familia == FOTOS_DA_VISTA else ""
    return (
        f"    src/hefesto_dualsense4unix/interface/olhar.py "
        f"--todas --publicado --doc{sufixo}\n    git add {familia}"
    )


def julgar(
    no_indice: Iterable[str],
    fotos_sujas: bool,
    historia_em_dia: bool | None,
) -> tuple[str, list[str]]:
    """O veredito, sem git nenhum: só caminhos e dois estados."""
    caminhos = list(no_indice)
    de_tela = sorted(c for c in caminhos if _toca(c, CODIGO_DA_TELA))

    if not familias_sem_prova(caminhos):
        return EM_DIA, de_tela
    if de_tela:
        return (CURA_EM_CURSO if fotos_sujas else BLOQUEADO), de_tela
    if historia_em_dia is False and not fotos_sujas:
        return DIVIDA_HERDADA, []
    return EM_BRANCO, []


def _git(raiz: Path, *args: str) -> str:
    saida = subprocess.run(
        ["git", *args], cwd=str(raiz), capture_output=True, text=True
    )
    if saida.returncode != 0:
        return ""
    return saida.stdout.strip()


def na_arvore_principal(raiz: Path) -> bool:
    """Esta é a árvore principal, ou uma worktree de trabalho?"""
    proprio = _git(raiz, "rev-parse", "--absolute-git-dir")
    comum = _git(raiz, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not proprio or not comum:
        return True
    return Path(proprio).resolve() == Path(comum).resolve()


def caminhos_no_indice(raiz: Path) -> list[str]:
    """O que este commit vai carregar. Sem `HEAD`, compara com a árvore vazia."""
    contra = "HEAD" if _git(raiz, "rev-parse", "--verify", "HEAD") else ARVORE_VAZIA
    saida = _git(raiz, "diff", "--cached", "--name-only", contra)
    return [linha for linha in saida.splitlines() if linha]


def fotos_sujas(raiz: Path) -> bool:
    """Alguma imagem está modificada na árvore? `--porcelain` responde por conteúdo."""
    return bool(_git(raiz, "status", "--porcelain", "--", FOTOS))


def _uma_familia_em_dia(raiz: Path, familia: str) -> bool | None:
    """A topologia de UMA família: a foto dela veio depois da mexida na tela?"""
    das_fotos = _git(raiz, "log", "-1", "--format=%H", "--", *_pathspec(familia))
    do_codigo = _git(raiz, "log", "-1", "--format=%H", "--", *CODIGO_DA_TELA)
    if not das_fotos or not do_codigo:
        return None
    if das_fotos == do_codigo:
        return True
    pergunta = subprocess.run(
        ["git", "merge-base", "--is-ancestor", do_codigo, das_fotos],
        cwd=str(raiz),
        capture_output=True,
    )
    return pergunta.returncode == 0


def historia_em_dia(raiz: Path) -> bool | None:
    """`HEAD` já deve foto? A MESMA topologia do portão da suíte, POR FAMÍLIA."""
    vereditos = [_uma_familia_em_dia(raiz, f) for f in FAMILIAS_DE_FOTO]
    if any(v is False for v in vereditos):
        return False
    if all(v is None for v in vereditos):
        return None
    return True


_CURA = (
    "  Cure rodando o retrato — uma execução por família, nenhum clique:\n"
    + "\n".join(comando_da_familia(f) for f in FAMILIAS_DE_FOTO)
    + "\n"
    "\n  Se as imagens saírem iguais, o recibo `PROVA-DA-FOTO.txt` muda "
    "sozinho\n"
    "  e já serve de prova; se saírem diferentes, OLHE-AS antes de commitar —\n"
    "  mudança de desenho é palavra dela (PROVA-DE-TELA-01).\n"
    "\n  Este gancho não tem chave própria de propósito. `git commit "
    "--no-verify`\n"
    "  passa, e aí quem cobra é `test_as_fotos_acompanham_a_versao.py` na "
    "suíte."
)


def main(argv: list[str] | None = None) -> int:
    del argv
    raiz_texto = _git(Path.cwd(), "rev-parse", "--show-toplevel")
    if not raiz_texto:
        return 0
    raiz = Path(raiz_texto)

    if not na_arvore_principal(raiz):
        return 0

    veredito, de_tela = julgar(
        caminhos_no_indice(raiz), fotos_sujas(raiz), historia_em_dia(raiz)
    )

    if veredito in (EM_BRANCO, EM_DIA):
        return 0

    if veredito == CURA_EM_CURSO:
        print(
            "portão das fotos: este commit mexe na tela e não leva foto — mas "
            f"há imagem modificada em `{FOTOS}`.\n"
            "  Passando: a cura está em curso. Mas ela está FORA deste "
            f"commit —\n    git add {FOTOS}\n"
            "  antes de commitar, ou a foto fica para trás e a suíte cobra.",
            file=sys.stderr,
        )
        return 0

    if veredito == DIVIDA_HERDADA:
        atrasadas = [
            f for f in FAMILIAS_DE_FOTO if _uma_familia_em_dia(raiz, f) is False
        ]
        das_fotos = _git(
            raiz, "log", "-1", "--format=%h", "--", *_pathspec(atrasadas[0])
        )
        do_codigo = _git(raiz, "log", "-1", "--format=%h", "--", *CODIGO_DA_TELA)
        print(
            "pre-commit: BLOQUEADO — a tela mudou em "
            f"{do_codigo} e as fotos de `{'`, `'.join(atrasadas)}` "
            f"são de {das_fotos}, que veio ANTES.\n"
            "  Este commit não tem culpa, mas a dívida é de agora: os merges "
            "de leva\n"
            "  não passam por gancho nenhum, e este é o primeiro commit "
            "depois deles.\n",
            file=sys.stderr,
        )
        print(_CURA, file=sys.stderr)
        return 1

    faltando = familias_sem_prova(caminhos_no_indice(raiz))
    print(
        "pre-commit: BLOQUEADO — este commit mexe no código da tela e não leva "
        f"a foto de `{'`, `'.join(faltando)}`.\n",
        file=sys.stderr,
    )
    for caminho in de_tela[:10]:
        print(f"    {caminho}", file=sys.stderr)
    if len(de_tela) > 10:
        print(f"    ... e mais {len(de_tela) - 10}", file=sys.stderr)
    print("", file=sys.stderr)
    print(_CURA, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
