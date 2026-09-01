#!/usr/bin/env python3
"""A RÉGUA DA FORMA: o "Guardar" recolhe as 21 linhas e as manda ao Python.

POR QUE ELA EXISTE, e é a metade da cura que nenhuma outra régua vê: o gesto
`guardar-definicoes` grava `o["forma"]`, e todas as outras réguas o alimentam com
um dicionário FABRICADO. Se o lado JS parasse de recolher, elas continuariam
verdes e o botão passaria a recusar dizendo "não consegui ler as linhas da tela"
— com o produto inteiro certo do outro lado.

O QUE ELA DIRIGE: a página PUBLICADA, num Chrome de verdade, com o `BOOTSTRAP`
do piloto injetado e a ponte trocada por um dublê que guarda o que chegaria ao
Python. É o mesmo motor que o `check_pecas_do_dualsense.py` usa, e o mesmo
caminho de eventos do clique do rato — `el.click()` passa pelo ouvinte delegado.

O QUE ELA **NÃO** ALCANÇA: o WebKitGTK, que é o motor do produto. O Chrome aqui
mede o CONTRATO do bootstrap (quem recolhe o quê), e a prova no motor de verdade
é o `--prova-clique` do piloto, que roda com o daemon vivo.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

CHROME = pathlib.Path("/usr/bin/google-chrome")
pytestmark = pytest.mark.skipif(
    not CHROME.exists(), reason="sem o Chrome do sistema — a régua não tem motor")


def _bootstrap() -> str:
    """O `BOOTSTRAP` do piloto, lido do fonte SEM importar `gi`.

    IMPORTAR O PILOTO TRARIA O GTK JUNTO, e uma régua que exige GTK deixa de
    rodar no CI. O que interessa aqui é o texto do script — e lê-lo do fonte é o
    que garante que a régua mede o bootstrap DE VERDADE, e não uma cópia.
    """
    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py").read_text(
        encoding="utf-8")
    m = re.search(r'BOOTSTRAP = r"""(.*?)"""', fonte, re.S)
    assert m, "não achei o BOOTSTRAP no piloto — a régua ficaria verde sobre nada"
    return m.group(1)


@pytest.fixture(scope="module")
def recolhido() -> dict:
    """O que o clique no "Guardar" mandaria ao Python."""
    from playwright.sync_api import sync_playwright

    from hefesto_dualsense4unix.interface import onde

    pagina = onde.pagina("06-navegacao.html", publicado=True)
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(
            executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = navegador.new_page(viewport={"width": 1180, "height": 900})
            pg.goto(pagina.as_uri())
            # A PONTE DE MENTIRA É O `webkit.messageHandlers`, e não uma
            # função nossa: o `manda()` do bootstrap posta ALI (`hefesto_vivo.py`,
            # `function manda`), e é esse o único ponto por onde o clique sai da
            # página. Trocar outra coisa faria a régua medir um caminho que o
            # produto não usa — e o Chrome, que não tem `window.webkit`,
            # derrubaria o clique com `Cannot read properties of undefined`.
            pg.evaluate("""
                window.__recebido = [];
                window.webkit = {messageHandlers: {hefesto: {
                    postMessage: function(s){ window.__recebido.push(s); }}}};
            """)
            pg.evaluate(_bootstrap())
            pg.eval_on_selector('[data-gesto="guardar-definicoes"]', "el => el.click()")
            crus = pg.evaluate("window.__recebido")
            assert crus, "o clique não saiu da página — ninguém postou nada"
            # O BOOTSTRAP MANDA TEXTO (`JSON.stringify(o)`), como o WebView
            # exige. Desfazer aqui é o que o piloto faz do lado Python.
            return json.loads(crus[-1])
        finally:
            navegador.close()


def test_o_guardar_manda_a_forma(recolhido: dict) -> None:
    """Sem a `forma`, o gesto não tem o que gravar e só sabe recusar."""
    assert recolhido["gesto"] == "guardar-definicoes", recolhido
    assert isinstance(recolhido.get("forma"), dict), (
        f"o clique chegou sem a `forma`: {recolhido!r}. O `data-hef-forma` saiu "
        f"do botão, ou o bootstrap parou de recolher.")


def test_a_forma_traz_as_vinte_e_uma_linhas_com_o_endereco_do_produto(
    recolhido: dict,
) -> None:
    """Cada chave é um botão que o produto conhece, e as 21 estão lá.

    O ENDEREÇO É O DO PRODUTO, e não um nome da tela: `core/acoes_de_botao.BOTOES`.
    Uma chave a mais ou a menos aqui é a tela e o produto falando línguas
    diferentes — e o gesto descartaria a linha em silêncio.
    """
    from hefesto_dualsense4unix.core.acoes_de_botao import BOTOES

    forma = recolhido["forma"]
    assert set(forma) == set(BOTOES), (
        f"a tela mandou {sorted(set(forma) - set(BOTOES))} a mais e "
        f"{sorted(set(BOTOES) - set(forma))} a menos")


def test_o_valor_de_cada_linha_e_um_rotulo_que_o_produto_traduz(
    recolhido: dict,
) -> None:
    """O caminho de volta fecha: o texto da opção vira token sem sobra.

    É este caso que pega a divergência que motivou o módulo — se alguém
    reescrever um rótulo no gerador sem mexer no `ACOES`, a tradução devolve
    `None` e o "Guardar" passaria a levantar em cima da linha reescrita.
    """
    from hefesto_dualsense4unix.core.acoes_de_botao import token_do_rotulo

    sem_traducao = {b: v for b, v in recolhido["forma"].items()
                    if token_do_rotulo(str(v)) is None}
    assert not sem_traducao, (
        f"estas linhas trazem um texto que `acoes_de_botao` não traduz: "
        f"{sem_traducao}\nA lista da tela e a do produto saem do mesmo lugar — "
        f"se divergiram, o desenho andou sem o gerador.")


def test_o_que_a_tela_mostra_e_o_que_o_produto_faz(recolhido: dict) -> None:
    """A página recém-aberta tem de mostrar o PADRÃO — não outro qualquer.

    ERA AQUI QUE ESTAVA O DEFEITO, e ele durou desde que a tabela foi escrita:
    a tela dizia que as três regiões do touchpad fazem *Botão esquerdo · Botão
    direito · F11*, e o produto faz *Backspace · Enter · Delete*. Ninguém
    comparava — e este caso é a comparação.
    """
    from hefesto_dualsense4unix.core.acoes_de_botao import padrao, token_do_rotulo

    de_fabrica = padrao()
    divergem = {
        botao: (token_do_rotulo(str(texto)), de_fabrica[botao])
        for botao, texto in recolhido["forma"].items()
        if token_do_rotulo(str(texto)) != de_fabrica[botao]
    }
    assert not divergem, (
        "a tela abre mostrando uma coisa e o produto faz outra "
        "(linha: mostrado -> faz):\n  "
        + "\n  ".join(f"{b}: {m} -> {f}" for b, (m, f) in sorted(divergem.items())))
