#!/usr/bin/env python3
"""USAR um símbolo é uma coisa; CITÁ-LO na prosa é outra. Aqui mora a diferença.

POR QUE ISTO EXISTE, E POR QUE É UM MÓDULO E NÃO UMA FUNÇÃO SOLTA
------------------------------------------------------------------
Em 06/09/2026 dois portões diferentes anunciaram, no mesmo dia, que uma dívida
tinha fechado — porque o nome de uma função da janela antiga *apareceu* na tela
nova. O que apareceu era **prosa**: uma docstring que EXPLICAVA o que a janela
antiga fazia::

    A LINHA **L315** DO CSV (…) A janela antiga tinha
    (`daemon_actions.on_daemon_migrate_to_systemd`).

Os dois portões:

* ``scripts/check_paridade_gtk_html.py`` — a regra ``divida-fechada``, com
  ``alvo in self.texto(p)``;
* ``scripts/check_donos_de_comportamento.py`` — a regra ``SO-GTK`` que já
  migrou, com ``simbolo in caminho.read_text()``.

E não era a primeira vez: em **03/09/2026** o mesmo símbolo, pelo mesmo caminho,
promoveu as linhas 315 e 343 do CSV da paridade a ``DIFERENTE``, e as duas
tiveram de ser devolvidas no mesmo dia. O ``porque`` de cada uma registra o
tombo.

**A regra desta casa é que a cura cobre TODOS os chamadores** — cobrir um deixa
a próxima pessoa remedindo o mesmo defeito, e foi o que aconteceu duas vezes
num dia em 05/09. Por isso a separação virou dono único, e os dois portões
perguntam a ele.

O QUE É PROSA, E O QUE NÃO É
-----------------------------
Prosa é **a docstring e o comentário**, e mais nada. Três tentativas erradas,
com o custo medido, para ninguém as repetir:

1. **apagar toda ``ast.Constant`` de texto** → 165 falsos. Cadeia usada como
   VALOR é código: ``"restaurar-de-fabrica"`` é o nome de um gesto e
   ``data-campo="fragil"`` é um endereço de tela;
2. **tirar comentário com ``(?m)#[^\\n]*``** → 93 falsos, porque o regex come o
   ``#`` de ``cor = "#A51C48"`` e o resto da linha junto;
3. **borda de palavra com ``(?<![\\w.])``** → 17 falsos: excluir o ponto faz
   ``mesa_viva.VIA_DO_TRANSPORTE`` deixar de casar, e acesso por atributo é uso.

Quem sabe separar isso é a gramática da linguagem, não um regex: o ``ast`` diz
qual cadeia é docstring, o ``tokenize`` diz qual ``#`` abre comentário.

FALHA PARA O LADO SEGURO
-------------------------
Arquivo que não parseia devolve o texto CRU. Uma régua que emudece por causa de
um ``.py`` a meio caminho de uma edição é pior que uma que exagera: ela dá verde
sobre o que não leu.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

_COMENTARIO_HTML = re.compile(r"<!--.*?-->", re.S)

_CACHE: dict[Path, str] = {}


def _inicio_das_linhas(fonte: str) -> list[int]:
    """O deslocamento em que cada linha começa."""
    inicio = [0]
    for linha in fonte.splitlines(keepends=True):
        inicio.append(inicio[-1] + len(linha))
    return inicio


def _docstrings(arvore: ast.AST) -> list[ast.Constant]:
    """As docstrings — e só elas, nunca toda cadeia de texto."""
    fora: list[ast.Constant] = []
    for no in ast.walk(arvore):
        if not isinstance(no, (ast.Module, ast.ClassDef,
                               ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        corpo = getattr(no, "body", None)
        if not corpo:
            continue
        primeira = corpo[0]
        if (isinstance(primeira, ast.Expr)
                and isinstance(primeira.value, ast.Constant)
                and isinstance(primeira.value.value, str)):
            fora.append(primeira.value)
    return fora


def _apagar(letras: list[str], a: int, b: int) -> None:
    """Espaço no lugar do trecho, preservando as quebras de linha."""
    for i in range(a, min(b, len(letras))):
        if letras[i] != "\n":
            letras[i] = " "


def sem_prosa(fonte: str, sufixo: str = ".py") -> str:
    """O texto sem docstring e sem comentário. O resto fica intacto."""
    if sufixo != ".py":
        return _COMENTARIO_HTML.sub(lambda m: " " * len(m.group(0)), fonte)

    letras = list(fonte)
    try:
        arvore = ast.parse(fonte)
    except SyntaxError:
        return fonte
    inicio = _inicio_das_linhas(fonte)
    for no in _docstrings(arvore):
        if no.lineno is None or no.end_lineno is None:
            continue
        _apagar(letras,
                inicio[no.lineno - 1] + no.col_offset,
                inicio[no.end_lineno - 1] + no.end_col_offset)

    parcial = "".join(letras)
    letras = list(parcial)
    try:
        for tok in tokenize.generate_tokens(io.StringIO(parcial).readline):
            if tok.type != tokenize.COMMENT:
                continue
            _apagar(letras,
                    inicio[tok.start[0] - 1] + tok.start[1],
                    inicio[tok.end[0] - 1] + tok.end[1])
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return parcial
    return "".join(letras)


def codigo_de(caminho: Path) -> str:
    """O arquivo sem a prosa, lido uma vez por processo."""
    if caminho in _CACHE:
        return _CACHE[caminho]
    try:
        cru = caminho.read_text(encoding="utf-8", errors="replace")
    except OSError:
        cru = ""
    _CACHE[caminho] = sem_prosa(cru, caminho.suffix)
    return _CACHE[caminho]


def agulha(simbolo: str) -> re.Pattern[str]:
    """O símbolo com borda de palavra dos DOIS lados, e o ponto de fora.

    Sem a borda, ``player_slot`` casa dentro de ``player_slot_color`` — foi
    assim que uma linha do CSV da paridade passou a vida inteira sem morder. E
    o ponto NÃO entra na borda da esquerda: excluí-lo faria
    ``mesa_viva.VIA_DO_TRANSPORTE`` deixar de casar, e acesso por atributo é
    uso do símbolo.
    """
    return re.compile(rf"(?<!\w){re.escape(simbolo)}(?![\w])")


def usa(caminho: Path, simbolo: str) -> bool:
    """O arquivo USA o símbolo — citá-lo num comentário não conta."""
    return agulha(simbolo).search(codigo_de(caminho)) is not None


def cita(caminho: Path, simbolo: str) -> bool:
    """O símbolo APARECE no arquivo, prosa incluída."""
    try:
        return agulha(simbolo).search(
            caminho.read_text(encoding="utf-8", errors="replace")) is not None
    except OSError:
        return False
