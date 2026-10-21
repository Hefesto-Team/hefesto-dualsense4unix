"""O acessório sem tipo ganha categoria e sinal.

A sprint: O-ACESSORIO-SEM-TIPO-GANHA-CATEGORIA-E-SINAL-NA-CONEXOES-01.

A queixa de 09/10/2026: três aparelhos de baixa energia no mesmo adaptador saíam com o «?», a
faixa vazia e o ponto vazado. As escolhas do usuário (09/10/2026, 16h): a categoria se chama
«Acessório», e a faixa são os 40 canais de baixa energia, «não medido».

MORDIDAS, uma por vez (cada uma reprova pelo menos um teste daqui): o ``TIPO_LE`` fora de
``sinais_dos_enlaces``; a chamada de ``_com_a_categoria_do_enlace`` fora da cena (o «?» volta);
as células LE fora de ``faixas_do_ar`` (o trilho mudo volta); o selo do sinal fora (o ponto volta
vazado); a leitura dos ``UUIDs`` fora do leitor do BlueZ.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import ar_do_adaptador as ar
from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import faixas_do_ar as fx
from hefesto_dualsense4unix.integrations import radio_da_mesa
from tests.unit import radio_de_mentira as rm  # noqa: F401  (a guarda do BlueZ da suíte)

RAIZ = Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup/08-conexoes.html"

ADAPTADOR = "aa:bb:cc:00:00:aa"
#: três acessórios de baixa energia, na faixa forjada
ACESSORIOS = ("aa:bb:cc:00:00:e1", "aa:bb:cc:00:00:e2", "aa:bb:cc:00:00:e3")
UUID_BATERIA = "0000180f-0000-1000-8000-00805f9b34fb"
#: um serviço de fabricante, com o último grupo na faixa forjada (12 hex lê-se como endereço)
UUID_DO_FABRICANTE = "5a300001-0023-4bd4-bbd5-aabbcc0000f1"

# --- o sinal: o enlace LE também se pergunta ---------------------------------------------


def _leitura() -> ar.ArDoAdaptador:
    return ar.ArDoAdaptador(hci=1, endereco=ADAPTADOR, conexoes=(
        ar.Enlace(11, "aa:bb:cc:00:00:01", ar.TIPO_ACL, True, 1, 1),
        ar.Enlace(17, ACESSORIOS[0], ar.TIPO_LE, True, 1, 1),
        ar.Enlace(18, ACESSORIOS[1], ar.TIPO_LE, True, 1, 1),
        # um celular com os dois enlaces: o do clássico vale, e o LE não se pergunta de novo
        ar.Enlace(19, "aa:bb:cc:00:00:02", ar.TIPO_LE, True, 1, 1),
        ar.Enlace(12, "aa:bb:cc:00:00:02", ar.TIPO_ACL, True, 1, 1)))


def test_o_sinal_se_pergunta_a_todo_enlace_e_o_classico_vence() -> None:
    perguntados: list[tuple[int, int]] = []

    def ler(hci: int, handle: int) -> int | None:
        perguntados.append((hci, handle))
        return {11: -50, 12: -52, 17: -61, 18: None}.get(handle, -99)

    sinais = radio_da_mesa.sinais_dos_enlaces({ADAPTADOR: _leitura()}, ler=ler)
    assert sorted(h for _hci, h in perguntados) == [11, 12, 17, 18]
    assert {hci for hci, _h in perguntados} == {1}
    assert sinais == {"aabbcc000001": -50, "aabbcc000002": -52,
                      "aabbcc0000e1": -61, "aabbcc0000e2": None}, "o «não sei» continua None"


def test_o_leitor_do_sinal_publica_o_do_acessorio_no_estado() -> None:
    """O caminho do daemon: a thread do ``LeitorDoSinal`` lê, e o estado publica o RSSI do
    enlace LE ao lado do mapa que ele não tem."""
    leitor = radio_da_mesa.LeitorDoSinal(lambda _hci, handle: -60 - handle % 10)
    assert leitor.talvez_ler({ADAPTADOR: _leitura()})
    prazo = time.monotonic() + 2.0
    while leitor.em_voo and time.monotonic() < prazo:
        time.sleep(0.01)
    _numero, sinais = leitor.leitura()
    lidos = ar.enlaces_do_adaptador(_leitura(), ler_mapa=lambda _h, _c: None,
                                    ler_qual=lambda _h, _c: None)
    publicado = radio_da_mesa.orcamento_por_adaptador(
        [], enlaces={ADAPTADOR: lidos}, sinais=sinais)[ADAPTADOR].publicar()
    assert publicado["enlaces"]["aabbcc0000e1"] == {
        "le": True, "canais_evitados": None, "qualidade_do_enlace": None, "rssi": -67}
    assert publicado["enlaces"]["aabbcc0000e2"]["rssi"] == -68
    json.dumps(publicado)


# --- o BlueZ: os UUIDs, pela mesma leitura de propriedade --------------------------------


def _busctl(uuids_de: dict[str, str]) -> bd.PeloBusctl:
    caminhos = ["/org/bluez", "/org/bluez/hci1"] + [
        f"/org/bluez/hci1/dev_{e.upper().replace(':', '_')}" for e in uuids_de]

    def executar(argumentos: Any) -> str | None:
        argumentos = list(argumentos)
        if argumentos[0] == "tree":
            return "\n".join(caminhos)
        if argumentos[0] != "get-property":
            raise AssertionError(f"o leitor mandou {argumentos[0]} ao BlueZ")
        caminho, nome = argumentos[2], argumentos[4]
        if nome == "UUIDs":
            for endereco, resposta in uuids_de.items():
                if caminho.endswith(endereco.upper().replace(":", "_")):
                    return resposta
        if nome == "Connected":
            return "b true"
        return None

    return bd.pelo_executor(executar)


def test_o_leitor_do_bluez_le_os_uuids_nas_duas_formas_do_busctl() -> None:
    leitor = _busctl({
        ACESSORIOS[0]: json.dumps({"type": "as", "data": [UUID_BATERIA.upper(),
                                                          UUID_DO_FABRICANTE]}),
        ACESSORIOS[1]: f'as 2 "{UUID_BATERIA}" "{UUID_DO_FABRICANTE}"',
        ACESSORIOS[2]: "as 0"})
    por_endereco = {a.endereco.lower(): a for a in leitor.aparelhos() or ()}
    assert por_endereco[ACESSORIOS[0]].uuids == (UUID_BATERIA, UUID_DO_FABRICANTE)
    assert por_endereco[ACESSORIOS[1]].uuids == (UUID_BATERIA, UUID_DO_FABRICANTE)
    assert por_endereco[ACESSORIOS[2]].uuids == ()


def test_os_uuids_do_barramento_vem_em_lista_e_lixo_nao_passa() -> None:
    assert bd._uuids([UUID_BATERIA, 7, "não é uuid", UUID_BATERIA]) == (UUID_BATERIA,)
    assert bd._uuids(None) == () and bd._uuids(180) == ()


# --- a régua: os 40 canais LE, «não medido», e o selo do sinal ---------------------------


def test_o_enlace_le_tem_os_40_canais_nao_medidos_e_nunca_o_mapa_do_adaptador() -> None:
    ap = fx.AparelhoNoAdaptador(id="x", tipo="acessorio", nome="Acessório", le=True, rssi=-61)
    adaptador = fx.Adaptador(id="L1", nome="Meio", evitados=frozenset(range(10, 30)),
                             aparelhos=(ap,))
    (linha,), = [linhas for _a, linhas in fx.montar([adaptador], ()).grupos]
    assert len(linha.celulas) == ar.CANAIS_DO_BT
    assert {c.estado for c in linha.celulas} == {fx.NAO_MEDIDO, fx.ANUNCIO}
    anuncio = [c.canal for c in linha.celulas if c.estado == fx.ANUNCIO]
    # 2402, 2426 e 2480 MHz: o canal LE 0, 12 e 39, duas células cada (a última cabe numa)
    assert anuncio == [0, 1, 24, 25, 78]
    assert linha.bons is None and linha.sem_faixa == fx.DIVIDE_O_RADIO
    assert linha.selo == fx.Selo(fx.SINAL, "sinal -61 dBm")
    sem_sinal = fx.montar([fx.Adaptador(id="L1", nome="Meio", aparelhos=(
        fx.AparelhoNoAdaptador(id="y", tipo="acessorio", nome="Acessório", le=True),))], ())
    assert sem_sinal.grupos[0][1][0].selo is None, "sem o número, o ponto não inventa um"


# --- a tela: a categoria e a linha ------------------------------------------------------


from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08
from hefesto_dualsense4unix.interface.pacotes import em_fundo


def _enlace(le: bool, rssi: int | None = -61) -> dict[str, Any]:
    return {"le": le, "canais_evitados": None if le else [3], "qualidade_do_enlace": None,
            "rssi": rssi}


def test_a_categoria_sai_do_enlace_le_e_do_tipo_que_falta() -> None:
    aps = [{"id": a08.nome_do_jogador.mac(e), "tipo": "outro", "lugar": "L1"} for e in ACESSORIOS]
    aps += [{"id": "AABBCC000004", "tipo": "relogio", "lugar": "L1"},
            {"id": "AABBCC000005", "tipo": "outro", "lugar": "L1"},
            {"id": "AABBCC000006", "tipo": "outro", "lugar": "L2"},
            {"id": "AABBCC000007", "tipo": "controle", "lugar": "L1"}]
    enlaces = {"L1": {a08._so_hex(e): _enlace(True) for e in ACESSORIOS}}
    enlaces["L1"] |= {"aabbcc000004": _enlace(True), "aabbcc000005": _enlace(False),
                      "aabbcc000007": _enlace(True)}
    enlaces["L2"] = {}
    a08._com_a_categoria_do_enlace(aps, enlaces)
    assert [a["tipo"] for a in aps] == [
        "acessorio", "acessorio", "acessorio",
        "relogio",   # o tipo lido vale: a categoria é só para quem não tem
        "outro",     # enlace clássico sem tipo: não é baixa energia
        "outro",     # sem enlace naquele adaptador
        "controle"]


def test_a_categoria_mora_numa_tabela_so() -> None:
    cat = a08.CATEGORIA_ACESSORIO
    assert a08.glifo_do_tipo(a08.TIPO_ACESSORIO) == cat["glifo"] != "ajuda"
    assert a08.PALAVRA_DO_TIPO[a08.TIPO_ACESSORIO] == cat["palavra"]
    # as cores são os tokens da raiz da aba (O-TEMA-DE-CORES-ENTRA-PELA-FOLHA-DE-USUARIO-01)
    assert a08.COR_DO_TIPO[a08.TIPO_ACESSORIO] == cat["cor"] == "var(--sala-acessorio)"
    assert cat["cor_na_regua"] == "var(--c-acessorio)"
    assert a08._cor_na_regua(a08.TIPO_ACESSORIO) == cat["cor_na_regua"]
    assert a08.COR_DA_FAIXA_NO_MAPA[a08.TIPO_ACESSORIO] == "var(--mapa-acessorio,#ff79c6)"
    assert (a08.TIPO_ACESSORIO, cat["legenda"]) in a08.LEGENDA_DAS_FAIXAS
    assert a08.TIPO_ACESSORIO in a08.TIPOS_COM_COR_NA_REGUA
    pagina = MOCKUP.read_text(encoding="utf-8")
    assert f'<symbol id="rd-{cat["glifo"]}"' in pagina
    raiz = re.search(r":root\{(--c-[^{}]*)\}", pagina)
    assert raiz and "--c-acessorio:#ff79c6" in raiz.group(1) and (
        "--sala-acessorio:#a8919f" in raiz.group(1))


def _linha(html: str, ident: str) -> str:
    achada = re.search(rf'<div class="ar-linha" data-id="{re.escape(ident)}".*?</div></div>',
                       html, re.S)
    assert achada, ident
    return achada.group(0)


def test_a_cena_inteira_do_bluez_ate_a_linha(monkeypatch: pytest.MonkeyPatch) -> None:
    """Do BlueZ de mentira (três aparelhos de baixa energia sem ``Icon``, ``Class`` nem
    ``Appearance``) e do ``radio_ar`` publicado até o HTML: o glifo do acessório, as 79
    células «não medido» e o ponto cheio com o sinal."""
    from hefesto_dualsense4unix.integrations.bluez_dbus import (
        AdaptadorDoBluez,
        AparelhoDoBluez,
    )
    from hefesto_dualsense4unix.integrations.mesa_de_radio import Mesa
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

    monkeypatch.setattr(em_fundo, "_FUNDO", {})
    for nome in ("_ABERTO", "_CENA_NA_TELA", "_NIVEL_NA_TELA"):
        monkeypatch.setattr(a08, nome, {})
    monkeypatch.setattr(em_fundo, "LER_NA_HORA", True)
    monkeypatch.setattr(a08, "_mesa_do_radio", lambda recarregar=False: Mesa())
    caminho = "/org/bluez/hci1"
    adaptadores = (AdaptadorDoBluez(caminho, "hci1", ADAPTADOR, varrendo=False),)
    aparelhos = tuple(
        AparelhoDoBluez(f"{caminho}/dev_{e.upper().replace(':', '_')}", caminho, e,
                        nome=f"LVS-{k}", conectado=True, pareado=True,
                        uuids=(UUID_DO_FABRICANTE,))
        for k, e in enumerate(ACESSORIOS))
    monkeypatch.setattr(em_fundo, "ler_o_bluez", lambda: (adaptadores, aparelhos))
    monkeypatch.setattr(a08, "_ler_a_maquina", lambda: (MaquinaConfig(), {}))
    monkeypatch.setattr(a08, "_ler_o_historico", lambda: {})
    monkeypatch.setattr(a08, "_ler_o_wifi", lambda: None)
    monkeypatch.setattr(a08, "_ler_os_zumbis", lambda: {})
    estado = {"controllers": [], "radio_ar": {ADAPTADOR: {
        "canais_evitados": [10, 11, 12],
        "enlaces": {a08._so_hex(e): _enlace(True, -61 - k) for k, e in enumerate(ACESSORIOS)}}}}
    cena = a08.cena_do_radio(pacotes.Contexto(state=estado, mesa=[], conectados=[]))
    assert [a["tipo"] for a in cena["aparelhos"]] == ["acessorio"] * 3
    html = a08.html_dos_canais(cena)
    for k, e in enumerate(ACESSORIOS):
        linha = _linha(html, a08.nome_do_jogador.mac(e))
        assert 'href="#rd-acessorio"' in linha and 'href="#rd-ajuda"' not in linha
        celulas = re.findall(r'<i class="([^"]*)" title="([^"]*)"', linha)
        assert len(celulas) == ar.CANAIS_DO_BT
        assert {c for c, _t in celulas} == {"n", "n a"}, "o mapa do adaptador virou do aparelho"
        assert celulas[24] == ("n a", "Canal LE 12 · 2426 MHz · anúncio, não medido")
        assert celulas[5] == ("n", "Canal LE 2 · 2406 MHz · não medido")
        assert f'class="ar-faixa le" role="img" aria-label="LVS-{k}: {a08.LE_NAO_MEDIDO}"' in linha
        ponto = re.search(r'<span class="ar-selo ([\w-]+)" role="img" title="([^"]*)"', linha)
        assert ponto and ponto.group(1) == fx.SINAL
        assert ponto.group(2) == f"Sinal {-61 - k} dBm · {fx.DIVIDE_O_RADIO}"
        assert ponto.group(2).count("dBm") == 1
    # sem o número do rádio, o ponto diz a frase UMA vez, no título e na fala
    sem_sinal = fx.montar([fx.Adaptador(id="L1", nome="Meio", aparelhos=(
        fx.AparelhoNoAdaptador(id="y", tipo="acessorio", nome="Sensor", le=True),))], ())
    ponto_sem = a08._o_ponto(sem_sinal.grupos[0][1][0])
    for campo in ("title", "aria-label"):
        dito = re.search(rf'{campo}="([^"]*)"', ponto_sem)
        assert dito and dito.group(1) == fx.DIVIDE_O_RADIO, (campo, ponto_sem)


# --- a tela no WebKit: a textura e o ponto, no motor do usuário -----------------------------------

SONDA = r"""
(function(){
  document.getElementById('cx8-3').checked = true;
  const linha = document.querySelector('.radio .ar-linha[data-tipo="acessorio"]');
  if(!linha) return JSON.stringify({linha: false});
  const faixa = linha.querySelector('.ar-faixa');
  const celulas = [...faixa.children];
  const estilo = el => getComputedStyle(el);
  const ponto = linha.querySelector('.ar-estado .ar-selo');
  const glifo = linha.querySelector('.ar-rot use');
  return JSON.stringify({
    linha: true,
    celulas: celulas.length,
    largura: Math.round(faixa.getBoundingClientRect().width),
    textura: celulas.filter(c => estilo(c).backgroundImage.includes('gradient')).length,
    anuncio: celulas.filter(c => estilo(c).boxShadow !== 'none').map(c => celulas.indexOf(c)),
    ponto_fundo: estilo(ponto).backgroundColor,
    ponto_borda: estilo(ponto).borderTopWidth,
    glifo: glifo ? glifo.getAttribute('href') : '',
    glifo_tem_desenho: glifo ? !!document.querySelector(glifo.getAttribute('href')) : false,
    legenda: !!document.querySelector('.radio .ar-legenda [data-tipo-da-legenda="acessorio"]'),
    faixa_do_controle: Math.round(document.querySelector(
      '.radio .ar-linha[data-tipo="controle"] .ar-faixa').getBoundingClientRect().width),
  });
})()
"""


def _no_webkit(pagina: Path) -> dict[str, Any]:
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    saiu: list[str] = []
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(1212, 1500)
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def guardou(v: Any, res: Any) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:  # pragma: no cover — só quando o roteiro quebra
            saiu.append(f"ERRO {e}")
        Gtk.main_quit()

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            GLib.timeout_add(300, lambda: (v.evaluate_javascript(
                SONDA, -1, None, None, None, guardou), False)[1])

    view.connect("load-changed", carregou)
    view.load_uri(pagina.as_uri())
    guarda = GLib.timeout_add(30000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert saiu, "o WebKit não respondeu em 30 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    return dict(json.loads(saiu[0]))


def test_no_webkit_a_linha_do_acessorio_tem_textura_anuncio_e_ponto_cheio() -> None:
    f = _no_webkit(MOCKUP)
    assert f["linha"] is True, "o desenho não tem a linha do acessório"
    assert f["celulas"] == ar.CANAIS_DO_BT and f["textura"] == ar.CANAIS_DO_BT
    assert f["anuncio"] == [0, 1, 24, 25, 78]
    assert f["glifo"] == "#rd-acessorio" and f["glifo_tem_desenho"] is True
    assert f["ponto_fundo"] not in ("rgba(0, 0, 0, 0)", "transparent"), "o ponto ficou vazado"
    assert f["ponto_borda"] == "0px"
    assert f["legenda"] is True
    assert f["largura"] > 0 and f["largura"] <= f["faixa_do_controle"]
