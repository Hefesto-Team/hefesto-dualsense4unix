#!/usr/bin/env python3
"""A dica de uma ligação para página do produto não promete o navegador.

Sprint: O-BOTAO-DO-MAPA-DA-08-DIZ-ONDE-ELE-ABRE-01.

Medido em 23/10/2026: o botão «Mapa do controle» da 08 dizia «abre no navegador» e o ícone do mapa
das entradas, no `mapa-do-radio`, também; as duas ligações vão a uma página do próprio produto, que
abre na mesma WebView (a interface não tem `decide-policy`, `xdg-open` nem `show_uri` para elas).
A dica prometia um lugar aonde o clique não vai.

A régua lê o gerador da 08, os desenhos e as páginas publicadas: em toda tag com `href` para uma
página `.html` do produto, nem o `title`, nem o `aria-label`, nem o `data-dica` dizem «navegador».

MORDIDA (24/10/2026): devolver «abre no navegador» ao `title` do gerador (`aba08.py`) ou ao
`aria-label` do `mockup/mapa-do-radio.html` reprova esta régua.
"""
from __future__ import annotations

import pathlib
from html.parser import HTMLParser

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src/hefesto_dualsense4unix/interface"
PUBLICADAS = INTERFACE / "paginas"  # (noqa-acento)
DICAS = ("title", "aria-label", "data-dica")
DA_SPRINT = ("08-conexoes.html", "mapa-do-radio.html")
FRASE_NOVA = "abre aqui, na janela"


def _e_pagina_do_produto(href: str) -> bool:
    alvo = href.split("#", 1)[0]
    return alvo.endswith(".html") and "://" not in alvo and not alvo.startswith("//")


class _Ligacoes(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.achados: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        atributos = dict(attrs)
        href = atributos.get("href") or ""
        if not _e_pagina_do_produto(href):
            return
        for chave in DICAS:
            texto = atributos.get(chave) or ""
            if "navegador" in texto.lower():
                linha = self.getpos()[0]
                self.achados.append(f"linha {linha}: <{tag} href={href!r} {chave}={texto!r}>")


def _promessas(texto: str) -> list[str]:
    leitor = _Ligacoes()
    leitor.feed(texto)
    leitor.close()
    return leitor.achados


def test_o_gerador_da_08_nao_promete_o_navegador() -> None:
    """Prova da D-2410-A-DICA-DIZ-QUE-ABRE-NA-JANELA."""
    achados = _promessas((INTERFACE / "aba08.py").read_text(encoding="utf-8"))
    assert achados == [], f"o gerador da 08 promete o navegador a uma página do produto: {achados}"


@pytest.mark.parametrize("nome", sorted(p.name for p in (RAIZ / "mockup").glob("*.html")))
def test_nenhum_desenho_promete_o_navegador(nome: str) -> None:
    achados = _promessas((RAIZ / "mockup" / nome).read_text(encoding="utf-8"))
    assert achados == [], f"mockup/{nome}: {achados}"


def test_os_dois_desenhos_da_sprint_dizem_onde_o_clique_vai() -> None:
    for nome in DA_SPRINT:
        assert FRASE_NOVA in (RAIZ / "mockup" / nome).read_text(encoding="utf-8"), nome


@pytest.mark.parametrize("nome", sorted(p.name for p in PUBLICADAS.glob("*.html")))
def test_nenhuma_pagina_publicada_promete_o_navegador(nome: str) -> None:
    texto = (PUBLICADAS / nome).read_text(encoding="utf-8")
    if nome in DA_SPRINT and FRASE_NOVA not in texto:
        pytest.skip(f"{nome}: o publicado ainda é o de antes; o `--publicar` é da costura")
    achados = _promessas(texto)
    assert achados == [], f"paginas/{nome}: {achados}"
