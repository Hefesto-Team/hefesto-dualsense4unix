#!/usr/bin/env python3
"""sums.py — o `SHA256SUMS` de tudo o que a release publica, e a conferência dele.

  sums.py gerar PASTA                grava PASTA/SHA256SUMS com o hash de cada arquivo da pasta
  sums.py conferir PASTA [--exigir PADRÃO...]
                                     confere o `SHA256SUMS` contra a pasta, nos dois sentidos

O formato é o do `sha256sum`: «HASH  nome» (dois espaços), o nome relativo à pasta, em ordem. Quem baixa
confere com `sha256sum -c SHA256SUMS --ignore-missing`.

`conferir` reprova (saída 1) quando: um arquivo da pasta não está no `SHA256SUMS`; uma linha do `SHA256SUMS`
não tem arquivo; um hash não bate; ou falta um arquivo de cada padrão em `--exigir` (por exemplo `'*.whl'`).
O que o job leva de um passo ao outro (a pasta baixada dos artefatos) é conferido contra o que foi gravado
quando o `SHA256SUMS` nasceu: arquivo trocado no caminho não passa.

O CONTRATO: idempotente, `--conferir` no `gerar` (sai 1 se o arquivo mudaria), resumo numa linha, detalhe
depois ou em `--detalhe ARQ`. Saída: 0 limpo; 1 diferença; 2 uso (pasta vazia ou sem arquivo).
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _comum

NOME = "SHA256SUMS"


def sha256_de(arq: Path) -> str:
    h = hashlib.sha256()
    with arq.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def arquivos_de(pasta: Path) -> list[str]:
    return sorted(p.relative_to(pasta).as_posix() for p in pasta.rglob("*") if p.is_file() and p.name != NOME)


def texto_das_somas(pasta: Path) -> str:
    return "".join(f"{sha256_de(pasta / n)}  {n}\n" for n in arquivos_de(pasta))


def ler_somas(arq: Path) -> dict[str, str]:
    somas: dict[str, str] = {}
    for ln in arq.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        hexa, _, nome = ln.partition("  ")
        somas[nome.strip()] = hexa.strip()
    return somas


def cmd_gerar(a: argparse.Namespace) -> int:
    pasta = Path(a.pasta)
    if not pasta.is_dir() or not arquivos_de(pasta):
        print(f"sums.py gerar: a pasta {pasta} não existe ou está vazia")
        return 2
    novo = texto_das_somas(pasta)
    arq = pasta / NOME
    antigo = arq.read_text(encoding="utf-8") if arq.is_file() else None
    n = len(arquivos_de(pasta))
    if novo == antigo:
        return _comum.encerrar("sums", pasta, 0, f"sums.py gerar: {NOME} já tem os {n} arquivo(s)", [], a.detalhe)
    if a.conferir:
        return _comum.encerrar("sums", pasta, 1, f"sums.py gerar: {NOME} mudaria ({n} arquivo(s))", [], a.detalhe)
    arq.write_text(novo, encoding="utf-8")
    return _comum.encerrar("sums", pasta, 0, f"sums.py gerar: {NOME} com {n} arquivo(s)", [], a.detalhe)


def cmd_conferir(a: argparse.Namespace) -> int:
    pasta = Path(a.pasta)
    arq = pasta / NOME
    if not arq.is_file():
        print(f"sums.py conferir: sem {arq}")
        return 1
    somas = ler_somas(arq)
    reais = arquivos_de(pasta)
    defeitos: list[str] = []
    defeitos += [f"fora do {NOME}: {n}" for n in reais if n not in somas]
    defeitos += [f"no {NOME} e sem arquivo: {n}" for n in somas if n not in reais]
    defeitos += [f"hash diferente: {n}" for n in reais if n in somas and sha256_de(pasta / n) != somas[n]]
    defeitos += [f"falta um arquivo {p}" for p in (a.exigir or []) if not any(fnmatch.fnmatch(n, p) for n in reais)]
    if defeitos:
        return _comum.encerrar("sums", pasta, 1, f"sums.py conferir: {len(defeitos)} defeito(s) em {len(reais)} arquivo(s)", defeitos, a.detalhe)
    return _comum.encerrar("sums", pasta, 0, f"sums.py conferir: {len(reais)} arquivo(s) batem com o {NOME}", [], a.detalhe)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("gerar")
    p.add_argument("pasta")
    p.add_argument("--conferir", action="store_true")
    p.add_argument("--detalhe", type=Path)
    p.set_defaults(f=cmd_gerar)
    p = sub.add_parser("conferir")
    p.add_argument("pasta")
    p.add_argument("--exigir", nargs="*", default=[], help="padrões de nome que têm de existir (um arquivo de cada)")
    p.add_argument("--detalhe", type=Path)
    p.set_defaults(f=cmd_conferir)
    a = ap.parse_args(argv)
    return int(a.f(a))


if __name__ == "__main__":
    sys.exit(main())
