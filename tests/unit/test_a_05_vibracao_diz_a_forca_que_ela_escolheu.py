#!/usr/bin/env python3
"""A ABA VIBRAÇÃO: o número da força é o que ela ESCOLHEU, e o punho aceso é o
que TREME de verdade.

TRÊS COISAS, e as três foram medidas em 03/09/2026 contra o daemon dela, com
dois controles na mesa (um no cabo, um por rádio).

1. **O NÚMERO DO MULTIPLICADOR ESTAVA MORTO.** A aba montava a barra
   "Personalizado" com ``state_full.rumble_mult_applied``. Cliquei os QUATRO
   degraus pela mesma porta que o botão da coluna usa
   (``rumble_policy_set_checked``) e reli o estado a cada um:

       policy_set(max       ) → policy='max'        applied=0.7
       policy_set(economia  ) → policy='economia'   applied=0.7
       policy_set(auto      ) → policy='auto'       applied=0.7
       policy_set(balanceado) → policy='balanceado' applied=0.7

   O daemon obedeceu as quatro vezes. O número que a tela mostra **não se moveu
   uma vez** — ficou em ``70%``, com a coluna acendendo "Balanceado", cujo
   multiplicador é ``1,0``. A dica dela, duas linhas acima na mesma tela,
   promete *"Balanceado 100%, como o jogo pediu"*. A tela se contradizia sozinha,
   e o ``Máx`` nunca acendia nem no "Máximo".

   O produto já sabia por escrito: ``daemon/lifecycle.py:2212-2221`` conta que
   ``_last_auto_mult`` fica **preso no default 0.7** em passthrough ocioso e que
   isso *"parecia atenuação real do rumble do jogo"*. A aba publicava
   exatamente essa aparência.

   A CURA É PONTE, e não conta nova: ``app/telas/vibracao._pedido_da_politica``
   é a MESMA linha da janela estável (``rumble_actions._pintar_a_linha_do_
   teto:537``), e ``_barra`` é o mesmo formatador das duas barras de motor.

2. **O PUNHO ACESO ERA O DA CENA DO MOCKUP.** O ``svg(acesos=…)`` funde a classe
   ``acesa`` na geração, e a página nasce com o motor DIREITO do P1 e o
   ESQUERDO do P2 acesos — para sempre, com a mesa parada e ``vpads == 0``. E o
   dado existia: ``pacote_da_coluna`` devolve ``treme`` por lado desde que
   nasceu, e o CSS que acende também. O valor era jogado fora entre um e outro.

3. **FRASES DA JANELA ESTÁVEL NÃO TINHAM ATRAVESSADO** — o teto da mesa (nos
   quatro tooltips de degrau) e a nota do card "Testar motores". Eram TRÊS até
   05/09/2026: a dos 5 segundos explicava o Modo Auto, que saiu desta tela por
   decisão dela. Elas são LIDAS, nunca redigitadas — uma segunda cópia de texto
   de tela diverge na primeira edição.

   **E O DONO MUDOU DE CASA EM 06/09/2026.** A fonte era o ``gui/main.glade``;
   a ``GTK-2`` deu às duas o dono ``app/telas/vibracao.py``, que é MOTOR e fica
   (``D-0609-GTK-LEVA-INTEIRA``). O nome público das constantes é o mesmo.

AS MORDIDAS, todas com ``cp`` para devolver:

* volte ``pct = col.get("pct")`` em ``a05_vibracao.pacote`` →
  ``test_o_multiplicador_e_o_pedido_do_degrau`` reprova nos quatro degraus, e
  ``test_o_max_acende_so_no_teto`` reprova dizendo que o "Máximo" não acende;
* apague a chamada de ``_endereca_o_tremor`` em ``aba05._coluna`` e rode o
  gerador → o próprio ``_conferir`` para a geração, e
  ``test_o_desenho_tem_endereco_para_os_dois_punhos`` reprova;
* apague o laço do ``treme`` no pacote →
  ``test_o_pacote_emite_o_tremor_que_o_produto_calculou`` reprova;
* tire ``{DICA_DO_TETO_DA_MESA}`` da dica e regere →
  ``test_as_frases_da_janela_estavel_estao_na_aba`` reprova nomeando qual;
* tire a guarda ``if vez != _VEZ[0]`` do gesto ``testar`` →
  ``test_um_segundo_testar_cancela_o_primeiro`` reprova.

ONDE ELA MEDE: na **BANCADA**, que é onde o gerador escreve e onde os endereços
existem. A página publicada só os recebe no ``--publicar 05``, que é ato dela.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.app.telas import vibracao as _tela

PAGINA = "05-vibracao.html"

UNIQS = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02")

APLICADO_PRESO = 0.7

PAR_NO_FISICO = (0, 200)


def _estado(policy: str = "balanceado", *, per_vpad: list | None = None) -> dict:
    """Um ``state_full`` de mentira com o multiplicador PRESO, como o dela."""
    return {
        "rumble_policy": policy,
        "rumble_mult_applied": APLICADO_PRESO,
        "active_profile": "regua",
        "rumble_ff": {"plays": 0, "nao_nulos": 0, "vpads": len(per_vpad or []),
                      "per_vpad": per_vpad or []},
    }


def _ctx(policy: str = "balanceado", *, per_vpad: list | None = None):
    """Um tique de mentira com dois controles — o pacote não toca o aparelho."""
    import pacotes

    conectados = [
        {"uniq": u, "player": i, "connected": True, "index": i - 1,
         "is_primary": i == 1, "transport": "usb" if i == 1 else "bt",
         "battery_pct": 90, "inputs": {}}
        for i, u in enumerate(UNIQS, start=1)
    ]
    mesa = [{"pref": f"p{i}", "jogador": i, "uniq": u, "nome": "Régua",
             "via": "USB" if i == 1 else "BT", "cor": "starlight-blue",
             "plastico": "#123456", "conectado": True}
            for i, u in enumerate(UNIQS, start=1)]
    return pacotes.Contexto(state=_estado(policy, per_vpad=per_vpad),
                            mesa=mesa, conectados=conectados, estados={})


def _pacote(policy: str = "balanceado", *, per_vpad: list | None = None) -> dict:
    import pacotes

    return pacotes.pacote_da_pagina(PAGINA, _ctx(policy, per_vpad=per_vpad)) or {}


@pytest.fixture(scope="module")
def bancada() -> str:
    import onde

    arq = onde.pagina(PAGINA)
    assert arq.exists(), f"a bancada não tem {PAGINA} — rode `python3 aba05.py`"
    return arq.read_text(encoding="utf-8")


def _bloco_do_lugar(html: str, pref: str) -> str:
    """O HTML de UM lugar da mesa, do `<div class="ctrl…">` até o próximo."""
    import re

    ate_a_faixa = html.split('class="vib-estado"', 1)[0]
    for pedaco in ate_a_faixa.split('<div class="ctrl')[1:]:
        achado = re.search(r'data-controle="(p\d+)"', pedaco.split(">", 1)[0])
        if achado and achado.group(1) == pref:
            return pedaco
    raise AssertionError(f"a bancada não tem o lugar {pref!r}")


def test_o_multiplicador_e_o_pedido_do_degrau() -> None:
    """O que a tela escreve é o multiplicador do degrau ACESO.

    O ESPERADO NÃO É DIGITADO: sai de ``app/telas/vibracao._escada()``, que é a
    única cópia autorizada em ``app/`` (``rumble_actions._POLICY_MULT``).
    Digitar ``100`` aqui seria a terceira tabela de degraus, e a régua ficaria
    verde no dia em que o produto mudasse o Balanceado.
    """
    escada = _tela._escada()
    for degrau in _tela.degraus_da_forca():
        esperado = f"{round(escada[degrau] * 100)}%"
        for uniq, col in _pacote(degrau)["colunas"].items():
            assert col["mult"] == esperado, (
                f"com o degrau {degrau!r} a coluna {uniq} escreveu "
                f"{col['mult']!r} — o produto pede {esperado}")


def test_o_multiplicador_nao_e_o_campo_preso() -> None:
    """A régua que separa a cura do defeito, e ela é uma só linha."""
    preso = f"{round(APLICADO_PRESO * 100)}%"
    escritos = {
        degrau: {col["mult"] for col in _pacote(degrau)["colunas"].values()}
        for degrau in _tela.degraus_da_forca()
    }
    assert all(v != {preso} for v in escritos.values()), (
        f"a aba voltou a mostrar o multiplicador PRESO ({preso}) — {escritos}")
    assert len({tuple(v) for v in escritos.values()}) > 1, (
        "os quatro degraus escreveram o MESMO número: o valor não acompanha a "
        f"escolha dela — {escritos}")


def test_o_cursor_da_barra_acompanha_o_pedido() -> None:
    """O cursor e o número contam a mesma história, e o cursor sai SEM `%`."""
    for degrau, mult in _tela._escada().items():
        esperado = f"{round(mult * 100)}"
        for col in _pacote(degrau)["colunas"].values():
            assert col["mult-pos"] == esperado, (
                f"o cursor do degrau {degrau!r} saiu em {col['mult-pos']!r}")
            assert "%" not in col["mult-pos"], "o cursor voltou a levar `%`"


def test_o_max_acende_so_no_teto() -> None:
    """O ``Máx`` é booleano e diz UMA coisa: este número é o topo da barra.

    **O TETO TROCOU DE DONO EM 03/09/2026**, e é a decisão dela: a barra deixou
    de parar no degrau ``Máximo`` (150) e vai até onde ela pode ARRASTAR —
    ``a05_vibracao.teto_da_barra()``, que sai do ``RUMBLE_CUSTOM_MULT_MAX`` do
    esquema. Consequência medida, e é o ponto deste caso: **nenhum dos quatro
    degraus acende o `Máx`**, nem o "Máximo" — ele não é mais o topo. Quem
    acende é a barra arrastada até o fim.

    MORDIDA: em ``a05_vibracao._no_teto``, volte a comparar com
    ``_tela.teto_da_barra()`` (150) — este caso reprova no ``max``, com o `Máx`
    aceso e um quarto da barra ainda por percorrer.
    """
    from pacotes import a05_vibracao as a05

    teto = a05.teto_da_barra()
    for degrau, mult in _tela._escada().items():
        no_teto = round(mult * 100) >= teto
        for col in _pacote(degrau)["colunas"].values():
            aceso = bool(col["mult-teto"])
            assert aceso is no_teto, (
                f"o degrau {degrau!r} vale {round(mult * 100)}% e o teto é "
                f"{teto}%: o `Máx` saiu {'aceso' if aceso else 'apagado'}")
    assert a05._no_teto({"n": f"{teto}%", "sabe": "1"}) == "1", (
        "o `Máx` não acende nem no topo da barra: ele virou enfeite")


def test_degrau_que_o_produto_nao_conhece_nao_afirma_numero() -> None:
    """Daemon velho, chave nova: a tela diz `—`, nunca um número plausível.

    ``_pedido_da_politica`` devolve ``None`` fora dos quatro, e ``_barra(None…)``
    devolve o travessão com ``sabe = ""`` — campo sem informação não acende o
    ``Máx`` nem afirma largura.
    """
    for col in _pacote("")["colunas"].values():
        assert col["mult"] == "—", f"a tela inventou {col['mult']!r}"
        assert col["mult-teto"] == "", "o `Máx` acendeu sobre um não-sei"


def test_o_desenho_tem_endereco_para_os_dois_punhos(bancada) -> None:
    """Os dois grupos de motor do SVG são endereçáveis, e a classe é a do desenho.

    ``data-hef-classe="acesa"`` porque quem escolheu o nome foi o SVG
    compartilhado, e não esta aba: o alvo ``classe`` do pintor usa ``on`` por
    omissão, e sem o atributo ele acenderia uma classe que o CSS não conhece —
    pintura contada, tela igual.

    A CONTA É POR LUGAR DESDE 07/09/2026, e era por "coluna viva". A troca é
    cura de defeito medido com os quatro DualSense dela na mesa: o lugar VAZIO
    era um cartão à parte, sem um único ``data-campo``, e o ``treme-e``/
    ``treme-d`` que o pacote emite para os QUATRO lugares chegava sem ter onde
    pousar. Contar ``colunas vivas`` era medir o desenho, não a mesa dela.
    """
    from hefesto_dualsense4unix.interface import aba05
    lugares = len(aba05.MESA)
    assert bancada.count("data-controle=\"p") == lugares, (
        f"a bancada não tem os {lugares} lugares — não há o que medir")
    for sigla in ("e", "d"):
        alvo = (f'data-campo="treme-{sigla}" data-hef-alvo="classe"'
                f' data-hef-classe="acesa"')
        assert bancada.count(alvo) == lugares, (
            f"o punho {sigla!r} não tem endereço em cada um dos {lugares} "
            f"lugares da mesa")


def test_o_lugar_vazio_nao_afirma_tremor(bancada) -> None:
    """Um lugar sem controle não acende punho nenhum, nem por engano."""
    from hefesto_dualsense4unix.interface import aba05
    vazios = [c["pref"] for c in aba05.MESA if not c.get("conectado", True)]
    assert vazios, "a mesa do desenho não tem lugar vazio — não há o que medir"
    for pref in vazios:
        bloco = _bloco_do_lugar(bancada, pref)
        assert 'data-campo="treme-' in bloco, (
            f"o lugar vazio {pref} perdeu o endereço do tremor — o pacote emite "
            f"`treme-e`/`treme-d` para os quatro lugares, e sem endereço o dado "
            f"do controle que chegar ali não tem onde pousar")
        assert " acesa" not in bloco, (
            f"o lugar vazio {pref} nasceu com um punho ACESO")


def test_o_pacote_emite_o_tremor_que_o_produto_calculou() -> None:
    """O lado que recebeu força acende; o outro APAGA — e o produto é quem diz."""
    vpad = {"player": 1, "rumble_no_fisico": list(PAR_NO_FISICO),
            "rumble_no_fisico_ha_s": 0.1, "last_weak": PAR_NO_FISICO[0],
            "last_strong": PAR_NO_FISICO[1]}
    pac = _pacote(per_vpad=[vpad])
    col = pac["colunas"][UNIQS[0]]

    por_motor = dict(zip(("weak", "strong"), PAR_NO_FISICO, strict=True))
    for lado, motor in _tela.LADO_PARA_MOTOR.items():
        deveria = "1" if por_motor[motor] else ""
        assert col[f"treme-{lado}"] == deveria, (
            f"o lado {lado!r} é o motor {motor!r} = {por_motor[motor]} e a aba "
            f"emitiu {col[f'treme-{lado}']!r}")

    outra = pac["colunas"][UNIQS[1]]
    assert outra["treme-e"] == "" and outra["treme-d"] == "", (
        f"a coluna sem gamepad virtual afirmou tremor: {outra}")


def test_a_mesa_parada_nao_acende_punho_nenhum() -> None:
    """``vpads == 0`` é o estado corrente da mesa dela, e nele nada treme."""
    for uniq, col in _pacote()["colunas"].items():
        assert col["treme-e"] == "" and col["treme-d"] == "", (
            f"a coluna {uniq} acendeu um punho com a mesa parada: {col}")


NO_DONO = (
    "DICA_DO_TETO_DA_MESA",
    "DICA_DOS_VALORES_QUE_PASSAM",
)


def test_as_frases_da_janela_estavel_estao_na_aba(bancada) -> None:
    """A aba nova diz o que o DONO ensina, com as MESMAS palavras.

    Não é preciosismo de texto: cada uma responde a uma pergunta que a aba nova
    deixava sem resposta — que o teto do orçamento existe ANTES de ele morder, e
    que o "Testar" passa pelo degrau antes de chegar ao controle.

    **ERAM TRÊS ATÉ 05/09/2026.** A terceira era *"Espera 5 segundos antes de
    trocar de faixa"*, e ela explicava o Modo Auto — que saiu desta tela por
    decisão dela (*"segue os três modos sempre"*, ver `aba05.FORCA`).

    **E A FONTE MUDOU EM 06/09/2026** (`GTK-3`, primeira volta): a régua lia o
    XML da janela, que está saindo. Quem responde agora é `app/telas/vibracao`,
    o dono que a `GTK-2` deu às duas frases — o mesmo lugar de onde o gerador
    da aba as lê. A pergunta medida não mudou uma vírgula: as duas telas dizem
    o mesmo, ou esta régua reprova.

    MORDIDA: troque uma letra de `DICA_DO_TETO_DA_MESA` em
    `app/telas/vibracao.py` sem regerar a aba — este caso reprova nomeando a
    constante.
    """
    from hefesto_dualsense4unix.app.telas import vibracao

    for nome in NO_DONO:
        frase = getattr(vibracao, nome, None)
        assert frase, (
            f"{nome} saiu de `app/telas/vibracao` — a âncora do gerador da aba "
            "05 também cai")
        assert frase.strip() in bancada, (
            f"a aba perdeu {nome}: {frase!r}. Regere com `python3 aba05.py`")


class _PonteDeMentira:
    """Anota o que foi chamado, na ordem. Não fala com daemon nenhum."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def chamar(self, metodo, **_kw):
        self.chamadas.append(metodo)
        return True

    def rumble_set_checked(self, *_a, **_kw):
        self.chamadas.append("rumble.set")
        return (True, None)

    def rumble_stop(self, *_a, **_kw):
        self.chamadas.append("rumble.stop")
        return True

    def rumble_passthrough(self, *_a, **_kw):
        self.chamadas.append("rumble.passthrough")
        return True

    def rumble_stop_checked(self, *_a, **_kw):
        self.chamadas.append("rumble.stop")
        return (True, None)

    def rumble_motores_set(self, *_a, **_kw):
        self.chamadas.append("rumble.motores.set")
        return (True, {"status": "ok"})


def test_o_testar_fica_ligado_e_so_o_parar_desliga() -> None:
    """O "Testar" é ESTADO, não pulso — e quem o encerra é ela."""
    import pacotes
    from pacotes import a05_vibracao as a05

    a05.parar_o_teste()
    ctx, clique = _ctx(), {"uniq": UNIQS[0]}

    p1 = _PonteDeMentira()
    pacotes.gesto_da_pagina(PAGINA, "testar")(ctx, clique, p1)
    assert p1.chamadas == ["controller.target.set", "rumble.set"], (
        f"o Testar não pode parar sozinho: {p1.chamadas}")
    assert a05.em_teste() == UNIQS[0], "o Testar não ficou ligado"

    p2 = _PonteDeMentira()
    pacotes.gesto_da_pagina(PAGINA, "testar")(ctx, {"uniq": UNIQS[1]}, p2)
    assert a05.em_teste() == UNIQS[1], "o segundo Testar não tomou o lugar"

    p3 = _PonteDeMentira()
    pacotes.gesto_da_pagina(PAGINA, "parar")(ctx, {"uniq": UNIQS[1]}, p3)
    assert p3.chamadas == ["controller.target.set", "rumble.stop",
                           "rumble.passthrough"], p3.chamadas
    assert a05.em_teste() == "", (
        "o Parar não apagou a marca — o próximo arraste de barra "
        "ressuscitaria o tremor de um teste que ela encerrou")


def test_a_barra_so_refresca_o_controle_que_esta_em_teste() -> None:
    """O "ao vivo": arrastar a barra reenvia o par — e só a quem está testando."""
    import pacotes
    from pacotes import a05_vibracao as a05

    a05.parar_o_teste()
    ctx = _ctx()

    p = _PonteDeMentira()
    pacotes.gesto_da_pagina(PAGINA, "motor")(
        ctx, {"uniq": UNIQS[0], "lado": "e", "valor": "50"}, p)
    assert "rumble.set" not in p.chamadas, (
        f"a barra vibrou sem teste ligado: {p.chamadas}")

    pacotes.gesto_da_pagina(PAGINA, "testar")(ctx, {"uniq": UNIQS[0]},
                                              _PonteDeMentira())
    p = _PonteDeMentira()
    pacotes.gesto_da_pagina(PAGINA, "motor")(
        ctx, {"uniq": UNIQS[0], "lado": "e", "valor": "70"}, p)
    assert "rumble.set" in p.chamadas, (
        f"a barra não refrescou o teste vivo: {p.chamadas}")

    p = _PonteDeMentira()
    pacotes.gesto_da_pagina(PAGINA, "motor")(
        ctx, {"uniq": UNIQS[1], "lado": "e", "valor": "70"}, p)
    assert "rumble.set" not in p.chamadas, (
        f"a barra do P2 mexeu no teste do P1: {p.chamadas}")
    a05.parar_o_teste()


MEDIDA = """
(function(){
  function estado(sel){
    var g = document.querySelector(sel);
    return g ? g.classList.contains('acesa') : null;
  }
  return JSON.stringify({
    esq: estado('[data-campo="treme-e"]'),
    dir: estado('[data-campo="treme-d"]')
  });
})()
"""


@pytest.fixture(scope="module")
def no_webkit() -> dict:
    """Abre a BANCADA num WebKit offscreen, pinta ``treme`` e lê as classes."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    from hefesto_dualsense4unix.interface import hefesto_vivo, onde

    import pacotes

    vpad = {"player": 1, "rumble_no_fisico": list(PAR_NO_FISICO),
            "rumble_no_fisico_ha_s": 0.1}
    carga = pacotes.normalizar(_pacote(per_vpad=[vpad]),
                               {UNIQS[0]: "p1", UNIQS[1]: "p2"})
    pintar = hefesto_vivo.PEDIR_A_PINTURA.replace(
        "CARGA", json.dumps(carga, ensure_ascii=False))

    saiu: list[str] = []
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(1180, 900)
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def mediu(v, res):
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:
            saiu.append(f"ERRO na medida: {e}")
        Gtk.main_quit()

    def pintou(v, res):
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:
            saiu.append(f"ERRO na pintura: {e}")
            Gtk.main_quit()
            return
        v.evaluate_javascript(MEDIDA, -1, None, None, None, mediu)

    def instalou(v, res):
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:
            saiu.append(f"ERRO no bootstrap: {e}")
            Gtk.main_quit()
            return
        v.evaluate_javascript(pintar, -1, None, None, None, pintou)

    def carregou(v, evento):
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(hefesto_vivo.BOOTSTRAP, -1, None, None,
                                  None, instalou)

    view.connect("load-changed", carregou)
    view.load_uri(onde.pagina(PAGINA).as_uri())
    guarda = GLib.timeout_add(20000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
    assert saiu, "o WebKit não respondeu em 20 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    return json.loads(saiu[0])


def test_o_punho_que_treme_acende_no_dom(no_webkit) -> None:
    """O esquerdo acende porque ``strong`` = 200; o direito apaga porque ``weak``"""
    assert no_webkit["esq"] is True, (
        "o punho esquerdo não acendeu com 200 no motor `strong`")
    assert no_webkit["dir"] is False, (
        "o punho direito continuou aceso da CENA do mockup com `weak` = 0 — a "
        "pintura não apagou o que o desenho cravou")
