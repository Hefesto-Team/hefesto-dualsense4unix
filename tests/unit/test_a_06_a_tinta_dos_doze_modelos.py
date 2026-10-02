#!/usr/bin/env python3
"""A TINTA DOS DOZE: publicar a folha dos 28 sem os servidores de pintura APAGA"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "06-navegacao.html"  # (noqa-acento) nome de arquivo

_URL = re.compile(r"url\(#([^)]+)\)")

_ID = re.compile(r'\sid="([^"]+)"')


@pytest.fixture
def bancada() -> str:
    from hefesto_dualsense4unix.interface import onde

    return onde.pagina(PAGINA).read_text(encoding="utf-8")


@pytest.fixture
def folha_da_pagina(bancada: str) -> str:
    """A folha dos 28 como a PÁGINA a publica — não como o SVG a guarda."""
    dentro = "".join(re.findall(r"<style[^>]*>(.*?)</style>", bancada, re.S))
    assert 'svg[data-colorway="white"]' in dentro, (
        "a página parou de publicar a folha das cores — sem ela esta régua "
        "não tem o que medir, e a aba volta a ter um modelo só")
    return dentro


def test_a_folha_da_pagina_pede_tinta(folha_da_pagina: str) -> None:
    """A guarda do vazio: se nenhum modelo pedisse `url(#…)`, os dois testes"""
    modelos = {
        m.group(1)
        for linha in folha_da_pagina.splitlines()
        if "url(#" in linha
        for m in [re.match(r'\s*svg\[data-colorway="([^"]+)"\]', linha)]
        if m
    }
    assert len(modelos) >= 10, (
        f"só {len(modelos)} modelos do mapa pintam por servidor de pintura — "
        f"eram doze em 03/09/2026. Se o mapa mudou, confira a conta; se a folha "
        f"encolheu, a página parou de publicar os 28")


def test_toda_tinta_referenciada_existe_na_pagina(
        bancada: str, folha_da_pagina: str) -> None:
    """O teste que a tela pagou: `url(#x)` sem `id="x"` não fica cinza, SOME."""
    pedidas = sorted(set(_URL.findall(folha_da_pagina)))
    publicados = set(_ID.findall(bancada))
    mortas = [i for i in pedidas if i not in publicados]
    assert not mortas, (
        f"a folha das cores da {PAGINA} pede {mortas} e a página não publica "
        f"esse `id`. Quem tiver um desses doze modelos NÃO vê o desenho cinza: "
        f"vê o corpo do controle sumir. Falta o `BLOCO_DA_TINTA` no `MIOLO` de "
        f"aba06.py")


def test_a_tinta_sai_uma_vez_e_sem_prefixo(bancada: str) -> None:
    """UMA cópia, e com o nome que a folha pede."""
    assert bancada.count('id="hachura-sem-hex"') == 1, (
        "o servidor de pintura da hachura aparece mais de uma vez (ou nenhuma) "
        "sem prefixo — a folha da página pede exatamente este nome")
    assert 'class="cores-do-dualsense"' in bancada, (
        "o bloco da tinta perdeu a classe que o identifica na página — quem "
        "for lê-la depois não acha o que este teste protege")
