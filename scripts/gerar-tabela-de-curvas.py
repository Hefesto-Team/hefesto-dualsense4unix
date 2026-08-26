#!/usr/bin/env python3
"""gerar-tabela-de-curvas.py — a tabela de curvas próprias sai do CATÁLOGO.

A CR-02 escreveu a regra, e o docstring de
`profiles/curva_propria.py::gerar_tabela_markdown` a repete literalmente: a
tabela de `docs/protocol/curvas-proprias.md` é *"gerada a partir dos perfis,
não escrita à mão"*, porque *"registro mantido à mão desatualiza, e registro
desatualizado não defende ninguém"*.

MEDIDO em 12/08/2026, e registrado como dívida em
`tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py`: **ninguém chamava a
função**. Só `tests/` a chamava, e nada em `scripts/`. A tabela do documento
era, portanto, mantida à mão — exatamente o que a CR-02 proibiu. Este arquivo
é o chamador que faltava, e o `--check` é o que impede a regra de voltar a ser
só uma frase.

O PORTÃO NASCE ANTES DO DADO, E ISSO É O DESENHO
-------------------------------------------------
Hoje não existe curva própria nenhuma no repositório: quem as vai medir é a
CR-04, com a mantenedora sentindo o gatilho. Com o catálogo vazio a função
devolve `_(nenhum ainda — ver CR-04)_`, que é a linha que o documento já tem —
então o portão entra verde e continua verde até o primeiro efeito nascer.

É de propósito. Um portão criado DEPOIS do dado nasce vermelho e é desligado na
mesma semana; criado antes, ele já está de pé no dia em que a primeira curva
chega, e a primeira curva chega com a tabela certa sem ninguém lembrar de nada.

ONDE MORA O CATÁLOGO
--------------------
`docs/data/curvas-proprias.json`, no formato de `CatalogoCurvasProprias`. O
arquivo ainda não existe, e a ausência dele é lida como catálogo vazio — não
como erro. O que É erro, e reprova alto, é o arquivo existir e não validar: aí
a proveniência de alguma curva está quebrada, e o silêncio seria a falha.

Uso:

    python3 scripts/gerar-tabela-de-curvas.py            # reescreve o bloco
    python3 scripts/gerar-tabela-de-curvas.py --check    # o bloco bate com o dado?
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.profiles.curva_propria import (  # noqa: E402
    CatalogoCurvasProprias,
    gerar_tabela_markdown,
)

CATALOGO = RAIZ / "docs" / "data" / "curvas-proprias.json"
DOCUMENTO = RAIZ / "docs" / "protocol" / "curvas-proprias.md"

ABRE = "<!-- BLOCO GERADO por scripts/gerar-tabela-de-curvas.py — não edite à mão -->"
FECHA = "<!-- FIM DO BLOCO GERADO -->"

LIMITE_DIFF = 40


def carrega_catalogo(caminho: Path) -> CatalogoCurvasProprias:
    """O catálogo do disco. Ausente é vazio; presente e inválido é erro alto."""
    if not caminho.is_file():
        return CatalogoCurvasProprias()
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as erro:
        raise SystemExit(
            f"{caminho.relative_to(RAIZ)}: não é JSON legível ({erro}). "
            "Um catálogo ilegível não vira tabela vazia em silêncio."
        ) from erro
    return CatalogoCurvasProprias.model_validate(dados)


def monta(raiz: Path) -> str:
    """O bloco inteiro, marcadores incluídos, com a tabela vinda do catálogo."""
    catalogo = carrega_catalogo(raiz / CATALOGO.relative_to(RAIZ))
    return "\n".join([ABRE, "", gerar_tabela_markdown(catalogo), "", FECHA])


def bloco_publicado(documento: str) -> str | None:
    achado = re.search(re.escape(ABRE) + r".*?" + re.escape(FECHA), documento, re.S)
    return achado.group(0) if achado else None


def documento_com_o_bloco(documento: str, bloco: str) -> str:
    inicio = documento.find(ABRE)
    fim = documento.find(FECHA)
    if inicio == -1 or fim == -1:
        raise SystemExit(
            f"{DOCUMENTO.relative_to(RAIZ)}: os marcadores do bloco gerado sumiram. "
            "Sem eles este gerador não sabe onde escrever — devolva-os ao documento."
        )
    return documento[:inicio] + bloco + documento[fim + len(FECHA):]


def divergencias(publicado: str, regerado: str) -> list[str]:
    return list(difflib.unified_diff(
        [linha.rstrip() for linha in publicado.splitlines()],
        [linha.rstrip() for linha in regerado.splitlines()],
        fromfile="o bloco publicado", tofile="o que o catálogo produz hoje",
        lineterm="", n=0,
    ))


def frase_do_tamanho(caminho: Path, quantas: int) -> str:
    """O que a régua mediu, dito em voz alta — ou a confissão de que não mediu.

    26/08/2026 (LEVA-4-E). Este script imprimia `atualizado (0 curva(s) no
    catálogo)` e saía `rc=0` sobre um catálogo que **não existe no disco**.
    `rc=0` ali é honesto — o bloco publicado de fato bate com a tabela vazia —,
    mas a PALAVRA `atualizado` é a mentira: nada foi conferido, porque não há
    nada para conferir, e quem lê a linha do `portoes.sh` conta um verde a
    mais. É o padrão que a casa nomeou em 25/08 — *a régua confunde a PALAVRA
    com o ATO* — e a saída aprovada naquele dia foi a régua do teclado, que
    disse *"a régua não achou NENHUM valor produzível — ela cegou"*.

    Um catálogo com UMA curva também não é medição: com um único item não há
    ordenação, nem colisão de nome, nem formatação a divergir.
    """
    try:
        onde = caminho.relative_to(RAIZ).as_posix()
    except ValueError:
        #: Catálogo fora da árvore só acontece em teste — e ali o endereço
        #: absoluto é o que ajuda a ler a falha.
        onde = caminho.as_posix()
    if not caminho.is_file():
        return (
            f"A RÉGUA NÃO MEDIU NADA: {onde} não existe no disco. O bloco "
            "publicado bate com a tabela VAZIA que um catálogo ausente produz "
            "— isso não é a tabela conferida contra o dado, é a ausência "
            "conferida contra si mesma."
        )
    if quantas == 0:
        return (
            f"A RÉGUA NÃO MEDIU NADA: {onde} existe e está SEM CURVA nenhuma. "
            "Zero linha comparada não é acordo entre a tabela e a fonte."
        )
    if quantas == 1:
        return (
            f"A RÉGUA MEDIU QUASE NADA: {onde} tem 1 curva. Com um item só não "
            "há ordem, nem nome repetido, nem formatação a divergir — o que "
            "passa aqui não diz quase nada sobre o que passaria com dez."
        )
    return f"atualizado ({quantas} curva(s) no catálogo {onde})"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="reprova se o bloco publicado não for o que o catálogo produz")
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
            print(f"{DOCUMENTO.relative_to(RAIZ)}: SEM BLOCO GERADO — a tabela de "
                  "curvas voltou a ser escrita à mão, que é o que a CR-02 proibiu. "
                  "Rode: python3 scripts/gerar-tabela-de-curvas.py", file=sys.stderr)
            return 1
        difs = divergencias(publicado, regerado)
        if difs:
            print(f"{DOCUMENTO.relative_to(RAIZ)}: DESATUALIZADO — a tabela publicada "
                  "não é a que o catálogo produz", file=sys.stderr)
            for linha in difs[:LIMITE_DIFF]:
                print(f"  {linha}", file=sys.stderr)
            if len(difs) > LIMITE_DIFF:
                print(f"  … e mais {len(difs) - LIMITE_DIFF} linha(s) de divergência",
                      file=sys.stderr)
            print(f"a fonte é: {CATALOGO.relative_to(RAIZ).as_posix()}", file=sys.stderr)
            print("rode: python3 scripts/gerar-tabela-de-curvas.py", file=sys.stderr)
            return 1
        quantas = len(carrega_catalogo(CATALOGO).curvas)
        print(f"{DOCUMENTO.relative_to(RAIZ)}: {frase_do_tamanho(CATALOGO, quantas)}")
        return 0

    caminho.write_text(documento_com_o_bloco(documento, regerado), encoding="utf-8")
    quantas = len(carrega_catalogo(CATALOGO).curvas)
    print(f"{DOCUMENTO.relative_to(RAIZ)}: bloco reescrito com {quantas} curva(s) "
          f"de {CATALOGO.relative_to(RAIZ).as_posix()}"
          + ("" if quantas > 1 else " — e um bloco vazio ou de item único não "
                                    "prova que o gerador sabe gerar"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
