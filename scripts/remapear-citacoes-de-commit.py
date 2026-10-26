#!/usr/bin/env python3
"""remapear-citacoes-de-commit.py — a citação de commit anda junto com o mapa da história.

Uma reescrita troca o SHA de cada commit, e a prosa, o comentário e o id de teste que citam o
velho passam a apontar para o nada. O mapa de cada reescrita (`filter-repo/commit-map`, ou o
`mapa-agosto.txt`) diz «velho novo»; este script segue a CADEIA de mapas, na ordem (agosto, 15/09,
a reescrita seguinte), e troca o SHA citado pelo último elo. Sem `--escrever`, só mostra a lista
seca (`velho -> novo`), que se revê antes de gravar.

Só troca o que resolve sem ambiguidade:

* o token tem de ter 7 a 40 dígitos hexadecimais (o comprimento que o `git log --abbrev` dá) e
  ser prefixo de UM só SHA conhecido (os dos mapas e os commits do repositório); prefixo de dois
  é ambíguo e fica;
* o token só de algarismos (ou só de letras) que resolve pode ser um número (ou uma palavra), e
  não um commit: fica, e vai para a lista dos «a conferir à mão», com o novo ao lado; quem
  coordena confere e grava com `--com-os-a-conferir` (medido em 21/10/2026: as doze citações só de
  algarismos que a árvore tinha eram todas de commit, e calá-las deixava a citação morta sem aviso);
* o último elo tem de ser outro SHA (commit podado vira zero no mapa: fica, e vai para a conta
  dos «podados») e, havendo repositório, tem de existir nele; o texto novo mantém o comprimento
  do citado, então nenhuma citação `arquivo:linha` anda, e tem de ser prefixo de UM só SHA
  conhecido (o curto que nasce ambíguo fica, e vai para a lista);
* hash do kernel ou do BlueZ não é prefixo de nenhum SHA nosso: não resolve, não se toca.

Cada mapa vem de `--mapa`; sem nenhum, vale a cadeia da casa. O mapa PADRÃO que não existe ainda
(o da reescrita seguinte) é dito na saída e pulado; um `--mapa` que não existe é erro, porque cadeia
sem um elo troca MENOS do que devia e parece verde.

A PONTE (medida em 21/10/2026). Os commits que o mapa de 15/09 devolve NÃO são os do `dev` de hoje:
aquela reescrita saiu num clone à parte, e o que o GitHub e a mesa têm é outra história, com a mesma
data e o mesmo assunto em cada commit e árvore diferente. Sem uma ponte, a cadeia termina num SHA
que não existe em lugar nenhum (e o guarda acima o recusa). `--gerar-ponte` faz o elo que falta,
«SHA de 15/09 -> commit do `dev` com a mesma data de autor e o mesmo assunto», só quando esse par é
único nos dois lados. O mapa da reescrita seguinte tem como chave os SHAs do `dev` de hoje, e por
isso encaixa depois da ponte: a segunda passada é a mesma linha com ele na lista.
"""

from __future__ import annotations

import argparse
import bisect
import os
import re
import subprocess
import sys
from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from pathlib import Path

MINIMO = 7
"""Dígitos mínimos do token. Medido em 21/10/2026: das citações de commit que a cadeia de agosto e
de 15/09 ainda devolve, nenhuma tem 9 dígitos ou mais (todas têm 7 ou 8); a ambiguidade é que
segura o resto, contra os ~14 mil SHAs conhecidos."""

DESENVOLVIMENTO = Path(os.environ.get("HEFESTO_DESENVOLVIMENTO", Path.home() / "Desenvolvimento"))
PONTE_DA_CASA = Path.home() / ".local/state/hefesto-casa/mapas-de-commit/ponte-15-09-para-dev.txt"
MAPAS_DA_CASA: tuple[Path, ...] = (
    DESENVOLVIMENTO / "_backup-hefesto-antes-da-reescrita/2026-10-05/mapa-agosto.txt",
    DESENVOLVIMENTO / "_reescrita/hefesto.git/filter-repo/commit-map",
    PONTE_DA_CASA,
    DESENVOLVIMENTO / "_reescrita-historia-sem-rastro/uniao.git/filter-repo/commit-map",
)
"""Agosto, 15/09, a ponte de 15/09 até o `dev` e a reescrita da história sem rastro, nesta ordem.
A ponte sai de `--gerar-ponte`; o último mapa nasce no degrau 10."""

_ZERO = "0" * 40
_HEX40 = re.compile(r"^[0-9a-f]{40}$")


class MapaInvalido(ValueError):
    """O arquivo não é um mapa «velho novo» de SHAs inteiros."""


def ler_mapa(caminho: Path) -> dict[str, str]:
    """`velho -> novo` de um mapa; cabeçalho `old new` e linha vazia passam, o resto tem de ser SHA."""
    mapa: dict[str, str] = {}
    for n, linha in enumerate(caminho.read_text(encoding="utf-8").splitlines(), 1):
        partes = linha.split()
        if not partes or partes[0] == "old":
            continue
        if len(partes) != 2 or not (_HEX40.match(partes[0]) and _HEX40.match(partes[1])):
            raise MapaInvalido(f"{caminho}:{n}: esperava «velho novo» de 40 dígitos")
        mapa[partes[0]] = partes[1]
    return mapa


@dataclass
class Cadeia:
    """Os mapas na ordem, os SHAs do repositório e o que a prova de ambiguidade consulta."""

    mapas: list[dict[str, str]]
    no_repositorio: Collection[str] | None = None
    """Os commits que o repositório tem. `None` = sem repositório: o último elo não é conferido.
    Um repositório que respondeu VAZIO não é «sem repositório»: nada nele existe."""
    _universo: list[str] = field(init=False, default_factory=list)
    _velhos: set[str] = field(init=False, default_factory=set)
    _existem: frozenset[str] | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        for m in self.mapas:
            self._velhos.update(m)
        todos = set(self._velhos)
        for m in self.mapas:
            todos.update(m.values())
        todos.update(self.no_repositorio or ())
        todos.discard(_ZERO)
        self._universo = sorted(todos)
        if self.no_repositorio is not None:
            self._existem = frozenset(self.no_repositorio)

    def _prefixados(self, token: str) -> list[str]:
        i = bisect.bisect_left(self._universo, token)
        achados: list[str] = []
        while i < len(self._universo) and self._universo[i].startswith(token):
            achados.append(self._universo[i])
            i += 1
            if len(achados) > 1:
                break
        return achados

    def resolve(self, token: str) -> str | None:
        """O SHA inteiro que o token nomeia, só se UM e só um SHA conhecido começa por ele."""
        achados = self._prefixados(token)
        if len(achados) != 1 or achados[0] not in self._velhos:
            return None
        return achados[0]

    def seguir(self, sha: str) -> str:
        """O último elo da cadeia; `_ZERO` se algum mapa diz que o commit foi podado."""
        for m in self.mapas:
            if sha in m:
                sha = m[sha]
                if sha == _ZERO:
                    return _ZERO
        return sha

    def existe(self, sha: str) -> bool:
        return self._existem is None or sha in self._existem

    def unico(self, curto: str, sha: str) -> bool:
        """O curto nomeia `sha` e só ele, entre os SHAs conhecidos."""
        return self._prefixados(curto) == [sha]


@dataclass
class Troca:
    linha: int
    velho: str
    novo: str


@dataclass
class Resultado:
    texto: str
    trocas: list[Troca] = field(default_factory=list)
    podados: list[Troca] = field(default_factory=list)
    """Citações de commit que o mapa diz podado (o novo é zero): ficam."""
    ausentes: list[Troca] = field(default_factory=list)
    """Citações cujo último elo não existe no repositório: ficam até ele existir."""
    a_conferir: list[Troca] = field(default_factory=list)
    """Só algarismos ou só letras, ou o curto novo ambíguo: ficam (salvo `com_os_a_conferir`)."""


def _tem_letra_e_numero(token: str) -> bool:
    return bool(re.search(r"[a-f]", token) and re.search(r"[0-9]", token))


def remapear_texto(
    texto: str, cadeia: Cadeia, minimo: int = MINIMO, com_os_a_conferir: bool = False
) -> Resultado:
    """Troca cada citação que a cadeia resolve; devolve o texto novo e a lista seca."""
    res = Resultado(texto)
    achar = re.compile(r"\b[0-9a-f]{%d,40}\b" % minimo)

    def troca(m: re.Match[str]) -> str:
        token = m.group(0)
        velho = cadeia.resolve(token)
        if velho is None:
            return token
        novo = cadeia.seguir(velho)
        if novo == velho:
            return token
        linha = texto.count("\n", 0, m.start()) + 1
        if novo == _ZERO:
            res.podados.append(Troca(linha, token, ""))
            return token
        curto = novo[: len(token)]
        if not cadeia.existe(novo):
            res.ausentes.append(Troca(linha, token, curto))
            return token
        if not cadeia.unico(curto, novo):
            res.a_conferir.append(Troca(linha, token, curto))
            return token
        if not _tem_letra_e_numero(token) and not com_os_a_conferir:
            res.a_conferir.append(Troca(linha, token, curto))
            return token
        res.trocas.append(Troca(linha, token, curto))
        return curto

    res.texto = achar.sub(troca, texto)
    return res


def _arquivos_do_git(raiz: Path, caminhos: Sequence[str]) -> list[Path]:
    """Os arquivos versionados sob cada caminho. Caminho que não casa nada é erro, não silêncio:
    um `$PASTAS` sem aspas no zsh chega como UM caminho com espaços e varreria zero arquivo."""
    achados: list[Path] = []
    for caminho in caminhos:
        saida = subprocess.run(
            ["git", "-C", str(raiz), "ls-files", "-z", "--", caminho],
            capture_output=True,
            check=True,
        ).stdout
        do_caminho = [raiz / p.decode() for p in saida.split(b"\0") if p]
        if not do_caminho:
            raise FileNotFoundError(f"nenhum arquivo versionado casa com «{caminho}»")
        achados.extend(do_caminho)
    return achados


def _commits_do_repositorio(raiz: Path) -> list[str]:
    """Os commits do repositório. Falha do git é erro: lista vazia desligaria a guarda de existência."""
    proc = subprocess.run(
        ["git", "-C", str(raiz), "--no-replace-objects", "rev-list", "--all"],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.split()


def _identidades(
    raiz: Path, shas: Sequence[str] | None, ref: str | None
) -> dict[str, tuple[str, str]]:
    """`sha -> (data de autor, assunto)` dos commits pedidos (ou de tudo o que `ref` alcança)."""
    cmd = ["git", "-C", str(raiz), "--no-replace-objects", "log", "--format=%H%x1f%at%x1f%s"]
    if shas is None:
        cmd.append(ref or "HEAD")
        entrada = None
    else:
        cmd += ["--no-walk=unsorted", "--stdin"]
        entrada = "\n".join(shas) + "\n"
    proc = subprocess.run(cmd, input=entrada, capture_output=True, text=True, check=False)
    ids: dict[str, tuple[str, str]] = {}
    for linha in proc.stdout.splitlines():
        sha, _, resto = linha.partition("\x1f")
        data, _, assunto = resto.partition("\x1f")
        ids[sha] = (data, assunto)
    return ids


def gerar_ponte(
    mapa: dict[str, str], repo_dos_alvos: Path, repo: Path, ref: str = "dev"
) -> tuple[dict[str, str], int]:
    """O elo `valor do mapa -> commit de `ref` em `repo``, pela data de autor e pelo assunto.

    Só entra o par único do lado do `dev` (dois commits de `ref` com a mesma data e o mesmo assunto
    são ambíguos e ficam de fora). Do outro lado a repetição vale: o clone de 15/09 guarda cópias do
    mesmo commit em ramos diferentes, e todas desembocam no mesmo commit do `dev`. Devolve a ponte
    e quantos valores ficaram sem par.
    """
    alvos = sorted({v for v in mapa.values() if v != _ZERO})
    dos_alvos = _identidades(repo_dos_alvos, alvos, None)
    daqui: dict[tuple[str, str], list[str]] = {}
    for sha, ident in _identidades(repo, None, ref).items():
        daqui.setdefault(ident, []).append(sha)
    ponte: dict[str, str] = {}
    for alvo in alvos:
        par_do_alvo = dos_alvos.get(alvo)
        pares = daqui.get(par_do_alvo, []) if par_do_alvo is not None else []
        if len(pares) == 1:
            ponte[alvo] = pares[0]
    return ponte, len(alvos) - len(ponte)


def escolher_mapas(pedidos: Sequence[str]) -> tuple[list[Path], list[Path]]:
    """(mapas que valem, mapas da casa ainda ausentes). `--mapa` ausente é erro; o da casa, não."""
    if pedidos:
        caminhos = [Path(p) for p in pedidos]
        faltam = [p for p in caminhos if not p.is_file()]
        if faltam:
            raise FileNotFoundError(f"mapa que não existe: {', '.join(map(str, faltam))}")
        return caminhos, []
    existem = [p for p in MAPAS_DA_CASA if p.is_file()]
    ausentes = [p for p in MAPAS_DA_CASA if not p.is_file()]
    if existem != list(MAPAS_DA_CASA[: len(existem)]):
        raise FileNotFoundError(f"elo no meio da cadeia ausente: {', '.join(map(str, ausentes))}")
    if not existem:
        raise FileNotFoundError("nenhum mapa da casa existe")
    return existem, ausentes


def _nome_do_mapa(p: Path) -> str:
    return p.parts[-4] if p.name == "commit-map" and len(p.parts) >= 4 else p.name


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("caminhos", nargs="*", help="arquivos ou pastas versionados a varrer")
    ap.add_argument("--mapa", action="append", default=[], help="um mapa da cadeia, na ordem")
    ap.add_argument("--raiz", default=".", help="a raiz do repositório (padrão: o diretório atual)")
    ap.add_argument("--minimo", type=int, default=MINIMO, help=f"dígitos mínimos (padrão {MINIMO})")
    ap.add_argument("--escrever", action="store_true", help="grava; sem isto só mostra")
    ap.add_argument(
        "--com-os-a-conferir",
        action="store_true",
        help="troca também o token só de algarismos ou só de letras, depois de conferido à mão",
    )
    ap.add_argument(
        "--gerar-ponte",
        nargs=3,
        metavar=("MAPA", "REPO_DOS_ALVOS", "SAIDA"),
        help="escreve em SAIDA a ponte dos valores de MAPA (que moram em REPO_DOS_ALVOS) até o dev",
    )
    ap.add_argument("--ref", default="dev", help="a ref do repositório onde a ponte desemboca")
    args = ap.parse_args(argv)

    raiz = Path(args.raiz).resolve()
    if args.gerar_ponte:
        mapa, alvos, saida = (Path(p) for p in args.gerar_ponte)
        try:
            ponte, sem_par = gerar_ponte(ler_mapa(mapa), alvos, raiz, args.ref)
        except (FileNotFoundError, MapaInvalido) as exc:
            print(f"remapear-citacoes-de-commit: {exc}", file=sys.stderr)
            return 2
        saida.parent.mkdir(parents=True, exist_ok=True)
        saida.write_text("old new\n" + "".join(f"{k} {v}\n" for k, v in sorted(ponte.items())))
        print(f"ponte: {len(ponte)} pares em {saida}; sem par único (ficam de fora): {sem_par}")
        return 0
    if not args.caminhos:
        ap.error("faltam os caminhos a varrer")
    try:
        mapas, ausentes = escolher_mapas(args.mapa)
        cadeia = Cadeia([ler_mapa(p) for p in mapas], _commits_do_repositorio(raiz))
        arquivos = _arquivos_do_git(raiz, args.caminhos)
    except (FileNotFoundError, MapaInvalido, subprocess.CalledProcessError) as exc:
        print(f"remapear-citacoes-de-commit: {exc}", file=sys.stderr)
        return 2

    print("cadeia:", " -> ".join(_nome_do_mapa(p) for p in mapas))
    for p in ausentes:
        print(f"mapa ainda ausente (as citações dele ficam): {p}")

    total = podados = ausentes_do_repo = a_conferir = com_troca = 0
    for arq in arquivos:
        if arq.is_symlink() or not arq.is_file():
            continue
        try:
            texto = arq.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue
        res = remapear_texto(texto, cadeia, args.minimo, args.com_os_a_conferir)
        podados += len(res.podados)
        ausentes_do_repo += len(res.ausentes)
        a_conferir += len(res.a_conferir)
        rel = arq.relative_to(raiz)
        for t in res.podados:
            print(f"   fica, podado no mapa: {rel}:{t.linha} {t.velho}")
        for t in res.ausentes:
            print(
                f"   fica, o novo não existe no repositório: {rel}:{t.linha} {t.velho} -> {t.novo}"
            )
        for t in res.a_conferir:
            print(f"   fica, a conferir à mão: {rel}:{t.linha} {t.velho} -> {t.novo}")
        if not res.trocas:
            continue
        com_troca += 1
        total += len(res.trocas)
        print(f"{rel}: {len(res.trocas)} trocas")
        for t in res.trocas:
            print(f"   {rel}:{t.linha} {t.velho} -> {t.novo}")
        if args.escrever:
            arq.write_bytes(res.texto.encode("utf-8"))
    verbo = "escritas" if args.escrever else "a escrever (sem --escrever)"
    print(
        f"total: {total} trocas em {com_troca} arquivos, {verbo}; "
        f"podados (ficam): {podados}; sem o commit novo no repositório (ficam): {ausentes_do_repo}; "
        f"a conferir à mão (ficam): {a_conferir}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
