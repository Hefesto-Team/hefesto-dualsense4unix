#!/usr/bin/env python3
"""A RÉGUA DO INTERRUPTOR APAGADO: apagado diz o LADO, e não aceita o clique.

ESCLARECIMENTO DELA, 06/09/2026 (06-Q1), e ele manda sobre a construção de
04/09:

    *"o switch fica apagado (não clicável) MAS mostra o estado real: pode ficar
    apagado no estado off, e pode ficar apagado no estado on"*

São duas frases e uma regra só: **apagado diz "não dá para mexer"; nunca diz
"está desligado"**. O que fala do LADO — a palavra, o pino, o fundo — não é do
portão, e o portão não encosta nele.

O QUE ESTAVA ERRADO, e as duas metades estavam medidas:

  1. a regra do portão pintava também o `.pino`, e ela vale **(0,3,0) contra os
     (0,6,0) dela** — `.quadro-corpo` + `:has()` (que conta pelo argumento mais
     específico) + `.tog` + `[data-gesto]`. **A do portão vencia, e o pino ficava
     cinza com o mouse LIGADO.** O que sobrava dizendo o lado era o fundo
     esverdeado, que sobrevivia por acidente: a regra do portão não declara
     `background`;
  2. o interruptor **continuava respondendo ao clique** — o comentário do
     gerador dizia, por escrito, que *"nada aqui é `disabled` nem
     `pointer-events:none`"* —, e ela pediu **não clicável**.

POR QUE ESTA RÉGUA LÊ O NAVEGADOR, e não o texto da folha: uma régua que
procurasse a string `--green` no CSS **daria verde com a regra do portão
vencendo por especificidade**, que é exatamente o defeito que esta sprint existe
para matar. Aqui quem resolve a cascata é o motor, e o que se lê é
`getComputedStyle` — o pixel, não a intenção.

O CLIQUE TAMBÉM É DO MOTOR. `el.click()` **não serve**: ele dispara o evento
mesmo num elemento com `pointer-events:none`, e daria verde sobre a metade que
não foi feita. Esta régua clica com o RATO (`page.mouse.click`), no centro do
interruptor, e a pergunta é a do hit-test: quem recebe o ponteiro ali?

O QUE ELA **NÃO** ALCANÇA: o WebKitGTK, que é o motor do produto. O Chrome aqui
mede a CASCATA e o HIT-TEST — os dois padronizados —, e a prova no motor de
verdade é a foto do piloto, que roda com o daemon vivo.
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

CHROME = pathlib.Path("/usr/bin/google-chrome")
pytestmark = pytest.mark.skipif(
    not CHROME.exists(), reason="sem o Chrome do sistema — a régua não tem motor")

#: O interruptor, pelo endereço que o gerador lhe deu.
TOG = '.tog[data-gesto="modo"]'
#: A linha que o contém — é ela quem passou a mostrar a recusa do ponteiro.
LINHA = '.at-linha:has(.tog[data-gesto="modo"])'
#: A linha da tira de estados de onde o `:has()` do portão parte.
PORTAO = '[data-campo="modo-portao"]'


def _bootstrap() -> str:
    """O `BOOTSTRAP` do piloto, lido do fonte SEM importar `gi`.

    Mesma razão da régua vizinha (`test_a_tela_entrega_as_vinte_e_uma_linhas`):
    importar o piloto traria o GTK junto, e uma régua que exige GTK deixa de
    rodar no CI. Ler do fonte é o que garante que se mede o ouvinte DE VERDADE.
    """
    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py").read_text(
        encoding="utf-8")
    m = re.search(r'BOOTSTRAP = r"""(.*?)"""', fonte, re.S)
    assert m, "não achei o BOOTSTRAP no piloto — a régua ficaria verde sobre nada"
    return m.group(1)


@pytest.fixture(scope="module")
def pagina():
    """A página PUBLICADA num Chrome de verdade, com a ponte do piloto dublada.

    PUBLICADA de propósito: é a que o piloto carrega
    (`hefesto_vivo`, `onde.pagina(..., publicado=True)`), e é a que está na
    frente dela. Medir a bancada aqui daria verde sobre uma folha que o produto
    ainda não renderiza.
    """
    from playwright.sync_api import sync_playwright

    from hefesto_dualsense4unix.interface import onde

    alvo = onde.pagina("06-navegacao.html", publicado=True)
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(
            executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = navegador.new_page(viewport={"width": 1180, "height": 900})
            pg.goto(alvo.as_uri())
            pg.evaluate("""
                window.__recebido = [];
                window.webkit = {messageHandlers: {hefesto: {
                    postMessage: function(s){ window.__recebido.push(s); }}}};
            """)
            pg.evaluate(_bootstrap())
            yield pg
        finally:
            navegador.close()


def _pintar(pg: Any, *, portao: bool, ligado: bool) -> None:
    """Põe a página na cena que o daemon produziria — pelas mesmas duas escritas.

    NADA É DIGITADO AQUI. A razão sai de `a06_navegacao.RAZAO_DO_PORTAO` (a
    mesma frase que o gesto levanta ao recusar), o "nada a dizer" sai de
    `NADA_A_DIZER`, e a palavra do lado sai de `LIGADO`/`DESLIGADO`. Uma cena
    montada com texto inventado mediria uma tela que o produto não pinta.

    AS DUAS ESCRITAS SÃO AS DO PILOTO: o alvo `html` na linha do portão, e a
    classe `ligado` no rótulo quando a palavra casa com o `data-hef-quando`.
    """
    from hefesto_dualsense4unix.interface.pacotes.a06_navegacao import (
        DESLIGADO,
        LIGADO,
        NADA_A_DIZER,
        RAZAO_DO_PORTAO,
    )

    razao = (f'<span class="laranja">{RAZAO_DO_PORTAO}</span>' if portao
             else NADA_A_DIZER)
    pg.evaluate(
        """([sel, tog, razao, palavra, acender]) => {
            document.querySelector(sel).innerHTML = razao;
            const el = document.querySelector(tog);
            el.classList.toggle('ligado', acender);
            el.querySelector('.txt').textContent = palavra;
            el.scrollIntoView({block: 'center'});
        }""",
        [PORTAO, TOG, razao, LIGADO if ligado else DESLIGADO, ligado])
    pg.evaluate("window.__recebido = []")


def _cor(pg: Any, seletor: str, propriedade: str) -> str:
    return pg.evaluate(
        "([s, p]) => getComputedStyle(document.querySelector(s))"
        ".getPropertyValue(p)",
        [seletor, propriedade])


def _clicar_com_o_rato(pg: Any, seletor: str) -> list[str]:
    """Clica no CENTRO do elemento com o rato, e devolve o que saiu da página.

    `page.mouse.click` e não `el.click()`: o segundo dispara o evento mesmo num
    elemento fora do alcance do ponteiro, e daria verde sobre a metade da cura
    que não foi feita. O que se quer saber é do HIT-TEST.
    """
    caixa = pg.evaluate(
        """(s) => { const r = document.querySelector(s).getBoundingClientRect();
                    return {x: r.left + r.width/2, y: r.top + r.height/2}; }""",
        seletor)
    pg.mouse.click(caixa["x"], caixa["y"])
    return pg.evaluate("window.__recebido")


# --------------------------------------------------------------------------
# 1. O LADO — e as duas cenas do portão não podem ser iguais
# --------------------------------------------------------------------------
def test_o_apagado_e_ligado_nao_fica_igual_ao_apagado_e_desligado(pagina) -> None:
    """As duas cenas do portão têm de DIFERIR — o defeito era elas serem iguais.

    Uma foto só não prova nada aqui, e uma asserção só também não: o que se
    mede é a DIFERENÇA entre o interruptor apagado com o mouse ligado e o mesmo
    interruptor com o mouse desligado.

    A MORDIDA: devolva ao gerador a regra
    `…:has(…) .tog[data-gesto="modo"] .pino{background:var(--border-sutil)}`,
    regere a página e publique — este caso reprova dizendo que os dois lados
    ficaram com a mesma cara.
    """
    _pintar(pagina, portao=True, ligado=True)
    pino_ligado = _cor(pagina, f"{TOG} .pino", "background-color")
    fundo_ligado = _cor(pagina, TOG, "background-color")

    _pintar(pagina, portao=True, ligado=False)
    pino_desligado = _cor(pagina, f"{TOG} .pino", "background-color")

    assert pino_ligado != pino_desligado, (
        f"o interruptor apagado ficou IGUAL nos dois lados — o pino é "
        f"{pino_ligado} com o mouse ligado e {pino_desligado} com ele "
        f"desligado. Apagado passou a dizer 'está desligado', que é o que o "
        f"esclarecimento dela proíbe.")
    assert fundo_ligado != _cor(pagina, TOG, "background-color"), (
        "o fundo do interruptor não muda de lado sob o portão — sobrou UMA "
        "coisa dizendo o lado, e ela é a que ninguém escreveu de propósito")


def test_o_portao_nao_encosta_no_lado(pagina) -> None:
    """Aceso é aceso, com portão ou sem — o lado sai do MESMO lugar nos dois.

    É a metade forte do esclarecimento dela: não basta as duas cenas do portão
    diferirem entre si; o portão não pode mexer no que fala do lado. Se algum
    dia ele apagar o pino "só um pouco", este caso pega e o anterior não.

    A MORDIDA: a mesma do caso acima.
    """
    _pintar(pagina, portao=False, ligado=True)
    aberto = (_cor(pagina, f"{TOG} .pino", "background-color"),
              _cor(pagina, TOG, "background-color"))
    _pintar(pagina, portao=True, ligado=True)
    fechado = (_cor(pagina, f"{TOG} .pino", "background-color"),
               _cor(pagina, TOG, "background-color"))

    assert aberto == fechado, (
        f"o portão mexeu no que diz o LADO: sem portão o pino e o fundo são "
        f"{aberto}, com portão são {fechado}. O portão apaga o CONTROLE, e o "
        f"lado continua sendo do daemon.")


def test_o_portao_continua_apagando_o_controle(pagina) -> None:
    """E a borda continua dizendo "não dá para mexer" — a cura não desfez a D-03.

    Sem esta, tirar a regra do portão inteira passaria nos dois casos acima: as
    cenas diferiram, o lado ficou intacto — e o interruptor não estaria mais
    apagado. Régua que só sabe passar não é régua.

    A MORDIDA: apague as três regras do portão no gerador — este caso reprova.
    """
    _pintar(pagina, portao=False, ligado=True)
    aberta = _cor(pagina, TOG, "border-top-color")
    _pintar(pagina, portao=True, ligado=True)
    fechada = _cor(pagina, TOG, "border-top-color")

    assert aberta != fechada, (
        f"a borda do interruptor não mudou sob o portão ({fechada}) — ele "
        f"deixou de parecer apagado, e ela volta a gastar o clique para "
        f"descobrir que não pode mexer")


# --------------------------------------------------------------------------
# 2. O CLIQUE — e o cursor que continua recusando
# --------------------------------------------------------------------------
def test_o_clique_no_interruptor_apagado_nao_chega_ao_python(pagina) -> None:
    """*"o switch fica apagado (**não clicável**)"* — e não clicável é do rato.

    A MORDIDA: tire o `pointer-events:none` da regra do portão, regere e
    publique — este caso reprova mostrando o gesto `modo` sendo postado.
    """
    _pintar(pagina, portao=True, ligado=True)
    # O CLIQUE VEM PRIMEIRO, e a ordem é medida: com o `pointer-events`
    # arrancado, é ESTA asserção que mostra o gesto `modo` sendo postado — o
    # desfecho que a §4-P2 da sprint manda ver. Deixá-la depois do hit-test
    # faria a régua morrer antes de exercitar o caminho que interessa.
    saiu = _clicar_com_o_rato(pagina, TOG)
    assert not any('"modo"' in s for s in saiu), (
        f"o clique no interruptor apagado chegou ao Python: {saiu!r}. Ela "
        f"gasta o clique para descobrir que não pode mexer, que é o que a "
        f"decisão de 04/09 já queria evitar e a de hoje fecha.")

    quem = pagina.evaluate(
        """(s) => { const r = document.querySelector(s).getBoundingClientRect();
                    const el = document.elementFromPoint(r.left + r.width/2,
                                                         r.top + r.height/2);
                    return el ? el.className : null; }""",
        TOG)
    assert "tog" not in str(quem), (
        f"o ponteiro ainda cai no interruptor (chegou em {quem!r}) — o "
        f"`pointer-events` do portão não está valendo")


def test_a_linha_do_interruptor_apagado_recusa_o_ponteiro(pagina) -> None:
    """O `cursor:not-allowed` mudou de elemento porque TINHA de mudar.

    Um elemento que não é alvo de ponteiro **não decide o cursor** — quem
    decide passa a ser o pai. Aplicar só o `pointer-events` trocaria um defeito
    por outro: o interruptor recusaria em silêncio e ainda pareceria clicável.

    A MORDIDA: tire o `cursor:not-allowed` da regra da `.at-linha` — este caso
    reprova acusando o interruptor apagado com cara de clicável.
    """
    _pintar(pagina, portao=False, ligado=True)
    assert _cor(pagina, LINHA, "cursor") != "not-allowed", (
        "a linha recusa o ponteiro com o portão ABERTO — a tela diria que não "
        "dá para mexer justamente quando dá")

    _pintar(pagina, portao=True, ligado=True)
    assert _cor(pagina, LINHA, "cursor") == "not-allowed", (
        "a linha do interruptor apagado não mostra a recusa: o ponteiro cai "
        "nela (o rótulo saiu do alcance) e o cursor voltou a ser o do pai")


def test_com_o_portao_aberto_o_clique_continua_chegando(pagina) -> None:
    """O espelho, e sem ele os dois casos acima passariam com o botão MORTO.

    O que a decisão dela pede é um interruptor que recusa **enquanto o modo não
    é "Controlar o PC"** — não um interruptor que parou de funcionar.

    A MORDIDA: ponha `pointer-events:none` na regra base do `.tog` — este caso
    reprova, e os dois de cima continuam verdes. É o par que os torna honestos.
    """
    _pintar(pagina, portao=False, ligado=False)
    saiu = _clicar_com_o_rato(pagina, TOG)
    assert any('"modo"' in s for s in saiu), (
        f"o interruptor parou de responder com o portão ABERTO: {saiu!r}. A "
        f"cura do apagado matou o botão inteiro.")
