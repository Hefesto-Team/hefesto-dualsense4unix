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
import bisect
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
    """A faixa é verdadeira: tem cada nome prometido inteiro e fora de comentário (o ``casa_o_nome``
    do validador) e, em `.py`, não começa antes do `def` dele abraçando código de fora."""
    if a < 1 or b < a or b > len(linhas):
        return False
    val = _validador_carregado()
    corpo = list(linhas)
    sufixo = Path(relativo).suffix
    if not all(val.casa_o_nome(nome, corpo, a, b, sufixo) for nome in nomes):
        return False
    if sufixo != ".py" or a == b:
        return True
    return all(val.abraca_de_fora(corpo, a, b, nome) is None for nome in nomes)


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
        if any(_validador_carregado().casa_o_nome(nome, velho, n, n, Path(relativo).suffix)
               for nome in nomes):
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
    for codigo in val.codigos_de(raiz):
        achados.extend(val.varrer_codigo(codigo, raiz, corpos)[0])
    por_chave: dict[tuple[str, str, bool], Citacao] = {}
    a_mao: list[str] = []
    for achado in achados:
        if achado.forma:
            a_mao.append(f"{achado}: é de forma, e se cura à mão")
            continue
        endereco = _ENDERECO.search(achado.endereco)
        nome = _NOME_NA_QUEIXA.search(achado.motivo)
        if endereco is None:
            a_mao.append(f"{achado}: não entendi o endereço")
            continue
        alvo = val.resolve(endereco["arq"], raiz)
        if alvo is None:
            continue
        curta = achado.curta
        chave = (achado.documento, endereco.group(0).strip("`"), curta)
        if chave not in por_chave:
            a = int(endereco["a"])
            por_chave[chave] = Citacao(
                raiz / achado.documento,
                endereco["arq"],
                alvo,
                a,
                int(endereco["b"] or a),
                endereco["b"] is not None,
                curta=curta,
            )
        por_chave[chave].linhas.add(achado.linha)
        if nome is None:
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
    for codigo in val.codigos_de(raiz):
        for trecho in val.trechos_do_codigo(codigo.read_text(encoding="utf-8")):
            for achado in val.ENDERECO_CSV.finditer(trecho.texto):
                anotar(codigo, trecho.texto, achado, val.SEPARADORES_DE_BLOCO)
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
"""Uma linha só com menos caracteres úteis que isto (`}`, `pass`, `</span>`) não identifica o que foi
citado. Os úteis são os de ``_caracteres_uteis``: sem marcação sem atributo, sem pontuação."""

PROFUNDIDADE_DA_SEGUNDA_CHANCE = 2
"""Quantas voltas a segunda chance dá para trás: o endereço que uma varredura ou um reapontamento em
massa deixou tem o endereço de ANTES dele; se a entrada desse também veio de uma varredura, a volta
seguinte olha o de antes dela, até este limite. Além dele, vai à mão."""

A_SEGUNDA_CHANCE_ATRAVESSA_A_MASSA_QUE_MUDOU_O_TRECHO = True
"""Se a segunda chance atravessa o reapontamento em massa que mudou o TRECHO citado (o endereço de
depois, no commit da massa, não tem o bloco que o de antes tinha na entrada dele). Esse commit pode ter
CORRIGIDO um endereço que nasceu errado, e levar o de antes para a frente desfaria a correção; ou pode
ter errado (o `719e58a46`), e o de antes é o certo. O texto não separa os dois casos sem a pista ao
lado. Com ``False``, a trava manda esses à mão. Decisão de 09/10/2026, a validar por ela: fica
``True`` até a amostra da costura (60 da segunda chance, limiar escrito antes) decidir."""

_TAG_COM_ATRIBUTO = re.compile(r"<[A-Za-z][A-Za-z0-9-]*\s+[^<>/\s][^<>]*>")
_TAG_SEM_ATRIBUTO = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*\s*/?>")


def _caracteres_uteis(linha: str) -> int:
    """Quanto a linha DIZ: as letras, os números e o `_`, sem a marcação que não carrega nada.

    ``</span>``, ``<br>`` e ``</div>`` são cenário, não citado. A tag com atributo fica inteira
    (``<div id="x">``): o atributo identifica. A pontuação e o espaço não contam.
    """
    com_atributo = _TAG_COM_ATRIBUTO.findall(linha)
    resto = _TAG_SEM_ATRIBUTO.sub(" ", _TAG_COM_ATRIBUTO.sub(" ", linha))
    return sum(len(tag) for tag in com_atributo) + sum(c.isalnum() or c == "_" for c in resto)


HISTORICO_DA_CRUA = 2000

ESTATISTICA: collections.Counter[str] = collections.Counter()
"""Chaves de motivo (``a_mao:<estado>``) somam em ``a_mao``."""

ESTADO_DA_MAO: dict[str, str] = {}
"""Da última corrida: a linha de cada «à mão» da via crua e o estado que a mandou para lá."""

DIVIDA: dict[str, list[str]] = {"nova": [], "de antes": []}
"""Da última corrida: o «à mão» que a mudança de agora criou, e o que já era dívida de antes."""


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

    Em ``csv`` a curta fica presa à inteira MAIS PRÓXIMA antes dela na mesma célula
    (``val.ancora_da_curta``: outro arquivo nomeado entre as duas a solta), e só é devolvida se
    essa âncora resolve (``resolve``) num arquivo do repositório: a que não resolve não é nossa, e
    nunca cai numa âncora mais antiga.
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
            presa = val.ancora_da_curta(linha, inteiras, vao[0])
            if presa is None or (resolve is not None and not resolve(presa["arq"])):
                continue
            ini = vao[0] - 1 if linha[vao[0] - 1] == "`" else vao[0]
            fim = vao[1] + 1 if linha[vao[1] : vao[1] + 1] == "`" else vao[1]
            b = c.group("b")
            yield (
                ini,
                fim,
                presa["arq"],
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
            registro = []
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
            caminho = nome_velho
    return historico


class _Memoria:
    """O que a leitura de UM documento já pagou: o histórico, as contagens por commit e os diffs.

    A segunda chance volta ao mesmo documento muitas vezes; sem isto cada volta releria o CSV de
    megabytes em cada commit. Só a contagem fica (as chaves internadas): é o que a pergunta usa.
    """

    def __init__(self) -> None:
        self._historico: dict[str, list[tuple[str, str, bool]]] = {}
        self._contagens: dict[str, collections.Counter[str]] = {}
        self._tirados: dict[tuple[str, str], int] = {}
        self._diffs: dict[tuple[str, str], tuple[dict[str, set[str]], dict[str, str]]] = {}

    def historico(self, raiz: Path, relativo: str) -> list[tuple[str, str, bool]]:
        if relativo not in self._historico:
            self._historico[relativo] = _historico_do_documento(raiz, relativo)
        return self._historico[relativo]

    def conta(
        self,
        cat: _Cat,
        val: ModuleType,
        modo: str,
        resolve: Callable[[str], bool] | None,
        sha: str,
        caminho: str,
    ) -> collections.Counter[str]:
        chave = f"{sha}:{caminho}"
        if chave not in self._contagens:
            texto = cat.texto(chave)
            conta = _contagens(texto, val, modo, resolve)[0] if texto is not None else None
            self._contagens[chave] = collections.Counter(
                {sys.intern(k): n for k, n in (conta or {}).items()}
            )
        return self._contagens[chave]

    def tirados(
        self,
        cat: _Cat,
        val: ModuleType,
        modo: str,
        resolve: Callable[[str], bool] | None,
        de: tuple[str, str],
        mais_velho: tuple[str, str],
    ) -> int:
        """Quantos endereços INTEIROS o commit ``de`` tirou do documento (o mais velho tinha, ele não)."""
        if (de[0], mais_velho[0]) not in self._tirados:
            inteiras = []
            for sha, caminho in (mais_velho, de):
                texto = cat.texto(f"{sha}:{caminho}")
                inteiras.append(
                    _contagens(texto, val, modo, resolve)[1]
                    if texto is not None
                    else collections.Counter()
                )
            self._tirados[(de[0], mais_velho[0])] = sum((inteiras[0] - inteiras[1]).values())
        return self._tirados[(de[0], mais_velho[0])]

    def antes_de(
        self,
        raiz: Path,
        val: ModuleType,
        modo: str,
        resolve: Callable[[str], bool] | None,
        sha: str,
        caminho: str,
        endereco: str,
    ) -> tuple[str | None, str]:
        """``(endereço de antes, "")`` ou ``(None, por que não)``: o que o commit ``sha`` trocou.

        Lê o par «removida → adicionada» do diff DO DOCUMENTO naquele commit. Só vale o par de
        linhas de mesma conta (o hunk troca N por N) e de mesma conta de endereços; a linha nova, a
        que ganhou ou perdeu endereço e o endereço que mais de um de antes explica não têm par.
        """
        chave = (sha, caminho)
        if chave not in self._diffs:
            self._diffs[chave] = _pares_do_diff(raiz, val, modo, resolve, sha, caminho)
        trocados, sem_par = self._diffs[chave]
        if endereco in sem_par:
            return None, sem_par[endereco]
        antigos = trocados.get(endereco, set())
        if not antigos:
            return None, "o diff do documento nesse commit não mostra o endereço sendo trocado"
        if len(antigos) > 1:
            return None, "o endereço de antes tem mais de uma origem no diff do documento"
        (antigo,) = antigos
        return antigo, ""


def _enderecos_da_linha(
    linha: str, val: ModuleType, modo: str, resolve: Callable[[str], bool] | None
) -> list[str]:
    return [
        _canonico(arquivo, a, b, faixa)
        for _i, _f, arquivo, a, b, faixa, _curta, _vao in _achar(linha, val, modo, resolve)
    ]


def _linha_de(quebras: list[int], posicao: int) -> int:
    """A linha (base 1) da letra ``posicao`` do texto cru, dadas as posições das quebras."""
    return bisect.bisect_left(quebras, posicao) + 1


def _celulas_por_linha(texto: str) -> tuple[list[list[str]], dict[int, int]]:
    """``(registros, dono)``: as células LIDAS de cada registro do CSV, e o registro de cada linha física.

    O registro de uma célula com quebra de linha (entre aspas) ocupa mais de uma linha física; o
    diff fala de linhas, e a curta só se prende à inteira da PRÓPRIA célula.
    """
    quebras = [i for i, letra in enumerate(texto) if letra == "\n"]
    registros: list[list[str]] = []
    dono: dict[int, int] = {}
    for registro in _registros_do_csv(texto):
        if not registro:
            continue
        _lido, inicio, _mapa = registro[0]
        ultimo, inicio_ultimo, mapa_ultimo = registro[-1]
        fim = mapa_ultimo[-1] if mapa_ultimo else inicio_ultimo + max(len(ultimo) - 1, 0)
        for numero in range(_linha_de(quebras, inicio), _linha_de(quebras, fim) + 1):
            dono[numero] = len(registros)
        registros.append([celula for celula, _i, _m in registro])
    return registros, dono


def _texto_no_commit(raiz: Path, objeto: str) -> str:
    feito = _git(raiz, "show", objeto)
    return feito.stdout if feito.returncode == 0 else ""


def _pares_do_diff(
    raiz: Path,
    val: ModuleType,
    modo: str,
    resolve: Callable[[str], bool] | None,
    sha: str,
    caminho: str,
) -> tuple[dict[str, set[str]], dict[str, str]]:
    """``({endereço novo: {endereços de antes}}, {endereço novo: por que não tem par})`` do commit.

    O CSV se lê por CÉLULA, como ``_contagens`` o lê: a linha física do diff junta células, e a
    curta de uma célula sem inteira se prendia à inteira de OUTRA (medido em 08/10/2026: 170
    curtas de `docs/data` assim, 0 pela leitura por célula). O par é de registro com registro
    (as linhas trocadas do hunk) e, dentro dele, de célula com célula.
    """
    feito = subprocess.run(
        [
            "git",
            "-C",
            str(raiz),
            "diff",
            "-U0",
            "--no-color",
            "--no-ext-diff",
            "--no-renames",
            f"{sha}^",
            sha,
            "--",
            caminho,
        ],
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    hunks: list[tuple[int, int, list[str], list[str]]] = []
    removidas: list[str] = []
    adicionadas: list[str] = []
    de_antes = de_depois = 0
    dentro = False
    for linha in feito.stdout.split("\n") if feito.returncode == 0 else []:
        if linha.startswith("@@"):
            if dentro:
                hunks.append((de_antes, de_depois, removidas, adicionadas))
            cabeca = _HUNK.match(linha)
            de_antes = int(cabeca["os"]) if cabeca else 0
            de_depois = int(cabeca["ns"]) if cabeca else 0
            removidas, adicionadas, dentro = [], [], True
        elif dentro and linha.startswith("-"):
            removidas.append(linha[1:])
        elif dentro and linha.startswith("+"):
            adicionadas.append(linha[1:])
    if dentro:
        hunks.append((de_antes, de_depois, removidas, adicionadas))
    trocados: dict[str, set[str]] = collections.defaultdict(set)
    sem_par: dict[str, str] = {}

    def parear(velhas: list[str], novas: list[str], quais: str) -> None:
        """Pareia as unidades (linhas, ou células de um registro) de mesma posição."""
        for velha, nova in zip(velhas, novas, strict=True):
            depois = _enderecos_da_linha(nova, val, modo, resolve)
            if not depois:
                continue
            antes = _enderecos_da_linha(velha, val, modo, resolve)
            if len(antes) == len(depois):
                for velho, novo in zip(antes, depois, strict=True):
                    if velho != novo:
                        trocados[novo].add(velho)
                continue
            porque = (
                f"a {quais} tinha {len(antes)} endereço(s) e passou a ter {len(depois)}: "
                "não há par de endereços"
            )
            for endereco in depois:
                sem_par.setdefault(endereco, porque)

    def sem_par_de(unidades: list[str], porque: str) -> None:
        for unidade in unidades:
            for endereco in _enderecos_da_linha(unidade, val, modo, resolve):
                sem_par.setdefault(endereco, porque)

    def desigual(velhas: list[str], novas: list[str]) -> str:
        return (
            f"o diff do documento troca {len(velhas)} linha(s) por {len(novas)}: "
            "não há par de linhas"
        )

    if modo != "csv":
        for _de_antes, _de_depois, velhas, novas in hunks:
            if len(velhas) != len(novas):
                sem_par_de(novas, desigual(velhas, novas))
            else:
                parear(velhas, novas, "linha")
        return dict(trocados), sem_par

    registros_antes, dono_antes = _celulas_por_linha(_texto_no_commit(raiz, f"{sha}^:{caminho}"))
    registros_depois, dono_depois = _celulas_por_linha(_texto_no_commit(raiz, f"{sha}:{caminho}"))
    pares: dict[tuple[int, int], None] = {}
    for de_antes, de_depois, velhas, novas in hunks:
        if len(velhas) != len(novas):
            tocados = {
                dono_depois[n] for n in range(de_depois, de_depois + len(novas)) if n in dono_depois
            }
            sem_par_de(
                [celula for k in sorted(tocados) for celula in registros_depois[k]],
                desigual(velhas, novas),
            )
            continue
        for i in range(len(novas)):
            r_antes = dono_antes.get(de_antes + i)
            r_depois = dono_depois.get(de_depois + i)
            if r_antes is not None and r_depois is not None:
                pares.setdefault((r_antes, r_depois))
    for r_antes, r_depois in pares:
        velhas, novas = registros_antes[r_antes], registros_depois[r_depois]
        if len(velhas) != len(novas):
            sem_par_de(
                novas,
                f"o registro tinha {len(velhas)} célula(s) e passou a ter {len(novas)}: "
                "não há par de células",
            )
            continue
        parear(velhas, novas, "célula")
    return dict(trocados), sem_par


def _introducoes(
    raiz: Path,
    cat: _Cat,
    val: ModuleType,
    documento: Path,
    atuais: collections.Counter[str],
    resolve: Callable[[str], bool] | None = None,
    *,
    depois_de: str | None = None,
    memo: _Memoria | None = None,
) -> dict[str, tuple[str | None, bool, bool, int]]:
    """``{endereço: (commit em que entrou, épocas diferentes, o documento nasceu ali, reescritos)}``.

    O commit é o mais antigo da corrida contínua em que o endereço está escrito ao menos tantas
    vezes quanto hoje, seguindo o documento pelas renomeações. ``None``: nenhum commit o tem ainda
    (acabou de ser escrito). O segundo valor sobe quando houve menos cópias antes: as cópias novas
    são de outra época. O quarto é quantos endereços INTEIROS o commit da entrada TIROU do
    documento (o reapontamento em massa troca centenas de uma vez; a curta anda no rastro da inteira
    que a ancora, e contá-la reescreveria como «massa» a célula que só mudou de texto).

    ``depois_de``: o commit a partir do qual se olha para trás (sem ele); ``atuais`` é então a
    contagem do documento NAQUELE instante, não a de hoje.
    """
    modo = _modo_de(documento)
    memo = memo if memo is not None else _Memoria()
    historico = memo.historico(raiz, _relativo(raiz, documento))
    if depois_de is not None:
        shas = [sha for sha, _caminho, _nasceu in historico]
        historico = historico[shas.index(depois_de) + 1 :] if depois_de in shas else []
    vivos = set(atuais)
    entrou: dict[str, tuple[str, str, bool]] = {}
    resultado: dict[str, tuple[str | None, bool, bool, int]] = {}
    for sha, caminho, nasceu in historico:
        if not vivos:
            break
        conta = memo.conta(cat, val, modo, resolve, sha, caminho)
        for endereco in list(vivos):
            if conta[endereco] >= atuais[endereco]:
                entrou[endereco] = (sha, caminho, nasceu)
            else:
                vivos.discard(endereco)
                sha_de, caminho_de, nasceu_de = entrou.get(endereco, ("", "", True))
                reescritos = (
                    memo.tirados(cat, val, modo, resolve, (sha_de, caminho_de), (sha, caminho))
                    if sha_de
                    else 0
                )
                resultado[endereco] = (sha_de or None, conta[endereco] > 0, nasceu_de, reescritos)
    for endereco in vivos:
        sha_de, _caminho_de, nasceu_de = entrou.get(endereco, ("", "", True))
        resultado[endereco] = (sha_de or None, False, nasceu_de, 0)
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
    destino: tuple[int, int] | None = None,
) -> tuple[str, tuple[int, int] | None, str]:
    """O bloco citado no commit ``sha``, procurado intacto e único no arquivo de hoje.

    ``destino``: o endereço que o documento diz HOJE, quando ``a``-``b`` é o de uma entrada de antes
    (a segunda chance). O bloco é lido em ``a``-``b``, mas o «no lugar» pergunta pelo destino.

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
    if b == a and _caracteres_uteis(bloco[0]) < LINHA_CURTA_DEMAIS:
        return (
            "nasceu_errada",
            None,
            (
                f"a linha citada (`{bloco[0].strip()}`) é curta demais para dizer o que foi citado "
                "(só marcação ou pontuação não identifica nada)"
            ),
        )
    de, ate = destino or (a, b)
    if atual[de - 1 : ate] == bloco:
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


_ENDERECO_CANONICO = re.compile(r"(?P<arq>.+):(?P<a>\d+)(?:-(?P<b>\d+))?")


def segunda_chance(
    raiz: Path,
    cat: _Cat,
    val: ModuleType,
    resolve: Callable[[str], bool] | None,
    memo: _Memoria,
    documento: Path,
    cit: Citacao,
    sha: str,
    atual: list[str],
    relativo: str,
    motivo_da_varredura: str,
    *,
    endereco: str | None = None,
    destino: tuple[int, int] | None = None,
    volta: int = 1,
) -> tuple[str, tuple[int, int] | None, str]:
    """O endereço que uma varredura ou um reapontamento em massa deixou não prova nada; o de ANTES dele, sim.

    Lê no diff do documento, naquele commit, qual endereço a linha tinha antes (``endereco`` é o que o
    documento diz depois), acha a entrada desse endereço de antes e roda ``levar_crua`` com o
    bloco DAQUELA entrada. Devolve o mesmo ``(estado, novo, motivo)``: ``no_lugar`` (o endereço de
    hoje já tem o bloco: a varredura acertou), ``andou`` (o bloco está intacto e único em outro
    lugar), ou o motivo de seguir à mão. Sem par de linhas, com a faixa de outra largura (o bloco
    de antes escreveria ``:N-N`` ou cortaria a faixa), sem a entrada de antes, ou depois de
    ``PROFUNDIDADE_DA_SEGUNDA_CHANCE`` voltas, fica ``varredura``, com o motivo de antes e o desta volta.
    """
    endereco = endereco or _canonico(cit.arquivo, cit.a, cit.b, cit.faixa)
    destino = destino or (cit.a, cit.b)

    def sem_prova(porque: str) -> tuple[str, tuple[int, int] | None, str]:
        return "varredura", None, f"{motivo_da_varredura}; sem segunda chance: {porque}"

    if _relativo(raiz, documento) in val.CODIGO_COM_CITACOES:
        return sem_prova("o arquivo de código só se reaponta em massa à mão, conferido")
    if volta > PROFUNDIDADE_DA_SEGUNDA_CHANCE:
        return sem_prova(
            f"o endereço de antes também veio de uma varredura ou de um reapontamento em massa, "
            f"{PROFUNDIDADE_DA_SEGUNDA_CHANCE} voltas atrás"
        )
    modo = _modo_de(documento)
    historico = memo.historico(raiz, _relativo(raiz, documento))
    posicao = next((i for i, (s, _c, _n) in enumerate(historico) if s == sha), None)
    if posicao is None or posicao + 1 >= len(historico):
        return sem_prova("o documento nasceu nesse commit, ou o histórico acaba nele")
    antigo, porque = memo.antes_de(raiz, val, modo, resolve, sha, historico[posicao][1], endereco)
    if antigo is None:
        return sem_prova(porque)
    achado = _ENDERECO_CANONICO.fullmatch(antigo)
    if achado is None or achado["arq"] != cit.arquivo:
        return sem_prova("o commit trocou também o arquivo citado")
    a, b = int(achado["a"]), int(achado["b"] or achado["a"])
    if b - a != destino[1] - destino[0]:
        return sem_prova(f"o commit mudou a largura do endereço (`{antigo}` -> `{endereco}`)")
    sha_antes, caminho_antes, _ = historico[posicao + 1]
    quantas = memo.conta(cat, val, modo, resolve, sha_antes, caminho_antes)[antigo]
    if quantas == 0:
        return sem_prova(f"o endereço de antes (`{antigo}`) não está no documento antes do commit")
    entrada = _introducoes(
        raiz,
        cat,
        val,
        documento,
        collections.Counter({antigo: quantas}),
        resolve,
        depois_de=sha,
        memo=memo,
    )[antigo]
    sha2, mista, nasceu, reescritos = entrada
    if sha2 is None or mista:
        return sem_prova(
            f"o endereço de antes (`{antigo}`) entrou em épocas diferentes no documento"
        )
    if not A_SEGUNDA_CHANCE_ATRAVESSA_A_MASSA_QUE_MUDOU_O_TRECHO:
        mudou = _a_massa_mudou_o_trecho(cat, relativo, sha, endereco, sha2, (a, b))
        if mudou:
            return sem_prova(mudou)
    estado, novo, motivo = levar_crua(
        cat, relativo, atual, a, b, sha2, cit.pistas, nasceu, reescritos, destino
    )
    if estado == "varredura":
        return segunda_chance(
            raiz,
            cat,
            val,
            resolve,
            memo,
            documento,
            cit,
            sha2,
            atual,
            relativo,
            motivo_da_varredura,
            endereco=antigo,
            destino=destino,
            volta=volta + 1,
        )
    if estado in ("no_lugar", "andou"):
        return estado, novo, ""
    return (
        estado,
        None,
        f"pelo endereço de antes da varredura (`{antigo}`, commit {sha2[:9]}): {motivo}",
    )


def _a_massa_mudou_o_trecho(
    cat: _Cat, relativo: str, sha: str, endereco: str, sha2: str, antes: tuple[int, int]
) -> str:
    """Por que o commit ``sha`` (a massa) mudou o trecho citado, ou ``""`` se ele só o levou.

    Compara o bloco do endereço de antes (``antes``) no commit em que ELE entrou (``sha2``) com o
    bloco do endereço que a massa deixou (``endereco``) no commit dela. Iguais: a massa só acompanhou
    o código. Diferentes: ela trocou o que se citava, o que pode ter sido uma correção.
    """
    achado = _ENDERECO_CANONICO.fullmatch(endereco)
    velho, depois = cat.linhas(sha2, relativo), cat.linhas(sha, relativo)
    if achado is None or velho is None or depois is None:
        return ""
    a, b = antes
    ea, eb = int(achado["a"]), int(achado["b"] or achado["a"])
    if b > len(velho) or eb > len(depois) or velho[a - 1 : b] == depois[ea - 1 : eb]:
        return ""
    return (
        f"o commit {sha[:9]}, que reescreveu o endereço sem prova, mudou o trecho citado "
        f"(`{endereco}` não tem o bloco que o endereço de antes tinha no commit {sha2[:9]}): pode ter "
        "sido uma correção, e a segunda chance não a desfaz"
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
        so_inteiras: bool = False,
    ) -> None:
        """``onde`` leva um índice de ``texto`` ao lugar dele no texto CRU do documento."""
        for inicio, fim, arquivo, a, b, faixa, curta, vao in _achar(texto, val, modo, resolve):
            if curta and so_inteiras:
                continue
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
    for codigo in val.codigos_de(raiz):
        for trecho in val.trechos_do_codigo(codigo.read_text(encoding="utf-8")):
            anotar(codigo, trecho.texto, "csv", _desde(0), val.SEPARADORES_DE_BLOCO,
                   so_inteiras=True)
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
            memo = _Memoria()
            entradas = _introducoes(raiz, cat, val, documento, atuais, resolve, memo=memo)
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
                    ESTADO_DA_MAO[a_mao[-1]] = "misturada"
                    continue
                if escritas[endereco] != atuais[endereco]:
                    ESTATISTICA["a_mao"] += 1
                    ESTATISTICA["a_mao:misturada"] += 1
                    a_mao.append(
                        f"{rotulo}: o mesmo texto também está escrito com símbolo prometido: "
                        "trocar um trocaria o outro"
                    )
                    ESTADO_DA_MAO[a_mao[-1]] = "misturada"
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
                if estado == "varredura":
                    estado, novo, motivo = segunda_chance(
                        raiz,
                        cat,
                        val,
                        resolve,
                        memo,
                        documento,
                        cit,
                        sha or "",
                        alvos[cit.alvo],
                        relativo,
                        motivo,
                    )
                    ESTATISTICA["segunda_chance"] += 1
                    if estado in ("no_lugar", "andou"):
                        ESTATISTICA[f"segunda_chance:{estado}"] += 1
                if estado == "no_lugar":
                    ESTATISTICA["recentes" if sha is None else "no_lugar"] += 1
                elif estado == "andou" and novo is not None:
                    ESTATISTICA["andaram"] += 1
                    trocas.append((cit, cit.novo_texto(*novo)))
                else:
                    ESTATISTICA["a_mao"] += 1
                    ESTATISTICA[f"a_mao:{estado}"] += 1
                    a_mao.append(f"{rotulo}: {motivo}")
                    ESTADO_DA_MAO[a_mao[-1]] = estado
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
    trechos = [
        (list(cit.trechos) or _trechos_da_curta(texto, cit)) if cit.curta else []
        for cit, _endereco in trocas
    ]
    inteiras: set[str] = set()
    for i, (cit, _endereco) in enumerate(trocas):
        if cit.curta:
            continue
        if cit.texto not in inteiras and _padrao_da_inteira(cit.texto).search(texto):
            inteiras.add(cit.texto)
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


_LINHA_DA_MAO = re.compile(r"^(?P<doc>[^\s`]+): `(?P<texto>[^`]+)`")


def _ref_padrao(raiz: Path) -> str:
    """De onde se mede «a mudança de agora»: o ``merge-base`` com ``dev``; sem ``dev``, o ``HEAD``."""
    feito = _git(raiz, "merge-base", "dev", "HEAD")
    return feito.stdout.strip() if feito.returncode == 0 and feito.stdout.strip() else "HEAD"


def _classificar_a_mao(
    raiz: Path, a_mao: Sequence[str], ref: str, certas: set[str]
) -> dict[str, list[str]]:
    """Separa o «à mão» em NOVO (a mudança desde ``ref`` o criou) e DE ANTES.

    É novo quando o endereço entrou no documento depois de ``ref``, ou quando as linhas ``a..b`` do
    arquivo citado diferem entre ``ref`` e a árvore de hoje. Linha que não se sabe ler, ou que o
    próprio script acabou de causar (``certas``: documento devolvido, troca que não casou), é nova.
    """
    val = _validador(raiz)
    resolve = _resolvedor(raiz, val)
    divida: dict[str, list[str]] = {"nova": [], "de antes": []}
    documentos: dict[str, tuple[collections.Counter[str], collections.Counter[str]] | None] = {}

    def contagens(
        documento: str,
    ) -> tuple[collections.Counter[str], collections.Counter[str]] | None:
        if documento not in documentos:
            antes = cat.texto(f"{ref}:{documento}")
            caminho = raiz / documento
            if antes is None or not caminho.is_file():
                documentos[documento] = None
            else:
                modo = _modo_de(caminho)
                hoje = caminho.read_text(encoding="utf-8", errors="replace")
                documentos[documento] = (
                    _contagem(antes, val, modo, resolve),
                    _contagem(hoje, val, modo, resolve),
                )
        return documentos[documento]

    def de_antes(linha: str) -> bool:
        lida = _LINHA_DA_MAO.match(linha)
        achado = _ENDERECO.search(lida["texto"]) if lida else None
        if lida is None or achado is None or linha in certas:
            return False
        a = int(achado["a"])
        b = int(achado["b"] or a)
        conta = contagens(lida["doc"])
        endereco = _canonico(achado["arq"], a, b, achado["b"] is not None)
        if conta is None or conta[0][endereco] < conta[1][endereco]:
            return False
        alvo = val.resolve(achado["arq"], raiz)
        velhas = cat.linhas(ref, _relativo(raiz, alvo)) if alvo is not None else None
        if alvo is None or velhas is None:
            return False
        hoje = alvo.read_text(encoding="utf-8", errors="replace").splitlines()
        return bool(velhas[a - 1 : b] == hoje[a - 1 : b])

    with _Cat(raiz) as cat:
        for linha in a_mao:
            divida["de antes" if de_antes(linha) else "nova"].append(linha)
    return divida


def reapontar(
    raiz: Path, *, escrever: bool, desde: str | None = None
) -> tuple[list[str], list[str]]:
    """Devolve (feitos, à mão). Com ``escrever``, grava e confere cada documento.

    ``desde``: o commit a partir do qual o «à mão» é NOVO (``DIVIDA``); o padrão é o ``merge-base``
    com ``dev``. Um ``desde`` que não existe levanta ``ValueError`` antes de qualquer leitura.
    """
    ref = desde or _ref_padrao(raiz)
    resolvido = _git(raiz, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    if resolvido.returncode != 0:
        raise ValueError(f"`--desde {ref}` não é um commit deste repositório")
    ref = resolvido.stdout.strip()
    ESTATISTICA.clear()
    ESTADO_DA_MAO.clear()
    certas: set[str] = set()
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
        ja = do_historico.setdefault((cit.documento, cit.texto, cit.curta), cit)
        if ja.curta and not ja.trechos:
            ja.trechos = list(cit.trechos)
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
            certas.add(a_mao[-1])
            continue
        texto, casou = _aplicar(original, trocas)
        for (cit, endereco), n in zip(trocas, casou, strict=True):
            if n == 0:
                a_mao.append(
                    f"{documento.relative_to(raiz)}: `{cit.texto}` -> `{endereco}`: o endereço "
                    "não está escrito no documento, nem inteiro nem na forma curta da linha"
                )
                certas.add(a_mao[-1])
                continue
            presa = f" (curta, presa a `{cit.arquivo}`)" if cit.curta else ""
            feitos.append(
                f"{documento.relative_to(raiz)}: `{cit.texto}` -> `{endereco}` ({n}x){presa}"
            )
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
            certas.add(a_mao[-1])
    DIVIDA.clear()
    DIVIDA.update(_classificar_a_mao(raiz, a_mao, ref, certas))
    DIVIDA["ref"] = [ref]
    return feitos, a_mao


def _quebradas_pela_troca(raiz: Path, documento: Path, novos: set[str]) -> list[str]:
    """As citações do documento que o endereço novo deixou podres."""
    val = _validador(raiz)
    if documento.suffix in (".md", ".csv") and (raiz / "docs") in documento.parents:
        varrer = val.varrer_planilha if documento.suffix == ".csv" else val.varrer_documento
        achados = varrer(documento, raiz, {})[0]
        return [str(a) for a in achados if any(novo in a.endereco for novo in novos)]
    if _relativo(raiz, documento) in val.CODIGO_COM_CITACOES:
        achados = val.varrer_codigo(documento, raiz, {})[0]
        return [str(a) for a in achados if any(novo in a.endereco for novo in novos)]
    citacoes, _ = podres_do_src(raiz)
    return [
        f"{c.documento.relative_to(raiz)}: `{c.texto}`"
        for c in citacoes
        if c.documento == documento and c.texto in novos
    ]


_MOTIVO_DA_MAO = {
    "varredura": "varredura ou massa sem prova",
    "mudou": "mudaram",
    "ambigua": "ambíguas",
    "misturada": "de épocas misturadas",
    "nasceu_errada": "nasceram erradas",
}


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
            "âncora é um arquivo do repositório, e a troca é pelo lugar onde ela está escrita. "
            "SEGUNDA CHANCE: antes de mandar à mão o endereço que uma varredura ou um "
            "reapontamento em massa deixou, o script lê no diff do documento, naquele commit, o "
            "endereço de ANTES da mesma linha, acha a entrada dele e leva o bloco daquela entrada: "
            "se o endereço de hoje já o tem, fica no lugar; se ele existe intacto e único em outro "
            "lugar, anda; senão fica à mão. Sem par (no CSV, de registro e de célula; no resto, "
            "de linha: contagem desigual de linhas ou de endereços, ou faixa de outra largura), sem "
            "a entrada de antes, ou se ela também veio de uma varredura mais de "
            f"{PROFUNDIDADE_DA_SEGUNDA_CHANCE} voltas atrás, fica à mão sem chute. Com "
            "A_SEGUNDA_CHANCE_ATRAVESSA_A_MASSA_QUE_MUDOU_O_TRECHO = False, fica à mão também o "
            "endereço que a varredura deixou num trecho diferente do de antes (pode ter sido "
            "correção). A LINHA TEM DE "
            "TER CONTEÚDO: marcação sem atributo (`</span>`, `<br>`) e pontuação não contam; "
            "a tag com atributo conta. "
            "O RC diz o que FALTA, não a dívida: vale 1 quando há troca a escrever (modo lista), "
            "à mão NOVA (o endereço entrou no documento depois de --desde, ou as linhas citadas "
            "do arquivo mudaram desde então) ou o --escrever devolveu um documento; a dívida de "
            "antes é contada por motivo, à parte, e não muda o rc."
        ),
    )
    parser.add_argument("--escrever", action="store_true", help="grava as trocas e as confere")
    parser.add_argument(
        "--desde",
        metavar="REF",
        default=None,
        help="de onde se mede «à mão nova» (padrão: o merge-base com `dev`; sem `dev`, o HEAD)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="raiz do repositório (padrão: a deste script)",
    )
    args = parser.parse_args(argv)
    raiz = args.root.resolve()
    try:
        feitos, a_mao = reapontar(raiz, escrever=args.escrever, desde=args.desde)
    except ValueError as erro:
        parser.error(str(erro))
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
    if ESTATISTICA["segunda_chance"]:
        resto = ESTATISTICA["segunda_chance"] - ESTATISTICA["segunda_chance:no_lugar"]
        print(
            f"segunda chance (varredura ou massa): {ESTATISTICA['segunda_chance']} lidas — "
            f"{ESTATISTICA['segunda_chance:no_lugar']} no lugar, "
            f"{ESTATISTICA['segunda_chance:andou']} andaram, "
            f"{resto - ESTATISTICA['segunda_chance:andou']} seguem à mão"
        )
    nova, de_antes = DIVIDA["nova"], DIVIDA["de antes"]
    ref = DIVIDA["ref"][0][:9] if DIVIDA.get("ref") else "?"
    if a_mao:
        print(
            f"{len(a_mao)} à mão (o script não chuta): {len(nova)} nova(s) desde {ref}, "
            f"{len(de_antes)} de antes"
        )
    if nova:
        print(f"à mão NOVA (a mudança desde {ref} deslocou e o script não levou; o rc fica 1):")
        for linha in nova:
            print(f"  {linha}")
    if de_antes:
        por_motivo = collections.Counter(
            _MOTIVO_DA_MAO.get(ESTADO_DA_MAO.get(x, ""), "outras") for x in de_antes
        )
        print(
            "à mão DE ANTES (dívida que esta mudança não criou; não muda o rc): "
            + ", ".join(f"{n} {motivo}" for motivo, n in por_motivo.most_common())
        )
        for linha in de_antes:
            print(f"  {linha}")
    return 1 if (feitos and not args.escrever) or nova else 0


if __name__ == "__main__":
    sys.exit(main())
