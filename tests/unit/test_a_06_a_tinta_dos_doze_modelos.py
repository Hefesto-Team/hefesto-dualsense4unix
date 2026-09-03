#!/usr/bin/env python3
"""A TINTA DOS DOZE: publicar a folha dos 28 sem os servidores de pintura APAGA
o desenho de doze modelos dela.

A LEI É DELA, 03/09/2026:

    "imagina que cada pessoa tenha um dualsense diferente. eu mapeei as
    cores, glifos, controles, id e tudo mais. é pro projeto usar esse meu
    trabalho. nada hardcoded"

O DEFEITO QUE ESTA RÉGUA NASCEU PARA PEGAR, medido no WebKit desta máquina em
03/09/2026, DEPOIS de a `06` publicar os 28 modelos:

    document.getElementById('hachura-sem-hex')        → null
    document.getElementById('casca-god-of-war-20th')  → null
    document.getElementById('casca-spider-man-2')     → null

Doze dos 28 modelos NÃO pintam com hex — pintam com servidor de pintura
(``fill:url(#…)``): a hachura dos que ela não amostrou e os dois gradientes de
casca. Os três ``id`` moram no ``<defs>`` do desenho, e ``monta.svg()`` PREFIXA
todo id por controle (``p1-hachura-sem-hex``…). A folha publicada na PÁGINA
continuou pedindo o nome sem prefixo, que já não existia em lugar nenhum.

**E REFERÊNCIA MORTA NÃO CAI NO CINZA — ELA APAGA A PEÇA.** Medido com
``chroma-teal`` escrito no cartão do P2: sobraram os gatilhos e as bolas dos
analógicos, e o corpo do controle SUMIU da tela. Não é a cor do aparelho nem o
neutro do "não sei" — é um terceiro estado que não quer dizer nada, e é PIOR que
o congelado que esta onda veio matar, porque não parece defeito: parece desenho.

Depois da cura, os mesmos 28 modelos escritos um a um no ``data-colorway`` do
cartão do P1, lidos por ``getComputedStyle().fill``: **28 de 28 pintaram o que o
mapa dela manda** (o ``url()`` volta do navegador com aspas, e é o mesmo valor).

A MORDIDA: tire o ``{BLOCO_DA_TINTA}`` do ``MIOLO`` de ``aba06.py`` e rode o
gerador. Ele PARA, nomeando o ``id`` morto; e se alguém publicar a página assim
por outro caminho, os dois testes abaixo reprovam.

A RÉGUA IRMÃ é ``test_a_06_o_desenho_vem_do_aparelho.py``, e elas não se
sobrepõem: aquela cobra que a página declare os 28 SELETORES; esta cobra que a
TINTA que esses seletores pedem exista. As duas verdes é o que faz a lei dela
valer para os 28, e não para os 16 que pintam com hex.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "06-navegacao.html"  # (noqa-acento) nome de arquivo

#: Uma referência a servidor de pintura, dentro de uma folha de estilo.
_URL = re.compile(r"url\(#([^)]+)\)")

#: Um `id` publicado por qualquer elemento da página.
_ID = re.compile(r'\sid="([^"]+)"')


@pytest.fixture
def bancada() -> str:
    from hefesto_dualsense4unix.interface import onde

    return onde.pagina(PAGINA).read_text(encoding="utf-8")


@pytest.fixture
def folha_da_pagina(bancada: str) -> str:
    """A folha dos 28 como a PÁGINA a publica — não como o SVG a guarda.

    É a diferença que o defeito inteiro mora: o texto é o mesmo, o contexto não.
    Dentro do SVG os `url(#…)` apontam para irmãos prefixados; publicada na
    página, eles passam a apontar para o documento.
    """
    dentro = "".join(re.findall(r"<style[^>]*>(.*?)</style>", bancada, re.S))
    assert 'svg[data-colorway="white"]' in dentro, (
        "a página parou de publicar a folha das cores — sem ela esta régua "
        "não tem o que medir, e a aba volta a ter um modelo só")
    return dentro


def test_a_folha_da_pagina_pede_tinta(folha_da_pagina: str) -> None:
    """A guarda do vazio: se nenhum modelo pedisse `url(#…)`, os dois testes
    abaixo passariam sem medir nada — que é o defeito que esta casa mais
    derruba."""
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
    """O teste que a tela pagou: `url(#x)` sem `id="x"` não fica cinza, SOME.

    Compara CONTRA A PÁGINA INTEIRA de propósito: o `<defs>` pode ser publicado
    solto (é o que a `aba06` faz) ou dentro de um dos desenhos — o que importa é
    que o navegador ache o `id`, e ele procura no documento.
    """
    pedidas = sorted(set(_URL.findall(folha_da_pagina)))
    publicados = set(_ID.findall(bancada))
    mortas = [i for i in pedidas if i not in publicados]
    assert not mortas, (
        f"a folha das cores da {PAGINA} pede {mortas} e a página não publica "
        f"esse `id`. Quem tiver um desses doze modelos NÃO vê o desenho cinza: "
        f"vê o corpo do controle sumir. Falta o `BLOCO_DA_TINTA` no `MIOLO` de "
        f"aba06.py")


def test_a_tinta_sai_uma_vez_e_sem_prefixo(bancada: str) -> None:
    """UMA cópia, e com o nome que a folha pede.

    Prefixar o `<defs>` publicado seria "consertar" pelo lado errado: a folha da
    página é UMA e não pode dizer quatro nomes. E publicá-lo duas vezes traria
    de volta id duplicado no documento, que é o defeito que `monta.svg()`
    prefixa para evitar.
    """
    assert bancada.count('id="hachura-sem-hex"') == 1, (
        "o servidor de pintura da hachura aparece mais de uma vez (ou nenhuma) "
        "sem prefixo — a folha da página pede exatamente este nome")
    assert 'class="cores-do-dualsense"' in bancada, (
        "o bloco da tinta perdeu a classe que o identifica na página — quem "
        "for lê-la depois não acha o que este teste protege")
