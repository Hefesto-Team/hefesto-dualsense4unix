#!/usr/bin/env python3
"""A TELA NÃO SAMBA — a interface parada não pode mexer no DOM.

**A palavra dela, 06/09/2026, com o produto aberto e um DualSense no cabo:**
*"a interface inteira tá sambando"* — e quatro sintomas: pisca/repinta sem
parar, cliques não aplicam ou atrasam, trava por instantes, e *"botões não
funcionam, algo ativa o tooltip mas ele se desativa"*.

POR QUE FOTO NENHUMA VIA ISSO, e é a razão de esta régua existir: duas fotos da
tela dela com um minuto de intervalo saem IDÊNTICAS. O defeito não está no
layout parado — está no MOVIMENTO entre dois tiques. E o contador de pinturas
que o piloto já tinha também não via: ele conta o que o piloto ACHA que
escreveu, e o defeito era justamente a escrita que ele não contava — um
`setAttribute` com o valor igual, um `classList.add` de uma classe que já
estava lá, um `innerHTML` que difere só na indentação.

**O FATO QUE ORGANIZA TUDO:** *escrever o mesmo valor É uma mutação de DOM*. A
especificação manda enfileirar um `MutationRecord` em toda troca de atributo,
não só quando o valor difere. E a DICA NATIVA do WebKit fecha quando o `title`
do elemento sob o cursor muda — a dez tiques por segundo, ela abria e morria
antes de ela conseguir ler. É o item *"algo ativa o tooltip mas ele se
desativa"*, medido.

O QUE ESTA RÉGUA COBRA, e cada item é um passo da A-TELA-SAMBA-01:

1. **o alvo `atributo` compara ANTES de escrever** — um `title` reescrito com o
   mesmo texto não produz mutação nenhuma;
2. **o selo da visita escreve UMA vez** — ele é `'1'` ou é ausência, e
   reescrevê-lo era a maior parcela do samba (6.700 das 7.100 mutações da aba
   Jogar em 100 tiques);
3. **o alvo `html` e os blocos lembram o que escreveram** — o serializador do
   navegador devolve outra forma (a indentação some, as aspas mudam, e o SELO
   da visita entra depois), e comparar contra a forma devolvida acusa mudança
   em todo tique. **`cor` e `plastico` NÃO precisaram disso**, e a medição é
   que disse: o CSSOM não reescreve o `style` quando a declaração não muda —
   a hipótese da sprint sobre eles caiu;
4. **um bloco não é trocado com um botão EM VOO dentro** — quem clicou não pode
   ter o nó arrancado debaixo do dedo entre o `mousedown` e o `click`;
5. **A PÁGINA INTEIRA, COM A MESA PARADA, MUTA ZERO** — é a régua de produto, e
   ela roda o piloto de verdade sobre a página publicada;
6. **o tique não enfileira** — com a ponte lenta, o piloto pula em vez de
   empilhar pintura sobre pintura.

A MORDIDA de cada uma está no docstring dela. A janela é OCULTA: ela tem UMA
tela.
"""
from __future__ import annotations

from typing import Any

import json
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: OS DOIS CONTROLES DA MESA DUBLÊ, na faixa sintética da casa. Nada de MAC real
#: em arquivo versionado — há dois portões, e eles não perdoam.
UNIQ_P1 = "aa:bb:cc:00:00:01"
UNIQ_P2 = "aa:bb:cc:00:00:02"

#: A PÁGINA QUE A RÉGUA DE PRODUTO MEDE. É a `01-jogar`, que é a que o `.desktop`
#: dela abre — o defeito foi relatado nela.
PAGINA = "01-jogar.html"

#: QUANTOS TIQUES A RÉGUA DE PRODUTO OLHA. Quarenta são quatro segundos: tempo
#: para o defeito de 06/09 aparecer 2.840 vezes, se ele voltar.
TIQUES = 40


def _ctl(uniq: str, transporte: str, jogador: int) -> dict[str, Any]:
    return {"uniq": uniq, "connected": True, "transport": transporte,
            "player": jogador, "battery": 64, "audio": {"mic_mudo": False}}


#: A MESA PARADA. Um `dict` LITERAL e imutável durante a medição — se o estado
#: mudasse, uma mutação seria correta e a régua não saberia distinguir.
ESTADO = {
    "active_profile": "regua",
    "gamepad_emulation": {"flavor": "dualsense"},
    "controllers": [_ctl(UNIQ_P1, "usb", 1), _ctl(UNIQ_P2, "bt", 2)],
}


# -- a bancada de JS: o BOOTSTRAP de verdade numa página de verdade -------

#: O ROTEIRO É PARAMETRIZADO PELO QUE SE QUER PINTAR, e o observador é o mesmo
#: das seis medições. Ele conta por tipo e por atributo, que é o que separa
#: "o piloto mexeu" de "o piloto mexeu no `title`".
ROTEIRO = r"""
(function(){
  const fora = {contas: [], pintou: [], detalhe: []};
  const alvo = document.createElement('div');
  alvo.id = 'regua-samba';
  document.body.appendChild(alvo);
  alvo.innerHTML = MONTAGEM;
  // O PREPARO roda ANTES do observador: é onde a régua veste um elemento da
  // PÁGINA (a fita, que é da página e não da montagem) com o que ela quer medir.
  PREPARO;
  // A RAIZ OBSERVADA é a montagem por omissão, e não o documento: os nomes de
  // `data-campo` desta régua (`plastico`, por exemplo) também existem na página
  // publicada, e observar tudo somaria as escritas legítimas daqueles elementos
  // às da peça em medição.
  const raiz = RAIZ;
  const obs = new MutationObserver(function(){});
  obs.observe(raiz, {attributes: true, childList: true, characterData: true,
                     subtree: true});
  // `takeRecords()` E NÃO O CALLBACK, e a diferença decide a régua: o callback
  // de um `MutationObserver` roda em MICROTAREFA, isto é, DEPOIS deste laço
  // inteiro — uma régua que contasse nele leria zero em todo passo e ficaria
  // verde sobre qualquer coisa. `takeRecords()` devolve a fila AGORA e a
  // esvazia, que é o que faz a conta ser deste passo.
  obs.takeRecords();
  for(const c of CARGAS){
    // O POUSO DO VOO quando a carga pedir: é o `voltouDoVoo` do próprio
    // BOOTSTRAP, e não uma classe tirada à mão — a régua tem de exercitar o
    // caminho que o produto usa.
    if(c.__pousa !== undefined){ window.__hef.voltouDoVoo(c.__pousa); obs.takeRecords(); }
    fora.pintou.push(window.__hef.pintar(c));
    const regs = obs.takeRecords();
    fora.contas.push(regs.length);
    for(const r of regs){
      if(fora.detalhe.length < 12){
        fora.detalhe.push(r.type + ':' + (r.attributeName || ''));
      }
    }
  }
  fora.html = alvo.innerHTML;
  return JSON.stringify(fora);
})()
"""


def _no_webkit(montagem: str, cargas: list[dict[str, Any]], *,
               preparo: str = "", raiz: str = "alvo") -> dict[str, Any]:
    """Abre uma página PUBLICADA num WebKit offscreen, com o BOOTSTRAP dentro.

    `Gtk.OffscreenWindow` e não `Gtk.Window`: sob Xvfb não há gerenciador de
    janelas e uma janela comum fica 1x1 para sempre. E offscreen também porque
    ela tem UMA tela.
    """
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    import hefesto_vivo as hv
    from hefesto_dualsense4unix.interface import onde

    roteiro = (ROTEIRO
               .replace("MONTAGEM", json.dumps(montagem))
               .replace("PREPARO", preparo or "0")
               .replace("RAIZ", raiz)
               .replace("CARGAS", json.dumps(cargas, ensure_ascii=False)))
    saiu: list[str] = []
    janela = Gtk.OffscreenWindow()
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def guardou(v: Any, res: Any) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:  # pragma: no cover — só quando o roteiro quebra
            saiu.append(f"ERRO {e}")
        Gtk.main_quit()

    def bootou(v: Any, res: Any) -> None:
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:  # pragma: no cover
            saiu.append(f"ERRO no BOOTSTRAP: {e}")
            Gtk.main_quit()
            return
        v.evaluate_javascript(roteiro, -1, None, None, None, guardou)

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            # O BOOTSTRAP É O DO PILOTO, lido do módulo — nunca copiado. Uma
            # cópia aqui viraria a segunda verdade sobre o `escrever()`.
            v.evaluate_javascript(hv.BOOTSTRAP, -1, None, None, None, bootou)

    view.connect("load-changed", carregou)
    view.load_uri(onde.pagina(PAGINA, publicado=True).as_uri())
    # O `timeout_add` PENDENTE DISPARA NO LAÇO DO PRÓXIMO TESTE de GUI do mesmo
    # processo, e já matou onze medições nesta casa.
    guarda = GLib.timeout_add(30000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert saiu, "o WebKit não respondeu em 30 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    return dict(json.loads(saiu[0]))


# -- 1. o alvo `atributo` -------------------------------------------------

def test_atributo_igual_nao_muta() -> None:
    """Um `title` reescrito com o MESMO texto não produz mutação nenhuma.

    É a régua do item que ela escreveu com todas as letras — *"algo ativa o
    tooltip mas ele se desativa"*. A dica nativa do WebKit fecha na mutação do
    atributo que a alimenta; com o `title` trocado dez vezes por segundo ela
    não sobrevive ao tempo de ler.

    A MORDIDA: devolva ao ramo `atributo` do BOOTSTRAP a forma de antes — o
    `setAttribute`/`removeAttribute` incondicional seguido da releitura — e a
    segunda pintura volta a contar 1.
    """
    fora = _no_webkit(
        '<b data-campo="dica" data-hef-alvo="atributo" '
        'data-hef-atributo="title">?</b>',
        [{"mesa": {"dica": "o que este botão faz"}}] * 3,
    )
    # DUAS na primeira: o selo da visita (que nasce ausente) e o `title`. É a
    # única pintura honesta desta medição — daí em diante o valor é o mesmo.
    assert fora["contas"][0] == 2, (
        "a primeira pintura tinha de escrever o selo e o `title` — "
        f"contou {fora['contas'][0]}")
    assert fora["contas"][1:] == [0, 0], (
        "reescrever o MESMO `title` mutou o DOM: a dica dela morre a cada "
        f"tique — {fora['contas']}, detalhe {fora.get('detalhe')}")
    assert fora["pintou"][1:] == [0, 0], (
        "o contador de pinturas mentiu: valor igual não é pintura")


def test_o_atributo_apagado_nao_muta_de_novo() -> None:
    """Apagar um atributo que já não existe também não é mutação.

    O ramo tem dois caminhos e o vazio é o outro. Sem esta régua, a cura podia
    curar metade — que é a forma de conserto que esta casa nomeou em 05/09.
    """
    fora = _no_webkit(
        '<b data-campo="dica" data-hef-alvo="atributo" '
        'data-hef-atributo="title">?</b>',
        [{"mesa": {"dica": ""}}] * 3,
    )
    # UMA na primeira, e ela é o SELO — o `title` nunca existiu, então apagá-lo
    # não pode escrever nada, nem na primeira volta.
    assert fora["contas"] == [1, 0, 0], (
        f"apagar o que não existe mexeu no DOM — {fora['contas']}, "
        f"detalhe {fora.get('detalhe')}")


# -- 2. o selo da visita --------------------------------------------------

def test_o_selo_da_visita_escreve_uma_vez_so() -> None:
    """`data-hef-visto` é `'1'` ou é ausência — reescrevê-lo é samba puro.

    Era a MAIOR parcela do defeito: 6.700 das 7.100 mutações que a aba Jogar
    fazia em 100 tiques com a mesa parada.

    O SELO NÃO PERDE NADA: a visita sem mudança continua deixando rastro,
    porque o rastro é o atributo ESTAR lá.

    A MORDIDA: tire a guarda `if(el.dataset.hefVisto !== '1')` do `escrever()`
    e a conta vira 1 por pintura, para sempre.
    """
    fora = _no_webkit(
        '<b data-campo="quieto">—</b>',
        [{"mesa": {"quieto": "o mesmo texto"}}] * 4,
    )
    assert fora["contas"][0] >= 1, "a primeira pintura tinha de escrever"
    assert fora["contas"][1:] == [0, 0, 0], (
        f"o selo foi reescrito com o valor igual — {fora['contas']}, "
        f"detalhe {fora.get('detalhe')}")
    assert 'data-hef-visto="1"' in fora["html"], (
        "o selo sumiu: a régua do mockup perde o que decide um INDECIDÍVEL")


# -- 3. cor, plástico e html ---------------------------------------------

def test_a_cor_e_o_plastico_repetidos_nao_mutam() -> None:
    """Repetir a mesma cor e o mesmo plástico não mexe no DOM.

    **ESTA RÉGUA NÃO MORDE CONTRA A CURA DE 06/09, PORQUE NÃO HOUVE CURA
    AQUI**, e dizê-lo é a metade honesta dela. A sprint supunha que estes dois
    ramos fossem culpados do samba por escreverem antes de comparar; a medição
    com o observador ligado por 100 tiques, mesa parada, nas dez abas, não
    achou **uma** mutação vinda deles. O CSSOM só reescreve o atributo `style`
    quando a DECLARAÇÃO muda, e escrever a mesma cor não muda declaração
    nenhuma. Os dois ramos ficaram como estavam.

    **O QUE ELA GUARDA É O CONTRATO**, e ele morde: troque o CSSOM por um
    `setAttribute('style', …)` — a forma que qualquer um escreveria sem saber
    disto — e a conta vira 1 por pintura, porque `setAttribute` muta sempre.
    Foi assim que ela foi provada em 06/09.
    """
    fora = _no_webkit(
        '<b data-campo="clique" data-hef-alvo="cor">L3</b>'
        '<div data-campo="plastico" data-hef-alvo="plastico">.</div>',
        [{"mesa": {"clique": "#6272a4", "plastico": "#ae335a"}}] * 3,
    )
    assert fora["contas"][1:] == [0, 0], (
        f"a cor ou o `--plastico` mexeram no DOM ao repetir — "
        f"{fora['contas']}, detalhe {fora.get('detalhe')}")


def test_o_bloco_reserializado_nao_e_reescrito() -> None:
    """Um bloco cujo HTML o navegador REESCREVE ao guardar não volta todo tique.

    É o mesmo defeito do alvo `html` um tamanho acima, e foi ele que fazia a
    lista dos 33 perfis (`perfis.lista`, aba 10) ser reconstruída inteira dez
    vezes por segundo — 132 nós por tique, 4.000 mutações em 40 tiques com a
    mesa parada. Clicar numa linha daquela lista era clicar num nó que ia
    deixar de existir.

    AQUI A DIFERENÇA É PROVOCADA de propósito — indentação e aspas simples, que
    é o que o serializador do WebKit normaliza —, porque no produto ela nasce do
    selo da visita, que a pintura carimba DEPOIS do bloco entrar.

    A MORDIDA: tire o `alvo.__hefBloco === html` do laço de blocos e a conta
    vira 1 por pintura.
    """
    fora = _no_webkit(
        "<div id='regua-bloco'>.</div>",
        [{"blocos": {"#regua-bloco": "\n  <b class='x'>a&amp;b</b>\n"}}] * 3,
    )
    assert fora["pintou"] == [1, 0, 0], (
        f"o bloco foi reescrito com o mesmo desenho — {fora['pintou']}")
    assert fora["contas"][1:] == [0, 0], (
        f"o bloco recriou o miolo sem nada ter mudado — {fora['contas']}")


def test_o_html_repetido_nao_muta_mesmo_reserializado() -> None:
    """O navegador devolve a SERIALIZAÇÃO dele, não o texto que entrou.

    A indentação some, as aspas mudam, a entidade vira caractere — e onde uma
    dessas diferenças existir, `el.innerHTML !== t` é verdade para sempre. É o
    que fazia `luz` e `players` (aba 04) e `adaptadores-tabela` (aba 08)
    recriarem o miolo dez vezes por segundo.

    A MORDIDA: tire o `el.__hefHtml`.
    """
    fora = _no_webkit(
        '<div data-campo="miolo" data-hef-alvo="html">.</div>',
        [{"mesa": {"miolo": "\n  <b class='x'>a&amp;b</b>\n"}}] * 3,
    )
    assert fora["contas"][1:] == [0, 0], (
        f"o miolo foi recriado com o mesmo desenho — {fora['contas']}")


# -- 4. o bloco e o botão em voo ------------------------------------------

def test_o_bloco_nao_destroi_um_botao_em_voo() -> None:
    """Um botão trabalhando nunca é arrancado debaixo do dedo dela.

    Um gesto desta casa leva 9,5 s (`daemon.reload`): são 95 tiques de chance
    de o bloco ser reconstruído entre o `mousedown` e o `click`, e o
    `hef-em-voo` — a única coisa na tela dizendo *"estou trabalhando"* — some
    com o nó que o vestia.

    A MORDIDA: tire o `if(alvo.querySelector('.hef-em-voo') …) continue` e o
    botão em voo desaparece na primeira troca de bloco.
    """
    fora = _no_webkit(
        '<div id="regua-bloco"><button class="hef-em-voo" '
        'data-hef-voo="7">clicado</button></div>',
        [{"blocos": {"#regua-bloco": "<i>outro miolo</i>"}}] * 3,
    )
    assert "hef-em-voo" in fora["html"], (
        "o bloco engoliu o botão em voo — o clique dela morre no meio")
    assert "outro miolo" not in fora["html"], (
        "o miolo novo entrou com o botão ainda em voo")
    assert fora["pintou"] == [0, 0, 0], (
        "o piloto contou pintura de um bloco que ele ADIOU — "
        f"{fora['pintou']}")
    assert fora["contas"] == [0, 0, 0], (
        f"o bloco adiado mexeu no DOM assim mesmo — {fora['contas']}")


def test_o_bloco_volta_a_pintar_quando_o_voo_pousa() -> None:
    """Adiar não é desistir: assim que o voo pousa, o bloco entra inteiro.

    Sem esta metade, a cura acima seria pior que o defeito — um bloco congelado
    para sempre é a tela afirmando o que deixou de ser verdade, que é o F7
    desta casa. O pouso é o `voltouDoVoo` do próprio BOOTSTRAP, o mesmo que o
    piloto chama quando o gesto responde.
    """
    fora = _no_webkit(
        '<div id="regua-bloco"><button class="hef-em-voo" '
        'data-hef-voo="7">clicado</button></div>',
        [{"blocos": {"#regua-bloco": "<i>miolo novo</i>"}},
         {"blocos": {"#regua-bloco": "<i>miolo novo</i>"}, "__pousa": 7},
         {"blocos": {"#regua-bloco": "<i>miolo novo</i>"}}],
    )
    assert fora["pintou"][0] == 0, (
        f"o bloco entrou por cima de um botão em voo — {fora['pintou']}")
    assert fora["pintou"][1] == 1, (
        "o bloco não entrou depois do pouso: adiar virou desistir — "
        f"{fora['pintou']}")
    assert fora["pintou"][2] == 0, (
        f"o bloco entrou DUAS vezes com o mesmo desenho — {fora['pintou']}")
    assert "miolo novo" in fora["html"], "o miolo novo nunca chegou à tela"


# -- 5. a régua de PRODUTO: a página inteira, com a mesa parada -----------

@pytest.fixture(scope="module")
def parada() -> dict[str, Any]:
    """Roda o piloto DE VERDADE sobre a página publicada, com a mesa parada."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    import argparse

    import hefesto_vivo as hv

    guardado = hv.mesa_viva.estado_do_daemon
    hv.mesa_viva.estado_do_daemon = lambda *a, **k: ESTADO  # type: ignore[assignment]
    args = argparse.Namespace(
        oculta=True, segundos=0.0, passear=False, parada=900, foto="",
        abre="", prova_no_aparelho=False, entre=2500, espera=1200,
        incluir_perigosos=False, prova_clique="", sem_cor=True,
        prova_de_mockup=False, voltas_por_aba=8, teto_de_mockup=-1,
        sem_cravado=False, sem_selo=False, conta_mutacoes=TIQUES,
    )
    piloto = hv.Piloto(args)
    guarda = GLib.timeout_add(60000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        hv.mesa_viva.estado_do_daemon = guardado  # type: ignore[assignment]
        piloto.tela.janela.destroy()
    return dict(piloto.mutacoes)


def test_a_pagina_parada_nao_muta_nada(parada: dict[str, Any]) -> None:
    """ZERO. É o número certo, e é o que o produto entrega desde 06/09/2026.

    Esta é a régua que mede o PRODUTO — as outras medem uma peça. Ela abre a
    página publicada, com o piloto de verdade e a mesa congelada, e conta o que
    o DOM sofreu em quarenta tiques.

    A MORDIDA: qualquer uma das seis curas arrancada faz esta reprovar, e a
    mensagem nomeia o endereço culpado.
    """
    assert parada, "o observador não devolveu tabela — a régua ficaria verde sobre nada"
    linhas = parada.get("linhas") or []
    culpados = ", ".join(
        f"{x['campo']}/{x['tipo']}/{x['detalhe']} x{x['n']}" for x in linhas[:6])
    assert parada.get("total") == 0, (
        f"a tela mexeu {parada.get('total')} vezes em {TIQUES} tiques com a "
        f"mesa PARADA — {culpados}")


def test_o_observador_sabe_acusar(parada: dict[str, Any]) -> None:
    """A régua acima só vale se o instrumento souber ver alguma coisa.

    *Antes de acreditar num vazio, prove que a régua sabe achar.* Aqui a prova
    é do outro lado: o mesmo observador, mexendo no DOM de propósito, TEM de
    contar. Sem isto, um observador que nunca ligou daria o mesmo zero.
    """
    fora = _no_webkit(
        '<b data-campo="anda">—</b>',
        [{"mesa": {"anda": "um"}}, {"mesa": {"anda": "dois"}},
         {"mesa": {"anda": "três"}}],
    )
    # 2 na primeira (o selo + o texto) e 1 em cada uma das duas seguintes.
    assert fora["contas"] == [2, 1, 1], (
        f"o observador não viu três mudanças de verdade — {fora['contas']}")


# -- 6. o tique não enfileira --------------------------------------------

def test_o_tique_nao_enfileira_com_a_ponte_lenta() -> None:
    """Com a ponte lenta, o piloto PULA — ele não empilha pintura sobre pintura.

    O DEFEITO É DE FORMA: a pintura é assíncrona, então dez tiques podem ter
    dez `run_javascript` no ar ao mesmo tempo, cada um com uma carga inteira, e
    o WebKit os executa em ordem, todos com dado velho. É o *"trava por
    instantes"* dela.

    A CONTA: com a ponte a 300 ms e o tique a 100 ms, três segundos cabem ~10
    pinturas se o piloto esperar e ~30 se ele empilhar.

    A MORDIDA: tire o `if(self._pintura_no_ar)` do `_tique` e a conta triplica.
    """
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    import argparse

    import hefesto_vivo as hv

    guardado = hv.mesa_viva.estado_do_daemon
    hv.mesa_viva.estado_do_daemon = lambda *a, **k: ESTADO  # type: ignore[assignment]
    args = argparse.Namespace(
        oculta=True, segundos=0.0, passear=False, parada=900, foto="",
        abre="", prova_no_aparelho=False, entre=2500, espera=1200,
        incluir_perigosos=False, prova_clique="", sem_cor=True,
        prova_de_mockup=False, voltas_por_aba=8, teto_de_mockup=-1,
        sem_cravado=False, sem_selo=False, conta_mutacoes=0,
    )
    piloto = hv.Piloto(args)
    chamadas: list[int] = []

    def ponte_lenta(js: str, resposta: Any) -> None:
        """A ponte que demora 300 ms — e é mais LENTA que a real, de propósito."""
        chamadas.append(1)

        def pousou() -> bool:
            resposta("0", None)
            return False

        GLib.timeout_add(300, pousou)

    def comecar() -> bool:
        if not piloto.pronto:
            return True
        piloto.ponte.perguntar = ponte_lenta  # type: ignore[assignment]
        chamadas.clear()
        GLib.timeout_add(3000, lambda: (Gtk.main_quit(), False)[1])
        return False

    guarda = GLib.timeout_add(60000, Gtk.main_quit)
    GLib.timeout_add(120, comecar)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        hv.mesa_viva.estado_do_daemon = guardado  # type: ignore[assignment]
        piloto.tela.janela.destroy()

    assert len(chamadas) <= 15, (
        f"o piloto mandou {len(chamadas)} pinturas em 3 s com a ponte a 300 ms "
        "— ele está enfileirando, e o WebKit as executa todas com dado velho")
    assert piloto._pulados_por_voo > 0, (
        "nenhum tique foi pulado: ou a ponte dublê não atrasou, ou a guarda "
        "não existe — as duas deixam esta régua verde sobre nada")


def test_a_fita_nao_e_trocada_com_um_chip_em_voo() -> None:
    """A fita é o caso EXTREMO do bloco: ela troca o próprio nó, não o miolo.

    `f.outerHTML = desejado` mata tudo o que está dentro dela — e os chips da
    fita são clicáveis: são eles que escolhem em qual controle o gesto age. Um
    chip clicado veste `hef-em-voo` até o gesto responder, e sem esta guarda ele
    desaparece no primeiro tique, com o clique dela no meio do caminho.

    Achado pela ONDA4-S10-O-TRANSPORTE-01 e confirmado aqui em 06/09/2026.

    A MORDIDA: tire a guarda do ramo `p.fita` e a fita volta a ser trocada com o
    chip em voo dentro.
    """
    fora = _no_webkit(
        "",
        [{"fita": '<div class="fita">a fita nova</div>'}] * 3,
        preparo=("(function(){const f=document.querySelector('.fita');"
                 "f.firstElementChild.classList.add('hef-em-voo');})()"),
        raiz="document.querySelector('.fita').parentElement",
    )
    assert fora["pintou"] == [0, 0, 0], (
        f"a fita foi trocada com um chip em voo dentro — {fora['pintou']}")
    # A PRIMEIRA VOLTA CARIMBA O SELO nos chips da fita da página — é uma vez
    # só, e é o que o laço de selos faz de propósito. O que esta régua cobra é
    # o REGIME: da segunda volta em diante, com o chip em voo, nada se move.
    assert fora["contas"][1:] == [0, 0], (
        f"a fita mexeu no DOM com um chip em voo dentro — {fora['contas']}")
