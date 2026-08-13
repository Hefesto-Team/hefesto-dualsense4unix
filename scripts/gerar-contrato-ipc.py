#!/usr/bin/env python3
"""gerar-contrato-ipc.py — a lista de métodos IPC sai do DISPATCHER, não da mão.

O defeito, medido em 13/08/2026: `docs/protocol/ipc-unix-socket.md` trazia uma
tabela "Métodos v1" escrita à mão com **dez** linhas, e o dicionário
`_handlers` de `daemon/ipc_server.py` registrava **trinta e sete** métodos.
Entre os ausentes estava a família inteira do rumble (`rumble.set`,
`rumble.stop`, `rumble.policy_set`, `rumble.policy_custom`,
`rumble.passthrough`), mais `plugin.list`, `plugin.reload`, `daemon.pause`,
`daemon.resume` e `profile.apply_draft`.

O QUE ESTE ARQUIVO EXISTE PARA IMPEDIR
--------------------------------------
Não é a tabela desatualizada — é o **número escrito à mão**. A contagem de
métodos ausentes do documento já saiu 15, 17, 18 e 14 em levantamentos
diferentes, **sem nenhum commit no meio**: cada régua contava de um jeito e
todas escreviam o resultado como se fosse fato. Um número que quatro medições
não reproduzem não é fato, é opinião com cara de dado.

A saída é a mesma do `specs.html` (`scripts/gerar-mapa.py`): o número não se
escreve, ele se **gera**. Depois disso a única forma de ele estar errado é o
gerador estar errado — e aí erra uma vez só, no mesmo lugar, para todo mundo.

O QUE ENTRA NO BLOCO, E DE ONDE VEM CADA COLUNA
-----------------------------------------------
Tudo é derivado; nada é digitado aqui:

- **Método** — a chave do dicionário `_handlers` (`daemon/ipc_server.py`), lida
  por AST. Sem importar o pacote: o portão roda em runner sem as dependências
  do projeto instaladas, e um `ImportError` viraria "zero métodos", que é o
  jeito silencioso de um gate se desligar (a mesma razão está escrita em
  `scripts/validar-referencias-docs.py`, em `indexar_metodos_ipc`).
- **Handler** — o nome e o ENDEREÇO do `async def` que atende, lido por AST de
  `daemon/ipc_handlers.py`. Endereço gerado nunca apodrece, que é exatamente o
  que `scripts/validar-citacoes-de-linha.py` cobra dos escritos à mão.
- **O que o handler diz de si** — a primeira linha do docstring dele. Handler
  sem docstring aparece dizendo que não tem: é dívida, e dívida some quando é
  contada.
- **Contrato em prosa** — se o método aparece, entre crases, na parte do
  documento que NÃO é este bloco. É a coluna que responde a pergunta cuja
  resposta variava: quantos métodos nasceram sem contrato escrito.

O `--check` PERGUNTA PELO CONTEÚDO, NÃO PELO RELÓGIO
-----------------------------------------------------
Ele remonta o bloco em memória e compara com o que está entre os marcadores no
documento. Comparar mtime foi o defeito que a MAPA-CONTEUDO-01 mediu em
12/08/2026 e curou no `gerar-mapa.py`; este nasce já do lado certo. Não há
selo de hora nenhum na saída, de propósito: sem relógio no artefato, não há
como um comparador ser tentado a olhar para ele.

Uso:

    python3 scripts/gerar-contrato-ipc.py            # reescreve o bloco
    python3 scripts/gerar-contrato-ipc.py --check    # o bloco bate com o código?
"""
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

#: As fontes do bloco. O documento entra na lista porque a coluna "Contrato em
#: prosa" lê a prosa dele — quem edita a prosa muda o bloco, e o `--check` tem
#: de dizer isso em vez de acusar o código.
FONTES = (DISPATCHER, HANDLERS, Path("docs") / "protocol" / "ipc-unix-socket.md")

ABRE = "<!-- BLOCO GERADO por scripts/gerar-contrato-ipc.py — não edite à mão -->"
FECHA = "<!-- FIM DO BLOCO GERADO -->"

#: Quantas linhas de divergência o erro imprime antes de resumir.
LIMITE_DIFF = 40


def metodos_do_dispatcher(raiz: Path) -> list[tuple[str, str]]:
    """Os pares (método, handler) do `_handlers`, na ORDEM em que estão escritos.

    A ordem é a do código de propósito: ela agrupa as famílias como quem
    escreveu o dispatcher as agrupou, e uma ordem derivada do dado é uma coisa
    a menos para alguém discordar na revisão.
    """
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
    """O documento com o bloco gerado removido.

    Sem esta poda a coluna "Contrato em prosa" responderia `sim` para todo
    mundo: o bloco cita cada método entre crases, e ele se encontraria.
    """
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
