"""O desenho do DualSense não grita no balão (A-TELA-SEM-O-QUE-A-REGUA-ACEITA-01).

O balão que aparece ao parar o mouse sobre uma peça é o ``<title>`` do SVG. Os
rótulos de grupo («CHASSI», «OMBROS E GATILHOS»…) e a ênfase de «INTEIRO» eram
caixa alta que a régua de maiúscula aceitava como dívida. A escolha
(08/10/2026) foi a opção a: balão com a primeira letra maiúscula e o resto
minúsculo.

Esta régua lê a FONTE (os dois SVG e a lista do exportador) e as páginas do
``mockup/``, que o gerador reescreve. Não depende de ``--publicar``, que é da
costura: o que ela mede é a origem.
"""
from __future__ import annotations

import ast
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
SVGS = (INTERFACE / "ds_limpo.svg", RAIZ / "assets" / "control-svg" / "dualsense.svg")
EXPORTAR = RAIZ / "scripts" / "tela" / "exportar.py"

_TITULO = re.compile(r"<title>([^<]*)</title>")
_GRITO = re.compile(r"(?<![^\W\d_])[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{3,}(?![^\W\d_])")


def _gritos(texto: str) -> list[str]:
    """Os gritos dos ``<title>`` do corpo: o do ``<head>`` é o nome da janela; ``{…}`` é código."""
    corpo = re.sub(r"<head>.*?</head>", "", texto, flags=re.S)
    return [g for t in _TITULO.findall(corpo) for g in _GRITO.findall(re.sub(r"\{[^}]*\}", "", t))]


def test_os_dois_svg_do_dualsense_nao_gritam_no_balao() -> None:
    for svg in SVGS:
        assert _TITULO.findall(svg.read_text(encoding="utf-8")), f"{svg}: nenhum <title> lido"
        assert _gritos(svg.read_text(encoding="utf-8")) == [], svg


def test_os_dois_svg_sao_o_mesmo_desenho() -> None:
    a, b = (s.read_bytes() for s in SVGS)
    assert a == b


def test_a_lista_de_grupos_do_exportador_nao_grita() -> None:
    """``exportar.py`` escreve arquivo no import: lê-se pela árvore, não se importa."""
    arvore = ast.parse(EXPORTAR.read_text(encoding="utf-8"))
    grupos = next(
        n.value for n in arvore.body
        if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "GRUPOS" for t in n.targets)
    )
    titulos = [ast.literal_eval(g.elts[1]) for g in grupos.elts]
    assert len(titulos) == 9
    for t in titulos:
        assert not _GRITO.search(t), t
    assert _gritos(EXPORTAR.read_text(encoding="utf-8")) == []


def test_nenhuma_pagina_do_mockup_mostra_balao_em_caixa_alta() -> None:
    paginas = sorted((RAIZ / "mockup").glob("*.html"))
    assert len(paginas) >= 10
    achados = {
        (p.name, g)
        for p in paginas
        for g in _gritos(p.read_text(encoding="utf-8"))
    }
    assert achados == set(), sorted(achados)


def test_o_campo_do_perfil_do_so_dentro_do_jogo_existe_e_viaja() -> None:
    """O campo que faz o «Só dentro do jogo» funcionar (feito pela navegação 1-17)."""
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    assert "teclado_so_no_jogo" in Profile.model_fields
    sem = Profile(name="regua-do-balao", match=MatchAny())
    assert sem.teclado_so_no_jogo is None
    assert "teclado_so_no_jogo" not in sem.model_dump(mode="json", exclude_none=True)
    com = Profile(name="regua-do-balao", match=MatchAny(), teclado_so_no_jogo=True)
    assert Profile.model_validate(com.model_dump(mode="json")).teclado_so_no_jogo is True
