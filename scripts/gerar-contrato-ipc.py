#!/usr/bin/env python3
"""gerar-contrato-ipc.py — a lista de métodos IPC sai do DISPATCHER, não da mão."""
from __future__ import annotations

import argparse
import ast
import difflib
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PACOTE = Path("src") / "hefesto_dualsense4unix"
DISPATCHER = PACOTE / "daemon" / "ipc_server.py"
HANDLERS = PACOTE / "daemon" / "ipc_handlers.py"
DOCUMENTO = RAIZ / "docs" / "protocol" / "ipc-unix-socket.md"

FONTES = (DISPATCHER, HANDLERS, Path("docs") / "protocol" / "ipc-unix-socket.md")

ABRE = "<!-- BLOCO GERADO por scripts/gerar-contrato-ipc.py — não edite à mão -->"
FECHA = "<!-- FIM DO BLOCO GERADO -->"

LIMITE_DIFF = 40


def metodos_do_dispatcher(raiz: Path) -> list[tuple[str, str]]:
    """Os pares (método, handler) do `_handlers`, na ORDEM em que estão escritos."""
    arvore = ast.parse((raiz / DISPATCHER).read_text(encoding="utf-8"))
    pares: list[tuple[str, str]] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Assign) or not isinstance(no.value, ast.Dict):
            continue
        if not any(isinstance(a, ast.Attribute) and a.attr == "_handlers"
                   for a in no.targets):
            continue
        for chave, valor in zip(no.value.keys, no.value.values, strict=True):
            if not (isinstance(chave, ast.Constant) and isinstance(chave.value, str)):
                continue
            nome = valor.attr if isinstance(valor, ast.Attribute) else "?"
            pares.append((chave.value, nome))
    return pares


def handlers_do_mixin(raiz: Path) -> dict[str, tuple[int, str | None]]:
    """Cada `_handle_*` do mixin, com a linha do `def` e a 1ª linha do docstring."""
    arvore = ast.parse((raiz / HANDLERS).read_text(encoding="utf-8"))
    achados: dict[str, tuple[int, str | None]] = {}
    for no in ast.walk(arvore):
        if not isinstance(no, ast.AsyncFunctionDef | ast.FunctionDef):
            continue
        if not no.name.startswith("_handle_"):
            continue
        doc = ast.get_docstring(no)
        primeira = doc.strip().splitlines()[0].strip() if doc else None
        achados[no.name] = (no.lineno, primeira)
    return achados


def celula(texto: str) -> str:
    """Um texto qualquer virando célula de tabela markdown sem quebrar a tabela."""
    return texto.replace("|", r"\|").replace("\n", " ")


def prosa_sem_o_bloco(documento: str) -> str:
    """O documento com o bloco gerado removido."""
    inicio = documento.find(ABRE)
    fim = documento.find(FECHA)
    if inicio == -1 or fim == -1:
        return documento
    return documento[:inicio] + documento[fim + len(FECHA):]


def monta(raiz: Path) -> str:
    """O bloco inteiro, marcadores incluídos, a partir do código e da prosa."""
    pares = metodos_do_dispatcher(raiz)
    mixin = handlers_do_mixin(raiz)
    documento = (raiz / DOCUMENTO.relative_to(RAIZ)).read_text(encoding="utf-8")
    prosa = prosa_sem_o_bloco(documento)

    linhas_da_tabela: list[str] = []
    sem_contrato: list[str] = []
    sem_docstring = 0
    for metodo, handler in pares:
        linha, primeira = mixin.get(handler, (0, None))
        if primeira is None:
            sem_docstring += 1
            diz = "_(o handler não tem docstring)_"
        else:
            diz = celula(primeira)
        endereco = (
            f"`{HANDLERS.relative_to(PACOTE).as_posix()}:{linha}` (`{handler}`)"
            if linha else "_(handler não encontrado)_"
        )
        tem_contrato = f"`{metodo}`" in prosa
        if not tem_contrato:
            sem_contrato.append(metodo)
        linhas_da_tabela.append(
            f"| `{metodo}` | {endereco} | {diz} | {'sim' if tem_contrato else '**não**'} |"
        )

    corpo = [
        ABRE,
        "",
        f"**{len(pares)} métodos** estão registrados no dicionário `_handlers` de "
        f"`{DISPATCHER.relative_to(PACOTE).as_posix()}`. Destes, **{len(sem_contrato)}** "
        "ainda não são citados em nenhuma outra parte deste documento, e "
        f"**{sem_docstring}** têm handler sem docstring.",
        "",
        "Esta tabela é **gerada**. O número acima nunca foi digitado por ninguém — "
        "e é por isso que ele está aqui: escrito à mão, ele já saiu 15, 17, 18 e 14 "
        "em levantamentos do mesmo dia.",
        "",
        "| Método | Handler | O que o handler diz de si | Contrato em prosa |",
        "|---|---|---|---|",
        *linhas_da_tabela,
        "",
        FECHA,
    ]
    return "\n".join(corpo)


def documento_com_o_bloco(documento: str, bloco: str) -> str:
    """O documento com o bloco trocado. Sem marcadores, é erro em voz alta."""
    inicio = documento.find(ABRE)
    fim = documento.find(FECHA)
    if inicio == -1 or fim == -1:
        raise SystemExit(
            f"{DOCUMENTO.relative_to(RAIZ)}: os marcadores do bloco gerado sumiram "
            f"({ABRE!r} / {FECHA!r}). Sem eles este gerador não sabe onde escrever — "
            "devolva-os ao documento antes de rodar."
        )
    return documento[:inicio] + bloco + documento[fim + len(FECHA):]


def bloco_publicado(documento: str) -> str | None:
    achado = re.search(re.escape(ABRE) + r".*?" + re.escape(FECHA), documento, re.S)
    return achado.group(0) if achado else None


def divergencias(publicado: str, regerado: str) -> list[str]:
    return list(difflib.unified_diff(
        [linha.rstrip() for linha in publicado.splitlines()],
        [linha.rstrip() for linha in regerado.splitlines()],
        fromfile="o bloco publicado", tofile="o que o dispatcher produz hoje",
        lineterm="", n=0,
    ))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="reprova se o bloco publicado não for o que o código produz")
    args = ap.parse_args()

    caminho = RAIZ / DOCUMENTO.relative_to(RAIZ)
    if not caminho.is_file():
        print(f"{DOCUMENTO.relative_to(RAIZ)}: NAO EXISTE", file=sys.stderr)
        return 1
    documento = caminho.read_text(encoding="utf-8")
    regerado = monta(RAIZ)

    if args.check:
        publicado = bloco_publicado(documento)
        if publicado is None:
            print(f"{DOCUMENTO.relative_to(RAIZ)}: SEM BLOCO GERADO — a lista de "
                  "métodos voltou a ser escrita à mão. Rode: "
                  "python3 scripts/gerar-contrato-ipc.py", file=sys.stderr)
            return 1
        difs = divergencias(publicado, regerado)
        if difs:
            print(f"{DOCUMENTO.relative_to(RAIZ)}: DESATUALIZADO — o bloco publicado "
                  "não é o que o dispatcher produz", file=sys.stderr)
            for linha in difs[:LIMITE_DIFF]:
                print(f"  {linha}", file=sys.stderr)
            if len(difs) > LIMITE_DIFF:
                print(f"  … e mais {len(difs) - LIMITE_DIFF} linha(s) de divergência",
                      file=sys.stderr)
            print("as fontes são: " + ", ".join(f.as_posix() for f in FONTES),
                  file=sys.stderr)
            print("rode: python3 scripts/gerar-contrato-ipc.py", file=sys.stderr)
            return 1
        print(f"{DOCUMENTO.relative_to(RAIZ)}: atualizado "
              f"({len(metodos_do_dispatcher(RAIZ))} métodos, conferidos no dispatcher)")
        return 0

    caminho.write_text(documento_com_o_bloco(documento, regerado), encoding="utf-8")
    print(f"{DOCUMENTO.relative_to(RAIZ)}: bloco reescrito com "
          f"{len(metodos_do_dispatcher(RAIZ))} métodos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
