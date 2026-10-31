"""Fixtures e testes não levam a biblioteca de jogos de ninguém: só appid e título fictícios.

As regras moram no portão `scripts/check_a_biblioteca_pessoal_fica_fora.py`; aqui as mesmas
regras rodam sobre o disco de `tests/`, inclusive o arquivo ainda fora do índice.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

_TESTES = Path(__file__).resolve().parents[1]
_FIXTURES = _TESTES / "fixtures"
_RAIZ = _TESTES.parent
_PORTAO = _RAIZ / "scripts" / "check_a_biblioteca_pessoal_fica_fora.py"


def _regras() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_biblioteca_pessoal", _PORTAO)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


R = _regras()


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


def _perfis() -> list[tuple[Path, dict[str, Any]]]:
    perfis: list[tuple[Path, dict[str, Any]]] = []
    for arquivo, texto in _textos():
        if arquivo.suffix == ".json":
            perfis.extend((arquivo, dados) for dados in R.perfis_em(json.loads(texto)))
    return perfis


def test_nenhum_appid_real_em_fixture() -> None:
    violacoes = [
        f"{arquivo.relative_to(_FIXTURES)}:{linha}"
        for arquivo, texto in _textos()
        for linha in R.appids_reais(f"{arquivo.name}\n{texto}")
    ]
    assert violacoes == [], (
        "appid de jogo de verdade em fixture — quem clona o repositório leva a "
        "biblioteca de quem a gravou; use 0 ou a faixa fictícia 9900000 a 9999999: "
        + "; ".join(violacoes)
    )


def test_os_perfis_de_fixture_so_casam_jogo_ficticio() -> None:
    perfis = _perfis()
    assert len(perfis) >= 37, f"a régua achou só {len(perfis)} perfis em fixtures"
    violacoes: list[str] = []
    for arquivo, dados in perfis:
        onde = arquivo.relative_to(_FIXTURES)
        violacoes.extend(f"{onde}: {campo}" for campo in R.defeitos_do_perfil(dados))
        if not R.nome_neutro(arquivo.stem.split("-")[0]):
            violacoes.append(f"{onde}: o nome do arquivo")
    assert violacoes == [], (
        "perfil de fixture que casa jogo de verdade — o título, o processo ou a "
        "classe de janela contam a biblioteca de quem gravou; troque por «Jogo "
        "Fictício …» / jogo_ficticio_* (ou ponha a categoria neutra em "
        "CATEGORIAS do portão): " + "; ".join(violacoes)
    )


def test_nenhum_appid_real_nos_testes() -> None:
    violacoes: list[str] = []
    for arquivo in sorted(_TESTES.rglob("*")):
        if not arquivo.is_file() or "__pycache__" in arquivo.parts:
            continue
        try:
            texto = arquivo.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for numero_da_linha, linha in enumerate(texto.splitlines(), start=1):
            violacoes.extend(
                f"{arquivo.relative_to(_TESTES)}:{numero_da_linha}"
                for achado in R.APPID_NO_TESTE.finditer(linha)
                if not R.appid_de_teste(achado.group(1)))
    assert violacoes == [], (
        f"{len(violacoes)} appid(s) de jogo de verdade nos testes — a Steam numera os apps de "
        "dez em dez, e o teste do comportamento por número de jogo usa a faixa fictícia "
        "(9900000 em diante), um número que a loja não dá (que não termina em 0) ou o dado "
        "que o produto lê do catálogo, nunca a biblioteca de quem desenvolve: "
        + "; ".join(violacoes[:40]))
