"""O número da barra acompanha a alavanca — O-NUMERO-DA-BARRA-NAO-CONGELA-NO-VALOR-VELHO-01.

O QUE SE MEDIU (08/10/2026, no piloto, em lar de mentira): duas barras da mesma
coluna mexidas seguidas. A Força ficou mostrando 3 com a alavanca em 8, e o gesto
seguinte mandou o 3 ao daemon (`trigger.set [0,9,3,60]`). Na base, a Amplitude B
mostrou 3 contra 60.

A CAUSA, medida aqui: a coluna da aba Gatilhos se troca por BLOCO, e o bloco não se
troca enquanto a alavanca está em voo. O gesto da segunda barra recolhia a coluna
pelo TEXTO do `.num` da primeira, que só muda quando o pacote devolve o bloco novo.
Arrastar antes disso mandava ao aparelho o número velho por cima do que a mão tinha
acabado de pôr.

A RÉGUA RODA NO TEMPO: dez voltas, alternando a ordem das barras e o ritmo (a
segunda barra depois do pouso da primeira, ou antes dele, com um tique no meio).
Ela usa o BOOTSTRAP do piloto num WebKit oculto, a página PUBLICADA e o pacote de
verdade (o tique e o gesto `ajuste`); só a ponte com o daemon é dublê, e ela grava
o que receberia. Em toda volta, o número mostrado e o valor mandado são os da
alavanca.

A MORDIDA: em `hefesto_vivo.BOOTSTRAP`, faça `alavanca_do_numero` devolver `null`
— o gesto volta a ler o texto, e as voltas em que a segunda barra vem antes do
pouso reprovam com o número velho no `trigger.set`.
"""
from __future__ import annotations

import json
import pathlib
import sys
from collections.abc import Callable
from typing import Any

import pytest
from tests.unit._mundo_da_aba_03 import SO_NA_PAGINA_ANTIGA

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface"))

PAGINA = "03-gatilhos.html"
UNIQ = "aa:bb:cc:00:00:01"
FALSO = {"uniq": UNIQ, "player": 1, "transport": "usb", "is_primary": True,
         "inputs": {"l2_raw": 0, "r2_raw": 0}}
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "USB", "cor": "starlight-blue", "mascara": "DualSense"}]
APLICOU = {"status": "ok", "aplicado_em": [UNIQ], "guardado_em": []}
CAIXA = '[data-controle="p1"] .ajustes.e'
VOLTAS = 10

_PERFIL_DA_CENA: dict[str, Any] = {}


class _Ponte:
    """A ponte que aceita e grava o que o daemon receberia."""

    def __init__(self) -> None:
        self.enviados: list[list[int]] = []

    def trigger_set_detalhado(self, lado: str, modo: str, params: list[int],
                              **_k: Any) -> tuple[bool, str, dict[str, Any]]:
        self.enviados.append(list(params))
        return True, "", APLICOU


@pytest.fixture
def a03() -> Any:
    import pacotes  # noqa: F401  (registra as dez)
    from pacotes import a03_gatilhos, perfil

    original = perfil.ativo
    perfil.ativo = lambda _nome: dict(_PERFIL_DA_CENA)
    a03_gatilhos.esquecer_o_rascunho()
    yield a03_gatilhos
    a03_gatilhos.esquecer_o_rascunho()
    perfil.ativo = original
    _PERFIL_DA_CENA.clear()


def _ctx() -> Any:
    from pacotes import Contexto

    _PERFIL_DA_CENA.clear()
    _PERFIL_DA_CENA.update({
        "triggers": {"left": {"mode": "Machine", "params": [0, 9, 3, 60]},
                     "right": {"mode": "Off", "params": []}},
        "controllers": {},
    })
    return Contexto(state={"active_profile": "régua"}, mesa=MESA,
                    conectados=[FALSO], estados={})


def _carga(a03: Any, ctx: Any) -> dict[str, Any]:
    """O tique da aba, com a coluna no endereço da página (o `pref`)."""
    p = a03.pacote(ctx)
    return {"blocos": {CAIXA: p["blocos"][CAIXA]},
            "colunas": {"p1": {k: v for k, v in p["colunas"][UNIQ].items()
                               if k.startswith("modo-chave")}}}


#: O canal do piloto vira uma fila que a régua esvazia a cada passo.
CANAL = r"""
window.__recebido = [];
window.webkit = {messageHandlers: {hefesto: {
  postMessage: function(s){ window.__recebido.push(s); }}}};
"""

#: A mão: muda a alavanca como o arrasto muda (a PROPRIEDADE) e solta.
MAO = r"""
window.__arrastar = function(i, v){
  const r = document.querySelector(CAIXA + ' input[data-i="' + i + '"]');
  if(!r) return 'sem alavanca ' + i;
  r.value = String(v);
  r.dispatchEvent(new Event('input', {bubbles: true}));
  r.dispatchEvent(new Event('change', {bubbles: true}));
  return '';
};
window.__ler = function(){
  const fora = [];
  for(const b of document.querySelectorAll(CAIXA + ' .barra')){
    const r = b.querySelector('input[type="range"]');
    const n = b.querySelector('.num');
    const c = b.querySelector('.cheio');
    const o = b.querySelector('.nome');
    fora.push({alavanca: r ? r.value : null, num: n ? n.textContent.trim() : null,
               cheio: c ? c.style.width : null, nome: o ? o.textContent.trim() : null});
  }
  return fora;
};
window.__esvaziar = function(){
  const s = window.__recebido; window.__recebido = []; return s;
};
""".replace("CAIXA", json.dumps(CAIXA))


def _no_webkit(passos: list[Callable[[Any], str]]) -> list[Any]:
    """Roda os passos em série no WebKit oculto; cada um vê a resposta do anterior."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    import hefesto_vivo as hv
    from hefesto_dualsense4unix.interface import onde

    saidas: list[Any] = []
    erro: list[str] = []
    janela = Gtk.OffscreenWindow()
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def proximo(v: Any) -> None:
        if len(saidas) == len(passos):
            Gtk.main_quit()
            return
        try:
            js = passos[len(saidas)](saidas[-1] if saidas else None)
        except Exception as e:  # o passo é Python: a falha sai com o nome, sem esperar a guarda
            erro.append(f"o passo {len(saidas)} quebrou no Python: {e!r}")
            Gtk.main_quit()
            return
        v.evaluate_javascript(js, -1, None, None, None, voltou)

    def voltou(v: Any, res: Any) -> None:
        try:
            saidas.append(json.loads(v.evaluate_javascript_finish(res).to_string()))
        except Exception as e:  # pragma: no cover — só quando o roteiro quebra
            erro.append(f"o passo {len(saidas)} quebrou: {e}")
            Gtk.main_quit()
            return
        proximo(v)

    def bootou(v: Any, res: Any) -> None:
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:  # pragma: no cover
            erro.append(f"o BOOTSTRAP quebrou: {e}")
            Gtk.main_quit()
            return
        proximo(v)

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(CANAL + MAO + hv.BOOTSTRAP, -1, None, None,
                                  None, bootou)

    view.connect("load-changed", carregou)
    view.load_uri(onde.pagina(PAGINA, publicado=True).as_uri())
    guarda = GLib.timeout_add(60000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert not erro, erro[0]
    assert len(saidas) == len(passos), "o WebKit não respondeu em 60 s"
    return saidas


def _pintar(carga: dict[str, Any]) -> str:
    return (f"(function(){{ window.__hef.pintar({json.dumps(carga, ensure_ascii=False)});"
            f" return JSON.stringify(window.__ler()); }})()")


def _arrastar(i: int, v: int, *, tique: dict[str, Any] | None = None) -> str:
    """Arrasta uma barra; com `tique`, o piloto pinta logo depois, com o voo no ar."""
    depois = (f"window.__hef.pintar({json.dumps(tique, ensure_ascii=False)});"
              if tique else "")
    return (f"(function(){{ const e = window.__arrastar({i}, {v}); {depois}"
            f" return JSON.stringify({{erro: e, ler: window.__ler()}}); }})()")


@SO_NA_PAGINA_ANTIGA
def test_o_numero_e_o_valor_mandado_sao_os_da_alavanca_em_dez_voltas(a03: Any) -> None:
    """Duas barras seguidas, dez voltas alternadas: nenhum número velho chega ao aparelho."""
    from pacotes import gesto_da_pagina

    acao = gesto_da_pagina(PAGINA, "ajuste")
    assert acao is not None, "o gesto `ajuste` perdeu o dono"
    ctx = _ctx()
    ponte = _Ponte()
    mandados: list[dict[str, Any]] = []
    #: (índice, valor) de cada barra em cada volta: a Força (2) e a Frequência
    #: (3) da Metralhadora, a ordem trocando a cada volta.
    forca = [4, 8, 6, 2, 7, 1, 5, 8, 3, 6]
    frequencia = [20, 30, 34, 40, 48, 50, 62, 70, 76, 90]
    voltas = [((2, forca[k]), (3, frequencia[k])) if k % 2 == 0
              else ((3, frequencia[k]), (2, forca[k])) for k in range(VOLTAS)]
    falhas: list[str] = []

    def gesto(_saida: Any) -> str:
        """O Python atende o que o canal recebeu e devolve o pouso de cada voo."""
        pousos = []
        for s in _saida if isinstance(_saida, list) else []:
            o = json.loads(s)
            if o.get("gesto") != "ajuste":
                continue
            o["uniq"] = UNIQ if o.get("controle") == "p1" else ""
            mandados.append(o)
            acao(ctx, o, ponte)
            pousos.append(f"window.__hef.voltouDoVoo({json.dumps(o['voo'])}, true);")
        return "".join(pousos)

    def esvaziar(_s: Any) -> str:
        return "JSON.stringify(window.__esvaziar())"

    def arrasto(i: int, v: int, *, com_tique: bool = False) -> Callable[[Any], str]:
        def passo(_s: Any) -> str:
            return _arrastar(i, v, tique=_carga(a03, ctx) if com_tique else None)
        return passo

    passos: list[Callable[[Any], str]] = [lambda _s: _pintar(_carga(a03, ctx))]
    #: Onde cada volta termina: o índice do passo que lê a coluna depois do último pouso.
    fins: list[int] = []
    for k, ((i1, v1), (i2, v2)) in enumerate(voltas):
        if k % 2 == 1:
            # A SEGUNDA BARRA ANTES DO POUSO, com um tique no meio: o bloco fica
            # adiado pelo voo, e o `.num` da primeira ainda tem o número de antes.
            passos += [
                arrasto(i1, v1, com_tique=True),
                arrasto(i2, v2),
                esvaziar,
            ]
        else:
            passos += [
                arrasto(i1, v1),
                esvaziar,
                lambda s: "(function(){ " + gesto(s) + " return '0'; })()",
                lambda _s: _pintar(_carga(a03, ctx)),
                arrasto(i2, v2),
                esvaziar,
            ]
        passos += [
            lambda s: "(function(){ " + gesto(s) + " return '0'; })()",
            lambda _s: _pintar(_carga(a03, ctx)),
        ]
        fins.append(len(passos) - 1)

    saidas = _no_webkit(passos)

    esperado = [0, 9, 3, 60]
    for k, ((i1, v1), (i2, v2)) in enumerate(voltas):
        esperado[i1] = v1
        esperado[i2] = v2
        lido = saidas[fins[k]]
        alavancas = [int(b["alavanca"]) for b in lido]
        nums = [int(b["num"]) for b in lido]
        if alavancas != esperado or nums != esperado:
            falhas.append(f"volta {k}: alavanca {alavancas}, número {nums}, "
                          f"a mão pôs {esperado}")
    # O QUE O DAEMON RECEBEU: o último envio de cada volta é a coluna inteira da mão.
    quer = [0, 9, 3, 60]
    por_volta = iter(ponte.enviados)
    for k, ((i1, v1), (i2, v2)) in enumerate(voltas):
        quer[i1] = v1
        primeiro = next(por_volta, None)
        quer[i2] = v2
        segundo = next(por_volta, None)
        if segundo != quer:
            falhas.append(f"volta {k}: o daemon recebeu {primeiro} e {segundo}, "
                          f"e a mão pôs {quer}")
    assert len(mandados) == 2 * VOLTAS, (
        f"cada arrasto é um gesto: {len(mandados)} de {2 * VOLTAS}")
    assert not falhas, (
        "o número da barra congelou no valor velho, e o gesto seguinte o mandou "
        "ao aparelho:\n" + "\n".join(falhas))


def _so_o_arrasto(i: int, v: int) -> str:
    """O dedo ainda na barra: só o `input`, sem o `change` de soltar."""
    return ("(function(){ const r = document.querySelector(" + json.dumps(CAIXA)
            + f" + ' input[data-i=\"{i}\"]'); r.value = '{v}';"
            " r.dispatchEvent(new Event('input', {bubbles: true}));"
            " return JSON.stringify(window.__ler()); })()")


def _o_voo_do_ajuste(recebido: list[str]) -> str:
    """O voo do único `ajuste` que o canal recebeu (o canal também leva o aviso da vista)."""
    voos = [o["voo"] for o in map(json.loads, recebido) if o.get("gesto") == "ajuste"]
    assert len(voos) == 1, recebido
    return str(voos[0])


@SO_NA_PAGINA_ANTIGA
def test_o_arrasto_leva_o_numero_e_a_recusa_devolve_os_dois(a03: Any) -> None:
    """Arrastando, o número e o `.cheio` seguem a mão; recusado, voltam ao que o aparelho tem.

    A MORDIDA: tire o `seguir_a_alavanca(ev.target)` do ouvinte de `input` e o número fica no 3
    durante o arrasto; tire a volta do `certo === false` no `voltouDoVoo` e a tela diz 7 sobre um
    gatilho que ficou no 3.
    """
    ctx = _ctx()
    carga = _carga(a03, ctx)
    saidas = _no_webkit([
        lambda _s: _pintar(carga),
        lambda _s: _so_o_arrasto(2, 7),
        lambda _s: _arrastar(2, 7),
        lambda _s: "JSON.stringify(window.__esvaziar())",
        lambda s: ("(function(){ window.__hef.voltouDoVoo("
                   + json.dumps(_o_voo_do_ajuste(s)) + ", false);"
                   " return JSON.stringify(window.__ler()); })()"),
    ])
    antes, arrastando, pousou = saidas[0], saidas[1], saidas[4]
    assert antes[2]["num"] == "3" and antes[2]["alavanca"] == "3", antes
    assert arrastando[2]["alavanca"] == "7" and arrastando[2]["num"] == "7", (
        f"o número não seguiu a mão durante o arrasto: {arrastando[2]}")
    assert arrastando[2]["cheio"] == "86%", (
        f"o `.cheio` não seguiu a mão (Força 1..8, 7 é 86%): {arrastando[2]}")
    assert [b["nome"] for b in arrastando] == [b["nome"] for b in antes], (
        "o rótulo da barra virou número: o par pegou o vizinho errado")
    voltou = (pousou[2]["alavanca"], pousou[2]["num"], pousou[2]["cheio"])
    assert voltou == ("3", "3", antes[2]["cheio"]), (
        f"a recusa deixou a tela no 7 com o aparelho no 3: {pousou[2]}")


@SO_NA_PAGINA_ANTIGA
def test_a_forma_le_a_alavanca_mesmo_com_o_texto_do_numero_velho(a03: Any) -> None:
    """O gesto recolhe a coluna pela alavanca, nunca pelo texto do `.num`.

    O seguir da alavanca já põe o texto em dia a cada arrasto; esta régua guarda a segunda
    metade da cura, que as outras não separam: se qualquer pintura deixar o texto do número
    atrás da alavanca (o bloco adiado pelo voo, ou um tique que pinte o `aj-val-*` pelo
    campo), a forma ainda manda o que a mão pôs. Medido na conferência (09/10/2026): tirar só
    o `par ? String(par.value)` da forma passava nas duas réguas de cima.

    A MORDIDA: na forma do BOOTSTRAP, troque o `par ? String(par.value)` por
    `false ? String(par.value)`: o gesto da Frequência leva a Força pelo texto, 3, e não 8.
    """
    ctx = _ctx()
    carga = _carga(a03, ctx)
    numero_velho = ("(function(){ const n = document.querySelector(" + json.dumps(CAIXA)
                    + " + ' .barra[data-ajuste=\"e-2\"] .num'); n.textContent = '3';"
                    " return JSON.stringify(window.__ler()); })()")
    saidas = _no_webkit([
        lambda _s: _pintar(carga),
        lambda _s: _so_o_arrasto(2, 8),
        lambda _s: numero_velho,
        lambda _s: "JSON.stringify(window.__esvaziar())",
        lambda _s: _arrastar(3, 50),
        lambda _s: "JSON.stringify(window.__esvaziar())",
    ])
    assert saidas[2][2] == {**saidas[2][2], "alavanca": "8", "num": "3"}, saidas[2]
    formas = [o.get("forma") or {} for o in map(json.loads, saidas[5])
              if o.get("gesto") == "ajuste"]
    assert len(formas) == 1, saidas[5]
    assert formas[0].get("aj-val-e-2") == "8", (
        f"a forma leu o texto do número, e não a alavanca: {formas[0]}")
    assert formas[0].get("aj-val-e-3") == "50", formas[0]
