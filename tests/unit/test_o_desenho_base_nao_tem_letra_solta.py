"""O desenho base do DualSense não tem letra solta fora de um glifo.

O-DESENHO-BASE-PERDE-O-R-SOLTO-01 (14/11/2026): o `ds_limpo.svg` trazia um `<text>` «R» fora de todo
grupo, que saía escuro por baixo do glifo do analógico direito nas abas 04, 05 e 08 e na
calibrar-sensores. MORDIDA: devolver a linha do «R» ao `ds_limpo.svg` reprova as duas réguas do
desenho; as páginas que embutem o desenho reprovam até o gerador e o `--publicar` passarem.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.interface import onde as onde_mora

RAIZ = Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
DESENHOS = (INTERFACE / "ds_limpo.svg", RAIZ / "assets" / "control-svg" / "dualsense.svg")
PAGINAS = ("04-iluminacao.html", "05-vibracao.html", "08-conexoes.html", "calibrar-sensores.html")
LETRA_SOLTA_DO_ANALOGICO = re.compile(r'<text\b[^>]*x="80\.617" y="63\.683">R</text>')


def _textos_fora_de_glifo(svg: str) -> list[str]:
    """Os `<text>` do desenho que não moram dentro de um grupo `glifo-*`."""
    soltos: list[str] = []
    pilha: list[bool] = []
    for m in re.finditer(r'<g\b[^>]*>|</g>|<text\b[^>]*>[^<]*</text>', svg):
        marca = m.group(0)
        if marca.startswith("</g"):
            if pilha:
                pilha.pop()
        elif marca.startswith("<g"):
            dono = re.search(r'\bid="([^"]+)"', marca)
            e_glifo = bool(dono and dono.group(1).startswith("glifo-"))
            pilha.append(bool(pilha and pilha[-1]) or e_glifo)
        elif not (pilha and pilha[-1]):
            soltos.append(marca)
    return soltos


@pytest.mark.parametrize("desenho", DESENHOS, ids=lambda p: p.name)
def test_todo_texto_do_desenho_mora_num_glifo(desenho: Path) -> None:
    soltos = _textos_fora_de_glifo(desenho.read_text(encoding="utf-8"))
    assert not soltos, f"{desenho.name}: texto fora de glifo: {[s[-40:] for s in soltos]}"


@pytest.mark.parametrize("onde", ("mockup", "publicado"))
@pytest.mark.parametrize("nome", PAGINAS)
def test_a_pagina_que_embute_o_desenho_nao_tem_o_r_solto(nome: str, onde: str) -> None:
    arquivo = onde_mora.pagina(nome, publicado=onde == "publicado")
    vezes = len(LETRA_SOLTA_DO_ANALOGICO.findall(arquivo.read_text(encoding="utf-8")))
    assert vezes == 0, f"{onde}/{nome}: o «R» solto do analógico direito aparece {vezes} vez(es)"
