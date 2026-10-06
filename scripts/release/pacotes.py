#!/usr/bin/env python3
"""pacotes.py — os arquivos de pacote de cada distribuição, na versão da tag e com o hash do tarball dela.

  pacotes.py preparar --numero V --tarball ARQ --saida DIR   copia o PKGBUILD, o .spec, o control e o nix para
                                                             DIR, conferindo a versão e gravando o hash no PKGBUILD
  pacotes.py abrir-pr --numero V --pasta DIR --repos LISTA   abre o PR de atualização em cada repositório de pacote

A versão dos quatro arquivos já foi gravada, no commit da release, pelo `versao.py gravar`: aqui ela só é
CONFERIDA contra a tag (um arquivo de pacote com outra versão reprova). O que a tag ainda não tinha é o hash do
tarball que o GitHub gera dela (`/archive/refs/tags/vV.tar.gz`, o mesmo que o `source=` do PKGBUILD baixa), e é
ele que `preparar` grava na cópia. O Nix compila da árvore local (`src = ../..`) e não leva hash de tarball.

`abrir-pr` recebe uma lista `DONO/NOME[:distro]` separada por vírgula (a distro é arch, fedora, debian ou nix; o
padrão é arch): clona o repositório, põe os arquivos dessa distro na raiz dele, commita com o autor do commit
da tag e abre o PR. O AUR e o Flathub são contas de quem mantém e não passam por aqui: a primeira publicação lá
é à mão, com os arquivos do artefato.

O CONTRATO: idempotente, `--conferir` no `preparar`, resumo numa linha. Saída: 0 feito; 1 a versão de um arquivo
de pacote não é a da tag, ou `--conferir` com o que fazer; 2 uso ou o que falta.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _comum
import sums

# distro -> [(arquivo na árvore, regex da versão dentro dele)]
ARQUIVOS = {
    "arch": [("packaging/arch/PKGBUILD", r"^pkgver=(\S+)")],
    "fedora": [("packaging/fedora/hefesto-dualsense4unix.spec", r"^Version:\s*(\S+)")],
    "debian": [("packaging/debian/control", r"^Version:\s*(\S+)")],
    "nix": [("packaging/nix/package.nix", r'version\s*=\s*"([^"]+)";')],
}


def preparar(a: argparse.Namespace) -> int:
    raiz = _comum.raiz_de(a.raiz)
    tarball = Path(a.tarball)
    if not tarball.is_file():
        print(f"pacotes.py preparar: sem o tarball {tarball}")
        return 2
    erros: list[str] = []
    for lista in ARQUIVOS.values():
        for rel, padrao in lista:
            arq = raiz / rel
            m = re.search(padrao, arq.read_text(encoding="utf-8"), re.MULTILINE) if arq.is_file() else None
            if not m:
                erros.append(f"{rel}: sem a linha da versão")
            elif m.group(1) != a.numero:
                erros.append(f"{rel}: diz {m.group(1)} e a tag é {a.numero}")
    if erros:
        return _comum.encerrar("pacotes", raiz, 1, f"pacotes.py preparar: {len(erros)} arquivo(s) de pacote fora da versão {a.numero}", erros, None)
    saida = Path(a.saida)
    hexa = sums.sha256_de(tarball)
    mudancas = []
    for distro, lista in ARQUIVOS.items():
        for rel, _p in lista:
            destino = saida / distro / Path(rel).name
            texto = (raiz / rel).read_text(encoding="utf-8")
            if distro == "arch":
                texto, n = re.subn(r"^sha256sums=\(.*\)\s*$", f"sha256sums=('{hexa}')", texto, count=1, flags=re.MULTILINE)
                if n != 1:
                    return _comum.encerrar("pacotes", raiz, 2, "pacotes.py preparar: o PKGBUILD não tem a linha sha256sums=(...)", [], None)
            if not destino.is_file() or destino.read_text(encoding="utf-8") != texto:
                mudancas.append(f"{distro}/{destino.name}")
                if not a.conferir:
                    destino.parent.mkdir(parents=True, exist_ok=True)
                    destino.write_text(texto, encoding="utf-8")
    if a.conferir and mudancas:
        return _comum.encerrar("pacotes", raiz, 1, f"pacotes.py preparar: {len(mudancas)} arquivo(s) mudariam em {saida}", mudancas, None)
    if not mudancas:
        return _comum.encerrar("pacotes", raiz, 0, f"pacotes.py preparar: {saida} já tem os arquivos da {a.numero} (hash {hexa[:12]})", [], None)
    return _comum.encerrar("pacotes", raiz, 0, f"pacotes.py preparar: {len(mudancas)} arquivo(s) em {saida} na {a.numero} (hash {hexa[:12]})", mudancas, None)


def _rodar(*cmd: str, cwd: Path | None = None) -> str:
    r = subprocess.run(list(cmd), cwd=cwd, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        raise SystemExit(f"pacotes.py abrir-pr: `{' '.join(cmd[:3])}` falhou: {(r.stderr or r.stdout).strip()[:300]}")
    return r.stdout


def abrir_pr(a: argparse.Namespace) -> int:
    raiz = _comum.raiz_de(a.raiz)
    pasta = Path(a.pasta)
    pedidos = [x.strip() for x in a.repos.split(",") if x.strip()]
    if not pedidos:
        print("pacotes.py abrir-pr: a lista de repositórios está vazia; nada a abrir")
        return 0
    autor = _comum.git(raiz, "log", "-1", "--format=%an%x1f%ae", "HEAD", ok=True).strip().split("\x1f")
    if len(autor) != 2 or not all(autor):
        print("pacotes.py abrir-pr: não achei o autor do commit da tag; sem ele o PR não abre")
        return 2
    abertos = []
    for pedido in pedidos:
        repo, _, distro = pedido.partition(":")
        distro = distro or "arch"
        origem = pasta / distro
        if distro not in ARQUIVOS or not origem.is_dir():
            print(f"pacotes.py abrir-pr: {pedido}: sem os arquivos da distro «{distro}» em {pasta}")
            return 2
        if a.conferir:
            abertos.append(f"{repo} ({distro}): abriria o PR atualiza-{a.numero}")
            continue
        with tempfile.TemporaryDirectory(prefix="pacotes-") as tmp:
            clone = Path(tmp) / "repo"
            _rodar("gh", "repo", "clone", repo, str(clone), "--", "--depth", "1")
            ramo = f"atualiza-{a.numero}"
            _rodar("git", "checkout", "-B", ramo, cwd=clone)
            for arq in origem.iterdir():
                shutil.copy2(arq, clone / arq.name)
            _rodar("git", "add", "-A", cwd=clone)
            if not _rodar("git", "status", "--porcelain", cwd=clone).strip():
                abertos.append(f"{repo} ({distro}): já está na {a.numero}")
                continue
            _rodar("git", "-c", f"user.name={autor[0]}", "-c", f"user.email={autor[1]}", "commit", "-m",
                   f"Atualiza para a versão {a.numero}", cwd=clone)
            _rodar("git", "push", "--force-with-lease", "origin", ramo, cwd=clone)
            _rodar("gh", "pr", "create", "--repo", repo, "--head", ramo, "--title", f"Atualiza para a versão {a.numero}",
                   "--body", f"A versão {a.numero} do Hefesto saiu; os arquivos de pacote seguem a tag.", cwd=clone)
            abertos.append(f"{repo} ({distro}): PR aberto de {ramo}")
    codigo = 1 if (a.conferir and abertos) else 0
    return _comum.encerrar("pacotes", raiz, codigo, f"pacotes.py abrir-pr: {len(abertos)} repositório(s) tratados na {a.numero}", abertos, None)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--raiz", help="a árvore (padrão: a deste script)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("preparar")
    p.add_argument("--numero", required=True)
    p.add_argument("--tarball", required=True)
    p.add_argument("--saida", required=True)
    p.add_argument("--conferir", action="store_true")
    p.set_defaults(f=preparar)
    p = sub.add_parser("abrir-pr")
    p.add_argument("--numero", required=True)
    p.add_argument("--pasta", required=True)
    p.add_argument("--repos", required=True, help="DONO/NOME[:distro], separados por vírgula")
    p.add_argument("--conferir", action="store_true")
    p.set_defaults(f=abrir_pr)
    a = ap.parse_args(argv)
    return int(a.f(a))


if __name__ == "__main__":
    sys.exit(main())
