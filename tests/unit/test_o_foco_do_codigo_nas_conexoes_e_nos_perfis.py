"""O foco que o código move nas Conexões e nos Perfis não abre a dica.

Sprint O-FOCO-DO-CODIGO-NAS-CONEXOES-E-NOS-PERFIS-NAO-ABRE-A-DICA-01 (cura da
D-0111-O-FOCO-DO-CODIGO-NAO-ABRE-A-DICA).

Medido em 25/11/2026: ``focarSemDica`` vivia local no ``base-comum.js`` e os oito pontos em que o
código move o foco (a pergunta, o painel «Conectar», o balão da sugestão e a devolução do foco em
``aba08.py``; a busca e o campo do nome em ``aba10.py``) chamavam ``.focus()`` cru, que abre a dica
de quem recebe o foco quando o gesto veio do teclado. A cura sobe a função a
``window.__hefFocarSemDica`` (um dono só) e os pontos a chamam.

A régua de texto reprova ``.focus()`` cru nos geradores de aba, com a lista declarada do que é foco
de quem usa (``FOCO_DE_QUEM_USA``, hoje vazia). A régua de comportamento abre a base comum num
Chrome, põe o teclado no comando e compara o foco do código com o do Tab.

MORDIDA: tirar a marca ``__hefFoco`` da função devolve a dica no ``test_o_foco_do_codigo_...``; um
``.focus()`` cru de volta num gerador reprova o teste de texto.
"""
from __future__ import annotations

import pathlib
import re
from collections.abc import Iterator
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
BASE_JS = (INTERFACE / "base-comum.js").read_text(encoding="utf-8")
CHROME = pathlib.Path("/usr/bin/google-chrome")

GERADORES = {"aba08.py": 5, "aba10.py": 3}

FOCO_DE_QUEM_USA: dict[str, int] = {}

_CRU = re.compile(r"\.focus\(")


def _fonte(nome: str) -> str:
    return (INTERFACE / nome).read_text(encoding="utf-8")


@pytest.mark.parametrize("nome", sorted(GERADORES))
def test_nenhum_gerador_de_aba_move_o_foco_cru(nome: str) -> None:
    """Todo ``.focus(`` de ``aba08.py`` e ``aba10.py`` é de quem usa e está declarado."""
    crus = len(_CRU.findall(_fonte(nome)))
    assert crus == FOCO_DE_QUEM_USA.get(nome, 0), (
        f"{nome} tem {crus} `.focus(` cru: o foco que o código move passa por "
        f"`window.__hefFocarSemDica`, o que é de quem usa entra em FOCO_DE_QUEM_USA")


@pytest.mark.parametrize("nome", sorted(GERADORES))
def test_os_pontos_de_foco_chamam_o_dono(nome: str) -> None:
    """Os pontos medidos (cinco nas Conexões, três nos Perfis) chamam o dono da função."""
    chamadas = _fonte(nome).count("window.__hefFocarSemDica(")
    esperadas = GERADORES[nome]
    assert chamadas == esperadas, f"{nome}: {chamadas} chamadas ao dono, eram {esperadas}"


def test_a_base_comum_e_o_dono_da_funcao() -> None:
    """A função mora no ``base-comum.js`` e sobe a ``window``, para as dez abas."""
    assert re.search(r"window\.__hefFocarSemDica\s*=", BASE_JS)


_PAGINA = (
    '<!doctype html><meta charset="utf-8"><body>'
    '<button id="a" data-dica="Dica de A">A</button>'
    '<button id="b" data-dica="Dica de B">B</button>'
    f"<script>{BASE_JS}</script></body>"
)

_DICA_ABERTA = """() => {
  const d = document.getElementById('hef-dica');
  return !!d && d.classList.contains('visivel');
}"""


@pytest.fixture(scope="module")
def pg(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Any]:
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema: a régua não tem motor")
    from playwright.sync_api import sync_playwright

    arq = tmp_path_factory.mktemp("foco") / "base.html"
    arq.write_text(_PAGINA, encoding="utf-8")
    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            p = nav.new_page(viewport={"width": 800, "height": 600})
            p.goto(arq.as_uri())
            yield p
        finally:
            nav.close()


def _limpar(pg: Any) -> None:
    pg.evaluate("() => { if (document.activeElement) document.activeElement.blur(); }")
    assert not pg.evaluate(_DICA_ABERTA)


def test_o_foco_do_teclado_abre_a_dica(pg: Any) -> None:
    """O controle da régua: o Tab no botão abre a dica; sem isso, o teste abaixo não prova nada."""
    _limpar(pg)
    pg.keyboard.press("Tab")
    assert pg.evaluate("() => document.activeElement.id") == "a"
    assert pg.evaluate(_DICA_ABERTA), "o Tab não abriu a dica: o instrumento não mede"
    _limpar(pg)


def test_o_foco_do_codigo_nao_abre_a_dica(pg: Any) -> None:
    """Com o teclado em uso, mover o foco pelo dono leva o foco e não abre a dica; o ``.focus()``
    cru, sim."""
    _limpar(pg)
    pg.keyboard.press("Tab")
    _limpar(pg)
    pg.evaluate("() => window.__hefFocarSemDica(document.getElementById('b'))")
    assert pg.evaluate("() => document.activeElement.id") == "b"
    assert not pg.evaluate(_DICA_ABERTA), "o foco do código abriu a dica"
    _limpar(pg)
    pg.evaluate("() => document.getElementById('a').focus()")
    assert pg.evaluate(_DICA_ABERTA), "o foco cru deixou de abrir a dica: o controle perdeu o dente"
    _limpar(pg)
