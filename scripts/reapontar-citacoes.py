#!/usr/bin/env python3
"""reapontar-citacoes.py — a citação `arquivo:linha` anda junto com o código.

POR QUE ELE EXISTE (25/09/2026)
--------------------------------
Toda leva que insere código no meio de um arquivo apodrece as citações que
apontam para baixo dele, e alguém as reaponta à mão: 27 de uma vez em 10/09, 30
no merge da 6e em 25/09 (e as oito faixas de `coop.py` cravadas numa régua), e
mais duas horas depois, quando o `doctor.sh` ganhou uma função. A ordem dela,
no mesmo dia: *«erro no install e durante o Merge quero q vc mesmo corrija na
origem melhorando o produto e o tornando cada vez mais inteligente e
integrado»*. <!-- noqa-acento: citação literal dela -->

O validador (`validar-citacoes-de-linha.py`) sabe QUAL símbolo cada citação
promete; a régua dos comentários de `src/`
(`tests/unit/test_portao_o_par_com_metade_ligada.py`) também. O que faltava era
saber PARA ONDE a linha foi, e isso o git sabe.

COMO ELE REAPONTA, e por que não é aritmética
---------------------------------------------
Para cada citação que reprova, e que promete um símbolo:

1. procura no histórico do arquivo citado a versão MAIS RECENTE em que a faixa
   era verdadeira (continha o símbolo prometido);
2. leva a faixa daquela versão até o arquivo de hoje pelos hunks do
   `git diff -U0` — a mesma conta que o `git blame` faz: linha que nenhum hunk
   tocou anda o que os hunks de cima andaram;
3. se uma ponta da faixa caiu dentro de um hunk, procura o BLOCO daquela versão,
   idêntico, no arquivo de hoje — só vale se ele aparece uma vez (é assim que a
   função que mudou de lugar é achada);
4. se nem isso, leva a faixa pela linha do próprio símbolo.

Só escreve quando a faixa nova contém TODO símbolo prometido. Depois de escrever
um documento, roda o validador de novo nele: se alguma citação que passava
passou a reprovar (o mesmo endereço servia a duas promessas), o documento volta
como estava e a citação vai para a lista «à mão».

Citação sem símbolo prometido não se reaponta: sem promessa não há como saber
quando ela era verdadeira. Ela sai na lista «à mão», com o motivo.

A SEGUNDA PERGUNTA: A FUNÇÃO INTEIRA QUE FICOU À DERIVA, E PASSAVA VERDE
------------------------------------------------------------------------
O validador pergunta se o símbolo prometido está DENTRO da faixa. Uma citação
da função inteira que andou menos que o tamanho dela continua com a linha do
`def` lá dentro, e passa verde apontando para o código errado. Medido no mapa em
25/09: de 184 citações que prometem uma função ou classe de definição única, 33
tinham o tamanho exato da função e estavam fora do lugar (`read_state` citado
em 3901-3982, e ele mora em 3971-4052; `numeros_de_jogador` 26 linhas acima de
onde está). Para arquivo `.py`, e só quando o símbolo tem UMA definição, a
citação é da função inteira se tem o tamanho dela hoje, ou se numa versão do
histórico ela batia exatamente com a função; então ela vai para onde a função
está. Citação de trecho de dentro da função não é tocada por esta pergunta.

A TERCEIRA: O TRECHO QUE ABRAÇA O `def` COMEÇANDO EM CÓDIGO DE FORA
--------------------------------------------------------------------
O trecho do começo da função (as primeiras 34 linhas do `_spawn_player`) que
andou menos que o próprio tamanho também passava verde na pergunta 2. A
pergunta 3 do validador (`abraca_de_fora`) o reprova, e o `_contem` daqui faz
a MESMA pergunta, a ele, para decidir qual versão do histórico era verdadeira
— então o trecho anda pelos hunks como qualquer outra citação podre.

Uso:

    python3 scripts/reapontar-citacoes.py              # só mostra
    python3 scripts/reapontar-citacoes.py --escrever   # reaponta e confere
"""

from __future__ import annotations

import argparse
import ast
import csv
import functools
import importlib.util
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

#: Quantas versões do arquivo citado ele olha para trás, no máximo. A versão
#: verdadeira costuma ser a de um ou dois commits antes; 400 cobre uma leva
#: inteira de costura sem deixar a busca sem teto.
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
    #: As linhas do documento em que o validador a achou. É o que deixa
    #: escrever a forma curta ``:N``, que só vale ancorada na MESMA linha.
    linhas: set[int] = field(default_factory=set)

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


def _contem(
    linhas: Sequence[str], a: int, b: int, nomes: set[str], relativo: str = ""
) -> bool:
    """A faixa é verdadeira: contém todo nome prometido e, em `.py`, não
    abraça o `def` de nenhum deles começando em código de fora (a pergunta 3
    do validador, perguntada a ele)."""
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
            # Inserção DEPOIS da linha `os_` da versão velha.
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
    """A faixa ``a-b`` de ``relativo``, levada para onde o trecho que ela prometia está hoje.

    ``None`` quando nenhuma versão do histórico tinha a promessa na faixa, ou
    quando o trecho não pode ser achado hoje sem chute.
    """
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
    # Uma ponta caiu num hunk: o bloco inteiro, idêntico e ÚNICO, no arquivo de hoje.
    bloco = velho[a - 1 : b]
    lugares = [
        i + 1 for i in range(len(atual) - len(bloco) + 1) if atual[i : i + len(bloco)] == bloco
    ]
    if len(lugares) == 1 and _contem(atual, lugares[0], lugares[0] + len(bloco) - 1, nomes, relativo):
        return lugares[0], lugares[0] + len(bloco) - 1
    if len(lugares) > 1 or hunks is None:
        return None
    # Pela linha do próprio símbolo: a primeira da faixa que o nomeia.
    for n in range(a, b + 1):
        if any(nome in velho[n - 1] for nome in nomes):
            hoje = _levar_linha(n, hunks)
            if hoje is None:
                return None
            a2, b2 = a + (hoje - n), b + (hoje - n)
            return (a2, b2) if _contem(atual, a2, b2, nomes, relativo) else None
    return None


#: Quantas versões do arquivo a pergunta da deriva olha para trás: ela parseia
#: cada uma (com cache), e é a pergunta mais cara do script.
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
    """A citação da função (ou classe) INTEIRA, ou da linha do ``def``, que ficou à deriva.

    ``None`` quando ela está no lugar, quando o símbolo não tem uma definição só,
    ou quando nada diz que ela era a função inteira — trecho de dentro da função
    não é desta pergunta.
    """
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


# ---------------------------------------------------------------------------
# As frentes: o que o validador cobra, a deriva, e os comentários de src/.
# ---------------------------------------------------------------------------


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
        if nome is None:
            a_mao.append(f"{achado}: sem símbolo prometido, não há como saber quando valia")
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
        por_chave[chave].nomes.add(nome["nome"])
        por_chave[chave].linhas.add(achado.linha)
    return list(por_chave.values()), a_mao


def com_promessa(raiz: Path) -> list[Citacao]:
    """Toda citação que o validador confere E que promete um símbolo, podre ou não.

    Lê como o validador lê — as mesmas expressões, a mesma âncora na mesma linha
    do `.md`, a mesma célula do CSV — e só conta o endereço com caminho escrito.
    """
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


def podres_do_src(raiz: Path) -> tuple[list[Citacao], list[str]]:
    """As citações dos comentários de `src/` que a régua deles reprova.

    Quem sabe o que é uma citação ali — as formas, a janela de três linhas, a
    âncora candidata — é a própria régua; este script pergunta a ela, e não
    escreve um segundo leitor.
    """
    src = raiz / "src" / "hefesto_dualsense4unix"
    regua = raiz / "tests" / "unit" / "test_portao_o_par_com_metade_ligada.py"
    if not regua.is_file() or not src.is_dir():
        return [], []
    sys.path.insert(0, str(raiz))
    # Perguntar à régua não pode deixar `__pycache__` na árvore de quem pergunta.
    bytecode, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec = importlib.util.spec_from_file_location("_regua_das_citacoes_do_src", regua)
        assert spec is not None and spec.loader is not None
        modulo = importlib.util.module_from_spec(spec)
        # O `@dataclass` da régua procura o módulo em `sys.modules`.
        sys.modules[spec.name] = modulo
        spec.loader.exec_module(modulo)
    finally:
        sys.path.remove(str(raiz))
        sys.dont_write_bytecode = bytecode
    queixas = modulo.enderecos_envelhecidos(src)
    pendentes: frozenset[str] = getattr(modulo, "_CITACOES_PENDENTES", frozenset())
    citacoes: list[Citacao] = []
    a_mao: list[str] = []
    for cit in modulo.citacoes_de_linha(src):
        if cit.chave not in queixas or cit.chave in pendentes:
            continue
        candidatas = list(modulo._ancoras_candidatas(src / cit.citante, cit.linha_da_citacao))
        # A régua só aponta UMA âncora por citação: a primeira candidata, NA
        # ORDEM dela, que tem definição única no alvo.
        linhas = cit.alvo.read_text(encoding="utf-8").splitlines()
        uma = next((n for n in candidatas if modulo._definicao_unica(linhas, n) is not None), None)
        if uma is None:
            a_mao.append(f"{queixas[cit.chave]}: sem âncora com definição única")
            continue
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
                {uma},
            )
        )
    return citacoes, a_mao


# ---------------------------------------------------------------------------
# Escrever, e conferir o que escreveu.
# ---------------------------------------------------------------------------


def _trocar(texto: str, velho: str, novo: str) -> tuple[str, int]:
    """Troca o endereço ``velho`` inteiro — nunca um prefixo de outro número."""
    padrao = re.compile(r"(?<![A-Za-z0-9_./-])" + re.escape(velho) + r"(?![0-9-])")
    return padrao.subn(novo, texto)


def _trocar_curta(texto: str, cit: Citacao, endereco: str) -> tuple[str, int]:
    """Troca a forma curta ``:N`` só nas linhas em que o validador a ancorou.

    No `.md` a forma curta herda o arquivo da citação inteira da MESMA linha, e
    é assim que o validador a lê. O endereço que ele devolve vem com o arquivo,
    e o texto não o tem: trocar pelo endereço inteiro dava zero, e a troca
    saía na lista dos feitos sem ter escrito nada (medido na costura da 6e-4,
    com a `dualsense-referencia-canonica.md:766`).
    """
    curto_velho = cit.texto[len(cit.arquivo):]
    curto_novo = endereco[len(cit.arquivo):]
    linhas = texto.split("\n")
    total = 0
    for numero in sorted(cit.linhas):
        if 1 <= numero <= len(linhas):
            linhas[numero - 1], n = _trocar(linhas[numero - 1], curto_velho, curto_novo)
            total += n
    return "\n".join(linhas), total


def reapontar(raiz: Path, *, escrever: bool) -> tuple[list[str], list[str]]:
    """Devolve (feitos, à mão). Com ``escrever``, grava e confere cada documento."""
    feitos: list[str] = []
    citacoes, a_mao = podres_do_validador(raiz)
    do_src, a_mao_src = podres_do_src(raiz)
    citacoes += do_src
    a_mao += a_mao_src
    planos: dict[Path, list[tuple[Citacao, str]]] = {}
    vistos: set[tuple[Path, str]] = set()
    for cit in citacoes:
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
    # A deriva: a função inteira que andou e segue com o `def` dentro da faixa.
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
    for documento, trocas in planos.items():
        original = documento.read_text(encoding="utf-8")
        texto = original
        for cit, endereco in trocas:
            texto, n = _trocar(texto, cit.texto, endereco)
            if n == 0:
                texto, n = _trocar_curta(texto, cit, endereco)
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
        description="Reaponta as citações `arquivo:linha` que o código deslocou, pelo histórico."
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
    if a_mao:
        print(f"{len(a_mao)} à mão (o script não chuta):")
        for linha in a_mao:
            print(f"  {linha}")
    return 1 if a_mao else 0


if __name__ == "__main__":
    sys.exit(main())
