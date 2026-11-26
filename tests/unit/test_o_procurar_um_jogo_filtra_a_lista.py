"""O «Procurar um jogo» da janela «Criar perfis» filtra a lista.

Sprint O-PROCURAR-UM-JOGO-FILTRA-A-LISTA-01.

Medido em 19/11/2026: o ``<input class="cj-busca">`` saía do gerador sem ouvinte; com a Steam de
48 jogos, digitar «resident» deixava os 48 na lista. A cura mora no ``comportamento.js``: a cada
``input`` o ``li`` cujo ``.cj-nome`` não casa some (sem acento, sem caixa), e o filtro volta quando
o produto repinta o miolo da janela (o campo nasce de novo, o trecho digitado é lembrado).

A régua monta a janela com o gerador da casa (``escolha_miolo_html``) e o ``SCRIPT`` do desenho, no
Chrome do sistema, e conta os ``li`` visíveis.

MORDIDA: sem o ouvinte de ``input`` do ``.cj-busca`` no ``comportamento.js``, os testes que
digitam reprovam; sem o vigia do ``#lanc-escolha``, o da repintura reprova.
"""
from __future__ import annotations

import pathlib
from collections.abc import Iterator
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import desenho_da_experimental as exp

CHROME = pathlib.Path("/usr/bin/google-chrome")

_NOMES = ("Resident Evil 4", "Resident Evil Village", "Pokémon Legends", "Ação Máxima",
          "Dungeons II", "Hades", "Celeste")


def _jogos(n: int = 48) -> list[exp.JogoDaLista]:
    base = [exp.JogoDaLista(f"steam_app_{i}", nome, tem=i % 3 == 0)
            for i, nome in enumerate(_NOMES)]
    base += [exp.JogoDaLista(f"steam_app_{i}", f"Jogo {i}") for i in range(len(_NOMES), n)]
    return base


def _pagina(jogos: list[exp.JogoDaLista]) -> str:
    miolo = exp.escolha_miolo_html("Steam", jogos)
    return (f'<!doctype html><meta charset="utf-8"><body>'
            f'<div id="escolher-jogo"><div id="lanc-escolha">{miolo}</div></div>'
            f"<script>{exp.SCRIPT}</script></body>")


_VISIVEIS = """() => [...document.querySelectorAll('.cj-lista li')]
  .filter(li => getComputedStyle(li).display !== 'none')
  .map(li => li.querySelector('.cj-nome').textContent)"""

_REPINTAR = "(m) => { document.getElementById('lanc-escolha').innerHTML = m; }"


@pytest.fixture(scope="module")
def pg(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Any]:
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema: a régua não tem motor")
    from playwright.sync_api import sync_playwright

    arq = tmp_path_factory.mktemp("busca") / "janela.html"
    arq.write_text(_pagina(_jogos()), encoding="utf-8")
    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            p = nav.new_page(viewport={"width": 1200, "height": 800})
            p.goto(arq.as_uri())
            p.wait_for_selector(".cj-busca")
            yield p
        finally:
            nav.close()


def _digitar(pg: Any, texto: str) -> list[str]:
    pg.fill(".cj-busca", "")
    pg.type(".cj-busca", texto)
    return list(pg.evaluate(_VISIVEIS))


def test_digitar_deixa_so_os_jogos_que_casam(pg: Any) -> None:
    """«resident» deixa os dois Resident Evil dos 48; apagar traz os 48 de volta."""
    assert len(pg.evaluate(_VISIVEIS)) == 48
    assert _digitar(pg, "resident") == ["Resident Evil 4", "Resident Evil Village"]
    assert len(_digitar(pg, "")) == 48


def test_a_busca_ignora_acento_e_caixa(pg: Any) -> None:
    """O trecho sem acento e em maiúscula acha o nome acentuado, e o acentuado também."""
    assert _digitar(pg, "POKEMON") == ["Pokémon Legends"]
    assert _digitar(pg, "ac" + "ao") == ["Ação Máxima"]
    assert _digitar(pg, "pokémon") == ["Pokémon Legends"]
    assert _digitar(pg, "zzzz") == []
    _digitar(pg, "")


def test_repintar_o_miolo_mantem_o_filtro(pg: Any) -> None:
    """O produto repinta o miolo (o campo nasce vazio): o trecho digitado volta e a lista segue
    filtrada, com a linha já criada trocada por «Tem perfil»."""
    _digitar(pg, "resident")
    novo = _jogos()
    novo[0] = exp.JogoDaLista(novo[0].chave, novo[0].nome, tem=True)
    pg.evaluate(_REPINTAR, exp.escolha_miolo_html("Steam", novo))
    pg.wait_for_function("() => document.querySelector('.cj-busca').value === 'resident'")
    assert list(pg.evaluate(_VISIVEIS)) == ["Resident Evil 4", "Resident Evil Village"]
    assert len(_digitar(pg, "")) == 48


def test_outro_lancador_comeca_sem_filtro(pg: Any) -> None:
    """A janela de outro lançador (outro título) não herda o trecho do anterior."""
    _digitar(pg, "resident")
    pg.evaluate(_REPINTAR, exp.escolha_miolo_html("Lutris", _jogos()))
    assert pg.evaluate("() => document.querySelector('.cj-busca').value") == ""
    assert len(pg.evaluate(_VISIVEIS)) == 48
