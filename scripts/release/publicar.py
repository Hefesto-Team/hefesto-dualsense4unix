#!/usr/bin/env python3
"""publicar.py — publica a release como rascunho, sobe os arquivos e só então a torna pública.

  publicar.py TAG --repo DONO/NOME --pasta DIST --notas ARQUIVO [--exigir PADRÃO...] [--conferir]

POR QUE ASSIM: a release imutável (`seguranca.releases_imutaveis` de `.github/repositorio.yml`) trava os
arquivos e a tag da versão no instante em que ela é publicada, e o GitHub nunca devolve uma tag que já foi
de uma release imutável. Apagar e recriar a versão (o que o fluxo antigo fazia a cada re-execução) deixa de
existir: o rascunho aceita arquivo trocado (`--clobber`), a publicada não aceita nada.

OS PASSOS, na ordem, e a saída 1 em qualquer um deles não deixa nada público:
  1. a pasta confere com o `SHA256SUMS` (o `sums.py conferir`), e tem um arquivo de cada `--exigir`;
  2. a release da tag: não existe -> nasce como rascunho (`--verify-tag`: a tag já tem de existir), com
     as notas do arquivo e as que o GitHub gera pelos rótulos de `.github/release.yml`; é rascunho -> segue;
     já é pública -> se os arquivos são os mesmos, nada a fazer; se não, recusa (uma versão publicada
     nunca se reescreve: a correção é a próxima versão);
  3. sobe cada arquivo (e o `SHA256SUMS`) com `--clobber`, que só existe para o rascunho;
  4. confere que o servidor tem exatamente os arquivos da pasta;
  5. publica (`--draft=false`).

O CONTRATO: idempotente (rodar de novo no rascunho refaz o que falta; na publicada diz que já está),
`--conferir` (diz o que faria, e não escreve), resumo numa linha. Saída: 0 feito ou já feito; 1 recusado ou
a conferência falhou; 2 uso.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sums

EXIGIDOS_DE_UMA_RELEASE = ("*.whl", "*.tar.gz", "*.AppImage", "*.deb", "*.flatpak")


def gh(*args: str, ok: bool = False) -> subprocess.CompletedProcess[str]:
    r = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    if r.returncode != 0 and not ok:
        raise SystemExit(f"publicar.py: gh {' '.join(args[:3])} falhou: {(r.stderr or r.stdout).strip()[:300]}")
    return r


def release_do_servidor(repo: str, tag: str) -> dict[str, object] | None:
    r = gh("release", "view", tag, "--repo", repo, "--json", "isDraft,assets", ok=True)
    if r.returncode != 0:
        if "not found" in (r.stderr + r.stdout).lower():
            return None
        raise SystemExit(f"publicar.py: não consegui ler a release {tag}: {(r.stderr or r.stdout).strip()[:300]}")
    dados: dict[str, object] = json.loads(r.stdout)
    return dados


def arquivos_do_servidor(release: dict[str, object]) -> dict[str, str | None]:
    return {a["name"]: a.get("digest") for a in release.get("assets", [])}  # type: ignore[union-attr]


def principal(a: argparse.Namespace) -> int:
    pasta = Path(a.pasta)
    notas = Path(a.notas)
    exigir = a.exigir if a.exigir is not None else list(EXIGIDOS_DE_UMA_RELEASE)
    if not pasta.is_dir() or not notas.is_file():
        print(f"publicar.py: sem a pasta {pasta} ou sem o arquivo de notas {notas}")
        return 2
    # 1. o que vai publicar confere com o SHA256SUMS
    ok = sums.main(["conferir", str(pasta), "--exigir", *exigir])
    if ok != 0:
        print("publicar.py: recusado: a pasta não confere com o SHA256SUMS; nada foi publicado")
        return 1
    locais = {p.relative_to(pasta).as_posix(): sums.sha256_de(p) for p in sorted(pasta.rglob("*")) if p.is_file()}
    # 2. a release da tag
    existente = release_do_servidor(a.repo, a.tag)
    if existente is not None and not existente["isDraft"]:
        remotos = arquivos_do_servidor(existente)
        mesmos = set(remotos) == set(locais) and all(
            d is None or d == f"sha256:{locais[n]}" for n, d in remotos.items()
        )
        if mesmos:
            print(f"publicar.py: {a.tag} já está publicada com os mesmos {len(locais)} arquivo(s); nada a fazer")
            return 0
        print(
            f"publicar.py: recusado: {a.tag} já está publicada com outros arquivos, e uma versão publicada nunca se "
            "reescreve; a correção é a versão seguinte"
        )
        return 1
    if a.conferir:
        estado = "criaria o rascunho, subiria" if existente is None else "subiria de novo"
        print(f"publicar.py: {a.tag}: {estado} {len(locais)} arquivo(s) e publicaria")
        return 1
    if existente is None:
        gh("release", "create", a.tag, "--repo", a.repo, "--draft", "--verify-tag",
           "--title", a.titulo or f"Hefesto - DualSense4Unix {a.tag}", "--notes-file", str(notas), "--generate-notes")
    # 3. os arquivos, com --clobber (só o rascunho aceita)
    gh("release", "upload", a.tag, "--repo", a.repo, "--clobber", *[str(pasta / n) for n in locais])
    # 4. o servidor tem exatamente a pasta
    depois = release_do_servidor(a.repo, a.tag)
    assert depois is not None
    no_servidor = arquivos_do_servidor(depois)
    faltam = sorted(set(locais) - set(no_servidor))
    sobram = sorted(set(no_servidor) - set(locais))
    trocados = sorted(n for n, d in no_servidor.items() if n in locais and d is not None and d != f"sha256:{locais[n]}")
    if faltam or sobram or trocados:
        print(f"publicar.py: recusado: o rascunho de {a.tag} não confere (faltam {faltam}, sobram {sobram}, trocados {trocados}); não foi publicado")
        return 1
    # 5. publica
    gh("release", "edit", a.tag, "--repo", a.repo, "--draft=false")
    print(f"publicar.py: {a.tag} publicada com {len(locais)} arquivo(s) e o SHA256SUMS")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("tag")
    ap.add_argument("--repo", required=True, help="DONO/NOME")
    ap.add_argument("--pasta", required=True, help="a pasta com os arquivos e o SHA256SUMS")
    ap.add_argument("--notas", required=True, help="o arquivo com as notas")
    ap.add_argument("--titulo")
    ap.add_argument("--exigir", nargs="*", default=None, help=f"padrões que a pasta tem de ter (padrão: {' '.join(EXIGIDOS_DE_UMA_RELEASE)})")
    ap.add_argument("--conferir", action="store_true", help="diz o que faria; sai 1 se faria alguma coisa")
    a = ap.parse_args(argv)
    try:
        return principal(a)
    except SystemExit as e:
        if isinstance(e.code, str):
            print(e.code)
            return 1
        raise


if __name__ == "__main__":
    sys.exit(main())
