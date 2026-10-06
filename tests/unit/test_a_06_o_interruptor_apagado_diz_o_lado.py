#!/usr/bin/env python3
"""A RÉGUA DO INTERRUPTOR APAGADO: apagado diz o LADO, e não aceita o clique."""
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

TOG = '.tog[data-gesto="modo"]'
LINHA = '.at-linha:has(.tog[data-gesto="modo"])'
PORTAO = '[data-campo="modo-portao"]'


def _bootstrap() -> str:
    """O `BOOTSTRAP` do piloto, lido do fonte SEM importar `gi`."""
    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py").read_text(
        encoding="utf-8")
    m = re.search(r'BOOTSTRAP = r"""(.*?)"""', fonte, re.S)
    assert m, "não achei o BOOTSTRAP no piloto — a régua ficaria verde sobre nada"
    return m.group(1)


@pytest.fixture(scope="module")
def pagina():
    """A página PUBLICADA num Chrome de verdade, com a ponte do piloto dublada."""
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
    """Põe a página na cena que o daemon produziria — pelas mesmas duas escritas."""
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
            // `querySelectorAll` desde 07/09/2026: a razão do portão deixou de
            // morar numa linha só. Ela foi para o `?` do "Status do Modo" e o
            // da "Função do teclado" (ordem de produto: *"essas 3 frases … quebram o
            // layout"*), e o piloto escreve em TODOS os elementos de mesmo
            // `data-campo`. Pintar só o primeiro mediria meia cena.
            for (const el of document.querySelectorAll(sel)) el.innerHTML = razao;
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
    """Clica no CENTRO do elemento com o rato, e devolve o que saiu da página."""
    caixa = pg.evaluate(
        """(s) => { const r = document.querySelector(s).getBoundingClientRect();
                    return {x: r.left + r.width/2, y: r.top + r.height/2}; }""",
        seletor)
    pg.mouse.click(caixa["x"], caixa["y"])
    return pg.evaluate("window.__recebido")


def test_o_apagado_e_ligado_nao_fica_igual_ao_apagado_e_desligado(pagina) -> None:
    """As duas cenas do portão têm de DIFERIR — o defeito era elas serem iguais."""
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
    """Aceso é aceso, com portão ou sem — o lado sai do MESMO lugar nos dois."""
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
    """E a borda continua dizendo "não dá para mexer" — a cura não desfez a D-03."""
    _pintar(pagina, portao=False, ligado=True)
    aberta = _cor(pagina, TOG, "border-top-color")
    _pintar(pagina, portao=True, ligado=True)
    fechada = _cor(pagina, TOG, "border-top-color")

    assert aberta != fechada, (
        f"a borda do interruptor não mudou sob o portão ({fechada}) — ele "
        f"deixou de parecer apagado, e ela volta a gastar o clique para "
        f"descobrir que não pode mexer")


def test_o_clique_no_interruptor_apagado_nao_chega_ao_python(pagina) -> None:
    """*"o switch fica apagado (**não clicável**)"* — e não clicável é do rato."""
    _pintar(pagina, portao=True, ligado=True)
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
    """O `cursor:not-allowed` mudou de elemento porque TINHA de mudar."""
    _pintar(pagina, portao=False, ligado=True)
    assert _cor(pagina, LINHA, "cursor") != "not-allowed", (
        "a linha recusa o ponteiro com o portão ABERTO — a tela diria que não "
        "dá para mexer justamente quando dá")

    _pintar(pagina, portao=True, ligado=True)
    assert _cor(pagina, LINHA, "cursor") == "not-allowed", (
        "a linha do interruptor apagado não mostra a recusa: o ponteiro cai "
        "nela (o rótulo saiu do alcance) e o cursor voltou a ser o do pai")


def test_com_o_portao_aberto_o_clique_continua_chegando(pagina) -> None:
    """O espelho, e sem ele os dois casos acima passariam com o botão MORTO."""
    _pintar(pagina, portao=False, ligado=False)
    saiu = _clicar_com_o_rato(pagina, TOG)
    assert any('"modo"' in s for s in saiu), (
        f"o interruptor parou de responder com o portão ABERTO: {saiu!r}. A "
        f"cura do apagado matou o botão inteiro.")
