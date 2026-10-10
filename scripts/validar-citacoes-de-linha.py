#!/usr/bin/env python3
"""validar-citacoes-de-linha.py — ABRE cada `arquivo:linha` citado e confere."""
from __future__ import annotations

import argparse
import ast
import csv
import functools
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

PASTA = Path("docs") / "protocol"

PASTA_CSV = Path("docs") / "data"

CSV_FORA_DO_PORTAO: dict[str, str] = {}

PREFIXOS = ("", "src/hefesto_dualsense4unix")

EXTENSOES = "[A-Za-z0-9]+"

ENDERECO = re.compile(
    rf"`(?P<arq>[A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:{EXTENSOES}))?"
    r":(?P<a>\d+)(?:-(?P<b>\d+))?`"
)

ENDERECO_CSV = re.compile(
    rf"(?<![A-Za-z0-9_./-])`?(?P<arq>[A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:{EXTENSOES}))"
    r":(?P<a>\d+)(?:-(?P<b>\d+))?`?"
)

CURTA_CSV = re.compile(
    r"(?:[,;(]|(?<![A-Za-z0-9_])e)\s*`?(?P<vao>:(?P<a>\d+)(?:-(?P<b>\d+))?)(?!\w)")
"""A forma curta numa célula (``:N`` ou ``:N-M`` depois de vírgula, ponto-e-vírgula, ``e`` ou
abre-parêntese): o arquivo é o da citação inteira mais próxima ANTES dela, na MESMA célula. A
gramática é a do ``_CURTA_DE_CSV`` do `reapontar-citacoes.py`, que a leva junto quando o código anda."""

NOME_DE_ARQUIVO = re.compile(
    r"(?<![A-Za-z0-9_./-])[A-Za-z0-9_][A-Za-z0-9_./-]*\."
    r"(?:py|pyi|c|h|cc|cpp|md|csv|html|js|mjs|sh|rules|conf|toml|json|txt|yml|yaml|service|desktop|ini|cfg)"
    r"(?![A-Za-z0-9_])")
"""Um arquivo NOMEADO na prosa, com ou sem número: entre a inteira e a curta, ele muda de quem é a
curta (`backend.py:1735`, depois «em `coop.py`, `:1511`»: o `:1511` é do `coop.py`)."""


def ancora_da_curta(celula: str, inteiras: list[re.Match[str]], vao: int) -> re.Match[str] | None:
    """A inteira a que a curta escrita em ``vao`` se prende, ou ``None``.

    É a inteira mais próxima ANTES dela na mesma célula, desde que nenhum OUTRO arquivo seja
    nomeado entre as duas: «`a.py:10` (…) no laço de `b.py`, `:20`» cita o `b.py`, e prender o
    `:20` ao `a.py` acusaria (e levaria) um endereço que nunca foi do `a.py`. O nome do mesmo
    arquivo no meio não solta a curta. Quem lê e quem leva a curta perguntam aqui: o validador e o
    ``_achar`` do `reapontar-citacoes.py`.
    """
    antes = [i for i in inteiras if i.end() <= vao]
    if not antes:
        return None
    ancora = antes[-1]
    proprio = ancora.group("arq").rsplit("/", 1)[-1]
    for nome in NOME_DE_ARQUIVO.finditer(celula, ancora.end(), vao):
        if nome.group(0).rsplit("/", 1)[-1] != proprio:
            return None
    return ancora

NOME_ANTES = re.compile(r"`(?P<nome>[A-Za-z_][A-Za-z0-9_]{2,})`\s*(?:em|no|na)\s+$")

NOME_DEPOIS = re.compile(
    r"\s*\(`(?P<nome>[A-Za-z_][A-Za-z0-9_]{2,})`\s*(?:[,)]|$)")

JANELA_ESQUERDA = 120

SEPARADORES_DE_BLOCO = ("\n", "·")


@dataclass(frozen=True)
class Achado:
    documento: str
    linha: int
    endereco: str
    motivo: str
    contexto: str = ""
    curta: bool = False
    """Escrita na forma curta ``:N``, presa à inteira da célula: o ``endereco`` diz o arquivo dela."""

    def __str__(self) -> str:
        onde = f" ({self.contexto})" if self.contexto else ""
        forma = " (forma curta na célula)" if self.curta else ""
        return f"{self.documento}:{self.linha}{onde}: {self.endereco}{forma} -- {self.motivo}"


def resolve(arquivo: str, raiz: Path) -> Path | None:
    """O caminho real de um arquivo citado, ou None se ele não é desta árvore."""
    for prefixo in PREFIXOS:
        candidato = raiz / prefixo / arquivo if prefixo else raiz / arquivo
        if candidato.is_file():
            return candidato
    return None


def nomes_prometidos(
    texto: str,
    inicio: int,
    fim: int,
    separadores: tuple[str, ...] = (),
) -> set[str]:
    """Os identificadores que a citação promete encontrar na faixa."""
    esquerda_bruta = texto[max(0, inicio - JANELA_ESQUERDA):inicio]
    for separador in separadores:
        esquerda_bruta = esquerda_bruta.rpartition(separador)[2]
    nomes: set[str] = set()
    esquerda = NOME_ANTES.search(esquerda_bruta)
    if esquerda:
        nomes.add(esquerda.group("nome"))
    direita = NOME_DEPOIS.match(texto[fim:fim + 80])
    if direita:
        nomes.add(direita.group("nome"))
    return nomes


@functools.lru_cache(maxsize=64)
def _inicios_das_definicoes(texto: str) -> dict[str, tuple[int, ...]]:
    """``{nome: (primeira linha, decorador incluído, de cada definição)}``."""
    try:
        arvore = ast.parse(texto)
    except (SyntaxError, ValueError):
        return {}
    inicios: dict[str, list[int]] = {}
    for no in ast.walk(arvore):
        if isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            primeira = min([d.lineno for d in no.decorator_list] + [no.lineno])
            inicios.setdefault(no.name, []).append(primeira)
    return {nome: tuple(linhas) for nome, linhas in inicios.items()}


def abraca_de_fora(corpo: list[str], primeira: int, ultima: int, nome: str) -> int | None:
    """A pergunta 3: a linha do `def` de ``nome`` quando a faixa o abraça"""
    inicios = _inicios_das_definicoes("\n".join(corpo)).get(nome, ())
    if len(inicios) != 1 or not primeira < inicios[0] <= ultima:
        return None
    antes = corpo[primeira - 1 : inicios[0] - 1]
    if all(not linha.strip() or linha.lstrip().startswith("#") for linha in antes):
        return None
    return inicios[0]


def confere_endereco(
    origem: str,
    linha: int,
    contexto: str,
    texto: str,
    achado: re.Match[str],
    arquivo: str,
    corpos: dict[Path, list[str]],
    raiz: Path,
    separadores: tuple[str, ...] = (),
    *,
    curta: bool = False,
) -> tuple[list[Achado], bool, bool]:
    """As três perguntas, para UM endereço.

    ``curta``: o ``achado`` é uma forma curta (o grupo ``vao`` é o ``:N``); o ``arquivo`` vem da
    inteira antes dela, e o nome prometido se procura em volta do ``:N``.
    """
    alvo = resolve(arquivo, raiz)
    if alvo is None:
        return [], False, True
    if alvo not in corpos:
        corpos[alvo] = alvo.read_text(encoding="utf-8", errors="replace").splitlines()
    corpo = corpos[alvo]

    primeira = int(achado.group("a"))
    ultima = int(achado.group("b") or achado.group("a"))
    endereco = f"`{arquivo}:{primeira}" + (
        f"-{ultima}`" if achado.group("b") else "`")

    if primeira < 1 or primeira > ultima:
        return ([Achado(origem, linha, endereco,
                        "a faixa está invertida ou começa em zero", contexto, curta)],
                True, False)
    if ultima > len(corpo):
        return ([Achado(origem, linha, endereco,
                        f"a linha não existe: {arquivo} tem {len(corpo)} linha(s)",
                        contexto, curta)],
                True, False)

    trecho = "\n".join(corpo[primeira - 1:ultima])
    de, ate = achado.span("vao") if curta else achado.span()
    nomes = sorted(nomes_prometidos(texto, de, ate, separadores))
    achados = [
        Achado(origem, linha, endereco,
               f"a faixa não contém `{nome}`, que a citação promete", contexto, curta)
        for nome in nomes
        if nome not in trecho
    ]
    if alvo.suffix == ".py" and achado.group("b"):
        for nome in nomes:
            no_def = abraca_de_fora(corpo, primeira, ultima, nome) if nome in trecho else None
            if no_def is not None:
                achados.append(Achado(
                    origem, linha, endereco,
                    f"a faixa começa antes do `def {nome}` (linha {no_def}) e abraça "
                    "código de fora dele: a função andou e a faixa não foi junto",
                    contexto, curta))
    return achados, True, False


def varrer_documento(
    documento: Path,
    raiz: Path,
    corpos: dict[Path, list[str]] | None = None,
) -> tuple[list[Achado], int, int]:
    """Devolve (achados, endereços conferidos, endereços ignorados por serem de fora)."""
    achados: list[Achado] = []
    conferidos = de_fora = 0
    if corpos is None:
        corpos = {}

    texto = documento.read_text(encoding="utf-8")
    relativo = documento.resolve().relative_to(raiz).as_posix()
    for numero, linha in enumerate(texto.splitlines(), 1):
        ancora: str | None = None
        for achado in ENDERECO.finditer(linha):
            explicito = achado.group("arq")
            if explicito:
                ancora = explicito
            arquivo = explicito or ancora
            if arquivo is None:
                continue
            seus, conferido, fora = confere_endereco(
                relativo, numero, "", linha, achado, arquivo, corpos, raiz)
            achados.extend(seus)
            conferidos += conferido
            de_fora += fora
    return achados, conferidos, de_fora


def varrer_planilha(
    planilha: Path,
    raiz: Path,
    corpos: dict[Path, list[str]] | None = None,
) -> tuple[list[Achado], int, int]:
    """O mesmo, célula a célula, lido pelo módulo `csv`."""
    achados: list[Achado] = []
    conferidos = de_fora = 0
    if corpos is None:
        corpos = {}
    relativo = planilha.resolve().relative_to(raiz).as_posix()

    with planilha.open(encoding="utf-8", newline="") as fluxo:
        leitor = csv.reader(fluxo)
        try:
            cabecalho = next(leitor)
        except StopIteration:
            return achados, conferidos, de_fora
        coluna_id = cabecalho.index("id") if "id" in cabecalho else 0
        fim_do_anterior = leitor.line_num
        for registro in leitor:
            inicio = fim_do_anterior + 1
            fim_do_anterior = leitor.line_num
            chave = registro[coluna_id] if coluna_id < len(registro) else ""
            for indice, celula in enumerate(registro):
                if ":" not in celula:
                    continue
                coluna = (cabecalho[indice] if indice < len(cabecalho)
                          else f"coluna {indice + 1}")
                contexto = f"{chave} · {coluna}" if chave else coluna
                inteiras = list(ENDERECO_CSV.finditer(celula))
                for achado in inteiras:
                    seus, conferido, fora = confere_endereco(
                        relativo, inicio, contexto, celula, achado,
                        achado.group("arq"), corpos, raiz, SEPARADORES_DE_BLOCO)
                    achados.extend(seus)
                    conferidos += conferido
                    de_fora += fora
                for curta in CURTA_CSV.finditer(celula):
                    ancora = ancora_da_curta(celula, inteiras, curta.start("vao"))
                    if ancora is None or resolve(ancora.group("arq"), raiz) is None:
                        continue  # sem inteira que a prenda, ou presa a arquivo de fora: não se lê
                    seus, conferido, fora = confere_endereco(
                        relativo, inicio, contexto, celula, curta,
                        ancora.group("arq"), corpos, raiz, SEPARADORES_DE_BLOCO, curta=True)
                    achados.extend(seus)
                    conferidos += conferido
                    de_fora += fora
    return achados, conferidos, de_fora


# --- a citação NOVA promete o nome (A-CITACAO-NOVA-DE-LINHA-PROMETE-O-NOME-01, 10/10/2026) ------
#
# A crua (`x.py:3` sem nome) só o histórico leva quando o código anda, e cada uma vira trabalho à
# mão do fecho. A antiga é das sprints das cruas; aqui se fecha a porta da NOVA: endereço que
# aparece em linha acrescentada desde o pé comum com o `dev`. A crua que só mudou de número ou de
# prosa em volta não é nova: cada crua removida do MESMO documento, para o mesmo arquivo citado,
# paga uma acrescentada (é o que o `reapontar --escrever` faz: o número muda, o nome não).

BASES_DAS_NOVAS = ("dev", "origin/dev")
"""Onde se procura o pé comum, nesta ordem: na árvore da casa o `dev`; no CI, o `origin/dev`."""

CELULAS_DE_ENDERECO_PURO: dict[str, tuple[tuple[str, ...], str]] = {
    "paridade-gtk-html.csv": (
        ("gtk_onde", "html_onde"),
        "10/10/2026: o `check_paridade_gtk_html.py` lê a célula como `caminho:N · caminho:N` e "
        "confere que cada um abre e é do lado certo; a forma nomeada não cabe nela"),
}
"""As colunas de planilha que são lista de endereço por formato, com o motivo. O ``--novas`` não
as lê: o nome prometido ali quebraria o leitor dono da coluna."""


def _git(raiz: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(raiz), "-c", "core.quotePath=false", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)


def pe_comum(raiz: Path, base: str | None) -> str | None:
    """O ``merge-base`` do HEAD com a base pedida (ou a primeira de BASES_DAS_NOVAS que responde)."""
    for ref in (base,) if base else BASES_DAS_NOVAS:
        saida = _git(raiz, "merge-base", "HEAD", ref)
        if saida.returncode == 0 and saida.stdout.strip():
            return saida.stdout.strip()
    return None


def vigiado(relativo: str) -> bool:
    """O mesmo alcance do ``--all``: `.md` sob `docs/protocol`, `.csv` direto em `docs/data`."""
    caminho = Path(relativo)
    if caminho.suffix == ".md":
        return caminho.is_relative_to(PASTA)
    return (caminho.suffix == ".csv" and caminho.parent == PASTA_CSV
            and caminho.name not in CSV_FORA_DO_PORTAO)


def linhas_mudadas(raiz: Path, pe: str) -> dict[str, tuple[list[tuple[int, str]], list[str]]]:
    """``{documento: (linhas acrescentadas com o número, linhas removidas)}`` desde ``pe``.

    Compara com a árvore de trabalho, para o que ainda não foi commitado contar; o documento novo
    que o git ainda não acompanha entra inteiro.
    """
    mudadas: dict[str, tuple[list[tuple[int, str]], list[str]]] = {}
    diff = _git(raiz, "diff", "-U0", "-M", "--no-color", "--no-ext-diff",
                "--src-prefix=a/", "--dst-prefix=b/", pe, "--", PASTA.as_posix(),
                PASTA_CSV.as_posix())
    atual: str | None = None
    numero = 0
    for linha in diff.stdout.splitlines():
        if linha.startswith("+++ "):
            destino = linha[4:]
            atual = destino[2:] if destino.startswith("b/") and vigiado(destino[2:]) else None
            if atual is not None:
                mudadas.setdefault(atual, ([], []))
        elif linha.startswith(("--- ", "diff ", "index ", "rename ", "similarity ", "new file",
                               "deleted file", "old mode", "new mode", "\\")):
            continue
        elif linha.startswith("@@"):
            cabeca = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", linha)
            numero = int(cabeca.group(1)) if cabeca else 0
        elif atual is None:
            continue
        elif linha.startswith("+"):
            mudadas[atual][0].append((numero, linha[1:]))
            numero += 1
        elif linha.startswith("-"):
            mudadas[atual][1].append(linha[1:])
    novos = _git(raiz, "ls-files", "--others", "--exclude-standard", "--",
                 PASTA.as_posix(), PASTA_CSV.as_posix())
    for relativo in novos.stdout.splitlines():
        if vigiado(relativo) and (raiz / relativo).is_file():
            texto = (raiz / relativo).read_text(encoding="utf-8", errors="replace")
            mudadas[relativo] = (list(enumerate(texto.splitlines(), 1)), [])
    return mudadas


def cruas_da_linha(
    linha: str, planilha: bool, raiz: Path,
) -> list[tuple[str, re.Match[str], bool]]:
    """As citações sem nome prometido de UMA linha: ``(arquivo, achado, curta)``.

    Só as de arquivo DESTA árvore: a fonte de fora (kernel, SDL) não anda com o nosso código, e o
    ``reapontar`` não a leva.
    """
    cruas: list[tuple[str, re.Match[str], bool]] = []
    if planilha:
        inteiras = list(ENDERECO_CSV.finditer(linha))
        candidatas = [(a.group("arq"), a, False) for a in inteiras]
        for curta in CURTA_CSV.finditer(linha):
            ancora = ancora_da_curta(linha, inteiras, curta.start("vao"))
            if ancora is not None:
                candidatas.append((ancora.group("arq"), curta, True))
        separadores: tuple[str, ...] = SEPARADORES_DE_BLOCO
    else:
        candidatas = []
        ancora_md: str | None = None
        for achado in ENDERECO.finditer(linha):
            ancora_md = achado.group("arq") or ancora_md
            if ancora_md is not None:
                candidatas.append((ancora_md, achado, False))
        separadores = ()
    for arquivo, achado, curta in candidatas:
        de, ate = achado.span("vao") if curta else achado.span()
        if resolve(arquivo, raiz) is None:
            continue
        if not nomes_prometidos(linha, de, ate, separadores):
            cruas.append((arquivo, achado, curta))
    return cruas


def nome_na_linha(alvo: Path, numero: int) -> str | None:
    """A ``def``/``class`` mais de dentro que contém a linha, lida pelo ``ast``; ``None`` fora disso."""
    if alvo.suffix != ".py":
        return None
    try:
        arvore = ast.parse(alvo.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, ValueError):
        return None
    melhor: tuple[int, str] | None = None
    for no in ast.walk(arvore):
        if isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            fim = no.end_lineno or no.lineno
            if no.lineno <= numero <= fim and (melhor is None or no.lineno > melhor[0]):
                melhor = (no.lineno, no.name)
    return melhor[1] if melhor else None


def trechos(linha: str, documento: str, raiz: Path) -> list[str]:
    """O que se lê de UMA linha: a linha do `.md`; as células da linha de planilha.

    A linha de planilha que é um registro inteiro se lê célula a célula, sem as colunas de
    CELULAS_DE_ENDERECO_PURO; a que é pedaço de uma célula de várias linhas se lê inteira.
    """
    if not documento.endswith(".csv"):
        return [linha]
    puras, _ = CELULAS_DE_ENDERECO_PURO.get(Path(documento).name, ((), ""))
    cabecalho = _cabecalho(raiz / documento)
    try:
        celulas = next(csv.reader([linha]))
    except (csv.Error, StopIteration):
        return [linha]
    if len(celulas) != len(cabecalho):
        return [linha]
    return [c for nome, c in zip(cabecalho, celulas, strict=True) if nome not in puras]


@functools.lru_cache(maxsize=32)
def _cabecalho(planilha: Path) -> tuple[str, ...]:
    try:
        with planilha.open(encoding="utf-8", newline="") as fluxo:
            return tuple(next(csv.reader(fluxo), []))
    except OSError:
        return ()


def varrer_novas(raiz: Path, pe: str) -> tuple[list[Achado], int]:
    """As cruas NOVAS desde ``pe``, e quantas antigas só mudaram de número ou de prosa."""
    achados: list[Achado] = []
    reescritas = 0
    for documento, (acrescentadas, removidas) in sorted(linhas_mudadas(raiz, pe).items()):
        planilha = documento.endswith(".csv")
        pagas: Counter[str] = Counter(
            Path(arquivo).as_posix()
            for linha in removidas for trecho in trechos(linha, documento, raiz)
            for arquivo, _, _ in cruas_da_linha(trecho, planilha, raiz))
        for numero, linha in acrescentadas:
            cruas = [c for trecho in trechos(linha, documento, raiz)
                     for c in cruas_da_linha(trecho, planilha, raiz)]
            for arquivo, achado, _curta in cruas:
                chave = Path(arquivo).as_posix()
                if pagas[chave] > 0:
                    pagas[chave] -= 1
                    reescritas += 1
                    continue
                primeira = int(achado.group("a"))
                faixa = f"{arquivo}:{primeira}" + (f"-{achado.group('b')}" if achado.group("b") else "")
                alvo = resolve(arquivo, raiz)
                nome = nome_na_linha(alvo, primeira) if alvo else None
                if nome is not None and not NOME_ANTES.search(f"`{nome}` em "):
                    nome = None  # curto demais para a gramática do nome prometido
                certa = f"`{nome or '<nome>'}` em `{faixa}`"
                achados.append(Achado(
                    documento, numero, f"`{faixa}`",
                    f"citação de linha NOVA sem nome prometido: escreva {certa}"
                    + ("" if nome else " com o nome que está na linha citada")
                    + ", e o `reapontar-citacoes.py` a leva quando o código andar"))
    return achados, reescritas


def documentos_de(raiz: Path) -> list[Path]:
    """Todo `.md` sob a pasta vigiada, em QUALQUER profundidade."""
    pasta = raiz / PASTA
    return sorted(pasta.rglob("*.md")) if pasta.is_dir() else []


def planilhas_de(raiz: Path) -> list[Path]:
    """Todo `*.csv` de `docs/data/` menos os declarados em CSV_FORA_DO_PORTAO."""
    pasta = raiz / PASTA_CSV
    if not pasta.is_dir():
        return []
    return sorted(p for p in pasta.glob("*.csv")
                  if p.name not in CSV_FORA_DO_PORTAO)


def conferir_novas(raiz: Path, base: str | None) -> int:
    """O modo ``--novas``: 0 sem crua nova, 1 com, 2 sem base (nunca passa calado)."""
    pe = pe_comum(raiz, base)
    if pe is None:
        pedidas = base or " nem ".join(BASES_DAS_NOVAS)
        print(f"ERRO: sem base: {pedidas} não tem pé comum com o HEAD, e sem ele não há como "
              "saber qual citação é nova. No CI, o checkout precisa do `origin/dev` "
              "(`fetch-depth: 0`).", file=sys.stderr)
        return 2
    achados, reescritas = varrer_novas(raiz, pe)
    if achados:
        print(f"{len(achados)} citação(ões) de linha NOVA(S) sem nome prometido desde {pe[:12]}:")
        for achado in achados:
            print(str(achado))
        return 1
    print(f"OK: nenhuma citação de linha nova sem nome desde {pe[:12]} "
          f"({reescritas} crua(s) antiga(s) só reescrita(s), que são das sprints das cruas).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reprova citação de linha que não abre ou não contém o que promete.")
    parser.add_argument("arquivos", nargs="*", type=Path,
                        help="documentos ou planilhas a varrer")
    parser.add_argument("--all", action="store_true",
                        help=f"varre {PASTA.as_posix()}/ e {PASTA_CSV.as_posix()}/*.csv")
    parser.add_argument("--novas", action="store_true",
                        help="reprova a citação de linha ACRESCENTADA desde o pé comum com o "
                             "`dev` que não promete o nome; sem base, falha")
    parser.add_argument("--base", default=None,
                        help="a ref do pé comum do --novas (padrão: dev, depois origin/dev)")
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parent.parent,
                        help="raiz do repositório (padrão: a deste script)")
    args = parser.parse_args(argv)

    raiz = args.root.resolve()
    if not raiz.is_dir():
        print(f"ERRO: raiz inexistente: {raiz}", file=sys.stderr)
        return 2

    rc_novas = 0
    if args.novas:
        rc_novas = conferir_novas(raiz, args.base)
        if not args.all and not args.arquivos:
            return rc_novas

    if args.all:
        alvos = documentos_de(raiz)
        planilhas = planilhas_de(raiz)
    else:
        pasta_vigiada = (raiz / PASTA).resolve()
        pasta_de_dados = (raiz / PASTA_CSV).resolve()
        alvos = [
            p for p in args.arquivos
            if p.suffix == ".md" and p.is_file()
            and p.resolve().is_relative_to(pasta_vigiada)
        ]
        planilhas = [
            p for p in args.arquivos
            if p.suffix == ".csv" and p.is_file()
            and p.resolve().parent == pasta_de_dados
            and p.name not in CSV_FORA_DO_PORTAO
        ]
    if not alvos and not planilhas:
        print("Nenhum documento para varrer.")
        return rc_novas

    achados: list[Achado] = []
    conferidos = de_fora = 0
    corpos: dict[Path, list[str]] = {}
    for alvo in alvos:
        seus, quantos, fora = varrer_documento(alvo, raiz, corpos)
        achados.extend(seus)
        conferidos += quantos
        de_fora += fora
    for planilha in planilhas:
        seus, quantos, fora = varrer_planilha(planilha, raiz, corpos)
        achados.extend(seus)
        conferidos += quantos
        de_fora += fora

    onde = f"{len(alvos)} documento(s) e {len(planilhas)} planilha(s)"
    if achados:
        print(f"{len(achados)} citação(ões) de linha podre(s) em {onde}:")
        for achado in achados:
            print(str(achado))
        print("")
        print("Cada linha acima cita um endereço que NÃO abre no que promete.")
        print("A afirmação pode continuar verdadeira — o que caducou é o")
        print("endereço. Reaponte-o para onde a coisa está hoje; não apague a")
        print("afirmação, e não troque o endereço por prosa vaga: um grau de")
        print("confiança sem `arquivo:linha` desce de nível nesta casa.")
        print("")
        print("O reapontamento tem dono: `python3 scripts/reapontar-citacoes.py")
        print("--escrever` leva cada endereço pelo histórico do git até onde o")
        print("símbolo prometido está hoje, e só escreve o que confere. A")
        print("citação crua (sem símbolo) o reapontar leva pelo histórico do")
        print("documento; sem `--escrever` ele só lista, e diz por que deixa à mão.")
        return max(1, rc_novas)

    print(f"OK: {conferidos} citação(ões) de linha conferida(s) em {onde}; "
          f"{de_fora} de fontes fora desta árvore (kernel, SDL, wine) "
          "foram ignoradas.")
    print("Limite: a crua que aponta uma linha que existe mas é a errada passa "
          "aqui; só o histórico a pega (`python3 scripts/reapontar-citacoes.py`, "
          "sem `--escrever`).")
    return rc_novas


if __name__ == "__main__":
    sys.exit(main())
