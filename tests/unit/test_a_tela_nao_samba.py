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

UNIQ_P1 = "aa:bb:cc:00:00:01"
UNIQ_P2 = "aa:bb:cc:00:00:02"

PAGINA = "01-jogar.html"

TIQUES = 40


def _ctl(uniq: str, transporte: str, jogador: int) -> dict[str, Any]:
    return {"uniq": uniq, "connected": True, "transport": transporte,
            "player": jogador, "battery": 64, "audio": {"mic_mudo": False}}


ESTADO = {
    "active_profile": "regua",
    "gamepad_emulation": {"flavor": "dualsense"},
    "controllers": [_ctl(UNIQ_P1, "usb", 1), _ctl(UNIQ_P2, "bt", 2)],
}


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
    """Abre uma página PUBLICADA num WebKit offscreen, com o BOOTSTRAP dentro."""
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
            v.evaluate_javascript(hv.BOOTSTRAP, -1, None, None, None, bootou)

    view.connect("load-changed", carregou)
    view.load_uri(onde.pagina(PAGINA, publicado=True).as_uri())
    guarda = GLib.timeout_add(30000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert saiu, "o WebKit não respondeu em 30 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    return dict(json.loads(saiu[0]))


def test_atributo_igual_nao_muta() -> None:
    """Um `title` reescrito com o MESMO texto não produz mutação nenhuma."""
    fora = _no_webkit(
        '<b data-campo="dica" data-hef-alvo="atributo" '
        'data-hef-atributo="title">?</b>',
        [{"mesa": {"dica": "o que este botão faz"}}] * 3,
    )
    assert fora["contas"][0] == 2, (
        "a primeira pintura tinha de escrever o selo e o `title` — "
        f"contou {fora['contas'][0]}")
    assert fora["contas"][1:] == [0, 0], (
        "reescrever o MESMO `title` mutou o DOM: a dica dela morre a cada "
        f"tique — {fora['contas']}, detalhe {fora.get('detalhe')}")
    assert fora["pintou"][1:] == [0, 0], (
        "o contador de pinturas mentiu: valor igual não é pintura")


def test_o_atributo_apagado_nao_muta_de_novo() -> None:
    """Apagar um atributo que já não existe também não é mutação."""
    fora = _no_webkit(
        '<b data-campo="dica" data-hef-alvo="atributo" '
        'data-hef-atributo="title">?</b>',
        [{"mesa": {"dica": ""}}] * 3,
    )
    assert fora["contas"] == [1, 0, 0], (
        f"apagar o que não existe mexeu no DOM — {fora['contas']}, "
        f"detalhe {fora.get('detalhe')}")


def test_o_selo_da_visita_escreve_uma_vez_so() -> None:
    """`data-hef-visto` é `'1'` ou é ausência — reescrevê-lo é samba puro."""
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


def test_a_cor_e_o_plastico_repetidos_nao_mutam() -> None:
    """Repetir a mesma cor e o mesmo plástico não mexe no DOM."""
    fora = _no_webkit(
        '<b data-campo="clique" data-hef-alvo="cor">L3</b>'
        '<div data-campo="plastico" data-hef-alvo="plastico">.</div>',
        [{"mesa": {"clique": "#6272a4", "plastico": "#ae335a"}}] * 3,
    )
    assert fora["contas"][1:] == [0, 0], (
        f"a cor ou o `--plastico` mexeram no DOM ao repetir — "
        f"{fora['contas']}, detalhe {fora.get('detalhe')}")


def test_o_bloco_reserializado_nao_e_reescrito() -> None:
    """Um bloco cujo HTML o navegador REESCREVE ao guardar não volta todo tique."""
    fora = _no_webkit(
        "<div id='regua-bloco'>.</div>",
        [{"blocos": {"#regua-bloco": "\n  <b class='x'>a&amp;b</b>\n"}}] * 3,
    )
    assert fora["pintou"] == [1, 0, 0], (
        f"o bloco foi reescrito com o mesmo desenho — {fora['pintou']}")
    assert fora["contas"][1:] == [0, 0], (
        f"o bloco recriou o miolo sem nada ter mudado — {fora['contas']}")


def test_o_html_repetido_nao_muta_mesmo_reserializado() -> None:
    """O navegador devolve a SERIALIZAÇÃO dele, não o texto que entrou."""
    fora = _no_webkit(
        '<div data-campo="miolo" data-hef-alvo="html">.</div>',
        [{"mesa": {"miolo": "\n  <b class='x'>a&amp;b</b>\n"}}] * 3,
    )
    assert fora["contas"][1:] == [0, 0], (
        f"o miolo foi recriado com o mesmo desenho — {fora['contas']}")


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
    """Adiar não é desistir: assim que o voo pousa, o bloco entra inteiro."""
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
    """ZERO. É o número certo, e é o que o produto entrega desde 06/09/2026."""
    assert parada, "o observador não devolveu tabela — a régua ficaria verde sobre nada"
    linhas = parada.get("linhas") or []
    culpados = ", ".join(
        f"{x['campo']}/{x['tipo']}/{x['detalhe']} x{x['n']}" for x in linhas[:6])
    assert parada.get("total") == 0, (
        f"a tela mexeu {parada.get('total')} vezes em {TIQUES} tiques com a "
        f"mesa PARADA — {culpados}")


def test_o_observador_sabe_acusar(parada: dict[str, Any]) -> None:
    """A régua acima só vale se o instrumento souber ver alguma coisa."""
    fora = _no_webkit(
        '<b data-campo="anda">—</b>',
        [{"mesa": {"anda": "um"}}, {"mesa": {"anda": "dois"}},
         {"mesa": {"anda": "três"}}],
    )
    assert fora["contas"] == [2, 1, 1], (
        f"o observador não viu três mudanças de verdade — {fora['contas']}")


def test_o_tique_nao_enfileira_com_a_ponte_lenta() -> None:
    """Com a ponte lenta, o piloto PULA — ele não empilha pintura sobre pintura."""
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
    """A fita é o caso EXTREMO do bloco: ela troca o próprio nó, não o miolo."""
    fora = _no_webkit(
        "",
        [{"fita": '<div class="fita">a fita nova</div>'}] * 3,
        preparo=("(function(){const f=document.querySelector('.fita');"
                 "f.firstElementChild.classList.add('hef-em-voo');})()"),
        raiz="document.querySelector('.fita').parentElement",
    )
    assert fora["pintou"] == [0, 0, 0], (
        f"a fita foi trocada com um chip em voo dentro — {fora['pintou']}")
    assert fora["contas"][1:] == [0, 0], (
        f"a fita mexeu no DOM com um chip em voo dentro — {fora['contas']}")


def test_a_largura_normalizada_pelo_cssom_nao_reconta() -> None:
    """`5.0%` escrito volta `5%` lido — e o contador não pode somar por isso."""
    fora = _no_webkit(
        '<i data-campo="barra" data-hef-alvo="largura" style="width:0%"></i>'
        '<i data-campo="alto" data-hef-alvo="altura" style="height:0%"></i>',
        [{"mesa": {"barra": "5.0", "alto": "22.0"}}] * 3,
    )
    assert fora["pintou"] == [2, 0, 0], (
        f"a largura/altura foi recontada com o mesmo valor — {fora['pintou']}. "
        "O CSSOM normalizou `5.0%` para `5%` e a comparação antes da escrita "
        "nunca casa")
    assert fora["contas"][1:] == [0, 0], (
        f"a largura mexeu no DOM ao repetir — {fora['contas']}")


def test_a_largura_invalida_nao_conta_pintura() -> None:
    """O travessão de um lugar sem dono não é largura, e não soma pintura."""
    fora = _no_webkit(
        '<i data-campo="barra" data-hef-alvo="largura" style="width:0%"></i>',
        [{"mesa": {"barra": None}}] * 3,
    )
    assert fora["pintou"] == [0, 0, 0], (
        f"o travessão contou como pintura numa barra — {fora['pintou']}")
