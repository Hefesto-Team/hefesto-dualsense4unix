#!/usr/bin/env python3
"""A RÉGUA DA TELA-CALADA-03 — Sistema e Conexões perguntam, e não narram.

**13/09/2026.** A palavra dela, com a foto do rodapé: *"essas frases de status
que aparecem no rodapé isso não deveria estar aparecendo"* — *"em todas as abas
da interface"*.

A RÉGUA QUE SAI DISSO TEM TRÊS METADES:

* a **pergunta** de um gesto em dois tempos FICA — sem ela o segundo clique não
  tem instrução;
* o **recibo** depois do gesto SAI — e vai ao diário da janela, não some;
* o **conteúdo que ela pediu** («Ver detalhes», «Ver plugins») fica.

O QUE CADA BLOCO COBRA
----------------------
1. **09, «Aplicar aos jogos da Steam».** O primeiro clique põe a pergunta do dono
   no painel de registro, e ela sobrevive ao tique; o segundo devolve só os
   rótulos, e o painel volta ao repouso. Medido antes no piloto oculto: o
   primeiro clique virava o botão em «Confirma?» e a tela não dizia uma palavra
   — a pergunta ia por `recado`, e a aba 09 não tem onde um recado pouse.
2. **09, os outros três segundos cliques** (consertos, Proton, camadas): só os
   rótulos, painel limpo, recibo do DONO no diário.
3. **09 com o serviço parado.** O ramo de erro do pacote emite o registro e o
   exame, e nenhum dos dois é o do desenho — no pacote e NO PIXEL, com a página
   publicada e o `BOOTSTRAP` do piloto num WebKit oculto.
4. **08, «A luz não acende».** Durante a espera a instrução fica; quando ela
   acaba falando, a linha do cartão volta ao nada e a frase vai ao diário.

A MORDIDA — as saídas estão coladas na entrega
----------------------------------------------
* devolver a pergunta ao `recado` em `aplicar_aos_jogos` → o bloco 1 reprova;
* tirar `_limpar_o_painel()` de um segundo clique → o bloco 2 reprova naquele
  gesto;
* tirar `REGISTRO` e os dois `exame-*` do ramo de erro → o bloco 3 reprova no
  pacote e no pixel;
* devolver a frase do fim em `linha_da_espera` → o bloco 4 reprova.

NADA AQUI SAI DA MÁQUINA DE QUEM RODA: a Steam, o Proton, os scripts, as camadas
e o rádio são dublês no ponto em que o motor mexeria nela, e todo dublê que tem
desfecho sabe recusar.
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.app.actions import daemon_actions as _daemon
from hefesto_dualsense4unix.interface import onde as _onde
from hefesto_dualsense4unix.interface.pacotes import Contexto, normalizar
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08
from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

#: Faixa sintética da casa — há dois portões de anonimato nesta árvore.
UNIQ = "aa:bb:cc:00:00:01"
CHAVE = "aabbcc000001"

#: O RESULTADO QUE O DUBLÊ DA STEAM DEVOLVE, e o recibo é calculado a partir
#: dele pelo DONO — nunca digitado aqui.
APLICADOS = {"applied": 3, "skipped": 0, "errors": 0}


def _ctx() -> Contexto:
    return Contexto(state={"active_profile": "regua"}, mesa=[], conectados=[],
                    estados={})


class PonteDeMentira:
    """Nenhum destes gestos fala com o daemon; a ponte existe pelo contrato.

    Ela RECUSA tudo e grava o pedido: um gesto que passasse a chamá-la sem
    ninguém saber apareceria em `chamadas`, e não num verde calado.
    """

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def chamar(self, metodo: str, *_a: object, **_k: object) -> bool:
        self.chamadas.append(metodo)
        return False


def _zerar() -> None:
    a09._ARMADO.clear()
    a09._LENTO.clear()
    a09._PAINEL[0] = None
    a08._ESPERAS.clear()


@pytest.fixture(autouse=True)
def _limpo():
    """O consentimento, o painel e as esperas são estado de MÓDULO."""
    _zerar()
    yield
    _zerar()


@pytest.fixture
def dono():
    from hefesto_dualsense4unix.app.actions.config import secao_controles

    return secao_controles


def _primeiro(gesto: str) -> dict[str, str]:
    """O clique 1: o rótulo do desenho, que não é o do botão armado."""
    return {"gesto": gesto, "texto": "o rótulo do desenho"}


def _confirma(gesto: str) -> dict[str, str]:
    """O clique 2: ele traz o rótulo que só existe no botão armado."""
    return {"gesto": gesto, "texto": a09.CONFIRMA}


def _com_a_steam(monkeypatch: pytest.MonkeyPatch, *, janela: str = "ok") -> dict:
    """Dubla a Steam no ponto em que o motor a FECHARIA — e sabe recusar."""
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    visto: dict[str, list] = {"fechou": [], "aplicou": []}

    def _aplicar() -> dict[str, int]:
        visto["aplicou"].append(True)
        return dict(APLICADOS)

    def _com_a_steam_fechada(acao):
        visto["fechou"].append(True)
        return (janela, acao() if janela == "ok" else None)

    monkeypatch.setattr(slo, "apply_wrapper_to_all_games", _aplicar, raising=False)
    monkeypatch.setattr(slo, "with_steam_closed", _com_a_steam_fechada)
    return visto


# ---------------------------------------------------------------------------
# 1 · «Aplicar aos jogos da Steam» pergunta NO PAINEL
# ---------------------------------------------------------------------------


def test_o_primeiro_clique_do_aplicar_poe_a_pergunta_no_painel(monkeypatch) -> None:
    visto = _com_a_steam(monkeypatch)
    carga = a09.aplicar_aos_jogos(_ctx(), _primeiro("aplicar-aos-jogos"),
                                  PonteDeMentira())

    assert visto == {"fechou": [], "aplicou": []}, (
        "a Steam dela foi fechada no PRIMEIRO clique — o consentimento sumiu")
    assert "recado" not in carga, (
        "a pergunta voltou ao `recado`: a aba 09 não tem cartão nem faixa onde "
        "ele pouse, e o primeiro clique volta a não mostrar nada")
    painel = (carga.get("mesa") or {}).get(a09.REGISTRO)
    assert painel, f"o primeiro clique não escreveu no painel de registro: {carga}"
    corpo = " ".join(_daemon.DaemonActionsMixin._STEAM_APPLY_CORPO.split())
    assert corpo in " ".join(painel.split()), (
        "a pergunta não é a do dono, palavra por palavra")
    assert painel.rstrip().endswith(a09.CLIQUE_DE_NOVO), painel
    assert a09._no_painel("repouso") == painel, (
        "a pergunta não sobrevive ao tique: o painel repinta o repouso por cima")


def test_a_pergunta_cabe_na_largura_do_painel(monkeypatch) -> None:
    """O painel é `white-space:pre`: linha que não cabe sai pela direita."""
    _com_a_steam(monkeypatch)
    carga = a09.aplicar_aos_jogos(_ctx(), _primeiro("aplicar-aos-jogos"),
                                  PonteDeMentira())
    linhas = carga["mesa"][a09.REGISTRO].split("\n")
    assert max(len(linha) for linha in linhas) <= a09.LARGURA_DA_PERGUNTA, linhas


def test_o_segundo_clique_do_aplicar_devolve_so_os_rotulos(monkeypatch, capsys) -> None:
    visto = _com_a_steam(monkeypatch)
    a09.aplicar_aos_jogos(_ctx(), _primeiro("aplicar-aos-jogos"), PonteDeMentira())
    carga = a09.aplicar_aos_jogos(_ctx(), _confirma("aplicar-aos-jogos"),
                                  PonteDeMentira())

    assert visto["aplicou"] == [True]
    assert set(carga) == {"blocos"}, (
        f"o segundo clique voltou a narrar: {sorted(carga)}")
    assert a09._no_painel("repouso") == "repouso", (
        "a pergunta do primeiro clique ficou no painel, velha, depois do "
        "consentimento dado")
    diario = capsys.readouterr().err
    assert f"[relato] {a09.PAGINA} · aplicar-aos-jogos: " in diario, diario
    assert _daemon.format_apply_wrapper_result(APLICADOS) in diario, (
        "o recibo sumiu em vez de ir ao diário da janela")


def test_a_recusa_do_segundo_clique_tambem_tira_a_pergunta(monkeypatch) -> None:
    """O dublê RECUSA (jogo aberto): o gesto levanta e a pergunta não fica.

    Ela diria "clique de novo para confirmar" sobre um consentimento que o
    `_confirmado` já consumiu — o próximo clique ARMA de novo, não confirma.
    """
    visto = _com_a_steam(monkeypatch, janela="jogo_aberto")
    a09.aplicar_aos_jogos(_ctx(), _primeiro("aplicar-aos-jogos"), PonteDeMentira())
    with pytest.raises(RuntimeError) as erro:
        a09.aplicar_aos_jogos(_ctx(), _confirma("aplicar-aos-jogos"),
                              PonteDeMentira())
    assert str(erro.value) == _daemon.format_steam_janela_recusa("jogo_aberto")
    assert visto["aplicou"] == []
    assert a09._no_painel("repouso") == "repouso"


# ---------------------------------------------------------------------------
# 2 · Os outros três segundos cliques: só os rótulos, painel limpo, recibo no
#     diário
# ---------------------------------------------------------------------------


def _dubla_consertos(monkeypatch) -> tuple[Any, str]:
    monkeypatch.setattr(a09, "CONSERTOS", ())
    monkeypatch.setattr(a09, "_consertos_no_disco", lambda: [])
    monkeypatch.setattr(a09._daemon, "medir_jogos_com_steam_input",
                        lambda: ["Um Jogo"])
    return a09.refazer_consertos, a09._daemon.format_fix_safe_result(
        {"ran": 0, "missing": 0, "steam_input": None,
         "steam_input_jogos": ["Um Jogo"]})


def _dubla_proton(monkeypatch) -> tuple[Any, str]:
    from hefesto_dualsense4unix.integrations import proton_pin

    travados = {"locked": 2, "skipped": 0, "errors": 0}
    monkeypatch.setattr(proton_pin, "lock_proton_for_all_games",
                        lambda: dict(travados), raising=False)
    monkeypatch.setattr(proton_pin, "steam_running", lambda: False, raising=False)
    return a09.refazer_proton, a09._daemon.format_proton_lock_result(travados)


def _dubla_camadas(monkeypatch) -> tuple[Any, str]:
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    monkeypatch.setattr(cv, "censo", lambda *a, **k: ["um-prefixo"])
    monkeypatch.setattr(cv, "pastas_compatdata", lambda *a, **k: ["/uma/pasta"])
    monkeypatch.setattr(cv, "curar_todos", lambda *a, **k: [])
    monkeypatch.setattr(a09._emulacao, "frase_do_censo",
                        lambda p, bibliotecas=1: ("o censo", True, False))
    monkeypatch.setattr(slo, "steam_game_running", lambda *a, **k: False)
    return a09.procurar_camadas, a09._emulacao.frase_do_resultado([], devolver=False)


@pytest.mark.parametrize(("nome", "dublar"), [
    ("refazer-consertos", _dubla_consertos),
    ("refazer-proton", _dubla_proton),
    ("procurar-camadas", _dubla_camadas),
])
def test_o_segundo_clique_limpa_o_painel_e_leva_o_recibo_ao_diario(
        monkeypatch, capsys, nome: str, dublar) -> None:
    gesto, recibo = dublar(monkeypatch)
    # O QUE ESTAVA NO PAINEL ANTES — um «Ver detalhes», digamos. O clique 1 de
    # dois deles escreve a pergunta por cima; o do Proton só arma.
    a09._PAINEL[0] = "o que estava no painel"
    gesto(_ctx(), _primeiro(nome), PonteDeMentira())
    assert a09._no_painel("repouso") != "repouso", (
        "o dublê não pôs nada no painel antes do segundo clique — a régua "
        "mediria um painel que já estava limpo")

    carga = gesto(_ctx(), _confirma(nome), PonteDeMentira())

    assert set(carga) == {"blocos"}, f"{nome}: o segundo clique narrou: {carga}"
    assert a09._no_painel("repouso") == "repouso", (
        f"{nome}: a pergunta do primeiro clique ficou no painel, velha")
    diario = capsys.readouterr().err
    assert f"[relato] {a09.PAGINA} · {nome}: {recibo}" in diario, (
        f"{nome}: o recibo do dono não chegou ao diário: {diario!r}")


# ---------------------------------------------------------------------------
# 3 · Serviço parado: nem o registro nem o exame do desenho
# ---------------------------------------------------------------------------


def _camada_levanta(monkeypatch) -> None:
    """A camada do produto levanta — é o que acontece com o serviço parado.

    `_leitura` é dublada porque ela roda ANTES da camada e pergunta ao systemd
    de quem roda a régua.
    """
    def _levanta(_leitura: object) -> dict:
        raise RuntimeError("o serviço não respondeu")

    monkeypatch.setattr(a09, "_leitura", lambda ctx: None)
    monkeypatch.setattr(a09._tela, "pacote", _levanta)
    monkeypatch.setattr(a09, "_status_do_daemon", lambda _s: "offline")


def test_com_o_servico_parado_o_pacote_escreve_o_painel_e_o_exame(monkeypatch) -> None:
    _camada_levanta(monkeypatch)
    carga = a09.pacote(_ctx())
    assert carga.get("sem_dono"), "o ramo de erro não foi exercido"
    nada = str(a09._monta().NADA_A_DIZER)
    for campo in (a09.REGISTRO, "exame-lista", "exame-contagem"):
        assert campo in carga, (
            f"o ramo de erro não emite `{campo}` — a página continua com o "
            "literal do desenho nesse endereço")
    assert carga[a09.REGISTRO] == "—", carga[a09.REGISTRO]
    assert carga["exame-lista"] == nada
    assert carga["exame-contagem"] == nada


def test_com_o_servico_parado_o_que_ela_pediu_continua_no_painel(monkeypatch) -> None:
    """A pergunta do «Aplicar aos jogos» chega pelo PACOTE, sem o serviço."""
    _camada_levanta(monkeypatch)
    _com_a_steam(monkeypatch)
    carga = a09.aplicar_aos_jogos(_ctx(), _primeiro("aplicar-aos-jogos"),
                                  PonteDeMentira())
    assert a09.pacote(_ctx())[a09.REGISTRO] == carga["mesa"][a09.REGISTRO]
    a09._PAINEL[0] = "linha do registro que ela pediu"
    assert a09.pacote(_ctx())[a09.REGISTRO] == "linha do registro que ela pediu"


ROTEIRO_09 = """
(function(){
  const r = document.querySelector('[data-campo="registro-texto"]');
  const l = document.querySelector('[data-campo="exame-lista"]');
  const c = document.querySelector('[data-campo="exame-contagem"]');
  if(!r || !l || !c) return JSON.stringify({erro: 'a página não tem os endereços'});
  const fora = {inicial: {registro: r.textContent, lista: l.textContent,
                          contagem: c.textContent}};
  for(const [nome, carga] of CARGAS){
    fora[nome] = {
      pintou: window.__hef.pintar(carga),
      registro: r.textContent,
      lista: l.textContent,
      contagem: c.textContent,
      largura: [r.clientWidth, r.scrollWidth],
    };
  }
  return JSON.stringify(fora);
})()
"""


@pytest.fixture(scope="module")
def no_webkit_09():
    """A página PUBLICADA num WebKit oculto, com o `BOOTSTRAP` do piloto.

    A carga sai de `a09_sistema.pacote` + `pacotes.normalizar`, a MESMA sequência
    do piloto — com a camada do produto levantando, que é o serviço parado.
    """
    pagina = _onde.pagina("09-sistema.html", publicado=True)
    if not pagina.is_file():
        pytest.skip("a página publicada da 09 não está no disco")

    with pytest.MonkeyPatch.context() as mp:
        _camada_levanta(mp)
        a09._PAINEL[0] = None
        parado = dict(normalizar(a09.pacote(_ctx())))
        _com_a_steam(mp)
        a09._ARMADO.clear()
        pergunta = a09.aplicar_aos_jogos(_ctx(), _primeiro("aplicar-aos-jogos"),
                                         PonteDeMentira())
        com_a_pergunta = dict(normalizar({a09.REGISTRO: pergunta["mesa"][a09.REGISTRO]}))
    a09._ARMADO.clear()
    a09._PAINEL[0] = None

    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    import hefesto_vivo

    saiu: list[str] = []
    # `Gtk.OffscreenWindow`: sob Xvfb não há gerenciador de janelas, e ela tem
    # UMA tela — janela de teste não nasce na frente dela. O tamanho é o da
    # moldura do produto (1180x777), para a largura do painel ser a de verdade.
    janela = Gtk.OffscreenWindow()
    view = WebKit2.WebView()
    view.set_size_request(1180, 777)
    janela.add(view)
    janela.show_all()
    cargas = [("parado", parado), ("pergunta", com_a_pergunta)]
    roteiro = (f"const CARGAS = {json.dumps(cargas, ensure_ascii=False)};\n"
               f"{ROTEIRO_09}")

    def guardou(v, res) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:  # pragma: no cover — só quando o roteiro quebra
            saiu.append(f"ERRO {e}")
        Gtk.main_quit()

    def bootou(v, res) -> None:
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:  # pragma: no cover
            saiu.append(f"ERRO no BOOTSTRAP: {e}")
            Gtk.main_quit()
            return
        v.evaluate_javascript(roteiro, -1, None, None, None, guardou)

    def carregou(v, evento) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(hefesto_vivo.BOOTSTRAP, -1, None, None, None,
                                  bootou)

    view.connect("load-changed", carregou)
    view.load_uri(pagina.as_uri())
    # O `timeout_add` PENDENTE DISPARA NO LAÇO DO PRÓXIMO TESTE de GUI do mesmo
    # processo — por isso ele é removido no `finally`.
    guarda = GLib.timeout_add(30000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert saiu, "o WebKit não respondeu em 30 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    return json.loads(saiu[0])


def test_no_pixel_o_servico_parado_apaga_o_registro_e_o_exame_do_desenho(
        no_webkit_09) -> None:
    inicial = no_webkit_09["inicial"]
    assert "23:41" in inicial["registro"], (
        "a página publicada não carrega mais o registro do desenho — esta "
        "mordida perdeu o alvo e precisa de outro literal")
    visto = no_webkit_09["parado"]
    assert "23:41" not in visto["registro"], (
        f"o registro inventado pelo desenho continua na tela: {visto['registro']!r}")
    assert "Mortal Kombat" not in visto["registro"]
    assert inicial["lista"].strip() and not visto["lista"].strip(), (
        f"o exame do desenho continua na tela: {visto['lista'][:120]!r}")
    assert inicial["contagem"] != visto["contagem"], visto["contagem"]
    assert "linhas" not in visto["contagem"], visto["contagem"]


def test_no_pixel_a_pergunta_cabe_no_painel_sem_rolar_de_lado(no_webkit_09) -> None:
    visto = no_webkit_09["pergunta"]
    assert a09.CLIQUE_DE_NOVO in visto["registro"], visto["registro"]
    largura, rolagem = visto["largura"]
    assert largura > 0, "o painel não tem largura — o WebKit não montou a página"
    assert rolagem <= largura, (
        f"a pergunta sai pela direita do painel ({rolagem}px em {largura}px) — "
        "a instrução do segundo tempo fica fora da vista")


# ---------------------------------------------------------------------------
# 4 · «A luz não acende»: a instrução fica, o fim não fala no cartão
# ---------------------------------------------------------------------------


def test_durante_a_espera_a_instrucao_fica(dono) -> None:
    a08.comecar_a_espera(UNIQ, agora=a08._agora(), sonda=lambda: {CHAVE})
    linha = a08.linha_da_espera(UNIQ)
    assert dono.FRASE_APERTE_PS in linha, linha
    assert dono.frase_da_procura(dono.ESPERA_PELO_PS_S) in linha, linha


def test_a_espera_que_acaba_falando_nao_fala_no_cartao(dono, capsys) -> None:
    """`nao_caiu` é o desfecho que FALA — e a frase não chega mais ao cartão.

    O RELÓGIO É CORRIDO NA ESPERA, e não pelo depósito: assim a espera acabada
    continua lá, e o que se mede é a LINHA — não a poda.
    """
    dele = a08.comecar_a_espera(UNIQ, agora=0.0, sonda=lambda: {CHAVE})
    dele.correr(float(dono.ESPERA_PELO_PS_S))
    assert not a08.esperando(UNIQ)
    assert dele.espera.porque == dono.FRASE_NAO_CAIU, (
        "o dublê não chegou ao desfecho que fala — a régua mediria o silêncio "
        "de uma espera que não tinha nada a dizer")
    assert a08.linha_da_espera(UNIQ) == a08._sem_valor(), (
        f"o recado do fim voltou ao cartão: {a08.linha_da_espera(UNIQ)!r}")
    assert dono.FRASE_NAO_CAIU in capsys.readouterr().err, (
        "o fim sumiu em vez de ir ao diário da janela")


def test_o_cartao_do_controle_que_esperou_recebe_a_contagem_e_depois_nada(
        dono) -> None:
    """Pelo PACOTE, por controle: a contagem na coluna dele, e depois o nada."""
    cru = {"uniq": UNIQ, "transport": "bt", "connected": True, "index": 0}
    eu = {"pref": "p1", "uniq": UNIQ, "jogador": 1, "cor": "white",
          "nome": "White", "via": "rádio", "transporte": "bt",
          "mascara": "DualSense"}
    ctx = Contexto(state={"controllers": [cru]}, mesa=[eu], conectados=[cru],
                   estados={})
    a08.comecar_a_espera(UNIQ, agora=a08._agora(), sonda=lambda: {CHAVE})

    durante = (a08.pacote(ctx).get("colunas") or {}).get(UNIQ, {}).get("luz-espera")
    assert durante and dono.FRASE_APERTE_PS in durante, durante

    for dele in a08._ESPERAS.values():
        dele.desde -= dono.ESPERA_PELO_PS_S + 5
    depois = (a08.pacote(ctx).get("colunas") or {}).get(UNIQ, {}).get("luz-espera")
    assert depois == a08._sem_valor(), (
        f"a espera acabou e o cartão continuou dizendo alguma coisa: {depois!r}")
