"""As faixas dizem quem briga com cada aparelho — AS-FAIXAS-DIZEM-QUEM-BRIGA-COM-CADA-APARELHO-01.

A entrada de cada régua é uma cena de mentira; o esperado sai da entrada (a banda do
Wi-Fi pela conta do padrão, os canais perdidos de cada enlace).

MORDIDAS, uma por vez (cada uma reprova pelo menos um teste daqui; a do roteiro é o último
teste): a marca do dono sem o `<u>` do canal perdido; a marca da vítima sem o `<u>` do canal
ocupado; o `Appearance` sem o tipo relógio; o mapa do enlace trocado pelo do adaptador; o
roteiro das faixas desligado (a mesma página com o `return` no topo).
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import ar_do_adaptador as ar
from hefesto_dualsense4unix.integrations import faixas_do_ar as fx
from hefesto_dualsense4unix.integrations import radio_da_mesa
from tests.conftest import exigir_gi_real
from tests.unit import radio_de_mentira as rm  # noqa: F401  (a guarda do BlueZ da suíte)

RAIZ = Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup/08-conexoes.html"

# --- o modelo puro ----------------------------------------------------------------------


def _aparelho(ident: str, tipo: str = "controle", *, perdidos: set[int] | None = None,
              le: bool = False) -> fx.AparelhoNoAdaptador:
    return fx.AparelhoNoAdaptador(
        id=ident, tipo=tipo, nome=ident,
        evitados=frozenset(perdidos) if perdidos is not None else None, le=le)


def _regua(*aparelhos: fx.AparelhoNoAdaptador, evitados: set[int] | None = None,
           ocupantes: tuple[fx.Ocupante, ...] = ()) -> fx.Regua:
    adaptador = fx.Adaptador(id="L1", nome="Esquerda", evitados=(
        frozenset(evitados) if evitados is not None else None), aparelhos=aparelhos)
    return fx.montar([adaptador], ocupantes)


WIFI = fx.Ocupante(id="wifi", tipo="wifi", nome="Wi-Fi", banda=frozenset(range(49, 71)))


def test_a_briga_se_cruza_nos_dois_sentidos() -> None:
    regua = _regua(_aparelho("p3", perdidos=set(range(50, 58))), _aparelho("p4"),
                   evitados=set(), ocupantes=(WIFI,))
    (p3, p4), = [linhas for _a, linhas in regua.grupos]
    (wifi,) = regua.outros
    assert {c.canal: c.dono for c in p3.celulas if c.estado == fx.PERDIDO} == dict.fromkeys(
        range(50, 58), "wifi")
    assert wifi.selo == fx.Selo("sofrendo", "tira canais de 1")
    assert {c.canal: c.marca for c in wifi.celulas if c.estado == fx.OCUPADO and c.marca} == (
        dict.fromkeys(range(50, 58), "p3"))
    assert "wifi" in p3.briga and "p3" in wifi.briga and "p4" in p3.briga
    assert p4.bons == 79 and p4.selo == fx.Selo("boa", "boa 79/79")


def test_o_canal_sem_dono_e_ruido_e_o_wifi_em_5ghz_nao_atrapalha() -> None:
    fora = fx.Ocupante(id="wifi", tipo="wifi", nome="Wi-Fi", banda=frozenset())
    regua = _regua(_aparelho("p1", perdidos={3, 4}), evitados=set(), ocupantes=(fora,))
    (p1,), = [linhas for _a, linhas in regua.grupos]
    assert {c.dono for c in p1.celulas if c.estado == fx.PERDIDO} == {fx.RUIDO}
    (wifi,) = regua.outros
    assert wifi.sem_faixa == fx.FORA_DA_FAIXA and wifi.selo == fx.Selo("boa", "não atrapalha")
    assert not wifi.celulas and "wifi" not in p1.briga


def test_enlace_le_nao_tem_faixa_propria_e_sem_mapa_nao_se_mede() -> None:
    regua = _regua(_aparelho("relogio", "relogio", le=True), _aparelho("celular", "celular"),
                   evitados=None)
    (relogio, celular), = [linhas for _a, linhas in regua.grupos]
    assert relogio.sem_faixa == fx.DIVIDE_O_RADIO and not relogio.celulas
    assert celular.sem_faixa == fx.NAO_SE_MEDE and celular.selo is None


def test_o_mapa_do_enlace_vale_mais_que_o_do_adaptador() -> None:
    regua = _regua(_aparelho("celular", "celular", perdidos={10}), _aparelho("p1"),
                   evitados={20, 21})
    (celular, p1), = [linhas for _a, linhas in regua.grupos]
    assert [c.canal for c in celular.celulas if c.estado == fx.PERDIDO] == [10]
    assert [c.canal for c in p1.celulas if c.estado == fx.PERDIDO] == [20, 21]


# --- o que o enlace entrega -------------------------------------------------------------


def _evento_de_qualidade(handle: int, qualidade: int, *, status: int = 0,
                         opcode: int = ar.OPCODE_LER_QUALIDADE) -> bytes:
    return bytes([0x04, 0x0E, 0x08, 0x01, opcode & 0xFF, opcode >> 8, status,
                  handle & 0xFF, handle >> 8, qualidade])


def test_a_qualidade_do_enlace_se_le_da_resposta_e_so_da_dele() -> None:
    assert ar.qualidade_da_resposta(_evento_de_qualidade(12, 180), 12) == 180
    assert ar.qualidade_da_resposta(_evento_de_qualidade(13, 180), 12) is None
    assert ar.qualidade_da_resposta(_evento_de_qualidade(12, 180, status=1), 12) is None
    assert ar.qualidade_da_resposta(
        _evento_de_qualidade(12, 180, opcode=ar.OPCODE_LER_MAPA_AFH), 12) is None


def test_todo_enlace_do_adaptador_e_lido_e_o_le_nao_pergunta_o_mapa() -> None:
    conexoes = (ar.Enlace(11, "aa:bb:cc:00:00:01", ar.TIPO_ACL, True, 1, 1),
                ar.Enlace(12, "aa:bb:cc:00:00:02", ar.TIPO_ACL, False, 1, 0),
                ar.Enlace(13, "aa:bb:cc:00:00:03", ar.TIPO_LE, True, 1, 1),
                ar.Enlace(14, "aa:bb:cc:00:00:02", ar.TIPO_LE, True, 1, 1))
    leitura = ar.ArDoAdaptador(hci=0, endereco="aa:bb:cc:00:00:aa", conexoes=conexoes)
    perguntados: list[int] = []

    def mapa(_hci: int, handle: int) -> ar.MapaAFH | None:
        perguntados.append(handle)
        if handle == 12:
            return None
        return ar.MapaAFH(handle, 1, tuple(n not in (5, 6) for n in range(79)))

    lidos = ar.enlaces_do_adaptador(leitura, ler_mapa=mapa, ler_qual=lambda _h, handle: handle * 10)
    assert perguntados == [11, 12], "o enlace LE não tem comando de mapa sem root"
    assert lidos["aa:bb:cc:00:00:01"] == ar.EnlaceLido(False, (5, 6), 110)
    assert lidos["aa:bb:cc:00:00:02"] == ar.EnlaceLido(False, None, 120), "o clássico vence o LE"
    assert lidos["aa:bb:cc:00:00:03"] == ar.EnlaceLido(True)


def test_o_estado_publica_os_enlaces_com_o_sinal_e_so_tipos_de_json() -> None:
    lidos = {"aa:bb:cc:00:00:01": ar.EnlaceLido(False, (5, 6), 110),
             "aa:bb:cc:00:00:03": ar.EnlaceLido(True)}
    orc = radio_da_mesa.orcamento_por_adaptador(
        [], enlaces={"aa:bb:cc:00:00:aa": lidos}, sinais={"aabbcc000001": -62})
    publicado = orc["aa:bb:cc:00:00:aa"].publicar()
    assert publicado["enlaces"] == {
        "aabbcc000001": {"le": False, "canais_evitados": [5, 6],
                         "qualidade_do_enlace": 110, "rssi": -62},
        "aabbcc000003": {"le": True, "canais_evitados": None,
                         "qualidade_do_enlace": None, "rssi": None}}
    json.dumps(publicado)


@pytest.mark.asyncio
async def test_o_daemon_le_todo_enlace_numa_thread_e_publica(monkeypatch: object) -> None:
    from tests.unit.test_os_hz_de_cada_controle import ADAPTADOR_A, _handlers

    _daemon, handlers = _handlers(monkeypatch)
    conexoes = (ar.Enlace(12, "aa:bb:cc:00:00:11", ar.TIPO_ACL, True, 1, 7),
                ar.Enlace(13, "aa:bb:cc:00:00:12", ar.TIPO_LE, True, 1, 7))
    leitura = ar.ArDoAdaptador(hci=2, endereco=ADAPTADOR_A, entrada_por_s=700.0,
                               conexoes=conexoes)
    handlers._ler_afh = lambda hci, handle: ar.MapaAFH(  # type: ignore[attr-defined]
        handle, 1, tuple(n not in (40, 41) for n in range(79)))
    handlers._talvez_ler_o_afh({ADAPTADOR_A: leitura})  # type: ignore[attr-defined]
    prazo = time.monotonic() + 2.0
    while handlers._afh_em_voo and time.monotonic() < prazo:  # type: ignore[attr-defined]
        time.sleep(0.01)
    publicado = handlers._enlaces_lidos[ADAPTADOR_A]  # type: ignore[attr-defined]
    assert publicado["aa:bb:cc:00:00:11"] == ar.EnlaceLido(False, (40, 41), None)
    assert publicado["aa:bb:cc:00:00:12"] == ar.EnlaceLido(True)
    assert handlers._afh_evitados == {ADAPTADOR_A: (40, 41)}  # type: ignore[attr-defined]


# --- a tela: a cena vira HTML ------------------------------------------------------------

exigir_gi_real("importa `interface.pacotes.a08_conexoes`, que carrega o GTK")

from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08


def _cena(*, wifi: list[dict[str, Any]] | None = None,
          aparelhos: list[dict[str, Any]] | None = None,
          enlaces: dict[str, Any] | None = None,
          evitados: list[tuple[int, int]] | None = None) -> dict[str, Any]:
    lug = {"id": "L1", "lugar": "L1", "nome": "Esquerda", "entrada": "Entrada 15",
           "sabido": True, "face": "", "hub": False, "varrendo": False, "junto": "",
           "usb3": False, "conectando": False, "chegou": [], "quedas": []}
    return {
        "lido": True, "lugares": [lug],
        "aparelhos": aparelhos or [], "enlaces": enlaces or {},
        "evitados": [{"lugar": "L1", "ini": a, "fim": b} for a, b in evitados or ()],
        "canais_medidos": {"L1": True}, "vizinhos": [], "wifi": wifi or [], "portas": [],
        "pedido": None, "proposta": None, "ocupado": False, "aberto": None, "perto": [],
        "procurando": a08.PROCURAR_DESLIGADO,
    }


def _ap(ident: str, tipo: str, **mais: Any) -> dict[str, Any]:
    return {"id": ident, "tipo": tipo, "lugar": "L1", "nome": ident, "rotulo": ident,
            "cor": "#7eb8d4" if tipo == "controle" else "", "esperando": False, "fixo": False,
            **mais}


def _celulas_com_marca(html: str, ident: str) -> dict[int, str]:
    """`{canal: cor da marca}` de uma linha, lidos do HTML que a tela recebe."""
    linha = re.search(rf'<div class="ar-linha" data-id="{ident}".*?</div></div>', html, re.S)
    assert linha, ident
    return {int(m.group(1)): m.group(2) for m in re.finditer(
        r'<i class="[pb]" title="Canal (\d+) [^"]*(?:perdido para|ocupado aqui)[^"]*">'
        r'<u style="--m:([^"]+)"></u></i>', linha.group(0))}


def test_o_canal_perdido_leva_a_marca_do_wifi_e_o_wifi_leva_a_do_controle() -> None:
    cena = _cena(aparelhos=[_ap("c1", "controle")], evitados=[(50, 58)],
                 wifi=[{"no": "", "mhz": 2462, "largura": 20}])
    html = a08.html_dos_canais(cena)
    marcas = _celulas_com_marca(html, "c1")
    assert set(marcas) == set(range(50, 58)) and set(marcas.values()) == {"var(--c-wifi)"}
    do_wifi = _celulas_com_marca(html, "wifi-0")
    assert set(do_wifi) == set(range(50, 58)) and set(do_wifi.values()) == {"#7eb8d4"}
    assert 'data-briga="wifi-0"' in html and 'data-briga="c1"' in html


def test_o_celular_conectado_aparece_com_o_mapa_dele_e_o_relogio_le_divide_o_radio() -> None:
    enlaces = {"L1": {"cc0000000001": {"le": False, "canais_evitados": [7, 8],
                                       "qualidade_do_enlace": 200, "rssi": -55},
                      "cc0000000002": {"le": True, "canais_evitados": None,
                                       "qualidade_do_enlace": None, "rssi": None}}}
    cena = _cena(aparelhos=[_ap("CC0000000001", "celular"), _ap("CC0000000002", "relogio")],
                 enlaces=enlaces, evitados=[(30, 32)])
    html = a08.html_dos_canais(cena)
    celular = re.search(r'data-id="CC0000000001".*?</div></div>', html, re.S).group(0)
    assert re.findall(r'title="Canal (\d+) [^"]*perdido', celular) == ["7", "8"]
    assert "sinal -55 dBm" in celular and "qualidade do enlace 200/255" in celular
    relogio = re.search(r'data-id="CC0000000002".*?</div></div>', html, re.S).group(0)
    assert fx.DIVIDE_O_RADIO in relogio and "<i " not in relogio.split("ar-estado")[0].split(
        'class="ar-faixa')[1]


def test_todo_aparelho_conectado_no_bluez_vira_linha_com_o_tipo_pelo_icon_class_ou_appearance(
        monkeypatch: pytest.MonkeyPatch) -> None:
    assert a08._tipo_do_aparelho("phone", None) == "celular"
    assert a08._tipo_do_aparelho("", 0x5A020C) == "celular"
    assert a08._tipo_do_aparelho("", 0x000704) == "relogio"
    assert a08._tipo_do_aparelho("", None, 0x00C0) == "relogio"
    assert a08._tipo_do_aparelho("", None, 0x0040) == "celular"
    assert a08._tipo_do_aparelho("", None, 0x0300) == "outro"
    assert a08._tipo_do_aparelho("input-keyboard", None, 0x00C0) == "teclado"


def test_a_legenda_tem_os_sete_tipos_e_a_faixa_nao_tem_as_portas() -> None:
    assert [t for t, _r in a08.LEGENDA_DAS_FAIXAS] == [
        "controle", "celular", "relogio", "wifi", "teclado", "mouse", "ruido"]
    assert "vizinhanca-das-portas" not in a08.campos_da_secao(_cena(aparelhos=[]))
    assert not hasattr(a08, "html_das_portas")


# --- a tela no WebKit: a geometria e o hover ---------------------------------------------

SONDA = r"""
(function(){
  document.getElementById('cx8-3').checked = true;
  const sem_transicao = document.createElement('style');
  sem_transicao.textContent = '.radio .ar-linha{transition:none !important}';
  document.head.appendChild(sem_transicao);
  const fora = {};
  const cab = document.querySelector('.radio .espectro-cab');
  const leg = cab.querySelector('.ar-legenda');
  const rc = cab.getBoundingClientRect(), rl = leg.getBoundingClientRect();
  fora.legenda_na_linha = rl.top >= rc.top - 2 && rl.bottom <= rc.bottom + 2 && rc.height < 44;
  const faixas = [...document.querySelectorAll('.radio .ar-faixa:not(.sem)')];
  fora.faixas = faixas.length;
  fora.celulas = faixas.map(f => f.children.length);
  fora.larguras = faixas.map(f => Math.round(f.getBoundingClientRect().width));
  const linhas = [...document.querySelectorAll('.radio .ar-linha')];
  fora.ids = linhas.map(l => l.dataset.id);
  const alvo = linhas.find(l => l.dataset.tipo === 'controle');
  const acesas = () => linhas.filter(l => l.classList.contains('acesa')).map(l => l.dataset.id);
  const pistas = document.querySelector('.radio .pistas');
  fora.antes = acesas();
  alvo.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));
  fora.alvo = alvo.dataset.id;
  fora.briga = (alvo.dataset.briga || '').split(' ').filter(Boolean);
  fora.acesas = acesas();
  fora.foco = pistas.hasAttribute('data-foco');
  const apagada = linhas.find(l => !l.classList.contains('acesa'));
  fora.opacidade_apagada = apagada ? getComputedStyle(apagada).opacity : null;
  fora.opacidade_acesa = getComputedStyle(alvo).opacity;
  alvo.dispatchEvent(new MouseEvent('mouseout', {bubbles: true}));
  fora.depois = acesas();
  const botao = document.querySelector('.radio .ar-legenda button[data-tipo-da-legenda="wifi"]');
  botao.click();
  fora.legenda_wifi = acesas();
  fora.pressionado = botao.getAttribute('aria-pressed');
  botao.click();
  fora.solto = acesas();
  return JSON.stringify(fora);
})()
"""


def _no_webkit(pagina: Path, antes: str = "") -> dict[str, Any]:
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
                antes + SONDA, -1, None, None, None, guardou), False)[1])

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


@pytest.fixture(scope="module")
def na_pagina() -> dict[str, Any]:
    return _no_webkit(MOCKUP)


def test_toda_faixa_tem_79_canais_do_mesmo_tamanho_e_a_legenda_esta_no_titulo(
        na_pagina: dict[str, Any]) -> None:
    assert na_pagina["faixas"] >= 6
    assert set(na_pagina["celulas"]) == {79}
    assert len(set(na_pagina["larguras"])) == 1, na_pagina["larguras"]
    assert na_pagina["legenda_na_linha"] is True


def test_passar_o_mouse_numa_linha_acende_ela_e_quem_briga_e_esmaece_o_resto(
        na_pagina: dict[str, Any]) -> None:
    f = na_pagina
    assert f["antes"] == [] and f["foco"] is True
    assert set(f["acesas"]) == {f["alvo"], *f["briga"]} & set(f["ids"])
    assert len(f["acesas"]) >= 3, "a briga do desenho não acendeu ninguém"
    assert float(f["opacidade_apagada"]) < 0.5 and float(f["opacidade_acesa"]) == 1.0
    assert f["depois"] == []


def test_a_legenda_acende_os_aparelhos_do_tipo_e_quem_perde_para_ele(
        na_pagina: dict[str, Any]) -> None:
    f = na_pagina
    assert f["pressionado"] == "true"
    assert any(i.startswith("wifi") or i == "E3" for i in f["legenda_wifi"])
    assert f["alvo"] in f["legenda_wifi"], "o controle que perde canais para o Wi-Fi não acendeu"
    assert f["solto"] == []


def test_mordida_sem_o_script_o_hover_nao_acende_nada(tmp_path: Path) -> None:
    """A MESMA página com o roteiro das faixas desligado: se o teste do hover passasse
    aqui, ele não mediria o roteiro."""
    pagina = MOCKUP.read_text(encoding="utf-8")
    assert pagina.count("if(window.__hefFaixas) return;") == 1
    cega = tmp_path / "08-sem-o-roteiro.html"
    cega.write_text(pagina.replace("if(window.__hefFaixas) return;", "return;"),
                    encoding="utf-8")
    sem = _no_webkit(cega)
    assert sem["acesas"] == [] and sem["foco"] is False
