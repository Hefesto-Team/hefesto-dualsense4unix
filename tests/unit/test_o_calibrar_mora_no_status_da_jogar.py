"""A JOGAR: o «Calibrar giroscópio» mora no cartão do Status, ao lado do Reconectar.

D-2910-O-CALIBRAR-MORA-NO-STATUS-DA-JOGAR. A calibração é de todos os controles de uma vez
(«Todos parados numa superfície plana»), e a ação que vale para todos mora no Status, como
o Reconectar; o topo de «Dispositivos conectados» fica só com o título e o Modo automático.
A mordida: `calibrar=True` de volta no `MIOLO_SEM_A_MASCARA` da `aba02.py` põe o botão de
novo no topo dos Dispositivos, e o teste reprova.
"""
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
def test_o_calibrar_esta_no_status_antes_do_reconectar_e_so_ali(publicado: bool) -> None:
    """D-2910-O-CALIBRAR-MORA-NO-STATUS-DA-JOGAR."""
    doc = onde.pagina("01-jogar.html", publicado=publicado).read_text(encoding="utf-8")
    status, dispositivos = _quadros(doc)
    assert doc.split("<body", 1)[1].count(LINK) == 1
    assert LINK not in dispositivos, "o Calibrar voltou ao topo de «Dispositivos conectados»"
    topo = status.split('class="quadro-topo"', 1)[1]
    assert LINK in topo
    assert topo.find(LINK) < topo.find("reconectar"), "o Calibrar saiu de antes do Reconectar"
    botao = re.search(rf'<a class="canto calibra[^"]*" {LINK} data-dica="([^"]+)">', topo)
    assert botao and botao.group(1) == "Todos parados numa superfície plana"
