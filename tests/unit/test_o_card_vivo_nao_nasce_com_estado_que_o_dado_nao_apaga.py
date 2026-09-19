"""O card VIVO não nasce pintado com estado que o dado não possa apagar.

A QUEIXA QUE ISTO CURA — 19/09/2026, palavras dela: *"o botão r2 fica sempre
pressionado isso pra todos os controles"*.  <!-- noqa-acento: citação literal dela -->

O DEFEITO, MEDIDO: o gerador da aba Controles dava a classe `plast` (a cor do
plástico) às três peças que o desenho original destaca — ``cross``, ``l2`` e
``r2`` — sempre que elas nasciam APAGADAS. E a ponte da tela só acende e apaga
UMA classe, a que `data-hef-classe` nomeia, com `on` por padrão
(`hefesto_vivo.BOOTSTRAP`, ramo `classe`: ``el.dataset.hefClasse || 'on'``).
Nenhum dado vivo desligava `plast`, então a peça ficava pintada para sempre.
No Cosmic Red dela o `--plastico` é rosa — a mesma cor do `.gb.on` —, e o R2
lia como apertado com o controle parado na mesa. Nos lugares P2-P4, que nascem
sem nada apertado, eram TRÊS peças.

É A SEGUNDA METADE DE UMA CURA DE 03/09/2026, que deu `data-campo` aos glifos
para o dado poder apagar a classe `on` — e deixou `plast` com o mesmo defeito.

A REGRA QUE ESTA RÉGUA GUARDA, e ela é geral: **um elemento que o piloto pinta
pelo alvo `classe` só pode nascer com a classe que esse piloto apaga.** Toda
outra classe dele é ESTRUTURA (`gb`, o que dá forma), nunca ESTADO.

ONDE ELA MORDE: devolva o ternário do `plast` a `interface/aba02.py::grade` e
rode o gerador — os dezesseis glifos de cada card voltam a nascer com a cor da
peça, e esta régua reprova nomeando a página, o glifo e a classe.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from hefesto_dualsense4unix.interface import onde

#: A aba dos cards dos controles. É a única com glifos de botão por card.
PAGINA = "02-controles.html"  # (noqa-acento) nome de arquivo

#: A CLASSE QUE DÁ FORMA, e a única que pode nascer sem ter quem a apague.
ESTRUTURA = "gb"

#: O QUE O PILOTO APAGA, e o nome não se digita aqui por gosto: é o default do
#: ramo `classe` do `hefesto_vivo.BOOTSTRAP` (``el.dataset.hefClasse || 'on'``).
#: Um glifo que declare `data-hef-classe` é medido por ele, não por este.
APAGAVEL_POR_PADRAO = "on"

_GLIFO = re.compile(
    r'<span class="(?P<classes>[^"]*)"[^>]*?data-glifo="(?P<glifo>[^"]+)"[^>]*?>',
    re.S,
)


def _paginas() -> list[pathlib.Path]:
    """A bancada e o publicado.

    OS DOIS, E NÃO SÓ UM: medir só a bancada deixaria a régua verde com a tela
    dela ainda na página velha; medir só o publicado daria verde sobre a página
    congelada. É a armadilha que esta casa já pagou quatro vezes num dia.
    """
    return [onde.pagina(PAGINA), onde.pagina(PAGINA, publicado=True)]


@pytest.fixture(params=["bancada", "publicado"])
def pagina(request: pytest.FixtureRequest) -> str:
    caminho = _paginas()[0 if request.param == "bancada" else 1]
    if not caminho.exists():  # pragma: no cover - a página existe nas duas
        pytest.skip(f"{caminho} não existe")
    return caminho.read_text(encoding="utf-8")


def _apagavel(tag: str) -> str:
    """A classe que o piloto apaga NESTE elemento — o `data-hef-classe` ou `on`."""
    achado = re.search(r'data-hef-classe="([^"]+)"', tag)
    return achado.group(1) if achado else APAGAVEL_POR_PADRAO


def test_ha_glifos_a_medir(pagina: str) -> None:
    """A régua que acha ZERO é erro, não silêncio — a lei desta casa."""
    assert len(_GLIFO.findall(pagina)) >= 16, (
        "nenhum glifo de botão na página: a régua está lendo o arquivo errado, "
        "ou o desenho mudou de marcação e esta expressão envelheceu"
    )


def test_glifo_so_nasce_com_estrutura_ou_com_o_que_o_dado_apaga(pagina: str) -> None:
    """Nenhum glifo carrega classe que o tique não possa tirar.

    É a régua inteira: a cor do plástico (`plast`) — ou qualquer outra pintura
    futura — não pode nascer num card que afirma o estado do aparelho.
    """
    presos: list[str] = []
    for achado in _GLIFO.finditer(pagina):
        tag = achado.group(0)
        classes = achado.group("classes").split()
        podem = {ESTRUTURA, _apagavel(tag)}
        sobra = [c for c in classes if c not in podem]
        if sobra:
            presos.append(f"{achado.group('glifo')}: {' '.join(sobra)}")
    assert not presos, (
        "glifo do card vivo nasceu com classe que o dado não apaga — a tela "
        "afirma estado do aparelho que o aparelho não disse: " + "; ".join(presos)
    )
