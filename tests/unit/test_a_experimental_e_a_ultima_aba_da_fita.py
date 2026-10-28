"""A Experimental é a última aba da fita (A-ABA-EXPERIMENTAL-VAI-PARA-O-FIM-DA-FITA-01, 21/10/2026).

A ordem que o usuário escolheu: Jogar · Gatilhos · Iluminação · Vibração · Navegação · Conexões ·
Sistema · Perfis · Experimental. O número do arquivo (`07-lancadores.html`) é o endereço, não a
posição. A Controles saiu da fita (28/10/2026) e mora na Jogar: toda página, do desenho e do
produto, leva a fita de nove, e a publicada que sai do produto (`monta.PAGINAS_QUE_SAIRAM`) não se
mede.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

from monta import PAGINAS_QUE_SAIRAM

PUBLICADO = INTERFACE / "paginas"  # (noqa-acento)

ORDEM = ("01-jogar", "03-gatilhos", "04-iluminacao", "05-vibracao", "06-navegacao",
         "08-conexoes", "09-sistema", "10-perfis", "07-lancadores")

_ABA = re.compile(r'<a class="aba[^"]*" href="(\d\d-[a-z]+)\.html"')

DOCUMENTOS = [
    INTERFACE / "topo.html",
    *sorted((RAIZ / "mockup").glob("[01]*.html")),
    *sorted(p for p in PUBLICADO.glob("[01]*.html") if p.name not in PAGINAS_QUE_SAIRAM),
]


@pytest.mark.parametrize("documento", DOCUMENTOS, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_a_fita_tem_a_experimental_por_ultimo(documento: Path) -> None:
    """A prova da D-2110-A-EXPERIMENTAL-E-A-ULTIMA-ABA, na fita de nove de toda página."""
    assert tuple(_ABA.findall(documento.read_text(encoding="utf-8"))) == ORDEM


def test_as_listas_das_abas_seguem_a_fita() -> None:
    ver = (INTERFACE / "ver.py").read_text(encoding="utf-8")
    bloco = ver[ver.index("ABAS = ["):ver.index("]", ver.index("ABAS = ["))]
    assert tuple(re.findall(r'"(\d\d-[a-z]+)\.html"', bloco)) == ORDEM
    monta = (INTERFACE / "monta.py").read_text(encoding="utf-8")
    bloco = monta[monta.index("ABAS = ["):monta.index("]", monta.index("ABAS = ["))]
    assert tuple(re.findall(r'"(\d\d-[a-z]+)"', bloco)) == ORDEM
