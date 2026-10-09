#!/usr/bin/env python3
"""check_comentario_cortado.py — comentário que termina no meio da frase, contado e travado.

O DEFEITO (08/10/2026): o commit `8002c142c` (02/10, «os comentários narrativos saem e as
docstrings ficam com a primeira linha») cortou blocos de comentário por linha e deixou só a
primeira, que muitas vezes acaba em «…a», «…que», «…e» e é seguida de código. Quem lê
`#: \\`TIQUE_MS\\` do produto (ver \\`_teto_da_fase_s\\`). Bater o teto não é pulo: a` não sabe o que
vem depois, e a casa não tinha régua para isso.

A RÉGUA CONTA o bloco de comentário que acaba em conectivo (a, o, de, que, e, para, com, em…)
ou numa citação `arquivo:linha` sem pontuação, seguido de linha que não é comentário.

A SEGUNDA PERGUNTA (O-COMENTARIO-COM-DOIS-PONTOS-SO-VALE-EM-CIMA-DE-ATRIBUICAO-01): o `#:` é o
comentário de documentação de atributo e só significa algo colado numa atribuição. O bloco com
`#:` cuja linha seguinte não começa uma atribuição (`NOME = 1`, `FORTE, LEVE = 1, 0`,
`nome: int = 1`) é resto de corte ou marca errada: acima de `def`, dentro de dicionário literal,
seguido de linha em branco ou no fim do arquivo.

O PISO É POR ARQUIVO E NÃO GUARDA NÚMERO (A-DIVIDA-DA-BASE-DESCE-POR-ARQUIVO-E-POR-QUEM-TOCA-01):
para cada arquivo que mudou desde o `merge-base` com `dev` (no CI, `origin/dev`), as duas
perguntas contam no disco e na base, e o arquivo que SOBE reprova, pelo nome. Descer não pede
nada: o ganho fica travado porque a base anda com o `dev`. Um número global só descia pelas mãos
de UMA mudança por vez, e duas sprints que curavam em paralelo brigavam pela mesma linha na
costura. Sem base alcançável a régua FALHA dizendo «sem base», nunca passa calada.

QUEM TOCA UM ARQUIVO CURA OS DELE (`--de <arquivo...>` lista): termine a frase com o que
`--original` diz, em até duas linhas, ou apague o fragmento quando o código já diz; nunca devolva
o parágrafo inteiro que o corte tirou.

Lê só o que o git versiona em `src/`, `tests/` e `scripts/` (`*.py`): a contagem é a mesma em
toda árvore. Os comentários são os TOKENS do Python, então um `#` dentro de string não conta.

    scripts/check_comentario_cortado.py              compara cada arquivo mudado com a base
    scripts/check_comentario_cortado.py --lista      um candidato por linha: arquivo:linha texto
                                                     (o `#:` solto vem marcado `[#:]`)
    scripts/check_comentario_cortado.py --de A B     os candidatos só dos arquivos dados
    scripts/check_comentario_cortado.py --original   o candidato com o texto de `8002c142c~1`
"""

from __future__ import annotations

import argparse
import ast
import functools
import io
import re
import subprocess
import sys
import tokenize
from collections.abc import Callable
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

#: de onde se mede «a mudança de agora», na ordem: o `dev` local e, no CI, o `origin/dev`
REFS_DA_BASE = ("dev", "origin/dev")

COMMIT_DO_CORTE = "8002c142c"
PASTAS = ("src", "tests", "scripts")

# as palavras com que uma frase NÃO acaba: artigos, preposições, conjunções e pronomes relativos
CONECTIVOS = frozenset({
    "a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "da", "do", "das", "dos", "em", "no",
    "na", "nos", "nas", "ao", "aos", "à", "às", "por", "pelo", "pela", "pelos", "pelas", "para",
    "pra", "com", "sem", "sob", "sobre", "entre", "até", "que", "e", "ou", "mas", "se", "como",
    "quando", "onde", "porque", "pois", "nem", "seu", "sua", "seus", "suas", "este", "esta",
    "esse", "essa", "isto", "isso", "cujo", "cuja", "ser", "é", "foi", "são",
})

_CITACAO_NO_FIM = re.compile(r"`[\w./-]+\.(?:py|sh|md|csv|html|js|json|yml):\d+`$")
_ULTIMA_PALAVRA = re.compile(r"([^\W\d_]+)$")


def termina_no_meio(ultima_linha: str) -> bool:
    """A última linha do bloco acaba onde uma frase não acaba?"""
    texto = ultima_linha.strip().lstrip("#").lstrip(":").strip()
    if not texto:
        return False
    if _CITACAO_NO_FIM.search(texto):
        return True
    achou = _ULTIMA_PALAVRA.search(texto)
    return achou is not None and achou.group(1).lower() in CONECTIVOS


@functools.lru_cache(maxsize=4)
def _comentarios_soltos(texto: str) -> dict[int, str]:
    """`{linha: comentário}` de cada linha que só tem comentário (os tokens, não o texto cru).

    Guardada para o mesmo texto: as duas perguntas leem os mesmos tokens. Não altere o dicionário.
    """
    soltos: dict[int, str] = {}
    try:
        for tok in tokenize.generate_tokens(io.StringIO(texto).readline):
            if tok.type == tokenize.COMMENT and not tok.line[: tok.start[1]].strip():
                soltos[tok.start[0]] = tok.string
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass  # o que o tokenizador leu até a quebra vale; arquivo quebrado não some da conta
    return soltos


def cortados_do_texto(texto: str) -> list[tuple[int, str]]:
    """`(linha, texto)` do fim de cada bloco de comentário cortado, em ordem.

    Bloco: linhas seguidas que só têm comentário. Cortado: a última acaba no meio e a
    linha seguinte existe e não é comentário (fim de arquivo não conta).
    """
    soltos = _comentarios_soltos(texto)
    linhas = texto.splitlines()
    achados: list[tuple[int, str]] = []
    for n in sorted(soltos):
        if n + 1 in soltos or n >= len(linhas):
            continue
        if termina_no_meio(soltos[n]):
            achados.append((n, soltos[n]))
    return achados


_ATRIBUICAO_CRUA = re.compile(r"^\s*[A-Za-z_][\w.]*(?:\s*,\s*[A-Za-z_][\w.]*)*\s*(?::[^=]+)?=(?!=)")


def _linhas_de_atribuicao(texto: str) -> set[int]:
    """As linhas em que começa uma atribuição: `=`, a anotada e o `type X = ...`.

    Arquivo que o `ast` não lê cai na forma crua da linha, para não sumir da conta.
    """
    try:
        arvore = ast.parse(texto)
    except (SyntaxError, ValueError):
        return {n for n, linha in enumerate(texto.splitlines(), 1) if _ATRIBUICAO_CRUA.match(linha)}
    tipos: tuple[type[ast.stmt], ...] = (ast.Assign, ast.AnnAssign)
    if hasattr(ast, "TypeAlias"):  # o `type X = ...` nasceu no 3.12
        tipos += (ast.TypeAlias,)
    return {n.lineno for n in ast.walk(arvore) if isinstance(n, tipos)}


def dois_pontos_soltos_do_texto(texto: str) -> list[tuple[int, str]]:
    """`(linha, texto)` do início de cada bloco com `#:` que não está colado numa atribuição.

    Bloco: linhas seguidas que só têm comentário. Colado: a linha logo depois da última do bloco
    começa uma atribuição; linha em branco, `def`, chave de dicionário e fim de arquivo não colam.
    """
    soltos = _comentarios_soltos(texto)
    atribuicoes = _linhas_de_atribuicao(texto)
    achados: list[tuple[int, str]] = []
    bloco: list[int] = []
    for n in [*sorted(soltos), -1]:
        if bloco and n == bloco[-1] + 1:
            bloco.append(n)
            continue
        tem_dois_pontos = bool(bloco) and any(soltos[i].startswith("#:") for i in bloco)
        if tem_dois_pontos and bloco[-1] + 1 not in atribuicoes:
            achados.append((bloco[0], soltos[bloco[0]]))
        bloco = [n]
    return achados


def arquivos_versionados(raiz: Path = RAIZ) -> list[str]:
    feito = subprocess.run(
        ["git", "ls-files", "-z", "--", *PASTAS],
        cwd=raiz, capture_output=True, text=True, check=False,
    )
    if feito.returncode != 0:
        raise RuntimeError(f"git ls-files falhou: {feito.stderr.strip()}")
    return sorted(a for a in feito.stdout.split("\0") if a.endswith(".py"))


def varrer(raiz: Path = RAIZ, pergunta: Callable[[str], list[tuple[int, str]]] = cortados_do_texto,
           ) -> list[tuple[str, int, str]]:
    """`(arquivo, linha, texto)` de cada achado da `pergunta` nos arquivos versionados."""
    achados: list[tuple[str, int, str]] = []
    for arquivo in arquivos_versionados(raiz):
        caminho = raiz / arquivo
        if not caminho.is_file():
            continue
        texto = caminho.read_text(encoding="utf-8", errors="replace")
        achados += [(arquivo, n, t) for n, t in pergunta(texto)]
    return achados


def varrer_dois_pontos(raiz: Path = RAIZ) -> list[tuple[str, int, str]]:
    """`(arquivo, linha, texto)` de todo bloco `#:` que não está colado numa atribuição."""
    return varrer(raiz, dois_pontos_soltos_do_texto)


PERGUNTAS: dict[str, Callable[[str], list[tuple[int, str]]]] = {
    "cortado": cortados_do_texto,
    "#: fora de atribuição": dois_pontos_soltos_do_texto,
}


def _git(raiz: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=raiz, capture_output=True, text=True, check=False)


def base_de_comparacao(raiz: Path = RAIZ) -> str | None:
    """O `merge-base` do `HEAD` com o primeiro de `REFS_DA_BASE` que existe, ou `None`."""
    for ref in REFS_DA_BASE:
        feito = _git(raiz, "merge-base", ref, "HEAD")
        if feito.returncode == 0 and feito.stdout.strip():
            return feito.stdout.strip()
    return None


def arquivos_mudados(raiz: Path, base: str) -> dict[str, str | None]:
    """`{caminho de agora: caminho na base}` dos `*.py` mudados desde `base` (`None`: nasceu)."""
    feito = _git(raiz, "diff", "--name-status", "-M", "-z", base, "--", *PASTAS)
    if feito.returncode != 0:
        raise RuntimeError(f"git diff falhou: {feito.stderr.strip()}")
    campos = feito.stdout.split("\0")
    mudados: dict[str, str | None] = {}
    i = 0
    while i < len(campos) and campos[i]:
        estado = campos[i]
        if estado[0] in "RC":
            antigo, novo, i = campos[i + 1], campos[i + 2], i + 3
        else:
            antigo, novo, i = campos[i + 1], campos[i + 1], i + 2
        if estado[0] == "D" or not novo.endswith(".py"):
            continue
        mudados[novo] = None if estado[0] == "A" else antigo
    return mudados


def subidas(raiz: Path, base: str) -> list[tuple[str, str, int, int]]:
    """`(arquivo, pergunta, na base, agora)` de cada arquivo em que uma pergunta SOBE."""
    achados: list[tuple[str, str, int, int]] = []
    for arquivo, antigo in sorted(arquivos_mudados(raiz, base).items()):
        caminho = raiz / arquivo
        if not caminho.is_file():
            continue
        agora = caminho.read_text(encoding="utf-8", errors="replace")
        antes = ""
        if antigo is not None:
            feito = _git(raiz, "show", f"{base}:{antigo}")
            antes = feito.stdout if feito.returncode == 0 else ""
        for nome, pergunta in PERGUNTAS.items():
            n_antes, n_agora = len(pergunta(antes)), len(pergunta(agora))
            if n_agora > n_antes:
                achados.append((arquivo, nome, n_antes, n_agora))
    return achados


def verificar(raiz: Path = RAIZ) -> tuple[int, list[str]]:
    """`(rc, linhas)`: rc 1 se algum arquivo mudado subiu, ou se não há base."""
    base = base_de_comparacao(raiz)
    if base is None:
        return 1, [f"FALHA: sem base: nem {' nem '.join(REFS_DA_BASE)} alcançável deste HEAD; "
                   "sem base a régua não mede (no CI, `fetch-depth: 0`)."]
    subiu = subidas(raiz, base)
    linhas = [f"{len(arquivos_mudados(raiz, base))} arquivo(s) .py mudado(s) desde {base[:9]}; "
              f"{len(subiu)} com mais candidato(s) que na base."]
    for arquivo, nome, antes, agora in subiu:
        linhas.append(f"FALHA: {arquivo}: {nome} {antes} -> {agora}. Termine a frase ou apague "
                      f"o fragmento (`--de {arquivo}` lista, `--original` traz o texto de antes).")
    return (1 if subiu else 0), linhas


def candidatos_de(arquivos: list[str], raiz: Path = RAIZ) -> list[str]:
    """Os candidatos das duas perguntas nos arquivos dados, um por linha."""
    linhas: list[str] = []
    for arquivo in arquivos:
        caminho = raiz / arquivo
        if not caminho.is_file() or not arquivo.endswith(".py"):
            continue
        texto = caminho.read_text(encoding="utf-8", errors="replace")
        linhas += [f"{arquivo}:{n} {t.strip()}" for n, t in cortados_do_texto(texto)]
        linhas += [f"[#:] {arquivo}:{n} {t.strip()}" for n, t in dois_pontos_soltos_do_texto(texto)]
    return linhas


def texto_de_antes_do_corte(arquivo: str, ultima_linha: str, raiz: Path = RAIZ) -> list[str]:
    """O bloco de comentário que começava na linha `ultima_linha` em `8002c142c~1` (ou [])."""
    feito = subprocess.run(
        ["git", "show", f"{COMMIT_DO_CORTE}~1:{arquivo}"],
        cwd=raiz, capture_output=True, text=True, check=False,
    )
    if feito.returncode != 0:
        return []
    velhas = feito.stdout.splitlines()
    alvo = ultima_linha.strip()
    for i, linha in enumerate(velhas):
        if linha.strip() == alvo:
            bloco = [linha]
            for seguinte in velhas[i + 1:]:
                if not seguinte.strip().startswith("#"):
                    break
                bloco.append(seguinte)
            return bloco
    return []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--lista", action="store_true", help="um candidato por linha")
    ap.add_argument("--original", action="store_true", help="com o texto de antes do corte")
    ap.add_argument("--de", nargs="+", metavar="ARQUIVO", help="os candidatos destes arquivos")
    args = ap.parse_args(argv)

    if args.de:
        print("\n".join(candidatos_de(args.de)) or "nenhum candidato.")
        return 0
    if args.lista or args.original:
        achados, soltos = varrer(), varrer_dois_pontos()
        for arquivo, n, texto in achados:
            print(f"{arquivo}:{n} {texto.strip()}")
            if args.original:
                for linha in texto_de_antes_do_corte(arquivo, texto):
                    print(f"    | {linha}")
        for arquivo, n, texto in soltos:
            print(f"[#:] {arquivo}:{n} {texto.strip()}")
        return 0
    rc, linhas = verificar()
    for linha in linhas:
        print(linha, file=sys.stderr if linha.startswith("FALHA") else sys.stdout)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
