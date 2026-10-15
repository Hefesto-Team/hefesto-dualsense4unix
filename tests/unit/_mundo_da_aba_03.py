"""Em que mundo a aba Gatilhos está: a página publicada é a antiga ou a do todo.

O pacote lê a página publicada e serve às duas. As réguas das barras de ajuste, do «Efeito
pronto» e do «Guardar» medem a página antiga: na do todo esses elementos não existem, e a
régua passaria a medir o vazio. Elas saem do caminho com a razão dita, e saem de vez junto com o
código do pacote que as serve, na limpeza que vem depois da publicação.
"""

from __future__ import annotations

import pathlib

import pytest

PUBLICADA = (pathlib.Path(__file__).resolve().parents[2]
             / "src/hefesto_dualsense4unix/interface/paginas/03-gatilhos.html")


def a_publicada_e_a_do_todo() -> bool:
    return 'class="g2-grade"' in PUBLICADA.read_text(encoding="utf-8")


SO_NA_PAGINA_ANTIGA = pytest.mark.skipif(
    a_publicada_e_a_do_todo(),
    reason="a página publicada é a do todo: sem barras de ajuste, curvas nem Guardar; o código "
           "do pacote e esta régua saem juntos na limpeza que vem depois da publicação")
