"""A Experimental é a última aba da fita (A-ABA-EXPERIMENTAL-VAI-PARA-O-FIM-DA-FITA-01, 21/10/2026).

A ordem que o usuário escolheu: Jogar · Gatilhos · Iluminação · Vibração · Navegação · Conexões ·
Sistema · Perfis · Experimental. O número do arquivo (`07-lancadores.html`) é o endereço, não a
posição. A Controles saiu da fita (28/10/2026) e mora na Jogar; a página publicada que ainda está
em trabalho no `DIVERGENCIAS` segue com a fita de dez até o `--publicar` dela.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
PUBLICADO = INTERFACE / "paginas"  # (noqa-acento)

ORDEM = ("01-jogar", "03-gatilhos", "04-iluminacao", "05-vibracao", "06-navegacao",
         "08-conexoes", "09-sistema", "10-perfis", "07-lancadores")
ORDEM_DA_FITA_DE_DEZ = ("01-jogar", "02-controles", *ORDEM[1:])

_ABA = re.compile(r'<a class="aba[^"]*" href="(\d\d-[a-z]+)\.html"')

DOCUMENTOS = [
    INTERFACE / "topo.html",
    *sorted((RAIZ / "mockup").glob("[01]*.html")),
    *sorted(PUBLICADO.glob("[01]*.html")),
]


EM_TRABALHO = set(re.findall(r"^## (\S+\.html)$",
                             (RAIZ / "mockup" / "DIVERGENCIAS.md").read_text(encoding="utf-8"),
                             re.M))


@pytest.mark.parametrize("documento", DOCUMENTOS, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_a_fita_tem_a_experimental_por_ultimo(documento: Path) -> None:
    """A prova da D-2110-A-EXPERIMENTAL-E-A-ULTIMA-ABA.

    A página publicada leva a fita do desenho quando a aba saiu do `DIVERGENCIAS`; enquanto a
    aba está em trabalho, o produto segue com a fita de dez.
    """
    em_trabalho = documento.parent == PUBLICADO and documento.name in EM_TRABALHO
    esperada = ORDEM_DA_FITA_DE_DEZ if em_trabalho else ORDEM
    assert tuple(_ABA.findall(documento.read_text(encoding="utf-8"))) == esperada


def test_as_listas_das_abas_seguem_a_fita() -> None:
    ver = (INTERFACE / "ver.py").read_text(encoding="utf-8")
    bloco = ver[ver.index("ABAS = ["):ver.index("]", ver.index("ABAS = ["))]
    assert tuple(re.findall(r'"(\d\d-[a-z]+)\.html"', bloco)) == ORDEM
    monta = (INTERFACE / "monta.py").read_text(encoding="utf-8")
    bloco = monta[monta.index("ABAS = ["):monta.index("]", monta.index("ABAS = ["))]
    assert tuple(re.findall(r'"(\d\d-[a-z]+)"', bloco)) == ORDEM
