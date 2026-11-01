#!/usr/bin/env python3
"""A biblioteca de jogos de quem desenvolve não entra no repositório: duas réguas independentes.

Estrutural: perfil versionado (`name` e `match`) só mora nos lugares de perfil, e ali o título, o
processo e a classe são fictícios (ou categoria neutra), com appid 0 ou na faixa 9900000 a 9999999.

Nominal: os títulos vedados vêm de fora do git (`HEFESTO_BIBLIOTECA_VEDADA`, o conteúdo, no CI; ou
`~/.config/hefesto/biblioteca-vedada`; ou `--lista`). Casa sem caixa, sem acento e sem separador, no
conteúdo e no nome de todo arquivo versionado e no nome dos ramos. A saída nunca imprime o título:
só o caminho, a linha e o número dele na lista. Sem a lista, só a régua estrutural roda, e
`HEFESTO_EXIGE_BIBLIOTECA_VEDADA=1` reprova.

Uso:
  check_a_biblioteca_pessoal_fica_fora.py               a árvore de trabalho (o índice do git)
  check_a_biblioteca_pessoal_fica_fora.py --rev REV     os arquivos de uma revisão
  check_a_biblioteca_pessoal_fica_fora.py --lista ARQ   a lista vem deste arquivo
  check_a_biblioteca_pessoal_fica_fora.py --ramo NOME   mede este nome de ramo, não os do repositório
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata
from collections.abc import Iterator
from pathlib import Path
from typing import Any

LISTA_PADRAO = Path.home() / ".config" / "hefesto" / "biblioteca-vedada"
ENV_LISTA = "HEFESTO_BIBLIOTECA_VEDADA"
ENV_EXIGE = "HEFESTO_EXIGE_BIBLIOTECA_VEDADA"

LUGARES_DE_PERFIL = (
    "assets/profiles_default/freestyle.json",
    "assets/estilos_de_jogo/",
    "tests/fixtures/perfis",
    "scripts/tela/perfis-duble.json",
)
CATALOGO_DO_PRODUTO = ("assets/profiles_default/", "assets/estilos_de_jogo/")
ONDE_O_APPID_E_FICTICIO = ("tests/fixtures/", "scripts/tela/perfis-duble.json")

_PAGINAS = "a sprint das páginas publicadas sem a biblioteca (30/10/2026)"
_DOCSTRINGS = "a sprint das docstrings das integrações (30/10/2026)"
DIVIDA = {
    # sai com: A-HISTORIA-SEM-A-BIBLIOTECA-PESSOAL-01
    "docs/data/decisoes-de-produto.csv": "a costura de O-INSTALL-NASCE-SEM-PERFIL-PESSOAL-01",
    "mockup/09-sistema.html": _PAGINAS,
    "mockup/10-perfis.html": _PAGINAS,
    "src/hefesto_dualsense4unix/interface/aba09.py": _PAGINAS,
    "src/hefesto_dualsense4unix/interface/aba10.py": _PAGINAS,
    "src/hefesto_dualsense4unix/interface/paginas/09-sistema.html": _PAGINAS,
    "src/hefesto_dualsense4unix/interface/paginas/10-perfis.html": _PAGINAS,
    "scripts/check_so_a_primeira_letra.py": _PAGINAS,
    "src/hefesto_dualsense4unix/integrations/api_de_entrada.py": _DOCSTRINGS,
    "src/hefesto_dualsense4unix/integrations/prontuario_dos_jogos.py": _DOCSTRINGS,
}

APPID_FICTICIO = range(9_900_000, 10_000_000)
STEAM_APP = re.compile(r"steam_app_(\d+)")
APPID_EM_CHAVE = re.compile(r"\"appid\"\s*:\s*\"?(\d+)")
APPID_NO_TESTE = re.compile(
    r"(?ix)(?:steam_app_|umu-|com/(?:app|sub|bundle)/|apps/|appmanifest_|compatdata/|shadercache/"
    r"|rungameid/|jogo\ da\ steam\ |appid\w*[\"']?\s*[:=]\s*[\"']?|appid\s+"
    r"|steam(?:app|game)id[\"']?\s*[:=]\s*[\"']?|steam_compat_app_id[\"']?\s*[:=]\s*[\"']?)"
    r"(\d+)(?!\d)")
_REGEX_ENVOLTA = re.compile(r"(?:\.\*)?\((.*)\)(?:\.\*)?")
_NAO_ALFANUMERICO = re.compile(r"[\W_]+")

CATEGORIAS = frozenset(
    {
        "ação",
        "aventura",
        "bow",
        "coop_local",
        "corrida",
        "esportes",
        "fallback",
        "fora do jogo",
        "fps",
        "freestyle",
        "meu_perfil",
        "navegação",
        "point_and_click",
        "universal",
    }
)


def sem_acento(texto: str) -> str:
    if texto.isascii():
        return texto.casefold()
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    ).casefold()


def ficticio(texto: str) -> bool:
    return "ficticio" in sem_acento(texto)


def appid_ficticio(numero: str) -> bool:
    return int(numero) == 0 or int(numero) in APPID_FICTICIO


def appid_de_teste(numero: str) -> bool:
    valor = int(numero)
    return valor == 0 or valor >= APPID_FICTICIO.start or valor % 10 != 0


def nome_neutro(nome: str) -> bool:
    neutro = sem_acento(nome)
    return ficticio(nome) or "fabricado" in neutro or neutro in {sem_acento(c) for c in CATEGORIAS}


def termos_do_titulo(regex: str) -> list[str]:
    envolta = _REGEX_ENVOLTA.fullmatch(regex)
    return (envolta.group(1) if envolta else regex).split("|")


def perfis_em(dados: Any) -> Iterator[dict[str, Any]]:
    if isinstance(dados, dict):
        if "name" in dados and isinstance(dados.get("match"), dict):
            yield dados
        for valor in dados.values():
            yield from perfis_em(valor)
    elif isinstance(dados, list):
        for valor in dados:
            yield from perfis_em(valor)


def defeitos_do_perfil(perfil: dict[str, Any]) -> list[str]:
    defeitos = []
    match = perfil["match"]
    if not isinstance(perfil["name"], str) or not nome_neutro(perfil["name"]):
        defeitos.append("name")
    for i, classe in enumerate(match.get("window_class") or []):
        numero = STEAM_APP.fullmatch(str(classe))
        if not (appid_ficticio(numero.group(1)) if numero else ficticio(str(classe))):
            defeitos.append(f"window_class[{i}]")
    for i, processo in enumerate(match.get("process_name") or []):
        if not ficticio(str(processo)):
            defeitos.append(f"process_name[{i}]")
    regex = match.get("window_title_regex")
    for i, termo in enumerate(termos_do_titulo(regex) if isinstance(regex, str) else []):
        if not ficticio(termo):
            defeitos.append(f"window_title_regex, termo {i + 1}")
    return defeitos


def appids_reais(texto: str) -> list[int]:
    linhas = []
    for padrao in (STEAM_APP, APPID_EM_CHAVE):
        for achado in padrao.finditer(texto):
            if not appid_ficticio(achado.group(1)):
                linhas.append(texto.count("\n", 0, achado.start()) + 1)
    return sorted(set(linhas))


def regua_estrutural(caminho: str, texto: str) -> list[str]:
    erros = []
    if caminho.startswith(ONDE_O_APPID_E_FICTICIO):
        nome = caminho.rsplit("/", 1)[-1]
        if not appid_ficticio_no_nome(nome):
            erros.append(f"{caminho}: o nome do arquivo leva appid fora da faixa fictícia")
        erros.extend(
            f"{caminho}:{linha}: appid fora da faixa fictícia (0 ou 9900000 a 9999999)"
            for linha in appids_reais(texto)
        )
    if not caminho.endswith(".json"):
        return erros
    try:
        dados = json.loads(texto)
    except ValueError:
        return erros
    perfis = list(perfis_em(dados))
    if not perfis:
        return erros
    if not caminho.startswith(LUGARES_DE_PERFIL):
        return [*erros, f"{caminho}: perfil versionado fora dos lugares de perfil"]
    if caminho.startswith(CATALOGO_DO_PRODUTO):
        return erros
    for i, perfil in enumerate(perfis):
        erros.extend(
            f"{caminho}: perfil {i + 1}, {campo} não é fictício nem categoria neutra"
            for campo in defeitos_do_perfil(perfil)
        )
    if caminho.startswith("tests/fixtures/") and not nome_neutro(
        caminho.rsplit("/", 1)[-1].removesuffix(".json").split("-")[0]
    ):
        erros.append(f"{caminho}: o nome do arquivo não é fictício nem categoria neutra")
    return erros


def appid_ficticio_no_nome(nome: str) -> bool:
    return all(appid_ficticio(a.group(1)) for a in STEAM_APP.finditer(nome))


def espremido(texto: str) -> tuple[str, set[int], list[int]]:
    letras: list[str] = []
    fronteiras = {0}
    linhas: list[int] = []
    linha = 1
    anterior = ""
    for bruto in unicodedata.normalize("NFKD", texto):
        if unicodedata.combining(bruto):
            continue
        if bruto == "\n":
            linha += 1
        if not bruto.isalnum():
            fronteiras.add(len(letras))
            anterior = ""
            continue
        if anterior and (
            (anterior.islower() and bruto.isupper()) or (anterior.isdigit() != bruto.isdigit())
        ):
            fronteiras.add(len(letras))
        for c in bruto.casefold():
            letras.append(c)
            linhas.append(linha)
        anterior = bruto
    fronteiras.add(len(letras))
    return "".join(letras), fronteiras, linhas


def chave(titulo: str) -> str:
    return _NAO_ALFANUMERICO.sub("", sem_acento(titulo))


def ler_lista(arquivo: Path | None) -> list[str] | None:
    if arquivo is not None:
        texto = arquivo.read_text(encoding="utf-8")
    elif os.environ.get(ENV_LISTA, "").strip():
        texto = os.environ[ENV_LISTA]
    elif LISTA_PADRAO.is_file():
        texto = LISTA_PADRAO.read_text(encoding="utf-8")
    else:
        return None
    return [ln.strip() for ln in texto.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]


class Vedados:
    def __init__(self, titulos: list[str]) -> None:
        self.chaves = [(n, chave(t)) for n, t in enumerate(titulos, start=1) if chave(t)]

    def casam(self, texto: str) -> list[tuple[int, int]]:
        bruto = _NAO_ALFANUMERICO.sub("", sem_acento(texto))
        candidatos = [(n, c) for n, c in self.chaves if c in bruto]
        if not candidatos:
            return []
        letras, fronteiras, linhas = espremido(texto)
        achados = set()
        for numero, alvo in candidatos:
            inicio = letras.find(alvo)
            while inicio >= 0:
                fim = inicio + len(alvo)
                if inicio in fronteiras and fim in fronteiras:
                    achados.add((linhas[inicio], numero))
                inicio = letras.find(alvo, inicio + 1)
        return sorted(achados)


def git(*args: str) -> bytes:
    r = subprocess.run(["git", *args], capture_output=True, check=False)
    if r.returncode != 0:
        sys.exit(f"biblioteca-pessoal: git {' '.join(args[:2])} falhou: "
                 f"{r.stderr.decode(errors='replace').strip()[:200]}")
    return r.stdout


def arquivos_da_arvore() -> Iterator[tuple[str, str | None]]:
    raiz = Path(git("rev-parse", "--show-toplevel").decode().strip())
    for caminho in sorted(filter(None, git("ls-files", "-z").decode().split("\0"))):
        alvo = raiz / caminho
        if alvo.is_symlink() or not alvo.is_file():
            yield caminho, None
            continue
        try:
            yield caminho, alvo.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            yield caminho, None


def arquivos_da_revisao(rev: str) -> Iterator[tuple[str, str | None]]:
    entradas = []
    for registro in filter(None, git("ls-tree", "-r", "-z", rev).split(b"\0")):
        meta, nome = registro.split(b"\t", 1)
        modo, tipo, sha = meta.split()
        if tipo == b"blob":
            entradas.append((nome.decode(), sha.decode(), modo == b"120000"))
    entradas.sort()
    pedido = "".join(f"{sha}\n" for _, sha, _ in entradas).encode()
    saida = subprocess.run(["git", "cat-file", "--batch"], input=pedido, capture_output=True,
                           check=True).stdout
    pos = 0
    for caminho, _, link in entradas:
        fim_do_cabecalho = saida.index(b"\n", pos)
        tamanho = int(saida[pos:fim_do_cabecalho].split()[2])
        corpo = saida[fim_do_cabecalho + 1: fim_do_cabecalho + 1 + tamanho]
        pos = fim_do_cabecalho + 1 + tamanho + 1
        try:
            yield caminho, None if link else corpo.decode("utf-8")
        except UnicodeDecodeError:
            yield caminho, None


def ramos() -> list[str]:
    saida = git("for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes")
    return sorted(filter(None, saida.decode(errors="replace").splitlines()))


def medir(
    rev: str | None, vedados: Vedados | None, nomes_de_ramo: list[str] | None = None
) -> tuple[list[str], list[str]]:
    erros: list[str] = []
    avisos: list[str] = []
    divida_viva: set[str] = set()
    listados = set()
    arquivos = arquivos_da_revisao(rev) if rev else arquivos_da_arvore()
    for indice, (caminho, texto) in enumerate(arquivos, start=1):
        listados.add(caminho)
        nome_casa = vedados.casam(caminho) if vedados else []
        rotulo = f"o arquivo nº {indice} da listagem do git" if nome_casa else caminho
        erros.extend(
            f"{rotulo}: o nome casa o título vedado nº {numero}" for _, numero in nome_casa
        )
        if texto is None:
            continue
        erros.extend(e.replace(caminho, rotulo, 1) for e in regua_estrutural(caminho, texto))
        if not vedados:
            continue
        achados = vedados.casam(texto)
        if achados and caminho in DIVIDA and not rev:
            divida_viva.add(caminho)
            avisos.append(f"{caminho}: {len(achados)} linha(s) com título vedado, dívida declarada "
                          f"de {DIVIDA[caminho]}")
            continue
        erros.extend(f"{rotulo}:{linha}: título vedado nº {numero}" for linha, numero in achados)
    if vedados and not rev:
        erros.extend(
            f"{caminho}: dívida morta (não traz mais título vedado): tire-a do DIVIDA"
            for caminho in sorted(set(DIVIDA) & listados - divida_viva)
        )
    if vedados and (nomes_de_ramo is not None or not rev):
        origem = "do `--ramo`" if nomes_de_ramo is not None else (
            "de `git for-each-ref refs/heads refs/remotes`")
        for indice, ramo in enumerate(
            nomes_de_ramo if nomes_de_ramo is not None else ramos(), start=1
        ):
            erros.extend(
                f"o ramo nº {indice} {origem}: o nome casa o título vedado nº {numero}"
                for _, numero in vedados.casam(ramo)
            )
    return erros, avisos


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    ap.add_argument("--rev", help="mede os arquivos desta revisão em vez da árvore de trabalho")
    ap.add_argument("--lista", type=Path, help="o arquivo com os títulos vedados, um por linha")
    ap.add_argument("--ramo", action="append",
                    help="mede este nome de ramo em vez de todos os do repositório (repetível)")
    args = ap.parse_args(argv)

    titulos = ler_lista(args.lista)
    vedados = Vedados(titulos) if titulos else None
    erros, avisos = medir(args.rev, vedados, args.ramo)
    for aviso in avisos:
        print(f"  aviso: {aviso}")
    for erro in erros:
        print(f"  ERRO: {erro}")
    if vedados is None:
        print("biblioteca-pessoal: só a régua estrutural rodou (sem a lista dos títulos vedados: "
              f"{ENV_LISTA} ou {LISTA_PADRAO})")
        if os.environ.get(ENV_EXIGE) == "1":
            print(f"FALHA: {ENV_EXIGE}=1 e a lista não veio")
            return 1
    if erros:
        print(f"FALHA: {len(erros)} ocorrência(s) da biblioteca pessoal no repositório; o piso é zero.")
        return 1
    contagem = f"{len(vedados.chaves)} título(s) vedado(s)" if vedados else "só a estrutural"
    print(f"OK: a biblioteca pessoal fica fora ({contagem}, {len(avisos)} dívida(s) declarada(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
