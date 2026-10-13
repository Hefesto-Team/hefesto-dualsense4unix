#!/usr/bin/env python3
"""A catraca da docstring longa: o texto de docstring acima de 10 linhas só desce.

A docstring diz o contrato (o que o módulo faz, por que, e para onde olhar). A
história da decisão mora em ``docs/research/o-porque-dos-modulos.md`` e nos
documentos de tema. O que esta catraca impede é o caminho de volta: a narração
que a dieta de código tirou dos comentários e que reaparece, linha a linha, dentro
de uma docstring.

A medida é o total de linhas, em ``src/``, das docstrings de módulo, classe e
função que passam de ``LIMITE`` linhas (contadas pelo ``ast``, texto cru:
comentário e string que não são docstring não contam). O piso mora em
``docs/data/a-catraca-da-docstring-longa.json`` e é o motor de ``scripts/catraca.py``:
um número que sobe reprova e diz o ARQUIVO que subiu; o que desce passa e pede a
descida do piso (``--aceitar``), que este portão não regrava sozinho.

Para subir de propósito: ``--forcar-piso docstring-longa «razão»``.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from catraca import (
    Catraca,
    CatracaTorta,
    Censo,
    Medida,
    executar,
    montar_argumentos,
)

PACOTE = Path("src/hefesto_dualsense4unix")
CADERNO = Path("docs/data/a-catraca-da-docstring-longa.json")
LIMITE = 10
NOME = "docstring-longa"

_COM_DOCSTRING = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def docstrings_longas(fonte: str, limite: int = LIMITE) -> list[tuple[str, int]]:
    """``(nome, linhas)`` de cada docstring do texto com mais de ``limite`` linhas."""
    try:
        arvore = ast.parse(fonte)
    except SyntaxError:
        return []
    achadas: list[tuple[str, int]] = []
    for no in ast.walk(arvore):
        if not isinstance(no, _COM_DOCSTRING):
            continue
        texto = ast.get_docstring(no, clean=False)
        if texto is None:
            continue
        linhas = len(texto.splitlines())
        if linhas > limite:
            achadas.append((getattr(no, "name", "<módulo>"), linhas))
    return achadas


def censo_das_docstrings(raiz: Path) -> Censo:
    """O total de linhas em docstrings longas; o de cada arquivo vai em ``por_item``."""
    base = raiz / PACOTE
    arquivos = sorted(base.rglob("*.py")) if base.is_dir() else []
    por_item: dict[str, int] = {}
    for p in arquivos:
        try:
            fonte = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        soma = sum(linhas for _nome, linhas in docstrings_longas(fonte))
        if soma:
            por_item[p.relative_to(base).as_posix()] = soma
    return Censo(
        numero=sum(por_item.values()),
        universo=len(arquivos),
        por_item=por_item,
        nota=f"linhas em docstrings de mais de {LIMITE} linhas, em {PACOTE}",
    )


MEDIDAS = (
    Medida(
        NOME,
        f"linhas em docstrings de mais de {LIMITE} linhas, em {PACOTE}",
        censo_das_docstrings,
        "linhas",
    ),
)


def main(argv: list[str] | None = None) -> int:
    p = montar_argumentos((__doc__ or "").split("\n", 1)[0])
    a = p.parse_args(argv)
    raiz = Path(a.raiz) if a.raiz else RAIZ
    catraca = Catraca(raiz / CADERNO, MEDIDAS, raiz)
    rc = executar(catraca, a, "A catraca da docstring longa")
    if rc == 0 and a.aceitar is None and not a.forcar_piso and not a.json:
        try:
            for v in catraca.comparar():
                if v.piso.numero is not None and v.numero is not None and v.numero < v.piso.numero:
                    print(
                        f"  o número desceu ({v.piso.numero} -> {v.numero}): "
                        f"grave o piso novo com `{Path(sys.argv[0]).name} --aceitar {NOME}`"
                    )
        except CatracaTorta as erro:
            print(f"RECUSADO: {erro}", file=sys.stderr)
            return 2
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
