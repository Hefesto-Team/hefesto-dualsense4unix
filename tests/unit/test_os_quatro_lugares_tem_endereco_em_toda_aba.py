#!/usr/bin/env python3
"""Todo lugar de controle — cheio ou VAZIO — tem endereço, nas sete abas."""

from __future__ import annotations

import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
BANCADA = RAIZ / "mockup"
PUBLICADO = RAIZ / "src/hefesto_dualsense4unix/interface/paginas"

COM_LUGAR = (
    "01-jogar", "02-controles", "03-gatilhos", "04-iluminacao",
    "05-vibracao", "06-navegacao", "08-conexoes",
)
SEM_LUGAR = ("07-lancadores", "09-sistema", "10-perfis")

CASAS = ("p1", "p2", "p3", "p4")

#: (`.ctl[data-controle="p1"]{--plastico:…}`) e um COMENTÁRIO. Contar a palavra
ENDERECO = re.compile(r'<[a-zA-Z][^>]*?data-controle="(p[1-4])"')


def _paginas():
    for raiz in (BANCADA, PUBLICADO):
        for nome in COM_LUGAR:
            caminho = raiz / f"{nome}.html"
            if caminho.exists():
                yield raiz.name, nome, caminho


@pytest.mark.parametrize("onde,aba,caminho", list(_paginas()),
                         ids=lambda x: x if isinstance(x, str) else "")
def test_as_quatro_casas_tem_endereco(onde: str, aba: str,
                                      caminho: pathlib.Path) -> None:
    """Os quatro lugares desta aba são alcançáveis pelo produto."""
    achados = set(ENDERECO.findall(caminho.read_text(encoding="utf-8")))
    faltam = [c for c in CASAS if c not in achados]
    assert not faltam, (
        f"{onde}/{aba}.html: os lugares {', '.join(faltam)} não têm "
        "`data-controle`. Eles APARECEM na tela e o produto não tem por onde "
        "escrever neles quando o controle chegar — que é exatamente o que ela "
        "mandou garantir em 03/09.")


@pytest.mark.parametrize("aba", SEM_LUGAR)
def test_a_lista_de_fora_continua_sem_lugar_por_controle(aba: str) -> None:
    """E as três de fora não ganharam lugar por controle sem ninguém ver."""
    caminho = PUBLICADO / f"{aba}.html"
    if not caminho.exists():
        pytest.skip(f"{aba} não está publicada")
    achados = set(ENDERECO.findall(caminho.read_text(encoding="utf-8")))
    assert not achados, (
        f"{aba}.html ganhou lugar por controle ({', '.join(sorted(achados))}) "
        "e continua na lista das que não têm. Mova-a para `COM_LUGAR`.")


def test_o_vazio_e_o_cheio_usam_o_mesmo_endereco() -> None:
    """Um lugar não pode trocar de endereço ao esvaziar."""
    ruins = []
    for onde, aba, caminho in _paginas():
        texto = caminho.read_text(encoding="utf-8")
        achados = ENDERECO.findall(texto)
        for casa in CASAS:
            n = achados.count(casa)
            if n != 1:
                ruins.append(f"{onde}/{aba}.html: {casa} aparece {n}x")
    assert not ruins, (
        "cada lugar tem de ter UM endereço, e um só:\n  " + "\n  ".join(ruins))
