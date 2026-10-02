#!/usr/bin/env python3
"""validar-citacoes-de-linha.py — ABRE cada `arquivo:linha` citado e confere."""
from __future__ import annotations

import argparse
import ast
import csv
import functools
import re
import sys
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

    def __str__(self) -> str:
        onde = f" ({self.contexto})" if self.contexto else ""
        return f"{self.documento}:{self.linha}{onde}: {self.endereco} -- {self.motivo}"


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
) -> tuple[list[Achado], bool, bool]:
    """As três perguntas, para UM endereço."""
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
                        "a faixa está invertida ou começa em zero", contexto)],
                True, False)
    if ultima > len(corpo):
        return ([Achado(origem, linha, endereco,
                        f"a linha não existe: {arquivo} tem {len(corpo)} linha(s)",
                        contexto)],
                True, False)

    trecho = "\n".join(corpo[primeira - 1:ultima])
    nomes = sorted(nomes_prometidos(texto, achado.start(), achado.end(), separadores))
    achados = [
        Achado(origem, linha, endereco,
               f"a faixa não contém `{nome}`, que a citação promete", contexto)
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
                    contexto))
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
                for achado in ENDERECO_CSV.finditer(celula):
                    seus, conferido, fora = confere_endereco(
                        relativo, inicio, contexto, celula, achado,
                        achado.group("arq"), corpos, raiz, SEPARADORES_DE_BLOCO)
                    achados.extend(seus)
                    conferidos += conferido
                    de_fora += fora
    return achados, conferidos, de_fora


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reprova citação de linha que não abre ou não contém o que promete.")
    parser.add_argument("arquivos", nargs="*", type=Path,
                        help="documentos ou planilhas a varrer")
    parser.add_argument("--all", action="store_true",
                        help=f"varre {PASTA.as_posix()}/ e {PASTA_CSV.as_posix()}/*.csv")
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parent.parent,
                        help="raiz do repositório (padrão: a deste script)")
    args = parser.parse_args(argv)

    raiz = args.root.resolve()
    if not raiz.is_dir():
        print(f"ERRO: raiz inexistente: {raiz}", file=sys.stderr)
        return 2

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
        return 0

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
        print("símbolo prometido está hoje, e só escreve o que confere.")
        return 1

    print(f"OK: {conferidos} citação(ões) de linha conferida(s) em {onde}; "
          f"{de_fora} de fontes fora desta árvore (kernel, SDL, wine) "
          "foram ignoradas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
