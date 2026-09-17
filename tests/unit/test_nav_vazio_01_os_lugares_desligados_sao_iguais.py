"""NAV-VAZIO-01 — os lugares desligados são IGUAIS, com qualquer das duas palavras.

**Queixa dela, 17/09/2026**, com a foto da aba Navegação na mão:

    "vê que o campo de p2 de desativado é diferente do campo p3 e p4? eu
     preciso que todos os campos desativados fiquem iguais pra todos"

A causa já estava NOMEADA nesta casa desde 04/09, dentro do próprio
``a06_navegacao.py``, e o texto de lá vale mais que qualquer paráfrase:

    POR QUE O P3 E O P4 ESCAPARAM (…): eles nascem ``class="nav-ctl vazia"`` no
    HTML (…). O P2 nasce OCUPADO e fica vazio em tempo de execução — e quem o
    esvazia escreve a classe **``off``**, que folha de estilo nenhuma menciona.
    **As duas palavras para o mesmo estado nunca se encontraram.**

Aquela leva curou a COR, por um caminho lateral (``folha_do_plastico``, que
pinta por ``data-controle`` e não depende da classe). A MOLDURA ficou de fora:
``.nav-ctl.vazia`` põe ``border`` e ``background:transparent``, e ``off`` não
punha nada. Foi exatamente isso que ela fotografou — o P2 desligado com caixa
diferente da do P3 e do P4.

**O DEFEITO É DA FAMÍLIA QUE MAIS CUSTOU AQUI:** duas palavras para um estado
só, cada uma com um dono, livres para divergir em silêncio. A cura não escolhe
uma e renomeia a outra — o ``off`` é escrito pelo passo ``vazios`` do piloto
para CINCO abas, e o ``vazia`` é o que o desenho aprovado carrega. A cura faz a
folha cobrir as duas, e esta régua cobra que ela continue cobrindo.

**A RÉGUA LÊ A PALAVRA DO PILOTO DO FONTE DELE**, em vez de digitar ``"off"``.
Uma régua que digitasse a palavra seria a terceira cópia — e a terceira cópia
diverge igual às duas primeiras. É a lição que esta casa aprendeu onze vezes
numa leva só: *as réguas digitavam o que deviam LER*.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from hefesto_dualsense4unix import interface


# ---------------------------------------------------------------------------
# as duas fontes de verdade, LIDAS e nunca digitadas
# ---------------------------------------------------------------------------
def _pasta() -> pathlib.Path:
    return pathlib.Path(interface.__file__).parent


def _folha_da_navegacao() -> str:
    """O CSS que a aba Navegação publica — do PUBLICADO, que é o que ela vê."""
    arq = _pasta() / "paginas" / "06-navegacao.html"  # noqa-acento: `paginas` é o nome da PASTA
    assert arq.is_file(), f"a página publicada não está em {arq}"
    return arq.read_text(encoding="utf-8")


def _palavra_que_o_piloto_escreve() -> str:
    """A classe que o passo ``vazios`` do piloto põe num lugar sem dono.

    LIDA do `hefesto_vivo.py`, nunca digitada aqui. Se o piloto trocar a
    palavra, esta régua passa a cobrar a palavra NOVA na folha — que é
    precisamente o encontro que o defeito de 04/09 não teve.
    """
    fonte = (_pasta() / "hefesto_vivo.py").read_text(encoding="utf-8")
    # Ancora no LAÇO do passo `vazios` e lê a classe que ele adiciona. A janela
    # é generosa de propósito: o laço carrega um comentário longo (a
    # A-TELA-SAMBA-01), e uma janela curta cortaria o `add` fora.
    inicio = fonte.find("p.vazios || []")
    assert inicio > 0, (
        "não achei o passo `vazios` do piloto em `hefesto_vivo.py` — ele mudou "
        "de forma, e esta régua precisa ser reapontada POR SÍMBOLO"
    )
    janela = fonte[inicio : inicio + 2000]
    achadas = re.findall(r"classList\.add\('([a-z-]+)'\)", janela)
    assert achadas, (
        "o passo `vazios` não adiciona classe nenhuma — ou ele parou de marcar "
        "o lugar sem dono, ou a forma mudou"
    )
    return achadas[0]


# ---------------------------------------------------------------------------
# 1 — o encontro das duas palavras
# ---------------------------------------------------------------------------
def test_a_folha_conhece_a_palavra_que_o_piloto_escreve() -> None:
    """O defeito inteiro em uma asserção.

    Em 04/09 o piloto escrevia `off` e a folha só sabia `vazia`. A régua lê as
    DUAS pontas e exige que se encontrem.
    """
    palavra = _palavra_que_o_piloto_escreve()
    folha = _folha_da_navegacao()
    assert f".nav-ctl.{palavra}" in folha, (
        f"o piloto marca o lugar sem dono com `.{palavra}`, e a folha da "
        f"Navegação não desenha essa classe. É o defeito de 04/09 outra vez: "
        f"duas palavras para o mesmo estado, e o lugar esvaziado em execução "
        f"fica com cara diferente do que nasceu vazio"
    )


def test_a_moldura_vale_para_as_duas_palavras() -> None:
    """A borda é o que ela viu diferente — não a cor, que já fora curada.

    A cura de 04/09 alcançou a cor por `folha_do_plastico`, que pinta por
    `data-controle`. A borda mora na classe, e era só do `.vazia`.
    """
    folha = _folha_da_navegacao()
    palavra = _palavra_que_o_piloto_escreve()

    # a declaração da moldura, seja qual for a forma do seletor
    regras = [
        linha for linha in folha.splitlines()
        if "border:1px solid var(--border-forte)" in linha and "nav-ctl" in linha
    ]
    assert regras, (
        "nenhuma regra da Navegação dá moldura ao lugar vazio — a borda voltou "
        "a depender de `var(--plastico)`, que num lugar sem controle é "
        "indefinido e derruba a declaração INTEIRA, em silêncio"
    )
    alcance = "\n".join(regras)
    for p in ("vazia", palavra):
        assert f".nav-ctl.{p}" in alcance, (
            f"a moldura do lugar vazio não alcança `.nav-ctl.{p}`. Os lugares "
            f"desligados têm de ficar IGUAIS — queixa dela de 17/09/2026, com "
            f"o P2 (esvaziado em execução) contra o P3 e o P4 (vazios de "
            f"nascença)"
        )


@pytest.mark.parametrize(
    "propriedade",
    ["color:var(--linha)", "border:1px solid var(--border-forte)"],
)
def test_nenhuma_regra_do_vazio_ficou_so_com_uma_palavra(propriedade: str) -> None:
    """Varredura: toda regra que desenha o vazio cobre as duas palavras.

    Não basta a moldura. Se o rótulo, o estado ou o desenho ficarem só no
    `.vazia`, o P2 desligado volta a divergir em outro detalhe — e a queixa
    dela é sobre os campos ficarem IGUAIS, não sobre uma propriedade.
    """
    folha = _folha_da_navegacao()
    palavra = _palavra_que_o_piloto_escreve()
    for linha in folha.splitlines():
        if propriedade not in linha or "nav-ctl" not in linha:
            continue
        assert f".nav-ctl.{palavra}" in linha or ".nav-ctl.vazia" not in linha, (
            f"esta regra desenha o lugar vazio só para uma das palavras:\n"
            f"  {linha.strip()[:160]}\n"
            f"o piloto escreve `.{palavra}`; a folha precisa cobrir as duas"
        )


# ---------------------------------------------------------------------------
# 2 — a régua sabe reprovar
# ---------------------------------------------------------------------------
def test_a_regua_sabe_reprovar(tmp_path: pathlib.Path) -> None:
    """A MORDIDA, sem tocar no produto.

    Monta uma folha com o defeito de 04/09 — moldura só no `.vazia`, piloto
    escrevendo `off` — e exige que a asserção central reprove. Se esta régua
    passar com a folha defeituosa, ela não mede nada.
    """
    folha_doente = (
        "  .nav-ctl.vazia{border:1px solid var(--border-forte);"
        "background:transparent}\n"
        "  .nav-ctl.vazia .nav-rot{color:var(--linha)}\n"
    )
    palavra = "off"

    regras = [
        linha for linha in folha_doente.splitlines()
        if "border:1px solid var(--border-forte)" in linha and "nav-ctl" in linha
    ]
    assert regras, "a folha de mentira precisa ter a moldura, senão mede outra coisa"
    alcance = "\n".join(regras)

    assert ".nav-ctl.vazia" in alcance, "controle: o `.vazia` está lá"
    assert f".nav-ctl.{palavra}" not in alcance, (
        "a folha DOENTE não pode conhecer a palavra do piloto — se conhecesse, "
        "esta mordida não estaria mordendo o defeito de 04/09"
    )

    # E a folha de verdade tem de passar no mesmo teste que a doente reprova.
    de_verdade = "\n".join(
        linha for linha in _folha_da_navegacao().splitlines()
        if "border:1px solid var(--border-forte)" in linha and "nav-ctl" in linha
    )
    assert f".nav-ctl.{_palavra_que_o_piloto_escreve()}" in de_verdade
