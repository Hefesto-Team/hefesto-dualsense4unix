#!/usr/bin/env python3
"""O recibo da medida: o que a trava do push da máquina lê, e a memória do verde de cada portão.

Dois assuntos, duas pastas do git comum:

- o RECIBO da camada completa, `hefesto-recibos/<árvore>.portoes-completo`: nasce só do verde e só da
  árvore que foi medida (`abrir` e `fechar`);
- a MEMÓRIA do verde, `hefesto-memoria/<portão>.<chave>`, noutra pasta de propósito (a trava do push lê
  a dos recibos e nada mais): um portão que passou sobre os MESMOS bytes que leu não roda de novo. A chave é o hash do conteúdo que ele lê (`chaves`), a anotação é do fim da corrida
  (`anotar`), e o recibo diz quais portões vieram da memória (`--lembrado`).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

PASTA = "hefesto-recibos"

_NOME = re.compile(r"^[a-z0-9][a-z0-9-]*$")

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
           nao_medidos: list[str], lembrados: list[str] | None = None) -> int:
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
        f"aberta: {aberta.get('aberto_em', '(sem registro)')}",
        f"arvore: {agora.arvore}",
        f"head: {agora.head or '(sem commit)'}",
        f"contagem: {contagem or '(não informada)'}",
        f"nao_medidos: {', '.join(nao_medidos) if nao_medidos else 'nenhum'}",
        f"lembrados: {', '.join(lembrados) if lembrados else 'nenhum'}",
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


# --- A MEMÓRIA DO VERDE ---------------------------------------------------------------------------
#
# Um portão que passou sobre os mesmos bytes que leu não precisa passar de novo. A chave de um portão é o
# hash do que ELE lê: por padrão a árvore INTEIRA (o rastreado, como está no disco, mais o que é novo e não
# é ignorado, mais o ignorado de `scripts/`: quatro portões abrem lá os dispositivos de trabalho que o git
# não leva, medido em 06/10/2026 por `strace`), a linha do portão, o arquivo que ele chama, o Python e o
# Chrome. Sem a quinta coluna da lista, vale o lado seguro: qualquer byte mudado roda o portão de novo.
#
# A quinta coluna estreita (globs, que alcançam também o ignorado) ou declara o que a árvore não guarda:
#   @sempre  o portão lê a máquina ou a história do git, e nunca é lembrado;
#   @dia     o portão compara com a data de hoje (prazo que vence), e a data entra na chave;
#   @head    o portão lê a história a partir do HEAD, e o HEAD entra na chave.
# Glob que não casa arquivo nenhum é erro de digitação, e erro de digitação não vira memória: o portão roda.

MEMORIA = "hefesto-memoria"
_VERSAO_DA_CHAVE = "1"
_GUARDA = 3
_VALIDADE = 30 * 86400
_SINAIS = {"@sempre", "@dia", "@head"}
_IGNORADOS_QUE_ENTRAM = ("scripts",)
_CHROME = "/usr/bin/google-chrome"


def _sha_do_arquivo(caminho: Path) -> str:
    try:
        if caminho.is_symlink():
            return "l:" + os.readlink(caminho)
        if not caminho.is_file():
            return "-"
        h = hashlib.sha256()
        with caminho.open("rb") as f:
            for bloco in iter(lambda: f.read(1 << 20), b""):
                h.update(bloco)
        return h.hexdigest()
    except OSError:
        return "-"


def _stat_de(caminho: str) -> str:
    try:
        st = os.stat(os.path.realpath(caminho))
    except OSError:
        return "ausente"
    return f"{st.st_size}:{st.st_mtime_ns}"


def _ambiente_da_chave() -> str:
    """O que, fora da árvore, muda o veredito: o Python, o que ele tem instalado e o Chrome."""
    try:
        instalado = _stat_de(sysconfig.get_paths()["purelib"])
    except (KeyError, OSError):
        instalado = "?"
    return "|".join((_VERSAO_DA_CHAVE, sys.version, sys.prefix, instalado, _stat_de(_CHROME)))


class Entradas:
    """Os arquivos que uma chave pode ler, listados uma vez por corrida e lidos uma vez por arquivo."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self._sha: dict[str, str] = {}
        self._base: set[str] | None = None
        self._globs: dict[str, set[str]] = {}

    def _lista(self, *args: str) -> set[str]:
        return set(_lista_z(_git(self.raiz, "ls-files", "-z", *args)))

    def base(self) -> set[str]:
        if self._base is None:
            achados = self._lista("--cached", "--others", "--exclude-standard")
            for pasta in _IGNORADOS_QUE_ENTRAM:
                achados |= self._lista("--others", "--ignored", "--exclude-standard", "--", pasta)
            self._base = achados
        return self._base

    def glob(self, padrao: str) -> set[str]:
        if padrao not in self._globs:
            pathspec = f":(glob){padrao}"
            achados = self._lista("--cached", "--others", "--exclude-standard", "--", pathspec)
            achados |= self._lista("--others", "--ignored", "--exclude-standard", "--", pathspec)
            self._globs[padrao] = achados
        return self._globs[padrao]

    def sha(self, rel: str) -> str:
        if rel not in self._sha:
            self._sha[rel] = _sha_do_arquivo(self.raiz / rel)
        return self._sha[rel]


def _avisa(texto: str) -> None:
    print(f"memória: {texto}", file=sys.stderr, flush=True)


def chave_do_portao(ent: Entradas, ambiente: str, ficha: str, runner: str, argv: str,
                    entradas: list[str]) -> str | None:
    """A chave do portão, ou None quando ele não pode ser lembrado."""
    sinais = [e for e in entradas if e.startswith("@")]
    globs = [e for e in entradas if not e.startswith("@")]
    desconhecidos = [s for s in sinais if s not in _SINAIS]
    if desconhecidos:
        _avisa(f"{ficha}: sinal desconhecido {', '.join(desconhecidos)} na quinta coluna; o portão roda sempre")
        return None
    if "@sempre" in sinais:
        return None
    arquivos: set[str] = set()
    if globs:
        for padrao in globs:
            casados = ent.glob(padrao)
            if not casados:
                _avisa(f"{ficha}: a entrada «{padrao}» não casa arquivo nenhum; o portão roda sempre")
                return None
            arquivos |= casados
    else:
        arquivos = set(ent.base())
    palavras = argv.split()
    for pedaco in palavras:
        if pedaco.startswith("-") or any(c in pedaco for c in "*?[=$"):
            continue
        if (ent.raiz / pedaco).is_file():
            arquivos.add(pedaco)
    h = hashlib.sha256()
    h.update(f"{ambiente}\n{ficha}|{runner}|{argv}\n".encode())
    if runner == "bin" and palavras:
        h.update(f"bin:{palavras[0]}:{_stat_de(palavras[0])}\n".encode())
    if "@dia" in sinais:
        h.update(f"dia:{date.today().isoformat()}\n".encode())
    if "@head" in sinais:
        try:
            h.update(f"head:{_git(ent.raiz, 'rev-parse', 'HEAD').strip()}\n".encode())
        except SemRetrato:
            return None
    for rel in sorted(arquivos):
        h.update(f"{rel}\0{ent.sha(rel)}\n".encode())
    return h.hexdigest()[:32]


def pasta_da_memoria(raiz: Path) -> Path:
    return pasta_dos_recibos(raiz).parent / MEMORIA


def _ultimo_ms(pasta: Path, ficha: str) -> int:
    """A duração da última corrida verde do portão: serve para escalonar o mais lento primeiro."""
    melhor: tuple[float, int] | None = None
    for arq in pasta.glob(f"{ficha}.*"):
        try:
            quando = arq.stat().st_mtime
            ms = int(json.loads(arq.read_text(encoding="utf-8")).get("ms", 0))
        except (OSError, ValueError, TypeError):
            continue
        if melhor is None or quando > melhor[0]:
            melhor = (quando, ms)
    return melhor[1] if melhor else 0


def chaves(raiz: Path, linhas: list[str]) -> int:
    """Lê `ficha|runner|argv|entradas` e escreve `ficha<TAB>chave<TAB>ms` (chave vazia: não se lembra)."""
    try:
        topo = Path(_git(raiz, "rev-parse", "--show-toplevel").strip()).resolve()
        pasta = pasta_da_memoria(topo)
        ent = Entradas(topo)
        ambiente = _ambiente_da_chave()
        saida: list[str] = []
        for linha in linhas:
            if not linha.strip():
                continue
            campos = [*linha.rstrip("\n").split("|", 3), "", "", "", ""][:4]
            ficha, runner, argv, entradas = campos
            if not _NOME.match(ficha):
                _avisa(f"ficha inválida {ficha!r}; o portão roda sempre")
                saida.append(f"{ficha}\t\t0")
                continue
            chave = chave_do_portao(ent, ambiente, ficha, runner, argv, entradas.split())
            saida.append(f"{ficha}\t{chave or ''}\t{_ultimo_ms(pasta, ficha)}")
        pasta.mkdir(parents=True, exist_ok=True)
    except (SemRetrato, OSError) as e:
        _avisa(f"sem memória nesta corrida — {e}")
        return 1
    print(f"#pasta\t{pasta}")
    print("\n".join(saida))
    return 0


def anotar(raiz: Path, linhas: list[str]) -> int:
    """Grava o verde (`ficha<TAB>chave<TAB>ms`) e poda: poucas chaves por portão, nenhuma velha."""
    try:
        topo = Path(_git(raiz, "rev-parse", "--show-toplevel").strip()).resolve()
        pasta = pasta_da_memoria(topo)
        pasta.mkdir(parents=True, exist_ok=True)
        quando = datetime.now().astimezone().isoformat(timespec="seconds")
        for linha in linhas:
            campos = linha.rstrip("\n").split("\t")
            if len(campos) != 3 or not campos[1] or not _NOME.match(campos[0]):
                continue
            ficha, chave, ms = campos
            novo = None
            try:
                with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=pasta, prefix=".novo-",
                                                 delete=False) as f:
                    novo = Path(f.name)
                    f.write(json.dumps({"portao": ficha, "chave": chave, "data": quando,
                                        "ms": int(ms) if ms.isdigit() else 0}))
                os.replace(novo, pasta / f"{ficha}.{chave}")
            except OSError:
                if novo is not None:
                    novo.unlink(missing_ok=True)
        agora = time.time()
        por_ficha: dict[str, list[tuple[float, Path]]] = {}
        for arq in pasta.iterdir():
            ficha, ponto, chave = arq.name.partition(".")
            if not ponto or ficha.startswith(".") or not chave:
                continue
            try:
                por_ficha.setdefault(ficha, []).append((arq.stat().st_mtime, arq))
            except OSError:
                continue
        for arquivos in por_ficha.values():
            for i, (mtime, arq) in enumerate(sorted(arquivos, key=lambda t: t[0], reverse=True)):
                if i >= _GUARDA or agora - mtime > _VALIDADE:
                    arq.unlink(missing_ok=True)
    except (SemRetrato, OSError) as e:
        _avisa(f"o verde desta corrida não foi anotado — {e}")
        return 1
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
    f.add_argument("--lembrado", action="append", default=[], dest="lembrados")
    c = sub.add_parser("chaves", help="lê `ficha|runner|argv|entradas` do stdin; escreve as chaves")
    c.add_argument("--raiz", default=".", type=Path)
    n = sub.add_parser("anotar", help="lê `ficha<TAB>chave<TAB>ms` do stdin; grava o verde e poda")
    n.add_argument("--raiz", default=".", type=Path)
    for p in (a, f):
        p.add_argument("--corrida", required=True, type=Path)
        p.add_argument("--raiz", default=".", type=Path)
    args = ap.parse_args(argv)
    if args.verbo == "chaves":
        return chaves(args.raiz, sys.stdin.read().splitlines())
    if args.verbo == "anotar":
        return anotar(args.raiz, sys.stdin.read().splitlines())
    if not _NOME.match(args.nome):
        _diz(f"nome inválido {args.nome!r}: só minúsculas, dígitos e hífen")
        return 2
    if args.verbo == "abrir":
        return abrir(args.nome, args.corrida, args.raiz)
    return fechar(args.nome, args.rc, args.corrida, args.raiz, args.contagem, args.nao_medidos,
                  args.lembrados)


if __name__ == "__main__":
    sys.exit(main())
