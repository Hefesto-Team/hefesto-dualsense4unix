"""O balão do rádio vizinho se lê: fundo da faixa e uma palavra ao lado do ícone."""

from __future__ import annotations

import pathlib
import re

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes.a08_conexoes`, que carrega o GTK")

from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PAGINAS = (
    RAIZ / "mockup/08-conexoes.html",
    RAIZ / "src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html",
)


def _palavras(vizinhos: list[dict[str, str]]) -> list[str]:
    html = a08.html_fora_da_faixa({"espectro": [], "vizinhos": vizinhos})
    return re.findall(r'<span class="palpite" aria-hidden="true">([^<]*)</span>', html)


def test_todo_balao_diz_uma_palavra() -> None:
    vizinhos = [
        {"id": "v1", "tipo": "", "nome": "", "sugestao": "mouse", "sugestao_tipo": "mouse"},
        {"id": "v2", "tipo": "", "nome": "", "sugestao": "", "sugestao_tipo": ""},
        {"id": "v3", "tipo": "teclado", "nome": "Teclado da sala", "sugestao": ""},
    ]
    assert _palavras(vizinhos) == ["Mouse?", a08.SEM_NOME_NO_BALAO, "Teclado da sala"]


def test_o_balao_nao_herda_o_fundo_do_sistema() -> None:
    for pagina in PAGINAS:
        css = pagina.read_text(encoding="utf-8")
        assert re.search(r"\.radio button\.selo-fora\{background:transparent", css), pagina
