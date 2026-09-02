#!/usr/bin/env python3
"""O pintor de verdade, num WebKit de verdade, pintando os dois alvos novos.

POR QUE NÃO UM DUBLÊ DE DOM: o ``escrever()`` do BOOTSTRAP é JavaScript, e a
única forma de saber o que ele faz é executá-lo no MOTOR QUE ELA VAI USAR.
Reescrevê-lo em Python para testar seria testar a reescrita. Esta casa já pagou
por medir contra a biblioteca errada, e a armadilha tem nome:
*"medir contra a biblioteca errada produz alarme convincente e falso"*.

A JANELA É ``Gtk.OffscreenWindow`` — sob Xvfb não há gerenciador de janelas e
uma ``Gtk.Window`` fica 1x1 para sempre. E ela é offscreen também porque a dona
do projeto tem UMA tela: janela de teste não nasce na frente dela.

O QUE ELE COBRA, e são quatro coisas que nenhum teste puro alcança:

1. **as irmãs apagam.** Os quatro degraus dividem UM ``data-campo``; pintar
   ``'balanceado'`` tem de apagar o ``'max'`` que estava aceso. Um segundo
   clique não pode deixar dois degraus acesos.
2. **o alvo é IDEMPOTENTE.** Pintar o mesmo valor de novo devolve ``0``. O
   ``cls()`` dos cinco pilotos velhos devolvia ``1`` SEMPRE, e um alvo assim
   infla a contagem de pinturas de toda aba que o use — que é O instrumento com
   que esta casa prova que um endereço existe.
3. **a cor é escrita no ``color``**, não no texto, e apaga com o vazio.
4. **o leitor da régua casa com o parser de Python**, endereço a endereço e
   valor a valor. É a mesma guarda que o ``--prova-de-mockup`` roda em cada aba
   sobre o DOM virgem — aqui ela roda sobre um caso que nenhuma página publicada
   ainda tem.

A MORDIDA: tire o ``el.classList.toggle`` do ramo ``classe`` do BOOTSTRAP e
``test_as_irmas_do_grupo_apagam`` reprova; troque ``el.style.color`` por
``el.textContent`` no ramo ``cor`` e ``test_a_cor_vai_para_o_color`` reprova
dizendo que a régua e o pintor discordam.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.interface import regua_do_mockup as regua

PILOTO = RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"

#: A PÁGINA DE ENSAIO. Ela reproduz, em miniatura, as cinco formas que os dois
#: alvos novos destravam — os quatro degraus da Vibração, o rótulo do teto, o
#: botão de jogador, a coluna da Perfis e o clique do analógico.
PAGINA = """<html><body>
<div data-controle="p1">
  <div class="seg">
    <button data-campo="degrau" data-hef-alvo="classe"
            data-hef-quando="economia">Economia</button>
    <button data-campo="degrau" data-hef-alvo="classe"
            data-hef-quando="balanceado">Balanceado</button>
    <button class="on" data-campo="degrau" data-hef-alvo="classe"
            data-hef-quando="max">M&aacute;ximo</button>
    <button data-campo="degrau" data-hef-alvo="classe"
            data-hef-quando="auto">Auto</button>
  </div>
  <span class="teto" data-campo="mult-teto" data-hef-alvo="classe">M&aacute;x</span>
  <span class="rotl" data-campo="l3" data-hef-alvo="cor"
        style="color:#6272a4">L3</span>
  <span class="rotl" data-campo="r3" data-hef-alvo="cor">R3</span>
</div>
<table><tr><td class="gr on" data-campo="ajuste"
             data-hef-alvo="classe">&#10003;</td></tr></table>
</body></html>"""


def _constante(nome: str) -> str:
    """O BOOTSTRAP e o LER_CAMPOS lidos do FONTE do piloto, e não importados.

    Importar ``hefesto_vivo`` arrastaria a janela GTK inteira para dentro do
    teste. O ``test_a_regua_le_os_mesmos_enderecos_do_bootstrap`` já lê o piloto
    assim, e pela mesma razão.
    """
    fonte = PILOTO.read_text(encoding="utf-8")
    achou = re.search(rf'^{nome} = r"""(.*?)"""$', fonte, re.S | re.M)
    assert achou, f"o piloto perdeu o {nome} — não há o que testar"
    return achou.group(1)


#: O ROTEIRO INTEIRO NUMA IDA SÓ ao motor: cada passo devolve o que precisa ser
#: julgado do lado Python. Um round-trip por asserção custaria dez cargas de
#: página para medir o que uma mede.
ROTEIRO = """
(function(){
  const fora = {};
  fora.virgem = JSON.parse(LEITOR_AQUI);
  fora.n_balanceado = window.__hef.pintar({colunas: {p1: {
      degrau: 'balanceado', 'mult-teto': false, l3: 'var(--plastico)'}},
      mesa: {ajuste: false}});
  fora.depois = JSON.parse(LEITOR_AQUI);
  fora.classes_depois = Array.prototype.map.call(
      document.querySelectorAll('[data-campo="degrau"]'),
      function(el){ return el.className; });
  fora.cor_depois = document.querySelector('[data-campo="l3"]').style.color;
  fora.texto_l3 = document.querySelector('[data-campo="l3"]').textContent;
  fora.n_denovo = window.__hef.pintar({colunas: {p1: {
      degrau: 'balanceado', 'mult-teto': false, l3: 'var(--plastico)'}},
      mesa: {ajuste: false}});
  fora.n_max = window.__hef.pintar({colunas: {p1: {degrau: 'max',
      'mult-teto': true, l3: ''}}, mesa: {ajuste: true}});
  fora.fim = JSON.parse(LEITOR_AQUI);
  fora.classes_fim = Array.prototype.map.call(
      document.querySelectorAll('[data-campo="degrau"]'),
      function(el){ return el.className; });
  fora.cor_fim = document.querySelector('[data-campo="l3"]').style.color;
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
        except Exception as e:
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
    GLib.timeout_add(20000, Gtk.main_quit)
    Gtk.main()
    assert saiu, "o WebKit não respondeu em 20 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    return json.loads(saiu[0])


def _endereco(linha: list) -> str:
    return f"{linha[1]}·{linha[0]}" if linha[1] else str(linha[0])


def _campos(linhas: list) -> dict[str, list[str]]:
    """``{endereço: [valores]}``, da leitura de tela do próprio piloto.

    É uma LISTA por endereço, e não um valor: os quatro degraus dividem um
    ``data-campo`` só, e um dicionário simples guardaria o último — que é
    justamente o que nunca acende.
    """
    fora: dict[str, list[str]] = {}
    for x in linhas:
        fora.setdefault(_endereco(x), []).append(str(x[3]))
    return fora


def _um(linhas: list, endereco: str) -> str:
    (valor,) = _campos(linhas)[endereco]
    return valor


def _aceso(linhas: list, endereco: str) -> list[str]:
    """Quais membros do grupo estão acesos, pela leitura do próprio piloto."""
    return [v for v in _campos(linhas)[endereco] if v]


# -- o leitor de tela e o parser de arquivo têm de dizer o MESMO ----------
def test_o_leitor_de_tela_casa_com_o_parser_do_arquivo(medido):
    """A guarda do DOM virgem, aplicada a um caso que nenhuma página tem ainda.

    Se os dois discordarem, a régua está lendo uma coisa e comparando outra — e
    diria PRODUTO sobre um campo que ninguém tocou.
    """
    cravados = regua._campos_cravados(PAGINA)
    virgem = medido["virgem"]
    assert len(virgem) == len(cravados)
    for c, linha in zip(cravados, virgem, strict=True):
        assert (str(linha[0]), str(linha[1])) == (c.chave, c.dono)
        assert str(linha[3]) == c.valor, (
            f"{c.endereco}: o arquivo diz {c.valor!r} e a tela virgem mostra "
            f"{linha[3]!r} — o parser e o leitor discordam no alvo {c.alvo}")


# -- (a) ligar uma classe desliga as irmãs -------------------------------
def test_as_irmas_do_grupo_apagam(medido):
    """Pintar ``balanceado`` apaga o ``max`` que estava aceso — e só um fica.

    O DEFEITO QUE ISTO IMPEDE está escrito no enunciado desta frente: *"senão o
    segundo clique deixa dois degraus acesos"*.
    """
    assert _aceso(medido["depois"], "p1·degrau") == ["balanceado"], (
        f"a tela devolveu {_campos(medido['depois'])['p1·degrau']} — o `max` "
        f"cravado no arquivo tinha de ter apagado")
    acesos = [c for c in medido["classes_depois"] if "on" in c.split()]
    assert len(acesos) == 1, (
        f"os quatro degraus acabaram com {len(acesos)} acesos: "
        f"{medido['classes_depois']}")


def test_o_grupo_volta_quando_o_valor_volta(medido):
    """E o caminho de volta também apaga: pintar ``max`` de novo devolve UM só."""
    assert _aceso(medido["fim"], "p1·degrau") == ["max"]
    assert len([c for c in medido["classes_fim"] if "on" in c.split()]) == 1


# -- (b) o alvo é idempotente e devolve 0 --------------------------------
def test_pintar_o_mesmo_valor_de_novo_devolve_zero(medido):
    """Um alvo que sempre diz "1" infla a contagem de todas as abas."""
    assert medido["n_balanceado"] > 0, (
        "a primeira pintura mudou classe, cor e booleano — tinha de contar")
    assert medido["n_denovo"] == 0, (
        f"pintar os MESMOS valores contou {medido['n_denovo']} pintura(s). O "
        f"`cls()` dos pilotos velhos devolvia 1 sempre, e é esse o defeito.")


def test_o_booleano_acende_e_apaga_por_si(medido):
    """O rótulo ``Máx`` e a coluna "Ajuste próprio": sem grupo, sem ``quando``."""
    assert _um(medido["depois"], "p1·mult-teto") == ""
    assert _um(medido["depois"], "ajuste") == ""
    assert _um(medido["fim"], "p1·mult-teto") == "sim"
    assert _um(medido["fim"], "ajuste") == "sim"


# -- a cor vai para o `color`, e o texto fica em paz ---------------------
def test_a_cor_vai_para_o_color(medido):
    """O clique do analógico é COR na GTK — e o rótulo ``L3`` continua ``L3``."""
    assert medido["cor_depois"] == "var(--plastico)"
    assert medido["texto_l3"] == "L3", (
        "pintar a cor não pode escrever nada dentro do círculo — foi por não "
        "haver este alvo que `a02_controles.py` teve de escrever `[L3]` em texto")
    assert _um(medido["depois"], "p1·l3") == "var(--plastico)"


def test_a_cor_vazia_apaga_e_devolve_a_folha_de_estilo(medido):
    """Um analógico solto volta à cor de sempre, em vez de ficar aceso."""
    assert medido["cor_fim"] == ""
    assert _um(medido["fim"], "p1·l3") == "", (
        "o vazio tem de APAGAR a cor de linha; sem isso o clique nunca acaba")


def test_o_selo_da_visita_marca_so_quem_o_pintor_tocou(medido):
    """O selo é o que decide um INDECIDÍVEL — e ele não pode selar tudo.

    ``r3`` tem endereço na página e nenhum pacote o declara. Se ele voltar
    selado, o selo não está registrando a visita: está sendo escrito no ar, e
    todo campo coincidente viraria PRODUTO de graça.
    """
    selos: dict[str, list[bool]] = {}
    for x in medido["fim"]:
        selos.setdefault(_endereco(x), []).append(bool(x[4]))
    assert selos["p1·degrau"] == [True] * 4
    assert selos["p1·l3"] == [True]
    assert selos["p1·r3"] == [False], (
        "ninguém pintou o `r3` neste roteiro — ele não pode ter selo")
