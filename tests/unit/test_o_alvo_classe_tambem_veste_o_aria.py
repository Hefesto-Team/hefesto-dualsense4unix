#!/usr/bin/env python3
"""O ALVO ``classe`` VESTE UM ATRIBUTO JUNTO — a dívida que a FOLHA achou.

**04/09/2026.** A frente da FOLHA (ONDA0-F) construiu o botão cinza da D-03
(*"Cinza antes, com a razão na dica"*) e parou numa dívida **do piloto**:

> *"nenhum alvo do ``hefesto_vivo.py`` escreve atributo E classe no mesmo
> elemento, e o ``aria-disabled`` do botão cinza precisa disso"*

E ela está certa, e o defeito é de FORMA: ``data-hef-alvo`` é **um** por
elemento. Um botão que fica cinza precisa das duas metades **ao mesmo tempo** —
a classe, que é o que a folha pinta, e o ``aria-disabled``, que é o que um
leitor de tela anuncia. Com um alvo só, ou o botão fica cinza sem dizer por quê
a quem não vê, ou diz e não fica cinza.

AS DUAS SAÍDAS QUE NÃO FORAM TOMADAS, e a razão de cada uma:

* **um alvo composto** (``classe:aria-disabled``) quebraria tudo que LÊ o alvo
  por igualdade — o ``LER_CAMPOS``, o ``regua_do_mockup._campo``, os
  ``campo.alvo == "…"``. O comentário do alvo ``atributo`` já paga essa lição;
* **um segundo ``data-campo``** no mesmo botão seria pior: dois endereços para o
  mesmo fato, que podem DIVERGIR na tela. É o oposto do que esta casa persegue.

A CURA É UMA VERDADE SÓ COM DUAS VOZES: a classe é a fonte; o atributo é
derivado dela, na língua do ARIA (``true``/``false`` — e não a ausência, porque
um ``aria-disabled`` ausente e um ``aria-disabled="false"`` **não** são a mesma
coisa para um leitor de tela). O nome vem do MESMO ``data-hef-atributo`` que o
alvo ``atributo`` já usa, e passa pela MESMA guarda.

A MORDIDA: apague o bloco ``if(junto && atributo_escrevivel(junto))`` do ramo
``classe`` e ``test_a_classe_e_o_aria_andam_juntos`` reprova dizendo que o botão
ficou cinza e não avisou ninguém.
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

#: A PÁGINA DE ENSAIO, e ela é a forma do botão cinza da S-03: a classe que a
#: folha pinta e o `aria-disabled` que o leitor de tela anuncia, no MESMO nó,
#: com UM `data-campo`.
#:
#: O terceiro botão pede um atributo PROIBIDO de propósito — a guarda tem de
#: recusá-lo sem derrubar a metade da classe, que é o comportamento honesto para
#: um erro de gerador.
PAGINA = """<html><body>
<div data-controle="p1">
  <button class="btn" data-campo="retomar-cinza" data-hef-alvo="classe"
          data-hef-classe="off" data-hef-atributo="aria-disabled">Retomar</button>
  <button class="btn" data-campo="so-a-classe" data-hef-alvo="classe"
          data-hef-classe="off">Reiniciar</button>
  <button class="btn" data-campo="atributo-proibido" data-hef-alvo="classe"
          data-hef-classe="off" data-hef-atributo="data-campo">Nunca</button>
</div>
</body></html>"""


def _constante(nome: str) -> str:
    """O BOOTSTRAP e o LER_CAMPOS lidos do FONTE do piloto, e não importados."""
    fonte = PILOTO.read_text(encoding="utf-8")
    achou = re.search(rf'^{nome} = r"""(.*?)"""$', fonte, re.S | re.M)
    assert achou, f"o piloto perdeu o {nome} — não há o que testar"
    return achou.group(1)


ROTEIRO = """
(function(){
  const fora = {};
  const b = document.querySelector('[data-campo="retomar-cinza"]');
  const proibido = document.querySelector('[data-campo="atributo-proibido"]');
  fora.aria_virgem = b.getAttribute('aria-disabled');

  fora.n_acende = window.__hef.pintar({colunas: {p1: {
      'retomar-cinza': 'sim', 'so-a-classe': 'sim', 'atributo-proibido': 'sim'}}});
  fora.aceso = {classe: b.className, aria: b.getAttribute('aria-disabled')};
  fora.proibido_aceso = {classe: proibido.className,
                         campo: proibido.getAttribute('data-campo')};
  // O ELEMENTO SEM `data-hef-atributo` é lido AQUI, ACESO — e não no fim do
  // roteiro, quando os três já foram apagados. A primeira versão desta régua
  // lia o estado final e acusava o alvo `classe` de não acender: mediu o
  // instante errado, e o alarme era do instrumento.
  const s0 = document.querySelector('[data-campo="so-a-classe"]');
  fora.so_a_classe = {classe: s0.className, atributos: s0.getAttributeNames().sort()};

  // O SEGUNDO TIQUE IGUAL: nem a classe nem o atributo contam de novo.
  fora.n_denovo = window.__hef.pintar({colunas: {p1: {
      'retomar-cinza': 'sim', 'so-a-classe': 'sim', 'atributo-proibido': 'sim'}}});

  fora.n_apaga = window.__hef.pintar({colunas: {p1: {
      'retomar-cinza': '', 'so-a-classe': '', 'atributo-proibido': ''}}});
  fora.apagado = {classe: b.className, aria: b.getAttribute('aria-disabled')};

  fora.leitura = JSON.parse(LEITOR_AQUI);
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

    roteiro = ROTEIRO.replace("LEITOR_AQUI", f"({_constante('LER_CAMPOS').strip()})")
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
        # Um `timeout_add` pendente depois da fixture dispara DENTRO do laço do
        # PRÓXIMO teste de GUI do mesmo processo. Já matou onze medições.
        GLib.source_remove(guarda)
        janela.destroy()
    assert saiu, "o WebKit não respondeu em 20 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    return json.loads(saiu[0])


# --------------------------------------------------------------------------
# 1. a dívida que a FOLHA achou
# --------------------------------------------------------------------------
def test_a_classe_e_o_aria_andam_juntos(medido: dict) -> None:
    assert medido["aria_virgem"] is None, (
        "a página de ensaio já trazia o `aria-disabled` — não há o que medir")
    aceso = medido["aceso"]
    assert "off" in aceso["classe"], (
        f"a classe não acendeu: {aceso['classe']!r}")
    assert aceso["aria"] == "true", (
        f"o botão ficou cinza e não avisou ninguém: aria-disabled={aceso['aria']!r}. "
        f"É a dívida que a frente da FOLHA relatou — a classe é o que a folha "
        f"pinta, e o `aria-disabled` é o que um leitor de tela anuncia.")


def test_apagar_diz_false_e_nao_some(medido: dict) -> None:
    """`aria-disabled` ausente e `aria-disabled="false"` NÃO são a mesma coisa.

    A especificação do ARIA é explícita, e é por isso que o atributo é escrito
    com a palavra em vez de removido: um botão que volta a funcionar tem de
    ANUNCIAR que voltou, e não apenas parar de anunciar que não funcionava.
    """
    apagado = medido["apagado"]
    assert "off" not in apagado["classe"], apagado
    assert apagado["aria"] == "false", (
        f"o botão voltou a funcionar e o `aria-disabled` virou {apagado['aria']!r}")


def test_o_segundo_tique_igual_conta_zero(medido: dict) -> None:
    """Nem a classe nem o atributo contam de novo — os dois são idempotentes.

    Um alvo que devolve 1 sempre infla a contagem de pinturas de toda aba que o
    use, e ela é O instrumento com que esta casa prova que um endereço existe.
    """
    assert medido["n_denovo"] == 0, (
        f"o mesmo valor pintado de novo contou {medido['n_denovo']}")


# --------------------------------------------------------------------------
# 2. o que ele NÃO faz
# --------------------------------------------------------------------------
def test_sem_data_hef_atributo_nada_muda(medido: dict) -> None:
    """O elemento que não pede atributo nenhum segue exatamente como antes.

    Os 105 endereços de alvo `classe` das dez abas não podem ganhar um atributo
    que ninguém pediu — a cura tem de ser invisível para quem não a usa.
    """
    s = medido["so_a_classe"]
    assert "off" in s["classe"], s
    assert not [a for a in s["atributos"] if a.startswith("aria-")], (
        f"o elemento sem `data-hef-atributo` ganhou um atributo ARIA: {s}")


def test_a_guarda_do_atributo_continua_valendo(medido: dict) -> None:
    """`data-campo` é vocabulário de ENDEREÇO, e o alvo não move a placa da porta.

    A guarda é a MESMA do alvo `atributo` — não há segunda lista a divergir. E o
    recusado não derruba a metade da classe: um erro de gerador deixa o botão
    cinza mesmo assim, que é o comportamento honesto.
    """
    p = medido["proibido_aceso"]
    assert p["campo"] == "atributo-proibido", (
        f"o alvo reescreveu o `data-campo`, que é o endereço por onde ele mesmo "
        f"entrou: {p['campo']!r}")
    assert "off" in p["classe"], (
        f"o nome recusado derrubou a metade da classe também: {p['classe']!r}")


# --------------------------------------------------------------------------
# 3. um endereço, uma leitura
# --------------------------------------------------------------------------
def test_a_leitura_de_volta_continua_lendo_a_classe(medido: dict) -> None:
    """O atributo é DERIVADO, e não um segundo campo a medir.

    Ler os dois faria a régua do mockup contar duas vezes o mesmo endereço — e
    a segunda contagem seria de um valor que a página nunca crava.
    """
    por_chave = {str(x[0]): (str(x[2]), str(x[3])) for x in medido["leitura"]}
    alvo, valor = por_chave["retomar-cinza"]
    assert alvo == "classe", f"o leitor mudou de alvo: {alvo!r}"
    # No fim do roteiro o botão está APAGADO — a classe saiu.
    assert valor == "", (
        f"a leitura devolveu {valor!r} para um botão cuja classe está apagada")
