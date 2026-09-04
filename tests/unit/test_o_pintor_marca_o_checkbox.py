#!/usr/bin/env python3
"""O DÉCIMO ALVO — ``marcado``, o único que escreve ``el.checked``.

**Decisão dela, 04/09/2026:** opção **a**, *décimo alvo ``marcado``*.

O QUE FALTAVA, medido: o pintor tinha nove alvos e **nenhum** tocava a
propriedade que decide se um checkbox está marcado. O acordeão do alto-falante
da aba 02 é um ``<input type="checkbox">`` em CSS puro, e o estado da saída não
tinha por onde chegar nele. O alvo ``valor`` não serve e a razão é do DOM: num
checkbox ``el.value`` é a string ``"on"`` — o atributo que vai no formulário —,
e escrever nele não marca nada nem desmarca nada.

POR QUE ISTO RODA NUM WebKit DE VERDADE: o ``escrever()`` é JavaScript, e a
única forma de saber o que ele faz é executá-lo **no motor que ela vai usar**.
Reescrevê-lo em Python para testar seria testar a reescrita — esta casa já pagou
por *medir contra a biblioteca errada*. A janela é ``Gtk.OffscreenWindow``: sob
Xvfb não há gerenciador de janelas e uma ``Gtk.Window`` fica 1x1 para sempre; e
ela tem UMA tela, então janela de teste não nasce na frente dela.

AS CINCO COISAS QUE ESTA RÉGUA COBRA:

1. **``marcado=sim`` ACENDE** um checkbox que nasceu apagado;
2. **``marcado=""`` e ``marcado="—"`` APAGAM** — o travessão é o que o molde
   escreve num lugar sem dono (``pacotes.TRAVESSAO``), e um acordeão que abrisse
   sozinho numa coluna vazia seria a tela afirmando o que não é;
3. **é IDEMPOTENTE**: o segundo tique com o mesmo valor devolve ``0``. Um alvo
   que devolve ``1`` sempre infla a contagem de pinturas de toda aba que o use —
   e ela é O instrumento com que esta casa prova que um endereço existe;
4. **a leitura de volta fala a MESMA língua da escrita** — ``sim`` / ``""``, e
   não ``true`` / ``false``. Sem isso a régua do mockup compararia a palavra do
   arquivo com um booleano do navegador e acusaria toda pintura certa;
5. **vale para o ``radio`` também**, que é o mesmo nó do HTML com outro tipo.

A MORDIDA: apague o ramo ``if(alvo === 'marcado')`` do ``escrever()`` no
BOOTSTRAP e ``test_o_checkbox_acende`` reprova dizendo que o checkbox nasceu e
ficou fechado; troque ``el.checked ? 'sim' : ''`` por ``el.checked`` no
``LER_CAMPOS`` e ``test_a_leitura_fala_a_lingua_da_escrita`` reprova.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

PILOTO = RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"

#: A PÁGINA DE ENSAIO, e ela é a forma REAL do acordeão da aba 02: um
#: ``<input type="checkbox">`` escondido, com o corpo abrindo por ``:checked``.
#: O ``radio`` está aqui porque o alvo vale para ele sem uma linha a mais, e uma
#: régua que só provasse o checkbox deixaria essa metade sem medição.
PAGINA = """<html><body>
<div data-controle="p1">
  <input type="checkbox" id="acordeao" data-campo="saida-aberta"
         data-hef-alvo="marcado">
  <label for="acordeao">Alto-falante</label>
  <div class="corpo">o miolo do acorde&atilde;o</div>
  <input type="radio" name="g" data-campo="rota-fone" data-hef-alvo="marcado">
  <input type="checkbox" data-campo="ja-aceso" data-hef-alvo="marcado" checked>
</div>
</body></html>"""


def _constante(nome: str) -> str:
    """O BOOTSTRAP e o LER_CAMPOS lidos do FONTE do piloto, e não importados.

    Importar ``hefesto_vivo`` arrastaria a janela GTK inteira para dentro do
    teste. É como ``test_o_pintor_acende_a_classe_e_apaga_as_irmas`` já lê o
    piloto, e pela mesma razão.
    """
    fonte = PILOTO.read_text(encoding="utf-8")
    achou = re.search(rf'^{nome} = r"""(.*?)"""$', fonte, re.S | re.M)
    assert achou, f"o piloto perdeu o {nome} — não há o que testar"
    return achou.group(1)


#: O ROTEIRO INTEIRO NUMA IDA SÓ ao motor: um round-trip por asserção custaria
#: seis cargas de página para medir o que uma mede.
ROTEIRO = """
(function(){
  const fora = {};
  const cx = document.getElementById('acordeao');
  fora.virgem = JSON.parse(LEITOR_AQUI);
  fora.checked_virgem = cx.checked;

  fora.n_acende = window.__hef.pintar({colunas: {p1: {
      'saida-aberta': 'sim', 'rota-fone': 'sim', 'ja-aceso': 'sim'}}});
  fora.aceso = JSON.parse(LEITOR_AQUI);
  fora.checked_aceso = cx.checked;

  // O SEGUNDO TIQUE COM O MESMO VALOR: o pintor tem de devolver zero.
  fora.n_denovo = window.__hef.pintar({colunas: {p1: {
      'saida-aberta': 'sim', 'rota-fone': 'sim', 'ja-aceso': 'sim'}}});

  // O VAZIO APAGA — e o travessão do lugar sem dono também.
  fora.n_apaga = window.__hef.pintar({colunas: {p1: {
      'saida-aberta': '', 'rota-fone': '\\u2014', 'ja-aceso': ''}}});
  fora.apagado = JSON.parse(LEITOR_AQUI);
  fora.checked_apagado = cx.checked;

  // E QUALQUER OUTRA PALAVRA TAMBÉM APAGA: a língua deste alvo é `sim`, e nada
  // mais. `true` chegando de um pacote não pode acender por acidente.
  fora.n_true = window.__hef.pintar({colunas: {p1: {'saida-aberta': 'true'}}});
  fora.checked_true = cx.checked;
  return JSON.stringify(fora);
})()
"""


@pytest.fixture(scope="module")
def medido() -> dict:
    """Abre um WebKit offscreen, instala o BOOTSTRAP e roda o roteiro."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    leitor = _constante("LER_CAMPOS").strip()
    roteiro = ROTEIRO.replace("LEITOR_AQUI", f"({leitor})")
    saiu: list[str] = []
    janela = Gtk.OffscreenWindow()
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def guardou(v, res):
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:  # a exceção É a resposta desta ponte
            saiu.append(f"ERRO {e}")
        Gtk.main_quit()

    def instalou(v, res):
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:
            saiu.append(f"ERRO no bootstrap: {e}")
            Gtk.main_quit()
            return
        v.evaluate_javascript(roteiro, -1, None, None, None, guardou)

    def carregou(v, evento):
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(_constante("BOOTSTRAP"), -1, None, None,
                                  None, instalou)

    view.connect("load-changed", carregou)
    view.load_html(PAGINA, "file:///")
    guarda = GLib.timeout_add(20000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        # O RELÓGIO DE SEGURANÇA É DESARMADO, e isso não é zelo: um
        # `timeout_add` pendente depois da fixture dispara DENTRO do laço do
        # PRÓXIMO teste de GUI do mesmo processo. Já matou onze medições de um
        # vizinho em 02/09.
        GLib.source_remove(guarda)
        janela.destroy()
    assert saiu, "o WebKit não respondeu em 20 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    return json.loads(saiu[0])


def _campos(linhas: list) -> dict[str, str]:
    """``{endereço: valor}`` da leitura de tela do próprio piloto."""
    return {str(x[0]): str(x[3]) for x in linhas}


# --------------------------------------------------------------------------
# 1. o alvo acende — e é o que não existia
# --------------------------------------------------------------------------
def test_o_checkbox_acende(medido: dict) -> None:
    assert medido["checked_virgem"] is False, (
        "a página de ensaio nasceu com o acordeão aberto — não há o que medir")
    assert medido["checked_aceso"] is True, (
        "`marcado=sim` não marcou o checkbox. É o defeito inteiro: dos nove "
        "alvos que o pintor tinha, nenhum escrevia `el.checked`, e o acordeão "
        "do alto-falante da aba 02 não tinha como saber o estado da saída.")
    assert medido["n_acende"] >= 2, (
        f"o pintor contou {medido['n_acende']} pinturas ao acender dois "
        f"checkbox e um radio. O contador é O instrumento com que esta casa "
        f"prova que um endereço existe.")


def test_o_radio_tambem(medido: dict) -> None:
    """O mesmo alvo, o mesmo nó do HTML, outro `type`. Zero linha a mais."""
    assert _campos(medido["aceso"])["rota-fone"] == "sim", (
        "o `radio` não acendeu. O alvo vale para todo checkbox E radio das dez "
        "abas — se ele parasse no checkbox, metade do que ele destrava ficaria "
        "sem canal, e ninguém veria.")


# --------------------------------------------------------------------------
# 2. o vazio e o travessão apagam
# --------------------------------------------------------------------------
def test_o_vazio_apaga(medido: dict) -> None:
    assert medido["checked_apagado"] is False, (
        "`marcado=''` não desmarcou. Um acordeão que fica aberto depois de o "
        "controle sair da mesa é a tela afirmando o que não é.")


def test_o_travessao_apaga(medido: dict) -> None:
    """O `—` é o que o molde escreve num lugar SEM DONO (`pacotes.TRAVESSAO`).

    Ele chega por um caminho diferente do vazio — o vazio é "não sei", o
    travessão é "não há ninguém aqui" — e os dois têm de apagar. É a mesma regra
    dos alvos `plastico` e `atributo`.
    """
    assert _campos(medido["apagado"])["rota-fone"] == "", (
        "o travessão do lugar sem dono deixou o radio aceso")


def test_so_a_palavra_sim_acende(medido: dict) -> None:
    """A língua deste alvo é `sim`, e é a MESMA do alvo `classe` booleano.

    Uma segunda palavra para o mesmo "ligado" seria a terceira maneira de dizer
    a mesma coisa nesta casa — e `true` chegando de um pacote acenderia por
    acidente um acordeão que ninguém mandou abrir.
    """
    assert medido["checked_true"] is False, (
        "a palavra `true` acendeu o checkbox. O alvo entende `sim`, e só.")


# --------------------------------------------------------------------------
# 3. idempotente — o segundo tique igual devolve zero
# --------------------------------------------------------------------------
def test_o_segundo_tique_igual_conta_zero(medido: dict) -> None:
    assert medido["n_denovo"] == 0, (
        f"o mesmo valor pintado de novo contou {medido['n_denovo']}. Um alvo "
        f"que devolve 1 sempre infla a contagem de pinturas de toda aba que o "
        f"use — e é essa contagem que prova que um endereço existe.")


# --------------------------------------------------------------------------
# 4. a leitura fala a língua da escrita
# --------------------------------------------------------------------------
def test_a_leitura_fala_a_lingua_da_escrita(medido: dict) -> None:
    """`sim` / `""`, nunca `true` / `false`.

    O ``LER_CAMPOS`` é o instrumento do ``--prova-de-mockup``, e ele compara o
    que a TELA mostra com o que o ARQUIVO crava. Devolver um booleano faria a
    régua comparar a palavra do arquivo com `true` e acusar **toda** pintura
    certa — é a mesma cura de forma que o alvo `cor` já custou uma medição.
    """
    aceso = _campos(medido["aceso"])
    apagado = _campos(medido["apagado"])
    assert aceso["saida-aberta"] == "sim", aceso
    assert apagado["saida-aberta"] == "", apagado
    assert aceso["saida-aberta"] not in ("true", "True"), (
        "a leitura devolveu um booleano em vez da palavra do contrato")


def test_o_que_ja_nascia_aceso_continua_aceso(medido: dict) -> None:
    """Um checkbox com `checked` no HTML lido ANTES de qualquer pintura.

    É a linha de base do virgem: sem ela, um alvo que marcasse tudo passaria em
    todos os outros testes desta página.
    """
    assert _campos(medido["virgem"])["ja-aceso"] == "sim", (
        "o leitor não viu o `checked` que o arquivo cravou — e é ele que separa "
        "o que o produto pintou do que o desenho já trazia")
    assert _campos(medido["virgem"])["saida-aberta"] == "", (
        "o leitor viu marcado um checkbox que o arquivo deixou fechado")
