"""O índice de `html/` leva aos TRÊS instrumentos, e nenhum link dele é quebrado.

Sprint `A-CASA-ARRUMADA-01`, HTML-1 e HTML-2 (25/08/2026).

O DEFEITO QUE ESTE PORTÃO EXISTE PARA PEGAR
-------------------------------------------
`html/index.html` é *"a única página que ela precisa abrir"*. Uma página com
essa promessa que deixa de citar um instrumento é pior que não existir: ela dá a
impressão de ter mostrado tudo. E um índice com link para arquivo que não está
no disco entrega o erro do navegador em vez do instrumento.

Os dois defeitos são silenciosos — ninguém percebe que um cartão sumiu, porque a
página continua bonita e continua abrindo. Este arquivo é a régua que os vê.

POR QUE ISTO NÃO É REDUNDANTE COM O `--check` DO GERADOR
--------------------------------------------------------
`scripts/gerar-indice-html.py --check` responde *"o publicado é o que este
script produz hoje?"*. Se alguém apagar um cartão da tupla `INSTRUMENTOS` do
gerador, ele fica VERDE — o publicado passa a ser exatamente o que o script
produz, com dois cartões. A pergunta deste teste é outra e independente: *"os
TRÊS instrumentos desta casa estão lá?"*. Duas réguas independentes é o que
revela; é regra desta casa.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PASTA = RAIZ / "html"
INDICE = PASTA / "index.html"

#: Os três instrumentos, escritos aqui À MÃO de propósito. Importar a tupla do
#: gerador faria o teste concordar com ele por construção — e o defeito que se
#: quer pegar é justamente um cartão sumir de lá.
OS_TRES = ("specs.html", "painel.html", "frases-de-tela.html")

#: A quarta página é o próprio índice; junto com as três, é o conjunto que tem
#: de carimbar (HTML-2).
OS_QUATRO = ("index.html", *OS_TRES)

HREF = re.compile(r'href="([^"]+)"')

#: A marca do carimbo da casa. Repetida aqui pela mesma razão de `OS_TRES`.
MARCA_DO_CARIMBO = "data-carimbo"


@pytest.fixture(scope="module")
def indice() -> str:
    if not INDICE.is_file():
        pytest.fail(
            f"{INDICE.relative_to(RAIZ)} não existe. Ele é GERADO: rode\n"
            "  python3 scripts/gerar-indice-html.py"
        )
    return INDICE.read_text(encoding="utf-8")


def _links(pagina: str) -> list[str]:
    """Os alvos locais do índice — sem âncoras e sem endereço de rede."""
    return [
        alvo
        for alvo in HREF.findall(pagina)
        if not alvo.startswith(("#", "mailto:", "http://", "https://"))
    ]


def test_o_indice_leva_aos_tres(indice: str) -> None:
    """Cada um dos três é um LINK do índice, não só um nome citado na prosa.

    Citar sem linkar não serve: o índice existe para ela abrir a página, e um
    nome escrito no meio de um parágrafo não abre nada.
    """
    alvos = set(_links(indice))
    faltando = [nome for nome in OS_TRES if nome not in alvos]
    assert not faltando, (
        "o índice de html/ não leva a: " + ", ".join(faltando) + ".\n"
        "Ele promete ser a única página que ela precisa abrir; um instrumento "
        "fora dele é um instrumento que ela não acha.\n"
        "Confira a tupla INSTRUMENTOS de scripts/gerar-indice-html.py e regere:\n"
        "  python3 scripts/gerar-indice-html.py"
    )


def test_nenhum_link_do_indice_aponta_para_o_vazio(indice: str) -> None:
    """Todo alvo do índice está no disco, ao lado dele."""
    quebrados = sorted({alvo for alvo in _links(indice) if not (PASTA / alvo).is_file()})
    assert not quebrados, (
        "link(s) do índice apontando para arquivo que não existe em html/: "
        + ", ".join(quebrados)
        + ".\nQuem abrir vai ver o erro do navegador em vez do instrumento."
    )


def test_o_indice_nao_pede_rede(indice: str) -> None:
    """A regra dos irmãos: autocontido, zero rede, zero CDN, zero fonte web.

    Escrita no `gerar-mapa.py` e válida para os quatro: *"um instrumento que só
    funciona com rede não serve para depurar rádio."*
    """
    fora = re.findall(r"https?://[^\"' )>]+", indice)
    assert not fora, (
        "o índice pede rede: " + ", ".join(sorted(set(fora))) + ".\n"
        "Os quatro instrumentos abrem com duplo clique, sem servidor e sem "
        "internet — é a regra que os torna úteis para depurar rádio."
    )


@pytest.mark.parametrize("nome", OS_QUATRO)
def test_os_quatro_carimbam_a_procedencia(nome: str) -> None:
    """HTML-2: os quatro trazem o MESMO carimbo — commit e data de geração.

    Sem ele, duas páginas geradas de commits diferentes parecem iguais, e a
    divergência só aparece quando alguém acredita num número velho.
    """
    caminho = PASTA / nome
    if not caminho.is_file():
        pytest.fail(
            f"html/{nome} não está no disco — regere os quatro:\n"
            "  python3 scripts/gerar-mapa.py && python3 scripts/gerar-painel.py "
            "&& python3 scripts/gerar-frases-de-tela.py "
            "&& python3 scripts/gerar-indice-html.py"
        )
    texto = caminho.read_text(encoding="utf-8", errors="replace")
    assert MARCA_DO_CARIMBO in texto, (
        f"html/{nome} não traz o carimbo da casa "
        f"(`{MARCA_DO_CARIMBO}`, scripts/carimbo_da_casa.py).\n"
        "Sem ele ninguém sabe de qual commit essa página nasceu, e o índice não "
        "consegue mostrar quando ela foi gerada."
    )


def test_a_raiz_nao_guarda_mais_os_tres() -> None:
    """Os três moram em `html/`, e em UM lugar só.

    Duas cópias do mesmo instrumento divergem no dia em que alguém regera uma
    delas — e a que ela abrir é a que estiver no marcador do navegador dela.
    """
    sobrando = [nome for nome in OS_TRES if (RAIZ / nome).is_file()]
    assert not sobrando, (
        "ainda há cópia na raiz de: " + ", ".join(sobrando) + ".\n"
        "Desde 25/08/2026 os instrumentos moram em html/. Duas cópias divergem "
        "na primeira vez que alguém regerar só uma."
    )
