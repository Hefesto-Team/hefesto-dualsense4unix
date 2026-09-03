#!/usr/bin/env python3
"""Todo lugar de controle — cheio ou VAZIO — tem endereço, nas sete abas.

A DECISÃO É DELA, 03/09/2026, e ela a enunciou assim:

    *"Tem que aparecer desligado enquanto não tem nenhum controle. A partir do
    momento que tiver, ele aparece o controle devidamente conectado. Se isso
    não ocorre com os 4 controles em cada aba, então temos que construir isso e
    garantir isso."*

**GARANTIR É ESTE ARQUIVO.**

O QUE ESTAVA ERRADO, medido no DOM VIVO em 03/09 com a janela oculta e o daemon
rodando — não no fonte, na tela::

    [data-controle="p1"] -> 1 elemento
    [data-controle="p2"] -> 1 elemento
    [data-controle="p3"] -> 0 elementos   <- ninguém
    [data-controle="p4"] -> 0 elementos   <- ninguém

As quatro colunas ESTAVAM na tela — desenho do controle, rótulo "P3 ·
Desconectado", as sete linhas na altura certa. O que faltava era o ENDEREÇO: o
lugar vazio era vazio só porque o desenho o desenhou vazio. Quando o terceiro
controle chegasse, o produto não teria por onde escrever nele.

TRÊS ABAS ESTAVAM ASSIM (`04-iluminacao`, `06-navegacao`, `08-conexoes`) e uma
já fazia certo (`05-vibracao`) — com o comentário no gerador dizendo por quê.
Esta régua é a promoção daquele comentário a portão.

POR QUE ELA MEDE O PUBLICADO E A BANCADA, e não só um: o produto renderiza o
publicado; a bancada é o que a próxima publicação leva. Uma régua que olhasse
só um dos dois passaria verde sobre metade do defeito.

A MORDIDA: tire o `data-controle` de qualquer lugar vazio de qualquer gerador,
regere, e :func:`test_as_quatro_casas_tem_endereco` reprova nomeando a aba.
"""

from __future__ import annotations

import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
BANCADA = RAIZ / "mockup"
PUBLICADO = RAIZ / "src/hefesto_dualsense4unix/interface/paginas"

#: AS ABAS QUE TÊM LUGAR POR CONTROLE. As três de fora não têm coluna por
#: aparelho nenhuma — `07-lancadores` fala de jogos, `09-sistema` da máquina e
#: `10-perfis` de perfis —, e exigir os quatro lugares delas seria inventar
#: requisito. Ficam nomeadas para que a lista não seja um silêncio.
COM_LUGAR = (
    "01-jogar", "02-controles", "03-gatilhos", "04-iluminacao",
    "05-vibracao", "06-navegacao", "08-conexoes",
)
SEM_LUGAR = ("07-lancadores", "09-sistema", "10-perfis")

CASAS = ("p1", "p2", "p3", "p4")

#: O QUE SE PROCURA. `data-controle="pN"` é o que `hefesto_vivo` usa nos DOIS
#: passos que decidem: o `1b`, que fecha o lugar sem dono, e o `1c`, que o
#: reabre quando o controle chega.
#:
#: A ABERTURA DE TAG É OBRIGATÓRIA, e não é capricho: a primeira versão desta
#: régua casava `data-controle="p1"` em QUALQUER lugar do arquivo, e acusou
#: duplicata em duas páginas onde a segunda ocorrência era uma REGRA DE CSS
#: (`.ctl[data-controle="p1"]{--plastico:…}`) e um COMENTÁRIO. Contar a palavra
#: em vez do elemento é o defeito que esta casa mais paga; aqui ele apareceu
#: dentro da própria régua que nasceu para pegá-lo.
ENDERECO = re.compile(r'<[a-zA-Z][^>]*?data-controle="(p[1-4])"')


def _paginas():
    for raiz in (BANCADA, PUBLICADO):
        for nome in COM_LUGAR:
            caminho = raiz / f"{nome}.html"
            if caminho.exists():
                yield raiz.name, nome, caminho


@pytest.mark.parametrize("onde,aba,caminho", list(_paginas()),
                         ids=lambda x: x if isinstance(x, str) else "")
def test_as_quatro_casas_tem_endereco(onde: str, aba: str,
                                      caminho: pathlib.Path) -> None:
    """Os quatro lugares desta aba são alcançáveis pelo produto."""
    achados = set(ENDERECO.findall(caminho.read_text(encoding="utf-8")))
    faltam = [c for c in CASAS if c not in achados]
    assert not faltam, (
        f"{onde}/{aba}.html: os lugares {', '.join(faltam)} não têm "
        "`data-controle`. Eles APARECEM na tela e o produto não tem por onde "
        "escrever neles quando o controle chegar — que é exatamente o que ela "
        "mandou garantir em 03/09.")


@pytest.mark.parametrize("aba", SEM_LUGAR)
def test_a_lista_de_fora_continua_sem_lugar_por_controle(aba: str) -> None:
    """E as três de fora não ganharam lugar por controle sem ninguém ver.

    Sem esta metade a lista `SEM_LUGAR` viraria uma isenção que ninguém revisa:
    no dia em que a `10-perfis` ganhar uma coluna por aparelho, ela tem de
    entrar em `COM_LUGAR` — e é este teste que obriga a conversa.
    """
    caminho = PUBLICADO / f"{aba}.html"
    if not caminho.exists():
        pytest.skip(f"{aba} não está publicada")
    achados = set(ENDERECO.findall(caminho.read_text(encoding="utf-8")))
    assert not achados, (
        f"{aba}.html ganhou lugar por controle ({', '.join(sorted(achados))}) "
        "e continua na lista das que não têm. Mova-a para `COM_LUGAR`.")


def test_o_vazio_e_o_cheio_usam_o_mesmo_endereco() -> None:
    """Um lugar não pode trocar de endereço ao esvaziar.

    É o defeito que a `06-navegacao` tinha noutra forma: o cartão nasce
    `class="nav-ctl"` e vira `class="nav-ctl vazia"`, e se o endereço saísse
    junto com o dono o produto perderia o lugar exatamente quando precisa dele.
    A conta abaixo é simples e morde: cada `pN` aparece UMA vez por página.
    """
    ruins = []
    for onde, aba, caminho in _paginas():
        texto = caminho.read_text(encoding="utf-8")
        achados = ENDERECO.findall(texto)
        for casa in CASAS:
            n = achados.count(casa)
            if n != 1:
                ruins.append(f"{onde}/{aba}.html: {casa} aparece {n}x")
    assert not ruins, (
        "cada lugar tem de ter UM endereço, e um só:\n  " + "\n  ".join(ruins))
