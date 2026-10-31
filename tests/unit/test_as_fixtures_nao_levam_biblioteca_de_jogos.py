"""Fixtures e testes não levam a biblioteca de jogos de ninguém: só appid e título fictícios."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

_TESTES = Path(__file__).resolve().parents[1]
_FIXTURES = _TESTES / "fixtures"

_APPID_FICTICIO = range(9_900_000, 10_000_000)
_STEAM_APP = re.compile(r"steam_app_(\d+)")
_APPID_EM_CHAVE = re.compile(r"\"appid\"\s*:\s*\"?(\d+)")
_APPID_NO_TESTE = re.compile(
    r"(?ix)(?:steam_app_|umu-|com/(?:app|sub|bundle)/|apps/|appmanifest_|compatdata/|shadercache/"
    r"|rungameid/|jogo\ da\ steam\ |appid\w*[\"']?\s*[:=]\s*[\"']?|appid\s+"
    r"|steam(?:app|game)id[\"']?\s*[:=]\s*[\"']?|steam_compat_app_id[\"']?\s*[:=]\s*[\"']?)"
    r"(\d+)(?!\d)")
_REGEX_ENVOLTA = re.compile(r"(?:\.\*)?\((.*)\)(?:\.\*)?")

_CATEGORIAS = frozenset(
    {
        "ação",
        "aventura",
        "bow",
        "coop_local",
        "corrida",
        "esportes",
        "fallback",
        "fps",
        "meu_perfil",
        "navegação",
        "point_and_click",
    }
)


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    ).casefold()


def _ficticio(texto: str) -> bool:
    return "ficticio" in _sem_acento(texto)


def _appid_ficticio(numero: str) -> bool:
    return int(numero) == 0 or int(numero) in _APPID_FICTICIO


def _appid_de_teste(numero: str) -> bool:
    valor = int(numero)
    return valor == 0 or valor >= _APPID_FICTICIO.start or valor % 10 != 0


def _categorias_neutras() -> set[str]:
    return {_sem_acento(categoria) for categoria in _CATEGORIAS}


def _nome_neutro(nome: str) -> bool:
    neutro = _sem_acento(nome)
    return _ficticio(nome) or "fabricado" in neutro or neutro in _categorias_neutras()


def _textos() -> list[tuple[Path, str]]:
    textos = []
    for arquivo in sorted(_FIXTURES.rglob("*")):
        if not arquivo.is_file():
            continue
        try:
            textos.append((arquivo, arquivo.read_text(encoding="utf-8")))
        except (UnicodeDecodeError, OSError):
            textos.append((arquivo, ""))
    return textos


def _perfis() -> list[tuple[Path, dict]]:
    perfis = []
    for arquivo, texto in _textos():
        if arquivo.suffix != ".json":
            continue
        dados = json.loads(texto)
        if isinstance(dados, dict) and isinstance(dados.get("match"), dict) and "name" in dados:
            perfis.append((arquivo, dados))
    return perfis


def _termos_do_titulo(regex: str) -> list[str]:
    envolta = _REGEX_ENVOLTA.fullmatch(regex)
    return (envolta.group(1) if envolta else regex).split("|")


def test_nenhum_appid_real_em_fixture() -> None:
    violacoes = []
    for arquivo, texto in _textos():
        for padrao in (_STEAM_APP, _APPID_EM_CHAVE):
            for achado in padrao.finditer(f"{arquivo.name}\n{texto}"):
                if not _appid_ficticio(achado.group(1)):
                    violacoes.append(f"{arquivo.relative_to(_FIXTURES)}: {achado.group(0)}")
    assert violacoes == [], (
        "appid de jogo de verdade em fixture — quem clona o repositório leva a "
        "biblioteca de quem a gravou; use 0 ou a faixa fictícia 9900000 a 9999999: "
        + "; ".join(violacoes)
    )


def test_os_perfis_de_fixture_so_casam_jogo_ficticio() -> None:
    perfis = _perfis()
    assert len(perfis) >= 37, f"a régua achou só {len(perfis)} perfis em fixtures"
    violacoes = []
    for arquivo, dados in perfis:
        onde = arquivo.relative_to(_FIXTURES)
        match = dados["match"]
        if not _nome_neutro(dados["name"]):
            violacoes.append(f"{onde}: name={dados['name']!r}")
        if not _nome_neutro(arquivo.stem.split("-")[0]):
            violacoes.append(f"{onde}: o nome do arquivo")
        for classe in match.get("window_class") or []:
            numero = _STEAM_APP.fullmatch(classe)
            if not (_appid_ficticio(numero.group(1)) if numero else _ficticio(classe)):
                violacoes.append(f"{onde}: window_class={classe!r}")
        for processo in match.get("process_name") or []:
            if not _ficticio(processo):
                violacoes.append(f"{onde}: process_name={processo!r}")
        regex = match.get("window_title_regex")
        for termo in _termos_do_titulo(regex) if regex else []:
            if not _ficticio(termo):
                violacoes.append(f"{onde}: window_title_regex com {termo!r}")
    assert violacoes == [], (
        "perfil de fixture que casa jogo de verdade — o título, o processo ou a "
        "classe de janela contam a biblioteca de quem gravou; troque por «Jogo "
        "Fictício …» / jogo_ficticio_* (ou ponha a categoria neutra em "
        "_CATEGORIAS): " + "; ".join(violacoes)
    )


def test_nenhum_appid_real_nos_testes() -> None:
    violacoes = []
    for arquivo in sorted(_TESTES.rglob("*")):
        if not arquivo.is_file() or "__pycache__" in arquivo.parts:
            continue
        try:
            texto = arquivo.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for numero_da_linha, linha in enumerate(texto.splitlines(), start=1):
            violacoes.extend(
                f"{arquivo.relative_to(_TESTES)}:{numero_da_linha}: {achado.group(0)}"
                for achado in _APPID_NO_TESTE.finditer(linha)
                if not _appid_de_teste(achado.group(1)))
    assert violacoes == [], (
        f"{len(violacoes)} appid(s) de jogo de verdade nos testes — a Steam numera os apps de "
        "dez em dez, e o teste do comportamento por número de jogo usa a faixa fictícia "
        "(9900000 em diante), um número que a loja não dá (que não termina em 0) ou o dado "
        "que o produto lê do catálogo, nunca a biblioteca de quem desenvolve: "
        + "; ".join(violacoes[:40]))
