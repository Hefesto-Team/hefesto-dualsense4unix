#!/usr/bin/env python3
"""O recibo da medida: o que a trava do push da máquina lê.

O DEFEITO, medido em 26 e 27/09/2026: os portões e a suíte só travavam se
alguém os rodasse, e o `dev` subiu dez vezes com o CI vermelho. A trava do push
da máquina pede, para a árvore do commit que sobe, dois arquivos em
``<git comum>/hefesto-recibos/``: ``<árvore>.portoes-completo`` e
``<árvore>.suite``. Até aqui nenhum roteiro os escrevia, e por isso a regra
dorme enquanto a pasta não existe. Quem a acorda é o primeiro recibo.

DOIS VERBOS, chamados pelo ``scripts/portoes.sh`` (camada completa) e pelo
``scripts/rodar-a-suite.sh`` (corrida inteira):

* ``abrir <nome>`` guarda, no arquivo da própria corrida (``--corrida``), a
  árvore do índice, o ``HEAD``, o que está mudado fora do índice e o que está
  fora do git sem ser ignorado;
* ``fechar <nome> <rc>`` escreve ``<git comum>/hefesto-recibos/<árvore>.<nome>``
  **só se** o ``rc`` é 0, a árvore do índice é a mesma do começo, e não havia
  nem há mudança rastreada fora do índice. O recibo diz a data, a árvore, o
  ``HEAD``, a contagem e os NÃO MEDIDOS.

A ÁRVORE É A DO CONTEÚDO, não a do ramo: os portões rodam depois do
``git add`` e antes do commit; o commit, o merge fast-forward e o push levam a
mesma árvore (``<sha>^{tree}``), e o diretório comum é um só para todas as
árvores de trabalho do mesmo ``.git``.

O ÍNDICE DE VERDADE NÃO É TOCADO. Medido em 28/09/2026 (git 2.43): o
``git write-tree`` toma a trava do índice mesmo com ``GIT_OPTIONAL_LOCKS=0``
(sai 128 se outra sessão a segura) e regrava o índice. O índice é compartilhado
entre as sessões da mesma árvore, então as três leituras rodam sobre uma CÓPIA
dele, que dá o mesmo hash.

ARQUIVO FORA DO GIT NO COMEÇO IMPEDE O RECIBO. Os portões e a suíte leem o
disco: um ``tests/unit/test_x.py`` ou um módulo de ``src/`` esquecido fora do
``git add`` entra na medida e não entra na árvore. É a regra «portões são cegos
a arquivo novo» pelo outro lado. O que aparecer DURANTE a corrida (sobra de
teste) não muda a árvore medida: sai nomeado no recibo, sem impedi-lo.

Uso:
    recibo_da_medida.py abrir  <nome> --corrida <arquivo> [--raiz <árvore>]
    recibo_da_medida.py fechar <nome> <rc> --corrida <arquivo> [--raiz <árvore>]
                               [--contagem <texto>] [--nao-medido <id>]...
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

#: A pasta que a trava do push lê, dentro do diretório git comum.
PASTA = "hefesto-recibos"

#: O nome vira sufixo de arquivo: nada de barra, ponto ou espaço.
_NOME = re.compile(r"^[a-z0-9][a-z0-9-]*$")

#: Quantos caminhos a mensagem nomeia antes de resumir.
_MOSTRA = 5


@dataclass
class Retrato:
    """O estado da árvore num instante, lido de uma cópia do índice."""

    raiz: str
    arvore: str
    head: str
    sujos: list[str]
    fora_do_git: list[str]


class SemRetrato(Exception):
    """O git não respondeu: sem retrato não há recibo."""


def _git(raiz: Path, *args: str, indice: Path | None = None) -> str:
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    if indice is not None:
        env["GIT_INDEX_FILE"] = str(indice)
    feito = subprocess.run(["git", *args], cwd=raiz, env=env, capture_output=True,
                           text=True, check=False)
    if feito.returncode != 0:
        erro = (feito.stderr.strip().splitlines() or [f"rc={feito.returncode}"])[-1]
        raise SemRetrato(f"`git {' '.join(args)}` falhou: {erro}")
    return feito.stdout


def _caminho_do_git(raiz: Path, saida: str) -> Path:
    p = Path(saida.strip())
    return p if p.is_absolute() else (raiz / p)


def _lista_z(saida: str) -> list[str]:
    return [c for c in saida.split("\0") if c]


def retratar(raiz: Path) -> Retrato:
    """Árvore, HEAD, mudados e fora do git, todos da MESMA cópia do índice."""
    topo = Path(_git(raiz, "rev-parse", "--show-toplevel").strip()).resolve()
    indice = _caminho_do_git(topo, _git(topo, "rev-parse", "--git-path", "index"))
    with tempfile.TemporaryDirectory(prefix="recibo-") as pasta:
        copia = Path(pasta) / "index"
        if indice.exists():
            shutil.copyfile(indice, copia)
        # sem índice (repositório recém-criado), o git lê a cópia ausente como vazia
        arvore = _git(topo, "write-tree", indice=copia).strip()
        sujos = _lista_z(_git(topo, "diff", "--name-only", "-z", indice=copia))
        fora = _lista_z(_git(topo, "ls-files", "--others", "--exclude-standard", "-z",
                             indice=copia))
    try:
        head = _git(topo, "rev-parse", "--verify", "-q", "HEAD^{commit}").strip()
    except SemRetrato:
        head = ""
    return Retrato(str(topo), arvore, head, sujos, fora)


def pasta_dos_recibos(raiz: Path) -> Path:
    comum = _caminho_do_git(raiz, _git(raiz, "rev-parse", "--git-common-dir"))
    return comum.resolve() / PASTA


def _nomeia(caminhos: list[str]) -> str:
    mais = len(caminhos) - _MOSTRA
    return ", ".join(caminhos[:_MOSTRA]) + (f" (e mais {mais})" if mais > 0 else "")


def _diz(texto: str) -> None:
    print(f"recibo: {texto}", flush=True)


def abrir(nome: str, corrida: Path, raiz: Path) -> int:
    # A abertura velha de outra corrida no mesmo arquivo nunca pode valer.
    corrida.unlink(missing_ok=True)
    try:
        r = retratar(raiz)
    except SemRetrato as e:
        _diz(f"{nome} não se abre, e esta corrida não deixa recibo — {e}")
        return 1
    dados = {"nome": nome, "aberto_em": datetime.now().astimezone().isoformat(timespec="seconds"),
             **asdict(r)}
    corrida.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    if r.sujos:
        _diz(f"{nome}: esta corrida não vai deixar recibo — há mudança fora do índice "
             f"em {_nomeia(r.sujos)}; o `git add` vem antes da medida")
    elif r.fora_do_git:
        _diz(f"{nome}: esta corrida não vai deixar recibo — há arquivo fora do git que a "
             f"medida lê e a árvore não leva: {_nomeia(r.fora_do_git)}")
    else:
        _diz(f"{nome} aberto sobre a árvore do índice {r.arvore}")
    return 0


def _recusa(nome: str, razao: str) -> int:
    _diz(f"{nome} não escrito — {razao}")
    return 1


def fechar(nome: str, rc: str, corrida: Path, raiz: Path, contagem: str,
           nao_medidos: list[str]) -> int:
    if rc.strip() != "0":
        return _recusa(nome, f"a medida não passou (rc={rc})")
    try:
        aberta = json.loads(corrida.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        aberta = {}
    if aberta.get("nome") != nome or not aberta.get("arvore"):
        return _recusa(nome, "a abertura desta corrida não foi registrada")
    if aberta.get("sujos"):
        return _recusa(nome, f"no começo havia mudança fora do índice: {_nomeia(aberta['sujos'])}")
    if aberta.get("fora_do_git"):
        return _recusa(nome, "no começo havia arquivo fora do git que a medida leu: "
                       + _nomeia(aberta["fora_do_git"]))
    try:
        agora = retratar(raiz)
    except SemRetrato as e:
        return _recusa(nome, str(e))
    if agora.raiz != aberta.get("raiz"):
        return _recusa(nome, f"a corrida abriu em {aberta.get('raiz')} e fechou em {agora.raiz}")
    if agora.sujos:
        return _recusa(nome, f"há mudança fora do índice: {_nomeia(agora.sujos)}")
    if agora.arvore != aberta["arvore"]:
        return _recusa(nome, "a árvore do índice mudou durante a corrida; o que foi medido "
                       "não é o que subiria")

    linhas = [
        f"medida: {nome}",
        f"data: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"aberta: {aberta['aberto_em']}",
        f"arvore: {agora.arvore}",
        f"head: {agora.head or '(sem commit)'}",
        f"contagem: {contagem or '(não informada)'}",
        f"nao_medidos: {', '.join(nao_medidos) if nao_medidos else 'nenhum'}",
    ]
    if agora.fora_do_git:
        linhas.append(f"apareceu_fora_do_git: {_nomeia(agora.fora_do_git)}")
    novo = None
    try:
        pasta = pasta_dos_recibos(Path(agora.raiz))
        pasta.mkdir(exist_ok=True)
        destino = pasta / f"{agora.arvore}.{nome}"
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=pasta, prefix=".novo-",
                                         delete=False) as f:
            novo = Path(f.name)
            f.write("\n".join(linhas) + "\n")
        os.replace(novo, destino)
    except (OSError, SemRetrato) as e:
        if novo is not None:
            novo.unlink(missing_ok=True)
        return _recusa(nome, f"não consegui gravar: {e}")
    _diz(f"{nome} escrito em {destino}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="O recibo da medida: o que a trava do push lê.")
    sub = ap.add_subparsers(dest="verbo", required=True)
    a = sub.add_parser("abrir")
    a.add_argument("nome")
    f = sub.add_parser("fechar")
    f.add_argument("nome")
    f.add_argument("rc")
    f.add_argument("--contagem", default="")
    f.add_argument("--nao-medido", action="append", default=[], dest="nao_medidos")
    for p in (a, f):
        p.add_argument("--corrida", required=True, type=Path)
        p.add_argument("--raiz", default=".", type=Path)
    args = ap.parse_args(argv)
    if not _NOME.match(args.nome):
        _diz(f"nome inválido {args.nome!r}: só minúsculas, dígitos e hífen")
        return 2
    if args.verbo == "abrir":
        return abrir(args.nome, args.corrida, args.raiz)
    return fechar(args.nome, args.rc, args.corrida, args.raiz, args.contagem, args.nao_medidos)


if __name__ == "__main__":
    sys.exit(main())
