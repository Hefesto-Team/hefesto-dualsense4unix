#!/usr/bin/env python3
"""reapontar-citacoes.py — a citação `arquivo:linha` anda junto com o código.

Duas vias, e as duas só escrevem o que se prova:

* a citação que PROMETE um símbolo anda pelo nome (o histórico acha o commit em que a faixa
  continha o símbolo, e o mapa leva a faixa até hoje);
* a citação CRUA (sem símbolo prometido, 83 % das de `docs/`) anda pelo histórico do documento:
  acha o commit em que o endereço entrou, lê o arquivo citado NAQUELE commit e só leva o bloco
  se ele existe hoje intacto e único. Senão, «à mão», com o motivo escrito.

O limite da via crua: a citação que já nasceu errada anda errada (foi o caso do `rumble.ff`).
"""

from __future__ import annotations

import argparse
import ast
import collections
import csv
import dataclasses
import functools
import importlib.util
import io
import re
import subprocess
import sys
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

HISTORICO = 400

_NOME_NA_QUEIXA = re.compile(r"a faixa (?:não contém `|começa antes do `def )(?P<nome>[^`]+)`")
_ENDERECO = re.compile(r"`?(?P<arq>[^`:\s]+):(?P<a>\d+)(?:-(?P<b>\d+))?`?")
_HUNK = re.compile(r"^@@ -(?P<os>\d+)(?:,(?P<oc>\d+))? \+(?P<ns>\d+)(?:,(?P<nc>\d+))? @@")


@dataclass
class Citacao:
    """Uma citação podre: onde está escrita, o que cita e o que promete."""

    documento: Path
    arquivo: str
    alvo: Path
    a: int
    b: int
    faixa: bool
    nomes: set[str] = field(default_factory=set)
    linhas: set[int] = field(default_factory=set)
    """Linhas do documento em que o validador (ou a régua de `src/`) a achou: só a fila de busca da
    curta que veio sem posição (ver ``_trechos_da_curta``)."""
    curta: bool = False
    """Escrita na forma curta ``:N`` (o arquivo vem da citação inteira, antes, na mesma linha ou célula)."""
    trechos: list[tuple[int, int]] = field(default_factory=list)
    """Da curta: onde cada ``:N`` está escrito, como ``(início, fim)`` no texto CRU do documento."""
    vezes: int = 1
    """Quantas vezes este endereço, nesta forma, está escrito no documento."""
    podre: bool = False
    """Reprovada pelo validador sem símbolo utilizável: só o histórico do documento a leva."""
    pistas: set[str] = field(default_factory=set)
    """Identificadores em crase ao lado do endereço: não PROMETEM nada, mas o trecho citado, no
    commit em que o endereço entrou, tem de mostrar ao menos um deles."""

    @property
    def texto(self) -> str:
        return f"{self.arquivo}:{self.a}-{self.b}" if self.faixa else f"{self.arquivo}:{self.a}"

    def novo_texto(self, a: int, b: int) -> str:
        return f"{self.arquivo}:{a}-{b}" if self.faixa else f"{self.arquivo}:{a}"


def _git(raiz: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(raiz), *args], capture_output=True, text=True, check=False
    )


@functools.cache
def _validador_carregado() -> ModuleType:
    return _validador(Path(__file__).resolve().parents[1])


def _validador(raiz: Path) -> ModuleType:
    caminho = Path(__file__).resolve().parent / "validar-citacoes-de-linha.py"
    spec = importlib.util.spec_from_file_location("validar_citacoes_de_linha", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("validar_citacoes_de_linha", modulo)
    spec.loader.exec_module(modulo)
    return modulo


def _contem(linhas: Sequence[str], a: int, b: int, nomes: set[str], relativo: str = "") -> bool:
    """A faixa é verdadeira: contém todo nome prometido e, em `.py`, não"""
    if a < 1 or b < a or b > len(linhas):
        return False
    trecho = "\n".join(linhas[a - 1 : b])
    if not all(nome in trecho for nome in nomes):
        return False
    if not relativo.endswith(".py") or a == b:
        return True
    abraca = _validador_carregado().abraca_de_fora
    return all(abraca(list(linhas), a, b, nome) is None for nome in nomes)


def _hunks(raiz: Path, sha: str, relativo: str) -> list[tuple[int, int, int, int]] | None:
    """Os hunks de ``sha:relativo`` até o arquivo de hoje (a árvore de trabalho)."""
    feito = _git(raiz, "diff", "-U0", "--no-color", "--no-ext-diff", sha, "--", relativo)
    if feito.returncode != 0:
        return None
    hunks = []
    for linha in feito.stdout.splitlines():
        achado = _HUNK.match(linha)
        if achado:
            hunks.append(
                (
                    int(achado["os"]),
                    int(achado["oc"] or 1),
                    int(achado["ns"]),
                    int(achado["nc"] or 1),
                )
            )
    return hunks


def _levar_linha(linha: int, hunks: list[tuple[int, int, int, int]]) -> int | None:
    """Onde a linha ``linha`` da versão velha está hoje; ``None`` se um hunk a tocou."""
    delta = 0
    for os_, oc, _ns, nc in hunks:
        if oc == 0:
            if os_ < linha:
                delta += nc
            continue
        if os_ <= linha <= os_ + oc - 1:
            return None
        if os_ + oc - 1 < linha:
            delta += nc - oc
    return linha + delta


def levar(
    raiz: Path, relativo: str, a: int, b: int, nomes: set[str], *, historico: int = HISTORICO
) -> tuple[int, int] | None:
    """A faixa ``a-b`` de ``relativo``, levada para onde o trecho que ela prometia está hoje."""
    atual = (raiz / relativo).read_text(encoding="utf-8", errors="replace").splitlines()
    if _contem(atual, a, b, nomes, relativo):
        return a, b
    commits = _git(raiz, "log", f"-n{historico}", "--format=%H", "--", relativo)
    for sha in commits.stdout.split():
        mostrado = _git(raiz, "show", f"{sha}:{relativo}")
        if mostrado.returncode != 0:
            continue
        velho = mostrado.stdout.splitlines()
        if not _contem(velho, a, b, nomes, relativo):
            continue
        return _mapear(raiz, sha, relativo, velho, atual, a, b, nomes)
    return None


def _mapear(
    raiz: Path,
    sha: str,
    relativo: str,
    velho: list[str],
    atual: list[str],
    a: int,
    b: int,
    nomes: set[str],
) -> tuple[int, int] | None:
    hunks = _hunks(raiz, sha, relativo)
    if hunks is not None:
        a2, b2 = _levar_linha(a, hunks), _levar_linha(b, hunks)
        if a2 is not None and b2 is not None and _contem(atual, a2, b2, nomes, relativo):
            return a2, b2
    bloco = velho[a - 1 : b]
    lugares = [
        i + 1 for i in range(len(atual) - len(bloco) + 1) if atual[i : i + len(bloco)] == bloco
    ]
    if len(lugares) == 1 and _contem(
        atual, lugares[0], lugares[0] + len(bloco) - 1, nomes, relativo
    ):
        return lugares[0], lugares[0] + len(bloco) - 1
    if len(lugares) > 1 or hunks is None:
        return None
    for n in range(a, b + 1):
        if any(nome in velho[n - 1] for nome in nomes):
            hoje = _levar_linha(n, hunks)
            if hoje is None:
                return None
            a2, b2 = a + (hoje - n), b + (hoje - n)
            return (a2, b2) if _contem(atual, a2, b2, nomes, relativo) else None
    return None


HISTORICO_DA_DERIVA = 150

_DEFINICOES: dict[tuple[str, str], dict[str, list[tuple[int, int]]]] = {}


def _definicoes(texto: str) -> dict[str, list[tuple[int, int]]]:
    """``{nome: [(início, fim)]}`` de toda função e classe do arquivo."""
    try:
        arvore = ast.parse(texto)
    except (SyntaxError, ValueError):
        return {}
    achadas: dict[str, list[tuple[int, int]]] = {}
    for no in ast.walk(arvore):
        if isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            achadas.setdefault(no.name, []).append((no.lineno, no.end_lineno or no.lineno))
    return achadas


def _unica(definicoes: dict[str, list[tuple[int, int]]], nome: str) -> tuple[int, int] | None:
    faixas = definicoes.get(nome, [])
    return faixas[0] if len(faixas) == 1 else None


def pelo_simbolo(
    raiz: Path, relativo: str, a: int, b: int, nome: str, *, historico: int = HISTORICO_DA_DERIVA
) -> tuple[int, int] | None:
    """A citação da função (ou classe) INTEIRA, ou da linha do ``def``, que ficou à deriva."""
    if not relativo.endswith(".py"):
        return None
    hoje = _unica(
        _definicoes((raiz / relativo).read_text(encoding="utf-8", errors="replace")), nome
    )
    if hoje is None:
        return None
    inicio, fim = hoje
    if (a, b) in ((inicio, fim), (inicio, inicio)):
        return None
    if b > a and b - a == fim - inicio:
        return inicio, fim
    commits = _git(raiz, "log", f"-n{historico}", "--format=%H", "--", relativo)
    for sha in commits.stdout.split():
        chave = (relativo, sha)
        if chave not in _DEFINICOES:
            mostrado = _git(raiz, "show", f"{sha}:{relativo}")
            _DEFINICOES[chave] = _definicoes(mostrado.stdout) if mostrado.returncode == 0 else {}
        antes = _unica(_DEFINICOES[chave], nome)
        if antes is None:
            continue
        if (a, b) == antes:
            return inicio, fim
        if a == b == antes[0]:
            return inicio, inicio
    return None


def podres_do_validador(raiz: Path) -> tuple[list[Citacao], list[str]]:
    """As citações que o `validar-citacoes-de-linha.py --all` reprova, agrupadas."""
    val = _validador(raiz)
    corpos: dict[Path, list[str]] = {}
    achados = []
    for documento in val.documentos_de(raiz):
        achados.extend(val.varrer_documento(documento, raiz, corpos)[0])
    for planilha in val.planilhas_de(raiz):
        achados.extend(val.varrer_planilha(planilha, raiz, corpos)[0])
    por_chave: dict[tuple[str, str], Citacao] = {}
    a_mao: list[str] = []
    for achado in achados:
        endereco = _ENDERECO.search(achado.endereco)
        nome = _NOME_NA_QUEIXA.search(achado.motivo)
        if endereco is None:
            a_mao.append(f"{achado}: não entendi o endereço")
            continue
        alvo = val.resolve(endereco["arq"], raiz)
        if alvo is None:
            continue
        chave = (achado.documento, endereco.group(0).strip("`"))
        if chave not in por_chave:
            a = int(endereco["a"])
            por_chave[chave] = Citacao(
                raiz / achado.documento,
                endereco["arq"],
                alvo,
                a,
                int(endereco["b"] or a),
                endereco["b"] is not None,
            )
        por_chave[chave].linhas.add(achado.linha)
        if nome is None:
            # linha que não existe, faixa invertida, `def` abraçado: o histórico do documento
            por_chave[chave].podre = True
        else:
            por_chave[chave].nomes.add(nome["nome"])
    return list(por_chave.values()), a_mao


def com_promessa(raiz: Path) -> list[Citacao]:
    """Toda citação que o validador confere E que promete um símbolo, podre ou não."""
    val = _validador(raiz)
    achadas: dict[tuple[Path, str], Citacao] = {}

    def anotar(
        documento: Path, texto: str, achado: re.Match[str], separadores: tuple[str, ...]
    ) -> None:
        arquivo = achado.group("arq")
        alvo = val.resolve(arquivo, raiz) if arquivo else None
        if alvo is None:
            return
        nomes = val.nomes_prometidos(texto, achado.start(), achado.end(), separadores)
        if not nomes:
            return
        a = int(achado.group("a"))
        faixa = achado.group("b") is not None
        cit = Citacao(documento, arquivo, alvo, a, int(achado.group("b") or a), faixa)
        chave = (documento, cit.texto)
        achadas.setdefault(chave, cit).nomes.update(nomes)

    for documento in val.documentos_de(raiz):
        for linha in documento.read_text(encoding="utf-8").splitlines():
            for achado in val.ENDERECO.finditer(linha):
                anotar(documento, linha, achado, ())
    for planilha in val.planilhas_de(raiz):
        with planilha.open(encoding="utf-8", newline="") as fluxo:
            for registro in csv.reader(fluxo):
                for celula in registro:
                    if ":" in celula:
                        for achado in val.ENDERECO_CSV.finditer(celula):
                            anotar(planilha, celula, achado, val.SEPARADORES_DE_BLOCO)
    return list(achadas.values())


def _regua_do_src(raiz: Path) -> ModuleType | None:
    """A régua das citações de `src/` (um teste), carregada como módulo; ``None`` sem ela."""
    src = raiz / "src" / "hefesto_dualsense4unix"
    regua = raiz / "tests" / "unit" / "test_portao_o_par_com_metade_ligada.py"
    if not regua.is_file() or not src.is_dir():
        return None
    sys.path.insert(0, str(raiz))
    bytecode, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec = importlib.util.spec_from_file_location("_regua_das_citacoes_do_src", regua)
        assert spec is not None and spec.loader is not None
        modulo = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = modulo
        spec.loader.exec_module(modulo)
    finally:
        sys.path.remove(str(raiz))
        sys.dont_write_bytecode = bytecode
    return modulo


def podres_do_src(raiz: Path) -> tuple[list[Citacao], list[str]]:
    """As citações dos comentários de `src/` que a régua deles reprova."""
    modulo = _regua_do_src(raiz)
    if modulo is None:
        return [], []
    src = raiz / "src" / "hefesto_dualsense4unix"
    queixas = modulo.enderecos_envelhecidos(src)
    pendentes: frozenset[str] = getattr(modulo, "_CITACOES_PENDENTES", frozenset())
    citacoes: list[Citacao] = []
    a_mao: list[str] = []
    for cit in modulo.citacoes_de_linha(src):
        if cit.chave not in queixas or cit.chave in pendentes:
            continue
        candidatas = list(modulo._ancoras_candidatas(src / cit.citante, cit.linha_da_citacao))
        linhas = cit.alvo.read_text(encoding="utf-8").splitlines()
        uma = next((n for n in candidatas if modulo._definicao_unica(linhas, n) is not None), None)
        texto = cit.bruta
        endereco = _ENDERECO.search(texto)
        if endereco is None:
            a_mao.append(f"{queixas[cit.chave]}: não entendi o endereço")
            continue
        citacoes.append(
            Citacao(
                src / cit.citante,
                endereco["arq"],
                cit.alvo,
                cit.ini,
                cit.fim,
                endereco["b"] is not None,
                {uma} if uma is not None else set(),
                {cit.linha_da_citacao},
                podre=uma is None,
            )
        )
    return citacoes, a_mao


def curtas_do_src(raiz: Path) -> list[Citacao]:
    """A forma curta ``:N`` em prosa de `src/`, presa à citação inteira antes, na mesma linha.

    A régua de `src/` só lê ``alvo.py:N`` com o arquivo; a curta (``e `:3989```) escapava dela
    e ficava para trás quando a inteira, ao lado, era reapontada.
    """
    modulo = _regua_do_src(raiz)
    if modulo is None:
        return []
    val = _validador(raiz)
    src = raiz / "src" / "hefesto_dualsense4unix"
    achadas: dict[tuple[Path, str], Citacao] = {}
    for arquivo in modulo._modulos(src):
        prosa = modulo._prosa_de(arquivo)
        if not any(":" in linha for linha in prosa.values()):
            continue
        texto = arquivo.read_text(encoding="utf-8")
        linhas = texto.split("\n")
        inicios = _inicios_das_linhas(linhas)
        for numero in sorted(prosa):
            if not 1 <= numero <= len(linhas):
                continue
            base = inicios[numero - 1]
            for _i, _f, nome, a, b, faixa, curta, vao in _achar(linhas[numero - 1], val, "py"):
                alvo = val.resolve(nome, raiz) if curta else None
                if alvo is None:
                    continue
                cit = Citacao(arquivo, nome, alvo, a, b, faixa, curta=True)
                achada = achadas.setdefault((arquivo, cit.texto), cit)
                if achada is not cit:
                    achada.vezes += 1
                achada.linhas.add(numero)
                achada.trechos.append((base + vao[0], base + vao[1]))
    return list(achadas.values())


_DOIS_PONTOS_E_NUMERO = re.compile(r":\d")

_CRASE = re.compile(r"`([^`\n]{2,60})`")
_IDENTIFICADOR = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
_DISTINTIVO = re.compile(r"_|[A-Za-z0-9][A-Z]|.{7}")
"""Só vale como pista o nome que se distingue: com `_`, com maiúscula no meio ou com 7+ letras
(`None`, `data`, `base` aparecem em qualquer trecho e não provam nada)."""
_JANELA_DA_PISTA = (60, 80)
"""Quantos caracteres antes e depois do endereço a crase ainda conta como «ao lado»."""


def _pistas(texto: str, inicio: int, fim: int) -> set[str]:
    """Os identificadores das crases coladas ao endereço (outro endereço ou caminho não conta).

    O pareamento das crases vem do texto inteiro (uma janela cortada no meio de uma crase
    inverteria quem é crase e quem é prosa); a janela só escolhe as que ficam ao lado.
    """
    antes, depois = _JANELA_DA_PISTA
    achadas: set[str] = set()
    for crase in _CRASE.finditer(texto):
        ao_lado = (inicio - antes <= crase.start() and crase.end() <= inicio) or (
            fim <= crase.start() and crase.end() <= fim + depois
        )
        corpo = crase.group(1)
        if not ao_lado or "/" in corpo or re.search(r":\d", corpo):
            continue
        achadas.update(i for i in _IDENTIFICADOR.findall(corpo) if _DISTINTIVO.search(i))
    return achadas


VARREDURA_DE_ARQUIVOS = 200
"""Um commit que tocou tantos arquivos foi uma varredura (renomear, limpar comentário): ninguém
conferiu cada endereço contra o código daquele instante, e ele não prova onde a linha estava."""

REESCRITA_EM_MASSA = 20
"""Um commit que tirou tantos endereços de UM documento que já existia foi um reapontamento em
massa (à mão, por script ou pela própria via crua de uma leva anterior): o endereço que ele deixou
foi calculado, não escrito olhando o código, e não prova onde a linha estava. Medido em 08/10/2026:
o `719e58a46` reescreveu 1157 endereços da paridade e 438 do mapa, e a `02-controles.html:2358` que
ele deixou para o quadradinho da cor apontava o link da aba Lançadores."""

LINHA_CURTA_DEMAIS = 6
"""Uma linha só com menos caracteres úteis que isto (`}`, `pass`) não identifica o que foi citado."""

HISTORICO_DA_CRUA = 2000

#: Contagem da última corrida: ``conferidas``, ``no_lugar``, ``andaram``, ``a_mao``, ``recentes``.
ESTATISTICA: collections.Counter[str] = collections.Counter()
"""Chaves de motivo (``a_mao:<estado>``) somam em ``a_mao``."""


class _Cat:
    """Um ``git cat-file --batch`` aberto: ler ``sha:caminho`` sem um processo por leitura."""

    def __init__(self, raiz: Path) -> None:
        self._p = subprocess.Popen(
            ["git", "-C", str(raiz), "cat-file", "--batch"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self._linhas: dict[tuple[str, str], list[str] | None] = {}
        self._raiz = raiz
        self._tamanho: dict[str, int] = {}

    def __enter__(self) -> _Cat:
        return self

    def __exit__(self, *_args: object) -> None:
        self.fechar()

    def fechar(self) -> None:
        if self._p.stdin is not None and not self._p.stdin.closed:
            self._p.stdin.close()
        if self._p.stdout is not None:
            self._p.stdout.close()
        self._p.wait()

    def texto(self, objeto: str) -> str | None:
        """O conteúdo de ``sha:caminho``, ou ``None`` se o objeto não existe."""
        assert self._p.stdin is not None and self._p.stdout is not None
        self._p.stdin.write(objeto.encode() + b"\n")
        self._p.stdin.flush()
        cabecalho = self._p.stdout.readline().split()
        if len(cabecalho) != 3 or cabecalho[-1] == b"missing":
            return None
        dados: bytes = self._p.stdout.read(int(cabecalho[2]))
        self._p.stdout.readline()
        texto: str = dados.decode("utf-8", errors="replace")
        return texto

    def arquivos(self, sha: str) -> int:
        """Quantos arquivos o commit ``sha`` tocou (o tamanho da varredura, se foi uma)."""
        if sha not in self._tamanho:
            feito = subprocess.run(
                [
                    "git",
                    "-C",
                    str(self._raiz),
                    "diff-tree",
                    "--no-commit-id",
                    "--name-only",
                    "-r",
                    "--root",
                    sha,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self._tamanho[sha] = len(feito.stdout.split())
        return self._tamanho[sha]

    def linhas(self, sha: str, relativo: str) -> list[str] | None:
        """As linhas de ``relativo`` no commit ``sha`` (numeração do ``splitlines``)."""
        chave = (sha, relativo)
        if chave not in self._linhas:
            if len(self._linhas) > 64:
                self._linhas.clear()
            texto = self.texto(f"{sha}:{relativo}")
            self._linhas[chave] = None if texto is None else texto.splitlines()
        return self._linhas[chave]


Endereco = tuple[int, int, str, int, int, bool, bool, tuple[int, int]]
"""``(início, fim, arquivo, a, b, faixa, curta, vão)`` de um endereço achado numa linha. O ``vão`` é o
trecho que a troca reescreve: o endereço inteiro, ou, na curta, só o ``:N`` / ``:N-M`` (sem a crase)."""

_CURTA_DE_CSV = re.compile(
    r"(?:[,;(]|(?<![A-Za-z0-9_])e)\s*`?(?P<vao>:(?P<a>\d+)(?:-(?P<b>\d+))?)(?!\w)"
)
"""A forma curta numa célula: ``:N`` ou ``:N-M`` solta, depois de vírgula, ponto-e-vírgula, ``e`` ou
abre-parêntese, com ou sem crase."""


def _resolvedor(raiz: Path, val: ModuleType) -> Callable[[str], bool]:
    """Pergunta, com memória, se o arquivo citado é um arquivo do repositório."""
    memoria: dict[str, bool] = {}

    def resolve(arquivo: str) -> bool:
        if arquivo not in memoria:
            memoria[arquivo] = val.resolve(arquivo, raiz) is not None
        return memoria[arquivo]

    return resolve


def _inicios_das_linhas(linhas: Sequence[str]) -> list[int]:
    """Onde cada linha começa no texto cru (as linhas vieram de ``split("\\n")``)."""
    inicios: list[int] = []
    onde = 0
    for linha in linhas:
        inicios.append(onde)
        onde += len(linha) + 1
    return inicios


def _vao_da_curta(m: re.Match[str]) -> tuple[int, int]:
    """O ``:N`` ou ``:N-M`` de uma curta achada por ``val.ENDERECO`` (a crase fica de fora)."""
    return m.start("a") - 1, m.end("b") if m.group("b") else m.end("a")


def _achar(
    linha: str, val: ModuleType, modo: str, resolve: Callable[[str], bool] | None = None
) -> Iterator[Endereco]:
    """Os endereços de UMA linha (ou célula), com a forma curta ``:N`` presa ao arquivo antes.

    ``md`` lê como o validador lê `docs/protocol`; ``csv``, como lê as planilhas; ``py``, os
    comentários e docstrings de `src/` (a citação inteira, com ou sem crase, e a curta).

    Em ``csv`` a curta fica presa à inteira MAIS PRÓXIMA antes dela na mesma célula, e só é
    devolvida se essa âncora resolve (``resolve``) num arquivo do repositório: a que não resolve
    não é nossa, e nunca cai numa âncora mais antiga.
    """
    if ":" not in linha:
        return
    ancora: str | None = None
    if modo == "csv":
        inteiras = list(val.ENDERECO_CSV.finditer(linha))
        for m in inteiras:
            b = m.group("b")
            yield (
                m.start(),
                m.end(),
                m["arq"],
                int(m["a"]),
                int(b or m["a"]),
                b is not None,
                False,
                (m.start(), m.end()),
            )
        for c in _CURTA_DE_CSV.finditer(linha):
            vao = c.span("vao")
            anteriores = [i for i in inteiras if i.end() <= vao[0]]
            if not anteriores or (resolve is not None and not resolve(anteriores[-1]["arq"])):
                continue
            ini = vao[0] - 1 if linha[vao[0] - 1] == "`" else vao[0]
            fim = vao[1] + 1 if linha[vao[1] : vao[1] + 1] == "`" else vao[1]
            b = c.group("b")
            yield (
                ini,
                fim,
                anteriores[-1]["arq"],
                int(c["a"]),
                int(b or c["a"]),
                b is not None,
                True,
                vao,
            )
        return
    inteiras = list(val.ENDERECO_CSV.finditer(linha)) if modo == "py" else []
    for m in val.ENDERECO.finditer(linha):
        explicito = m.group("arq")
        if not explicito:
            anteriores = [i for i in inteiras if i.end() <= m.start()]
            if anteriores:
                ancora = anteriores[-1]["arq"]
        else:
            ancora = explicito
        if modo == "py" and explicito:
            continue
        arquivo = explicito or ancora
        if arquivo is None:
            continue
        b = m.group("b")
        yield (
            m.start(),
            m.end(),
            arquivo,
            int(m["a"]),
            int(b or m["a"]),
            b is not None,
            not explicito,
            _vao_da_curta(m) if not explicito else (m.start(), m.end()),
        )
    if modo == "py":
        for m in inteiras:
            b = m.group("b")
            yield (
                m.start(),
                m.end(),
                m["arq"],
                int(m["a"]),
                int(b or m["a"]),
                b is not None,
                False,
                (m.start(), m.end()),
            )


def _canonico(arquivo: str, a: int, b: int, faixa: bool) -> str:
    return f"{arquivo}:{a}-{b}" if faixa else f"{arquivo}:{a}"


def _modo_de(documento: Path) -> str:
    return {".md": "md", ".csv": "csv"}.get(documento.suffix, "py")


_ATE_O_FIM_DO_CAMPO = re.compile(r"[^,\r\n]*")

Celula = tuple[str, int, list[int] | None]
"""``(texto lido, início no texto cru, mapa)``. O ``mapa`` dá, para cada letra do texto lido, o lugar
dela no texto cru; ``None`` quando as duas coincidem (campo sem aspas)."""


def _registros_do_csv(texto: str) -> Iterator[list[Celula]]:
    """Os registros do CSV como o ``csv.reader`` os lê, cada célula com o seu lugar no texto CRU.

    O leitor do ``csv`` não diz onde a célula começa: aspas dobradas (``""``), vírgula e quebra de
    linha dentro dela mudam o deslocamento. A troca por posição precisa do cru.
    """
    i, n = 0, len(texto)
    while i < n:
        registro: list[Celula] = []
        while True:
            inicio = i
            partes: list[str] = []
            mapa: list[int] | None = None
            if i < n and texto[i] == '"':
                mapa = []
                i += 1
                while i < n:
                    j = texto.find('"', i)
                    j = n if j < 0 else j
                    partes.append(texto[i:j])
                    mapa.extend(range(i, j))
                    i = j
                    if i >= n:
                        break
                    if texto.startswith('""', i):
                        partes.append('"')
                        mapa.append(i)
                        i += 2
                        continue
                    i += 1
                    break
                resto = _ATE_O_FIM_DO_CAMPO.match(texto, i)
                assert resto is not None
                partes.append(resto.group())
                mapa.extend(range(i, resto.end()))
                i = resto.end()
            else:
                resto = _ATE_O_FIM_DO_CAMPO.match(texto, i)
                assert resto is not None
                partes.append(resto.group())
                i = resto.end()
            registro.append(("".join(partes), inicio, mapa))
            if i >= n:
                break
            quebra = texto[i]
            i += 1
            if quebra == ",":
                continue
            if quebra == "\r" and texto.startswith("\n", i):
                i += 1
            break
        if len(registro) == 1 and registro[0][0] == "" and registro[0][2] is None:
            registro = []  # a linha em branco: o ``csv.reader`` devolve ``[]``
        yield registro


def _contagens(
    texto: str, val: ModuleType, modo: str, resolve: Callable[[str], bool] | None = None
) -> tuple[collections.Counter[str], collections.Counter[str]]:
    """``(todas, inteiras)``: quantas vezes cada endereço está escrito no texto, e quantas dessas na
    forma inteira. A curta conta presa ao arquivo da inteira que a ancora."""
    todas: collections.Counter[str] = collections.Counter()
    inteiras: collections.Counter[str] = collections.Counter()

    def somar(unidade: str) -> None:
        for _i, _f, arquivo, a, b, faixa, curta, _vao in _achar(unidade, val, modo, resolve):
            endereco = _canonico(arquivo, a, b, faixa)
            todas[endereco] += 1
            if not curta:
                inteiras[endereco] += 1

    if modo == "csv":
        # célula a célula, pela mesma ``_achar``: nenhum endereço cruza a vírgula do CSV
        for registro in csv.reader(io.StringIO(texto, newline="")):
            for celula in registro:
                if _DOIS_PONTOS_E_NUMERO.search(celula) is not None:
                    somar(celula)
        return todas, inteiras
    for linha in texto.split("\n"):
        if _DOIS_PONTOS_E_NUMERO.search(linha) is not None:
            somar(linha)
    return todas, inteiras


def _contagem(
    texto: str, val: ModuleType, modo: str, resolve: Callable[[str], bool] | None = None
) -> collections.Counter[str]:
    """Quantas vezes cada endereço (com a curta presa ao arquivo) está escrito no texto."""
    return _contagens(texto, val, modo, resolve)[0]


def _relativo(raiz: Path, caminho: Path) -> str:
    return caminho.resolve().relative_to(raiz.resolve()).as_posix()


def _historico_do_documento(raiz: Path, relativo: str) -> list[tuple[str, str, bool]]:
    """``[(commit, caminho do documento naquele commit, nasceu ali)]``, do mais novo ao mais velho.

    Segue o documento pelas renomeações (``--follow``): renomear não o faz nascer de novo, e o
    endereço que entrou antes do nome novo tem de ser lido no código de ANTES. Sem isso, a
    `decisoes-de-produto.csv` (renomeada num commit de 279 arquivos) tomava a renomeação por
    nascimento, e o endereço que uma varredura reescreveu passava por recém-nascido.
    """
    feito = _git(
        raiz,
        "log",
        "--follow",
        "-M",
        f"-n{HISTORICO_DA_CRUA}",
        "--format=%x00%H",
        "--name-status",
        "--",
        relativo,
    )
    historico: list[tuple[str, str, bool]] = []
    caminho = relativo
    for bloco in feito.stdout.split("\0")[1:]:
        linhas = [linha for linha in bloco.splitlines() if linha.strip()]
        if not linhas:
            continue
        sha, estado, nome_velho = linhas[0].strip(), "", ""
        for linha in linhas[1:]:
            campos = linha.split("\t")
            if len(campos) >= 2:
                estado, caminho = campos[0][:1], campos[-1]
                nome_velho = campos[1] if estado == "R" and len(campos) == 3 else ""
        historico.append((sha, caminho, estado == "A"))
        if nome_velho:
            caminho = nome_velho  # daqui para trás, o documento tinha o nome velho
    return historico


def _introducoes(
    raiz: Path,
    cat: _Cat,
    val: ModuleType,
    documento: Path,
    atuais: collections.Counter[str],
    resolve: Callable[[str], bool] | None = None,
) -> dict[str, tuple[str | None, bool, bool, int]]:
    """``{endereço: (commit em que entrou, épocas diferentes, o documento nasceu ali, reescritos)}``.

    O commit é o mais antigo da corrida contínua em que o endereço está escrito ao menos tantas
    vezes quanto hoje, seguindo o documento pelas renomeações. ``None``: nenhum commit o tem ainda
    (acabou de ser escrito). O segundo valor sobe quando houve menos cópias antes: as cópias novas
    são de outra época. O quarto é quantos endereços INTEIROS o commit da entrada TIROU do
    documento (o reapontamento em massa troca centenas de uma vez; a curta anda no rastro da inteira
    que a ancora, e contá-la reescreveria como «massa» a célula que só mudou de texto).
    """
    modo = _modo_de(documento)
    vivos = set(atuais)
    entrou: dict[str, tuple[str, bool]] = {}
    tirados: dict[str, int] = {}
    resultado: dict[str, tuple[str | None, bool, bool, int]] = {}
    anterior: tuple[str, collections.Counter[str]] | None = None
    sem_curtas: collections.Counter[str] = collections.Counter()
    for sha, caminho, nasceu in _historico_do_documento(raiz, _relativo(raiz, documento)):
        if not vivos:
            break
        texto = cat.texto(f"{sha}:{caminho}")
        conta, inteiras = (
            _contagens(texto, val, modo, resolve)
            if texto is not None
            else (collections.Counter(), collections.Counter())
        )
        if anterior is not None:
            # o estado deste commit é o de ANTES do mais novo: o que some dele é o que o mais novo tirou
            tirados[anterior[0]] = sum((inteiras - sem_curtas).values())
        anterior = (sha, conta)
        sem_curtas = inteiras
        for endereco in list(vivos):
            if conta[endereco] >= atuais[endereco]:
                entrou[endereco] = (sha, nasceu)
            else:
                vivos.discard(endereco)
                sha_de, nasceu_de = entrou.get(endereco, (None, True))
                resultado[endereco] = (
                    sha_de,
                    conta[endereco] > 0,
                    nasceu_de,
                    tirados.get(sha_de or "", 0),
                )
    for endereco in vivos:
        sha_de, nasceu_de = entrou.get(endereco, (None, True))
        resultado[endereco] = (sha_de, False, nasceu_de, 0)
    return resultado


def levar_crua(
    cat: _Cat,
    relativo: str,
    atual: list[str],
    a: int,
    b: int,
    sha: str | None,
    pistas: set[str] | None = None,
    documento_nasceu_no_commit: bool = True,
    reescritos: int = 0,
) -> tuple[str, tuple[int, int] | None, str]:
    """O bloco citado no commit ``sha``, procurado intacto e único no arquivo de hoje.

    Devolve ``(estado, novo, motivo)``. ``estado``: ``no_lugar``; ``andou`` (``novo`` é o endereço);
    ou o motivo de ir à mão — ``nasceu_errada`` (o histórico prova que o endereço nunca apontou o
    citado), ``ambigua`` (o bloco se repete), ``varredura`` (o documento já existia e o commit
    que reescreveu o endereço tocou centenas de arquivos, ou tirou ``REESCRITA_EM_MASSA``
    endereços dele de uma vez) e ``mudou`` (nenhuma cópia intacta hoje).
    """
    if a < 1 or b < a:
        return "nasceu_errada", None, "a faixa está invertida ou começa em zero"
    if sha is None:
        if b > len(atual):
            return (
                "nasceu_errada",
                None,
                (f"o endereço é novo e a linha não existe: {relativo} tem {len(atual)} linha(s)"),
            )
        return "no_lugar", None, ""
    if not documento_nasceu_no_commit and cat.arquivos(sha) >= VARREDURA_DE_ARQUIVOS:
        return (
            "varredura",
            None,
            (
                f"o commit {sha[:9]}, que reescreveu o endereço num documento que já existia, tocou "
                f"{cat.arquivos(sha)} arquivos: foi uma varredura, e ela não prova onde a linha estava"
            ),
        )
    if not documento_nasceu_no_commit and reescritos >= REESCRITA_EM_MASSA:
        return (
            "varredura",
            None,
            (
                f"o commit {sha[:9]} reescreveu {reescritos} endereços deste documento de uma vez: foi "
                "um reapontamento em massa, e o endereço que ele deixou não prova onde a linha estava"
            ),
        )
    velho = cat.linhas(sha, relativo)
    if velho is None:
        return (
            "nasceu_errada",
            None,
            f"{relativo} não existia no commit {sha[:9]}, em que o endereço entrou",
        )
    if b > len(velho):
        return (
            "nasceu_errada",
            None,
            (
                f"o endereço já nascia errado: {relativo} tinha {len(velho)} linha(s) no commit "
                f"{sha[:9]}, em que ele entrou"
            ),
        )
    bloco = velho[a - 1 : b]
    if not any(linha.strip() for linha in bloco):
        return "nasceu_errada", None, f"o trecho citado estava em branco no commit {sha[:9]}"
    if b == a and len(bloco[0].strip()) < LINHA_CURTA_DEMAIS:
        return (
            "nasceu_errada",
            None,
            (f"a linha citada (`{bloco[0].strip()}`) é curta demais para dizer o que foi citado"),
        )
    if atual[a - 1 : b] == bloco:
        return "no_lugar", None, ""
    corpo = "\n".join(bloco)
    if pistas and not any(pista in corpo for pista in pistas):
        return (
            "nasceu_errada",
            None,
            (
                f"o endereço já nascia errado: no commit {sha[:9]} o trecho citado não tem "
                f"{', '.join(f'`{p}`' for p in sorted(pistas))}, que a frase pôs ao lado"
            ),
        )
    n = len(bloco)

    def lugares(corpo: list[str]) -> list[int]:
        return [i + 1 for i in range(len(corpo) - n + 1) if corpo[i : i + n] == bloco]

    if len(lugares(velho)) > 1:
        return (
            "ambigua",
            None,
            (
                f"o trecho citado já se repetia em {relativo} no commit {sha[:9]}: "
                "não há como saber qual cópia era"
            ),
        )
    hoje = lugares(atual)
    if len(hoje) == 1:
        return "andou", (hoje[0], hoje[0] + n - 1), ""
    if not hoje:
        return (
            "mudou",
            None,
            (f"o trecho citado mudou: nenhuma cópia intacta dele em {relativo} hoje"),
        )
    return (
        "ambigua",
        None,
        f"o trecho citado aparece {len(hoje)} vezes em {relativo}: não há como saber qual",
    )


def _desde(base: int) -> Callable[[int], int]:
    """O mapa de uma linha de markdown: a posição na linha mais o início dela no texto."""
    return lambda i: base + i


def cruas(raiz: Path) -> list[Citacao]:
    """Toda citação de `docs/` sem símbolo prometido, na forma inteira e na curta."""
    val = _validador(raiz)
    resolve = _resolvedor(raiz, val)
    achadas: dict[tuple[Path, str, bool], Citacao] = {}

    def anotar(
        documento: Path,
        texto: str,
        modo: str,
        onde: Callable[[int], int],
        separadores: tuple[str, ...],
        antes: str = "",
    ) -> None:
        """``onde`` leva um índice de ``texto`` ao lugar dele no texto CRU do documento."""
        for inicio, fim, arquivo, a, b, faixa, curta, vao in _achar(texto, val, modo, resolve):
            alvo = val.resolve(arquivo, raiz)
            if alvo is None or val.nomes_prometidos(texto, inicio, fim, separadores):
                continue
            cit = Citacao(documento, arquivo, alvo, a, b, faixa, curta=curta)
            achada = achadas.setdefault((documento, cit.texto, curta), cit)
            if achada is not cit:
                achada.vezes += 1
            achada.pistas |= _pistas(antes + texto, len(antes) + inicio, len(antes) + fim)
            if curta:
                achada.trechos.append((onde(vao[0]), onde(vao[1] - 1) + 1))

    for documento in val.documentos_de(raiz):
        linhas = documento.read_text(encoding="utf-8").split("\n")
        anterior = ""
        for linha, base in zip(linhas, _inicios_das_linhas(linhas), strict=True):
            anotar(documento, linha, "md", _desde(base), (), anterior)
            anterior = linha.lstrip("> ") + " "
    for planilha in val.planilhas_de(raiz):
        for registro in _registros_do_csv(planilha.read_text(encoding="utf-8")):
            for celula, inicio, mapa in registro:

                def onde(i: int, inicio: int = inicio, mapa: list[int] | None = mapa) -> int:
                    return inicio + i if mapa is None else mapa[i]

                anotar(planilha, celula, "csv", onde, val.SEPARADORES_DE_BLOCO)
    return list(achadas.values())


def pelo_historico(
    raiz: Path, candidatas: Sequence[Citacao]
) -> tuple[list[tuple[Citacao, str]], list[str]]:
    """Leva cada citação crua pelo histórico do SEU documento. Devolve (trocas, à mão)."""
    val = _validador(raiz)
    resolve = _resolvedor(raiz, val)
    por_documento: dict[Path, list[Citacao]] = {}
    for cit in candidatas:
        por_documento.setdefault(cit.documento, []).append(cit)
    trocas: list[tuple[Citacao, str]] = []
    a_mao: list[str] = []
    alvos: dict[Path, list[str]] = {}
    with _Cat(raiz) as cat:
        for documento, lista in por_documento.items():
            texto = documento.read_text(encoding="utf-8", errors="replace")
            atuais = _contagem(texto, val, _modo_de(documento), resolve)
            entradas = _introducoes(raiz, cat, val, documento, atuais, resolve)
            escritas: collections.Counter[str] = collections.Counter()
            for cit in lista:
                escritas[_canonico(cit.arquivo, cit.a, cit.b, cit.faixa)] += cit.vezes
            for cit in lista:
                ESTATISTICA["conferidas"] += 1
                endereco = _canonico(cit.arquivo, cit.a, cit.b, cit.faixa)
                rotulo = f"{documento.relative_to(raiz)}: `{cit.texto}`"
                if cit.curta:
                    rotulo += f" (forma curta `{cit.texto[len(cit.arquivo) :]}`)"
                    if documento.suffix == ".csv":
                        ESTATISTICA["curtas_de_csv"] += cit.vezes
                sha, mista, nasceu, reescritos = entradas.get(endereco, (None, False, True, 0))
                if mista:
                    ESTATISTICA["a_mao"] += 1
                    ESTATISTICA["a_mao:misturada"] += 1
                    a_mao.append(
                        f"{rotulo}: o mesmo endereço entrou em épocas diferentes neste "
                        "documento: não há como saber qual cópia vale por qual código"
                    )
                    continue
                if escritas[endereco] != atuais[endereco]:
                    ESTATISTICA["a_mao"] += 1
                    ESTATISTICA["a_mao:misturada"] += 1
                    a_mao.append(
                        f"{rotulo}: o mesmo texto também está escrito com símbolo prometido: "
                        "trocar um trocaria o outro"
                    )
                    continue
                relativo = _relativo(raiz, cit.alvo)
                if cit.alvo not in alvos:
                    alvos[cit.alvo] = cit.alvo.read_text(
                        encoding="utf-8", errors="replace"
                    ).splitlines()
                estado, novo, motivo = levar_crua(
                    cat,
                    relativo,
                    alvos[cit.alvo],
                    cit.a,
                    cit.b,
                    sha,
                    cit.pistas,
                    nasceu,
                    reescritos,
                )
                if estado == "no_lugar":
                    ESTATISTICA["recentes" if sha is None else "no_lugar"] += 1
                elif estado == "andou" and novo is not None:
                    ESTATISTICA["andaram"] += 1
                    trocas.append((cit, cit.novo_texto(*novo)))
                else:
                    ESTATISTICA["a_mao"] += 1
                    ESTATISTICA[f"a_mao:{estado}"] += 1
                    a_mao.append(f"{rotulo}: {motivo}")
    return trocas, a_mao


def _padrao_da_inteira(velho: str) -> re.Pattern[str]:
    return re.compile(r"(?<![A-Za-z0-9_./-])" + re.escape(velho) + r"(?![0-9-])")


def _trocar(texto: str, velho: str, novo: str) -> tuple[str, int]:
    """Troca o endereço ``velho`` inteiro — nunca um prefixo de outro número."""
    return _padrao_da_inteira(velho).subn(novo, texto)


def _trocar_curta(texto: str, cit: Citacao, endereco: str) -> tuple[str, int]:
    """Troca a forma curta ``:N`` SÓ nos trechos em que ela está escrita (``cit.trechos``).

    O trecho é o lugar da curta no texto cru: um ``:N`` igual, ancorado a outro arquivo, na mesma
    linha ou na mesma célula, não é tocado. Um trecho que não mostra mais a curta velha (o texto já
    andou) não é trocado.
    """
    curto_velho = cit.texto[len(cit.arquivo) :]
    curto_novo = endereco[len(cit.arquivo) :]
    total = 0
    for inicio, fim in sorted(cit.trechos, reverse=True):
        if texto[inicio:fim] == curto_velho:
            texto = texto[:inicio] + curto_novo + texto[fim:]
            total += 1
    return texto, total


def _trechos_da_curta(texto: str, cit: Citacao) -> list[tuple[int, int]]:
    """Onde, nas linhas em que o validador a ancorou, a curta de ``cit`` está escrita.

    Para a citação que o validador entrega pela forma inteira e que o documento só escreve na
    curta (``:N`` ao lado de outra citação): o lugar sai da mesma ``_achar`` que as lê, e só vale a
    curta presa ao MESMO arquivo e aos mesmos números.
    """
    val = _validador_carregado()
    modo = _modo_de(cit.documento)
    linhas = texto.split("\n")
    inicios = _inicios_das_linhas(linhas)
    trechos: list[tuple[int, int]] = []
    for numero in sorted(cit.linhas):
        if not 1 <= numero <= len(linhas):
            continue
        for _i, _f, arquivo, a, b, faixa, curta, vao in _achar(linhas[numero - 1], val, modo):
            if curta and (arquivo, a, b, faixa) == (cit.arquivo, cit.a, cit.b, cit.faixa):
                trechos.append((inicios[numero - 1] + vao[0], inicios[numero - 1] + vao[1]))
    return trechos


def _aplicar(texto: str, trocas: Sequence[tuple[Citacao, str]]) -> tuple[str, list[int]]:
    """Aplica as trocas de UM documento sem cascata, e diz quantas vezes cada uma casou.

    ``x:10 -> x:20`` e ``x:20 -> x:30`` não se encadeiam: cada endereço velho vira primeiro um
    marcador, e só depois o marcador vira o endereço novo. A forma curta troca pelo LUGAR onde está
    escrita, de trás para frente (as posições são as do texto que entrou); a inteira, pelo texto.
    """
    marcador = [f"\x00{i}\x00" for i in range(len(trocas))]
    casou = [0] * len(trocas)
    pela_curta = [cit.curta for cit, _endereco in trocas]
    trechos = [list(cit.trechos) if cit.curta else [] for cit, _endereco in trocas]
    inteiras: set[str] = set()
    for i, (cit, _endereco) in enumerate(trocas):
        if cit.curta:
            continue
        if cit.texto not in inteiras and _padrao_da_inteira(cit.texto).search(texto):
            inteiras.add(cit.texto)  # a inteira leva todas as escritas do mesmo texto de uma vez
        else:
            pela_curta[i] = True
            trechos[i] = _trechos_da_curta(texto, cit)
    lugares = sorted((-inicio, i, fim) for i, lista in enumerate(trechos) for inicio, fim in lista)
    usados: set[tuple[int, int]] = set()
    for menos_inicio, i, fim in lugares:
        inicio = -menos_inicio
        if (inicio, fim) in usados:
            continue
        cit, _endereco = trocas[i]
        sozinha = dataclasses.replace(cit, trechos=[(inicio, fim)])
        texto, n = _trocar_curta(texto, sozinha, cit.arquivo + marcador[i])
        if n:
            usados.add((inicio, fim))
            casou[i] += n
    for i, (cit, _endereco) in enumerate(trocas):
        if not pela_curta[i]:
            texto, casou[i] = _trocar(texto, cit.texto, marcador[i])
    for (cit, endereco), marca, curta in zip(trocas, marcador, pela_curta, strict=True):
        texto = texto.replace(marca, endereco[len(cit.arquivo) :] if curta else endereco)
    return texto, casou


def reapontar(raiz: Path, *, escrever: bool) -> tuple[list[str], list[str]]:
    """Devolve (feitos, à mão). Com ``escrever``, grava e confere cada documento."""
    ESTATISTICA.clear()
    feitos: list[str] = []
    citacoes, a_mao = podres_do_validador(raiz)
    do_src, a_mao_src = podres_do_src(raiz)
    citacoes += do_src
    a_mao += a_mao_src
    planos: dict[Path, list[tuple[Citacao, str]]] = {}
    vistos: set[tuple[Path, str]] = set()
    pelo_nome = [c for c in citacoes if not c.podre]
    do_historico = {(c.documento, c.texto, c.curta): c for c in citacoes if c.podre}
    for cit in cruas(raiz) + curtas_do_src(raiz):
        do_historico.setdefault((cit.documento, cit.texto, cit.curta), cit)
    for cit in pelo_nome:
        vistos.add((cit.documento, cit.texto))
        relativo = cit.alvo.resolve().relative_to(raiz.resolve()).as_posix()
        novo = levar(raiz, relativo, cit.a, cit.b, cit.nomes)
        rotulo = (
            f"{cit.documento.relative_to(raiz)}: `{cit.texto}` ({', '.join(sorted(cit.nomes))})"
        )
        if novo is None:
            a_mao.append(f"{rotulo}: nenhuma versão do histórico acha o trecho sem chute")
            continue
        planos.setdefault(cit.documento, []).append((cit, cit.novo_texto(*novo)))
    for cit in com_promessa(raiz):
        if (cit.documento, cit.texto) in vistos:
            continue
        relativo = cit.alvo.resolve().relative_to(raiz.resolve()).as_posix()
        destinos = {pelo_simbolo(raiz, relativo, cit.a, cit.b, nome) for nome in cit.nomes}
        destinos.discard(None)
        if len(destinos) == 1:
            (novo,) = destinos
            assert novo is not None
            planos.setdefault(cit.documento, []).append((cit, cit.novo_texto(*novo)))
        elif len(destinos) > 1:
            a_mao.append(
                f"{cit.documento.relative_to(raiz)}: `{cit.texto}` promete "
                f"{', '.join(sorted(cit.nomes))}, e cada um manda para um lugar"
            )
    trocas_cruas, a_mao_cruas = pelo_historico(raiz, list(do_historico.values()))
    a_mao += a_mao_cruas
    for cit, endereco in trocas_cruas:
        planos.setdefault(cit.documento, []).append((cit, endereco))
    for documento, trocas in planos.items():
        original = documento.read_text(encoding="utf-8")
        if "\x00" in original:
            a_mao.append(
                f"{documento.relative_to(raiz)}: tem byte nulo, não há como trocar sem cascata"
            )
            continue
        texto, casou = _aplicar(original, trocas)
        for (cit, endereco), n in zip(trocas, casou, strict=True):
            if n == 0:
                a_mao.append(
                    f"{documento.relative_to(raiz)}: `{cit.texto}` -> `{endereco}`: o endereço "
                    "não está escrito no documento, nem inteiro nem na forma curta da linha"
                )
                continue
            feitos.append(f"{documento.relative_to(raiz)}: `{cit.texto}` -> `{endereco}` ({n}x)")
        if not escrever or texto == original:
            continue
        documento.write_text(texto, encoding="utf-8")
        quebradas = _quebradas_pela_troca(raiz, documento, {novo for _c, novo in trocas})
        if quebradas:
            documento.write_text(original, encoding="utf-8")
            feitos = [f for f in feitos if not f.startswith(f"{documento.relative_to(raiz)}:")]
            a_mao.append(
                f"{documento.relative_to(raiz)}: devolvido como estava — o endereço novo "
                f"quebraria outra promessa ({'; '.join(quebradas)})"
            )
    return feitos, a_mao


def _quebradas_pela_troca(raiz: Path, documento: Path, novos: set[str]) -> list[str]:
    """As citações do documento que o endereço novo deixou podres."""
    if documento.suffix in (".md", ".csv") and (raiz / "docs") in documento.parents:
        val = _validador(raiz)
        varrer = val.varrer_planilha if documento.suffix == ".csv" else val.varrer_documento
        achados = varrer(documento, raiz, {})[0]
        return [str(a) for a in achados if any(novo in a.endereco for novo in novos)]
    citacoes, _ = podres_do_src(raiz)
    return [
        f"{c.documento.relative_to(raiz)}: `{c.texto}`"
        for c in citacoes
        if c.documento == documento and c.texto in novos
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reaponta as citações `arquivo:linha` que o código deslocou, pelo histórico.",
        epilog=(
            "A citação crua (sem símbolo prometido) anda pelo histórico do documento: o commit em "
            "que o endereço entrou, o arquivo citado NAQUELE commit e o bloco procurado intacto e "
            "único hoje. LIMITE: a citação que já nasceu errada anda errada (foi o caso do "
            "`rumble.ff`); o script move o que apontava, não corrige o que nunca apontou certo. "
            "O endereço que uma varredura (centenas de arquivos) ou um reapontamento em massa "
            "(dezenas de endereços do mesmo documento num commit) deixou vai à mão: ele foi "
            "calculado, e não prova onde a linha estava. A forma curta (`:N`, `:N-M`) vale em .md, "
            "em .csv (solta, depois de vírgula, ponto-e-vírgula, `e` ou `(`) e em prosa de `src/`: "
            "anda com a inteira MAIS PRÓXIMA antes dela, na mesma linha ou célula, só se essa "
            "âncora é um arquivo do repositório, e a troca é pelo lugar onde ela está escrita."
        ),
    )
    parser.add_argument("--escrever", action="store_true", help="grava as trocas e as confere")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="raiz do repositório (padrão: a deste script)",
    )
    args = parser.parse_args(argv)
    raiz = args.root.resolve()
    feitos, a_mao = reapontar(raiz, escrever=args.escrever)
    verbo = "reapontada(s)" if args.escrever else "a reapontar (rode com --escrever)"
    print(f"{len(feitos)} citação(ões) {verbo}:")
    for linha in feitos:
        print(f"  {linha}")
    if ESTATISTICA["conferidas"]:
        print(
            f"cruas: {ESTATISTICA['conferidas']} conferidas — {ESTATISTICA['no_lugar']} no lugar, "
            f"{ESTATISTICA['recentes']} recém-escritas, {ESTATISTICA['andaram']} andaram, "
            f"{ESTATISTICA['a_mao']} à mão ("
            f"{ESTATISTICA['a_mao:mudou']} mudaram sem cópia intacta, "
            f"{ESTATISTICA['a_mao:ambigua']} ambíguas, "
            f"{ESTATISTICA['a_mao:misturada']} de épocas misturadas, "
            f"{ESTATISTICA['a_mao:varredura']} escritas numa varredura ou num reapontamento "
            "em massa, "
            f"{ESTATISTICA['a_mao:nasceu_errada']} já nasceram erradas); "
            f"{ESTATISTICA['curtas_de_csv']} forma(s) curta(s) lida(s) em CSV"
        )
    if a_mao:
        print(f"{len(a_mao)} à mão (o script não chuta):")
        for linha in a_mao:
            print(f"  {linha}")
    return 1 if a_mao else 0


if __name__ == "__main__":
    sys.exit(main())
