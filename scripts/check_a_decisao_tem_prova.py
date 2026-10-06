#!/usr/bin/env python3
"""check_a_decisao_tem_prova.py — decidida não é feita, e agora alguém cobra.

DECISAO-SEM-DONO-01. O `docs/data/decisoes-dela.csv` guarda a decisão e o dono
dela, e até aqui o registro parava no momento em que ela respondia: nada ligava
a linha ao código. O microfone mudo de 17/09 era uma decisão de 25/08.

A ESCADA do campo `estado`, nas palavras que ela aceitou em 23/09:

    aberta -> decidida -> implementada -> feita -> no ar        (e `caduca`)

`implementada`, `feita` e `no ar` EXIGEM o campo `prova`: um ou mais
`tests/…/arquivo.py::função` separados por « | », em que a função existe e traz
o id da decisão. A palavra sozinha não sobe o degrau.

O PORTÃO, em quatro regras:

  1. estado fora da escada, marca fora do vocabulário ou prova que não abre
     (arquivo ou função inexistente, ou função que não cita a decisão): VERMELHO.
  2. degrau acima de `decidida` sem prova: VERMELHO.
  3. `decidida` sem prova e sem a marca `processo` só passa se estiver no PISO
     (`docs/data/decisoes-sem-prova.txt`, um id por linha). Decisão NOVA sem
     prova não passa, e a lista sai nominal.
  4. id que ganhou prova, ganhou a marca, caducou ou saiu do CSV tem de sair do
     piso (`--aceitar`). Piso velho deixaria uma decisão nova entrar pela vaga
     de uma que já foi paga.

O PISO DESCE SOZINHO E SÓ SOBE À MÃO. O `--aceitar` nunca acrescenta: ele só
tira. Uma decisão registrada antes da régua dela (o registro é no dia em que ela
responde, e o código vem depois) entra no piso pela mão de quem a registra, numa
linha que aparece no diff, de preferência sob um comentário datado que diz de
onde ela veio. O portão não distingue essa entrada de uma que fura a fila: quem
confere o diff do piso é quem a distingue.

A marca `processo` é declarada uma a uma, nunca por palavra: a triagem por
vocabulário dá 34% de «indecidível» (`medir_decisoes_sem_prova.py`).

O QUE ELE MEDE, E É DITO EM VOZ ALTA: a EXISTÊNCIA da prova e a ligação dela com
o id, não a QUALIDADE. Verde aqui não quer dizer que a régua morde nem que o
produto cumpre a decisão: D-AUDIO-E-GIRO-NASCEM-LIGADOS teve citação em tests/
por treze dias com o microfone mudo no produto dela. Quem sobe uma decisão a
`implementada` arranca a cura e vê a régua reprovar, e diz isso no commit.
"""

from __future__ import annotations

import argparse
import ast
import csv
import re
import sys
from typing import Any
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CSV_DAS_DECISOES = Path("docs/data/decisoes-dela.csv")
PISO = Path("docs/data/decisoes-sem-prova.txt")

ESTADOS = ("aberta", "decidida", "implementada", "feita", "no ar", "caduca")
DEGRAUS_QUE_EXIGEM_PROVA = ("implementada", "feita", "no ar")
MARCAS = ("", "processo")
COLUNAS_NOVAS = ("prova", "marca")
SEPARADOR_DE_PROVAS = " | "


def _linhas(raiz: Path) -> list[dict[str, str]]:
    with (raiz / CSV_DAS_DECISOES).open(encoding="utf-8", newline="") as fp:
        return list(csv.DictReader(fp))


def _ler_piso(raiz: Path) -> list[str] | None:
    caminho = raiz / PISO
    if not caminho.is_file():
        return None
    ids = []
    for bruta in caminho.read_text(encoding="utf-8").splitlines():
        linha = bruta.split("#", 1)[0].strip()
        if linha:
            ids.append(linha)
    return ids


def _regex_do_id(ident: str) -> re.Pattern[str]:
    return re.compile(r"(?<![A-Za-z0-9_-])" + re.escape(ident) + r"(?![A-Za-z0-9_-])")


class _Fontes:
    """Cada arquivo de teste lido e analisado uma vez só."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self._memo: dict[str, tuple[str, ast.AST] | None] = {}

    def arquivo(self, rel: str) -> tuple[str, ast.AST] | None:
        if rel not in self._memo:
            caminho = self.raiz / rel
            try:
                fonte = caminho.read_text(encoding="utf-8")
                self._memo[rel] = (fonte, ast.parse(fonte))
            except (OSError, SyntaxError):
                self._memo[rel] = None
        return self._memo[rel]

    def funcao(self, rel: str, nome: str) -> str | None:
        """O texto da função `nome` (em qualquer escopo), ou None se não existe."""
        lido = self.arquivo(rel)
        if lido is None:
            return None
        fonte, arvore = lido
        achados = [
            ast.get_source_segment(fonte, no) or ""
            for no in ast.walk(arvore)
            if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and no.name == nome
        ]
        return "\n".join(achados) if achados else None


def problemas_da_prova(ident: str, prova: str, fontes: _Fontes) -> list[str]:
    """Cada prova declarada tem de abrir: arquivo, função e o id dentro dela."""
    ruins: list[str] = []
    padrao = _regex_do_id(ident)
    for parte in (p.strip() for p in prova.split("|")):
        if not parte:
            continue
        rel, separador, nome = parte.partition("::")
        if not separador or not nome or not rel.startswith("tests/") or not rel.endswith(".py"):
            ruins.append(
                f"{ident}: a prova «{parte}» não tem a forma `tests/…/arquivo.py::função`"
            )
            continue
        if not (fontes.raiz / rel).is_file():
            ruins.append(f"{ident}: a prova {rel} não existe")
            continue
        texto = fontes.funcao(rel, nome)
        if texto is None:
            ruins.append(f"{ident}: a prova {rel}::{nome} não é uma função desse arquivo")
        elif not padrao.search(texto):
            ruins.append(
                f"{ident}: a função {rel}::{nome} existe e NÃO cita a decisão "
                "(prova que não nomeia o que prova não se liga à linha)"
            )
    return ruins


def medir(raiz: Path) -> dict[str, Any]:
    linhas = _linhas(raiz)
    fontes = _Fontes(raiz)
    ruins: list[str] = []
    cabecalho = set(linhas[0].keys()) if linhas else set()
    faltando = [c for c in COLUNAS_NOVAS if c not in cabecalho]
    if not linhas:
        ruins.append(f"{CSV_DAS_DECISOES} não tem uma linha sequer")
    if faltando:
        ruins.append(
            "o CSV perdeu a(s) coluna(s) " + ", ".join(faltando) + ": sem elas toda decisão "
            "pareceria sem prova ou toda prova pareceria ausente"
        )
    ids_vistos: set[str] = set()
    sem_prova: list[str] = []
    com_prova: list[str] = []
    processo: list[str] = []
    for linha in linhas:
        ident = linha.get("id", "")
        estado = linha.get("estado", "")
        prova = (linha.get("prova") or "").strip()
        marca = (linha.get("marca") or "").strip()
        if ident in ids_vistos:
            ruins.append(f"{ident}: id repetido no CSV")
        ids_vistos.add(ident)
        if estado not in ESTADOS:
            ruins.append(f"{ident}: estado «{estado}» fora da escada {' -> '.join(ESTADOS)}")
            continue
        if marca not in MARCAS:
            ruins.append(f"{ident}: marca «{marca}» fora do vocabulário {MARCAS[1:]}")
        if prova:
            ruins.extend(problemas_da_prova(ident, prova, fontes))
            com_prova.append(ident)
        elif estado in DEGRAUS_QUE_EXIGEM_PROVA:
            ruins.append(f"{ident}: estado «{estado}» sem o campo `prova` (a palavra não sobe o degrau)")
        if marca == "processo":
            processo.append(ident)
        if estado == "decidida" and not prova and not marca:
            sem_prova.append(ident)
    piso = _ler_piso(raiz)
    if piso is None:
        ruins.append(f"{PISO} não existe: sem o piso toda decisão sem prova seria nova")
        piso = []
    novas = sorted(set(sem_prova) - set(piso))
    velhas = sorted(set(piso) - set(sem_prova))
    repetidas = sorted({i for i in piso if piso.count(i) > 1})
    return {
        "linhas": len(linhas),
        "problemas": ruins,
        "sem_prova": sorted(sem_prova),
        "com_prova": sorted(com_prova),
        "processo": sorted(processo),
        "piso": piso,
        "novas_sem_prova": novas,
        "piso_velho": velhas,
        "piso_repetido": repetidas,
    }


def _imprimir_ids(ids: list[str], limite: int = 60) -> None:
    for ident in ids[:limite]:
        print(f"  {ident}")
    if len(ids) > limite:
        print(f"  ... e mais {len(ids) - limite}")


def aceitar(raiz: Path, m: dict[str, Any], semear: bool = False) -> int:
    """Desce o piso até as decisões que ainda estão sem prova. Nunca sobe.

    `semear` é só para o piso que ainda não existe (ou está vazio): o primeiro
    censo, que grava as decisões que já nasceram sem prova.
    """
    if semear and (raiz / PISO).is_file() and _ler_piso(raiz):
        print("RECUSADO: o piso já existe e tem decisões; `--semear` é só para o primeiro censo.")
        return 2
    if semear:
        m = {**m, "novas_sem_prova": []}
    if m["problemas"]:
        print("RECUSADO: o CSV tem defeito de forma ou prova que não abre; não se grava piso sobre ele.")
        return 2
    if m["novas_sem_prova"]:
        print(
            f"RECUSADO: {len(m['novas_sem_prova'])} decisão(ões) sem prova que não estão no piso. "
            "O --aceitar só desce o piso: dê prova (ou, se é de processo, a marca) a cada uma, "
            "ou, se é decisão registrada antes da régua dela, acrescente o id ao piso à mão."
        )
        _imprimir_ids(m["novas_sem_prova"])
        return 2
    cabecalho = (
        "# PISO das decisões decididas e sem prova (scripts/check_a_decisao_tem_prova.py).\n"
        "# Um id por linha. Desce sozinho: `--aceitar` tira o que ganhou prova ou a marca\n"
        "# `processo`. Só sobe à mão, no diff: a decisão registrada antes da régua dela.\n"
    )
    corpo = "".join(f"{i}\n" for i in m["sem_prova"])
    (raiz / PISO).write_text(cabecalho + corpo, encoding="utf-8")
    print(f"piso gravado: {len(m['sem_prova'])} decisões sem prova")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="A decisão decidida tem prova, marca de processo ou está no piso.")
    ap.add_argument("--raiz", default=None, help="a árvore a medir (padrão: a do script)")
    ap.add_argument("--aceitar", action="store_true", help="desce o piso até o que ainda está sem prova")
    ap.add_argument("--semear", action="store_true", help="grava o primeiro piso (só com o piso ausente ou vazio)")
    ap.add_argument("--nominal", action="store_true", help="lista as decisões sem prova do piso")
    args = ap.parse_args(argv)
    raiz = Path(args.raiz).resolve() if args.raiz else RAIZ
    try:
        m = medir(raiz)
    except (OSError, csv.Error) as erro:
        print(f"VERMELHO: não consegui ler {CSV_DAS_DECISOES}: {erro}")
        return 1
    if args.aceitar or args.semear:
        return aceitar(raiz, m, semear=args.semear)

    reprovou = False
    if m["problemas"]:
        reprovou = True
        print(f"VERMELHO: {len(m['problemas'])} defeito(s) no registro das decisões:")
        for p in m["problemas"][:60]:
            print(f"  {p}")
    if m["novas_sem_prova"]:
        reprovou = True
        print(f"VERMELHO: {len(m['novas_sem_prova'])} decisão(ões) decidida(s) SEM PROVA e fora do piso:")
        _imprimir_ids(m["novas_sem_prova"])
        print(
            "  Dê a cada uma o campo `prova` (`tests/…/arquivo.py::função`, com o id dentro da função) "
            "ou, se é de processo, a marca `processo`."
        )
    if m["piso_velho"]:
        reprovou = True
        print(f"VERMELHO: {len(m['piso_velho'])} id(s) no piso que já não estão sem prova:")
        _imprimir_ids(m["piso_velho"])
        print("  Rode `scripts/check_a_decisao_tem_prova.py --aceitar`: o piso desce, e só desce.")
    if m["piso_repetido"]:
        reprovou = True
        print("VERMELHO: id repetido no piso: " + ", ".join(m["piso_repetido"]))
    if reprovou:
        return 1
    if args.nominal:
        _imprimir_ids(m["sem_prova"], limite=10**6)
    print(
        f"VERDE: {m['linhas']} decisões · {len(m['com_prova'])} com prova que abre · "
        f"{len(m['processo'])} de processo · {len(m['sem_prova'])} no piso (descem pelo --aceitar)"
    )
    print(
        "E VERDE AQUI NÃO QUER DIZER FEITO: este portão mede que a prova EXISTE e cita a decisão, "
        "não que a régua morde nem que o produto cumpre. Para subir uma decisão a `implementada`, "
        "arranque a cura, veja a régua reprovar e devolva."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
