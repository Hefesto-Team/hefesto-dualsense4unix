from __future__ import annotations

import re

import pytest

from hefesto_dualsense4unix.interface import onde

LINK = 'href="calibrar-sensores.html"'


def _quadros(doc: str) -> tuple[str, str]:
    corpo = doc.split("<body", 1)[1]
    status = corpo.split('class="quadro hef-q', 1)[1].split('<div class="quadro estica">', 1)[0]
    dispositivos = corpo.split('<div class="quadro estica">', 1)[1]
    return status, dispositivos


@pytest.mark.parametrize("publicado", [False, True], ids=["desenho", "publicado"])
def test_o_calibrar_esta_imediatamente_a_esquerda_do_modo_automatico(publicado: bool) -> None:
    doc = onde.pagina("01-jogar.html", publicado=publicado).read_text(encoding="utf-8")
    status, dispositivos = _quadros(doc)
    assert doc.split("<body", 1)[1].count(LINK) == 1
    assert LINK not in status, "o Calibrar voltou ao Status, ao lado do Reconectar"
    topo = dispositivos.split('<div class="quadro-corpo">', 1)[0]
    vizinhos = re.search(
        rf'<a class="btn nativo-nao" {LINK} data-dica="([^"]+)">(?:(?!</a>).)*</a>\s*'
        r'<button class="modo-auto"', topo, re.S)
    assert vizinhos, ("D-3110-O-CALIBRAR-FICA-A-ESQUERDA-DO-MODO-AUTOMATICO: o Calibrar saiu de "
                      "imediatamente à esquerda do Modo automático")
    assert vizinhos.group(1) == "Todos parados numa superfície plana"
