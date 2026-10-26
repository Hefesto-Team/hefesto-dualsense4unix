#!/usr/bin/env python3
"""validar-citacoes-de-linha.py — ABRE cada `arquivo:linha` citado e confere."""
from __future__ import annotations

import argparse
import ast
import bisect
import csv
import functools
import io
import re
import subprocess
import sys
import tokenize
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prosa_do_codigo

PASTA = Path("docs") / "protocol"

PASTA_CSV = Path("docs") / "data"

CSV_FORA_DO_PORTAO: dict[str, str] = {}

CODIGO_COM_CITACOES: dict[str, str] = {
    "tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py": (
        "25/10/2026, AS-CITACOES-DA-CASA-SABE-E-AS-DE-LINHA-UNICA-GANHAM-REGUA-01: as razões das "
        "isenções da casa-sabe citam `arquivo:linha` em cadeias Python (121 citações, mais 2 "
        "exemplos fabricados), e nenhuma régua as lia: 59 só abriam pelo prefixo de `src/` ou pelo "
        "fim do caminho, 18 eram curtas, e 5 apontavam a linha errada"),
}
"""O código cujas cadeias e comentários são PROSA que cita: lido como as planilhas, cadeia a cadeia
(a cadeia emendada é uma só), com o caminho inteiro a partir da raiz e sem a forma curta."""

PREFIXOS = ("", "src/hefesto_dualsense4unix")

EXTENSOES = "[A-Za-z0-9]+"

ENDERECO = re.compile(
    rf"`(?P<arq>[A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:{EXTENSOES}))?"
    r":(?P<a>\d+)(?:-(?P<b>\d+))?`"
)

ENDERECO_CSV = re.compile(
    rf"(?<![A-Za-z0-9_./-])`?(?P<arq>\.?[A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:{EXTENSOES}))"
    r":(?P<a>\d+)(?:-(?P<b>\d+))?`?"
)
"""A inteira solta (planilha, código). O ``.`` do começo é o da pasta oculta (``.github/…``), que sem
ele a régua não via."""

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

NOME = r"[A-Za-z_][A-Za-z0-9_-]+[A-Za-z0-9_]"
"""O nome que a citação promete: identificador de três letras ou mais, ou o id e a classe do HTML,
com o ``-`` no meio (``est-mic``), que o ``casa_o_nome`` lê inteiros."""

NOME_ANTES = re.compile(rf"`(?P<nome>{NOME})`\s*(?:em|no|na)\s+$")

NOME_DEPOIS = re.compile(
    rf"\s*\(`(?P<nome>{NOME})`\s*(?:[,)]|$)")

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
    forma: bool = False
    """A queixa é da FORMA da citação (o nome vizinho, o caminho curto, a curta no código), e não do
    lugar: o código não andou, e o `reapontar-citacoes.py` não a leva; só a mão a cura."""

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


_BORDA_DO_NOME: dict[str, str] = {".html": r"\w-", ".htm": r"\w-", ".js": r"\w$", ".mjs": r"\w$"}
"""O que, além de letra, dígito e ``_``, ainda é parte do nome: o ``-`` do id e da classe do HTML, o
``$`` do JS. O ponto nunca: ``self.nome`` usa ``nome``."""


@functools.lru_cache(maxsize=64)
def _linhas_sem_comentario(texto: str, sufixo: str) -> tuple[str, ...]:
    return tuple(prosa_do_codigo.sem_comentario(texto, sufixo).split("\n"))


@functools.lru_cache(maxsize=1024)
def _agulha_do_nome(nome: str, sufixo: str) -> re.Pattern[str]:
    borda = _BORDA_DO_NOME.get(sufixo, r"\w")
    return re.compile(rf"(?<![{borda}]){re.escape(nome)}(?![{borda}])")


def casa_o_nome(nome: str, corpo: list[str], primeira: int, ultima: int, sufixo: str) -> bool:
    """O nome está INTEIRO na faixa citada do ``corpo`` (as duas pontas incluídas), fora de comentário.

    Inteiro: ``cor`` não casa em ``cores``, e no HTML ``est`` não casa em ``est-mic``. Fora de
    comentário: o ``#`` do ``.py``, o ``<!-- -->`` do HTML e o ``//`` e o ``/* */`` do JS não
    contam, e a docstring e a cadeia contam, porque a prosa da tela mora nelas. É o dono do
    casamento: o ``_contem`` do `reapontar-citacoes.py` pergunta aqui.
    """
    if nome not in "\n".join(corpo[primeira - 1:ultima]):
        return False
    limpo = _linhas_sem_comentario("\n".join(corpo), sufixo)
    trecho = "\n".join(limpo[primeira - 1:ultima])
    return _agulha_do_nome(nome, sufixo).search(trecho) is not None


@functools.lru_cache(maxsize=64)
def _ligacoes_por_linha(texto: str) -> frozenset[tuple[str, int]]:
    """``{(nome, linha)}`` de cada nome que o ``.py`` LIGA numa linha: a do ``def`` e a da ``class``
    (sem o decorador), e a da atribuição a um nome (``NOME = …``, ``nome: T = …``)."""
    try:
        arvore = ast.parse(texto)
    except (SyntaxError, ValueError):
        return frozenset()
    ligacoes: set[tuple[str, int]] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            ligacoes.add((no.name, no.lineno))
        elif isinstance(no, ast.Assign | ast.AnnAssign):
            alvos = no.targets if isinstance(no, ast.Assign) else [no.target]
            ligacoes.update((a.id, a.lineno) for a in alvos if isinstance(a, ast.Name))
    return frozenset(ligacoes)


DISTANCIA_DO_VIZINHO = 1
"""A citação de UMA linha reprova se o nome que ela promete casa também a esta distância dela.

Medido em 25/10/2026 sobre as 610 citações de linha única com nome prometido do ``--all``: 14 casavam
o nome na linha de cima ou na de baixo, 13 a duas linhas e 5 a três. Das 14, seis prometem o nome que
a própria linha liga (cinco ``def`` cujo decorador ``@gesto`` repete o nome acima, e uma atribuição),
e ficam isentas; as outras oito eram de `docs/data/paridade-gtk-html.csv` e passaram a prometer o
nome que só a linha delas tem. Com o nome na vizinha, uma linha inserida ou tirada acima deixa a
citação verde no lugar errado: o deslocamento de uma linha é o caso de toda costura, e é ele que a
régua pega. A promessa com o nome a duas linhas já reprova nesse deslocamento de uma (a linha que
desce para o lugar da citada não tem o nome); só o de duas a escaparia, e o N=2 reprovaria também
três linhas do `mapa-controles.csv`, que não é desta régua de posse."""


def vizinha_com_o_nome(corpo: list[str], linha: int, nome: str, sufixo: str) -> int | None:
    """A linha vizinha (a ``DISTANCIA_DO_VIZINHO``) em que ``nome`` também casa, ou ``None``.

    O nome que o ``.py`` LIGA na própria linha (o ``def``, a ``class``, a atribuição) é dela só: a
    linha vizinha que o repete (o decorador, o uso logo abaixo) não é ele, e uma linha a mais acima
    leva a citação para fora da ligação, onde a régua reprova.
    """
    if sufixo == ".py" and (nome, linha) in _ligacoes_por_linha("\n".join(corpo)):
        return None
    for outra in range(linha - DISTANCIA_DO_VIZINHO, linha + DISTANCIA_DO_VIZINHO + 1):
        if outra != linha and 1 <= outra <= len(corpo) and casa_o_nome(
                nome, corpo, outra, outra, sufixo):
            return outra
    return None


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

    de, ate = achado.span("vao") if curta else achado.span()
    nomes = sorted(nomes_prometidos(texto, de, ate, separadores))
    achados = [
        Achado(origem, linha, endereco,
               f"a faixa não contém `{nome}`, que a citação promete", contexto, curta)
        for nome in nomes
        if not casa_o_nome(nome, corpo, primeira, ultima, alvo.suffix)
    ]
    if not achado.group("b"):
        for nome in nomes:
            if not casa_o_nome(nome, corpo, primeira, primeira, alvo.suffix):
                continue
            vizinha = vizinha_com_o_nome(corpo, primeira, nome, alvo.suffix)
            if vizinha is not None:
                achados.append(Achado(
                    origem, linha, endereco,
                    f"`{nome}` casa também na linha {vizinha}, vizinha da citada: com uma linha "
                    "a mais ou a menos acima a citação segue verde no lugar errado; prometa o "
                    "nome que só a linha citada tem (o `def`, a classe, a chave ou a cadeia dela)",
                    contexto, curta, forma=True))
    if alvo.suffix == ".py" and achado.group("b"):
        for nome in nomes:
            no_def = (abraca_de_fora(corpo, primeira, ultima, nome)
                      if casa_o_nome(nome, corpo, primeira, ultima, alvo.suffix) else None)
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
                        continue
                    seus, conferido, fora = confere_endereco(
                        relativo, inicio, contexto, celula, curta,
                        ancora.group("arq"), corpos, raiz, SEPARADORES_DE_BLOCO, curta=True)
                    achados.extend(seus)
                    conferidos += conferido
                    de_fora += fora
    return achados, conferidos, de_fora


@dataclass(frozen=True)
class Trecho:
    """Uma cadeia (a emendada é UMA: ``"a" "b"`` é ``"ab"``) ou um comentário de um ``.py``."""

    texto: str
    marcos: tuple[tuple[int, int], ...]
    """``(letra do texto, linha do arquivo)`` onde cada pedaço começa, e cada quebra de linha da cadeia
    de três aspas: a linha de uma letra é a do último marco antes dela."""

    def linha_de(self, letra: int) -> int:
        return self.marcos[bisect.bisect_right([m[0] for m in self.marcos], letra) - 1][1]


def trechos_do_codigo(texto: str) -> list[Trecho]:
    """As cadeias e os comentários do código, pelo ``tokenize`` (a f-string não é prosa que cita)."""
    trechos: list[Trecho] = []
    partes: list[str] = []
    marcos: list[tuple[int, int]] = []

    def fechar() -> None:
        if partes:
            trechos.append(Trecho("".join(partes), tuple(marcos)))
        partes.clear()
        marcos.clear()

    try:
        for tok in tokenize.generate_tokens(io.StringIO(texto).readline):
            if tok.type == tokenize.STRING:
                try:
                    valor = ast.literal_eval(tok.string)
                except (ValueError, SyntaxError):
                    fechar()
                    continue
                if not isinstance(valor, str):
                    fechar()
                    continue
                onde = sum(len(p) for p in partes)
                marcos.append((onde, tok.start[0]))
                if tok.start[0] != tok.end[0]:
                    marcos.extend((onde + i + 1, tok.start[0] + k + 1)
                                  for k, i in enumerate(
                                      j for j, letra in enumerate(valor) if letra == "\n"))
                partes.append(valor)
            elif tok.type == tokenize.COMMENT:
                trechos.append(Trecho(tok.string, ((0, tok.start[0]),)))
            elif tok.type != tokenize.NL:
                fechar()
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    fechar()
    return trechos


CURTA_NO_CODIGO = re.compile(r"(?<![A-Za-z0-9_./-]):\d+(?:-\d+)?(?![\d])|(?<=\d)\+\d+")
"""A forma curta solta numa cadeia (``(:277)``, `` `install.sh`:1437``) e o ``:N+M``: no código a
citação se escreve inteira, porque a curta e o arquivo entre crases não se leem nem se levam."""


@functools.lru_cache(maxsize=4)
def _arquivos_da_arvore(raiz: Path) -> tuple[str, ...]:
    feito = _git(raiz, "ls-files")
    if feito.returncode == 0 and feito.stdout:
        return tuple(feito.stdout.splitlines())
    return tuple(sorted(p.relative_to(raiz).as_posix() for p in raiz.rglob("*")
                        if p.is_file() and ".git" not in p.parts))


def caminho_inteiro(arquivo: str, raiz: Path) -> str | None:
    """O caminho a partir da raiz do arquivo citado por um caminho que só abre com prefixo ou pelo
    fim (``daemon/main.py``, ``doctor.sh``); ``None`` se nenhum, ou mais de um, termina assim."""
    alvo = resolve(arquivo, raiz)
    if alvo is not None:
        return alvo.relative_to(raiz).as_posix()
    candidatos = [p for p in _arquivos_da_arvore(raiz) if p.endswith(f"/{arquivo}")]
    return candidatos[0] if len(candidatos) == 1 else None


def varrer_codigo(
    codigo: Path,
    raiz: Path,
    corpos: dict[Path, list[str]] | None = None,
) -> tuple[list[Achado], int, int]:
    """O mesmo, trecho a trecho de um arquivo de CODIGO_COM_CITACOES.

    A citação tem o caminho inteiro a partir da raiz, e a curta não se escreve: a que só abre com o
    prefixo de `src/` ou pelo fim do caminho reprova dizendo o caminho inteiro, e a de fora (o
    exemplo fabricado de um teste, o kernel) é ignorada como nas planilhas.
    """
    achados: list[Achado] = []
    conferidos = de_fora = 0
    if corpos is None:
        corpos = {}
    relativo = codigo.resolve().relative_to(raiz).as_posix()
    for trecho in trechos_do_codigo(codigo.read_text(encoding="utf-8")):
        texto = trecho.texto
        if ":" not in texto:
            continue
        for achado in ENDERECO_CSV.finditer(texto):
            arquivo = achado.group("arq")
            linha = trecho.linha_de(achado.start())
            if not (raiz / arquivo).is_file():
                inteiro = caminho_inteiro(arquivo, raiz)
                if inteiro is None:
                    de_fora += 1
                    continue
                conferidos += 1
                achados.append(Achado(
                    relativo, linha, f"`{achado.group(0).strip('`')}`",
                    f"o caminho não abre a partir da raiz: escreva `{inteiro}`", forma=True))
                continue
            seus, conferido, fora = confere_endereco(
                relativo, linha, "", texto, achado, arquivo, corpos, raiz, SEPARADORES_DE_BLOCO)
            achados.extend(seus)
            conferidos += conferido
            de_fora += fora
        for curta in CURTA_NO_CODIGO.finditer(texto):
            conferidos += 1
            achados.append(Achado(
                relativo, trecho.linha_de(curta.start()), f"`{curta.group(0)}`",
                "forma curta no código: escreva a citação inteira, `caminho:N`, a partir da raiz",
                forma=True))
    return achados, conferidos, de_fora


def codigos_de(raiz: Path) -> list[Path]:
    """Os arquivos de CODIGO_COM_CITACOES que existem nesta árvore."""
    return [raiz / r for r in sorted(CODIGO_COM_CITACOES) if (raiz / r).is_file()]


BASES_DAS_NOVAS = ("dev", "origin/dev")
"""Onde se procura o pé comum, nesta ordem: na árvore da casa o `dev`; no CI, o `origin/dev`."""

CELULAS_DE_ENDERECO_PURO: dict[str, tuple[tuple[str, ...], str]] = {
    "paridade-gtk-html.csv": (
        ("gtk_onde", "html_onde"),
        "10/10/2026: o `check_paridade_gtk_html.py` lê a célula como `caminho:N · caminho:N` e "
        "confere que cada um abre e é do lado certo. 25/10/2026: ele aceita também "
        "`caminho:N (`nome`)` (`NOME_PROMETIDO`), e a crua continua aceita: o `--novas` não a exige"),
}
"""As colunas de planilha que são lista de endereço por formato, com o motivo. O ``--novas`` não
exige o nome nelas, porque o leitor dono da coluna aceita as duas formas; o ``--all`` confere o
nome que a célula prometer."""


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
        candidatas: list[tuple[str, re.Match[str], bool]] = [
            (a.group("arq"), a, False) for a in inteiras]
        for pedaco in CURTA_CSV.finditer(linha):
            ancora = ancora_da_curta(linha, inteiras, pedaco.start("vao"))
            if ancora is not None:
                candidatas.append((ancora.group("arq"), pedaco, True))
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
                    nome = None
                certa = f"`{nome or '<nome>'}` em `{faixa}`"
                achados.append(Achado(
                    documento, numero, f"`{faixa}`",
                    f"citação de linha NOVA sem nome prometido: escreva {certa}"
                    + ("" if nome else " com o nome que está na linha citada")
                    + ", e o `reapontar-citacoes.py` a leva quando o código andar"))
    return achados, reescritas


def _linhas_do_diff(raiz: Path, pe: str, relativo: str) -> tuple[set[int], set[int]]:
    """``(linhas acrescentadas, no lado de hoje; linhas removidas, no lado do pé)`` de ``relativo``
    desde ``pe``, contra a árvore de trabalho, como o :func:`linhas_mudadas`."""
    diff = _git(raiz, "diff", "-U0", "--no-color", "--no-ext-diff", pe, "--", relativo)
    acrescentadas: set[int] = set()
    removidas: set[int] = set()
    for linha in diff.stdout.splitlines():
        cabeca = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", linha)
        if cabeca:
            velha, quantas_velhas = int(cabeca[1]), int(cabeca[2] or 1)
            nova, quantas_novas = int(cabeca[3]), int(cabeca[4] or 1)
            removidas.update(range(velha, velha + quantas_velhas))
            acrescentadas.update(range(nova, nova + quantas_novas))
    return acrescentadas, removidas


def cruas_do_codigo(texto: str, raiz: Path) -> list[tuple[int, str, str]]:
    """``(linha, caminho inteiro do citado, citação escrita)`` de cada citação sem nome prometido
    das cadeias de um arquivo de CODIGO_COM_CITACOES (a cadeia emendada é uma só, e o nome pode vir
    no pedaço de baixo). O caminho inteiro é a chave: a citação que só passou a sair da raiz é a
    mesma."""
    cruas: list[tuple[int, str, str]] = []
    for trecho in trechos_do_codigo(texto):
        if ":" not in trecho.texto:
            continue
        for achado in ENDERECO_CSV.finditer(trecho.texto):
            inteiro = caminho_inteiro(achado.group("arq"), raiz)
            if inteiro is None or nomes_prometidos(
                    trecho.texto, achado.start(), achado.end(), SEPARADORES_DE_BLOCO):
                continue
            cruas.append((trecho.linha_de(achado.start()), inteiro, achado.group(0).strip("`")))
    return cruas


def varrer_novas_do_codigo(raiz: Path, pe: str) -> tuple[list[Achado], int]:
    """O mesmo do :func:`varrer_novas`, nas cadeias de CODIGO_COM_CITACOES: a crua removida do
    arquivo, para o mesmo arquivo citado, paga uma acrescentada."""
    achados: list[Achado] = []
    reescritas = 0
    for codigo in codigos_de(raiz):
        relativo = codigo.relative_to(raiz).as_posix()
        acrescentadas, removidas = _linhas_do_diff(raiz, pe, relativo)
        if not acrescentadas:
            continue
        antes = _git(raiz, "show", f"{pe}:{relativo}")
        pagas: Counter[str] = Counter(
            inteiro for linha, inteiro, _ in cruas_do_codigo(
                antes.stdout if antes.returncode == 0 else "", raiz)
            if linha in removidas)
        for linha, inteiro, escrita in cruas_do_codigo(codigo.read_text(encoding="utf-8"), raiz):
            if linha not in acrescentadas:
                continue
            if pagas[inteiro] > 0:
                pagas[inteiro] -= 1
                reescritas += 1
                continue
            achados.append(Achado(
                relativo, linha, f"`{escrita}`",
                "citação de linha NOVA sem nome prometido: escreva o nome que está na linha "
                "citada logo depois dela, (`nome`), e o `reapontar-citacoes.py` a leva quando o "
                "código andar"))
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
    do_codigo, reescritas_do_codigo = varrer_novas_do_codigo(raiz, pe)
    achados += do_codigo
    reescritas += reescritas_do_codigo
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
                        help=f"varre {PASTA.as_posix()}/, {PASTA_CSV.as_posix()}/*.csv e CODIGO_COM_CITACOES")
    parser.add_argument("--novas", action="store_true",
                        help="reprova a citação de linha ACRESCENTADA desde o pé comum com o "
                             "`dev` que não promete o nome (documento, planilha e cadeia de "
                             "CODIGO_COM_CITACOES); sem base, falha")
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
        codigos = codigos_de(raiz)
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
        codigos = [
            p for p in args.arquivos
            if p.is_file() and p.resolve().is_relative_to(raiz)
            and p.resolve().relative_to(raiz).as_posix() in CODIGO_COM_CITACOES
        ]
    if not alvos and not planilhas and not codigos:
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
    for codigo in codigos:
        seus, quantos, fora = varrer_codigo(codigo, raiz, corpos)
        achados.extend(seus)
        conferidos += quantos
        de_fora += fora

    onde = (f"{len(alvos)} documento(s), {len(planilhas)} planilha(s) e "
            f"{len(codigos)} arquivo(s) de código")
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
