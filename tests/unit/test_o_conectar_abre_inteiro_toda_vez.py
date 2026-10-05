"""O «Conectar» abre inteiro toda vez — O-CONECTAR-ABRE-INTEIRO-TODA-VEZ-01."""

from __future__ import annotations

import gc
import re
import time
from typing import Any

import pytest

from tests.unit import radio_de_mentira as rm
from tests.unit.radio_de_mentira import VERMELHO

PCI = "0000:00:14.0"
ADAPTADORES = ("aa:bb:cc:00:00:09", "aa:bb:cc:00:00:15", "aa:bb:cc:00:00:21")
LUGARES = (f"pci-{PCI}-usb-0:1.2", f"pci-{PCI}-usb-0:4.1.4", f"pci-{PCI}-usb-0:4.1.3")
NOMES = ("Esquerda", "Direita", "Centro")
PULSEIRA = "aa:bb:cc:00:00:31"
BALANCA = "aa:bb:cc:00:00:32"
A, B, C = "aa:bb:cc:00:00:3a", "aa:bb:cc:00:00:3b", "aa:bb:cc:00:00:3c"


def _id(endereco: str) -> str:
    """O id da tela: 12 hex em maiúsculas, a forma do ``_mac`` do pacote."""
    return endereco.replace(":", "").upper()


def _visto(adaptador: int, aparelho: str, rssi: int, **kw: Any) -> Any:
    """Um aparelho que o adaptador ``hci{adaptador}`` está vendo, com o sinal dele."""
    from hefesto_dualsense4unix.integrations.bluez_dbus import AparelhoDoBluez

    no = f"/org/bluez/hci{adaptador}/dev_{aparelho.upper().replace(':', '_')}"
    return AparelhoDoBluez(no, f"/org/bluez/hci{adaptador}", aparelho.upper(),
                           nome=kw.pop("nome", "Aparelho"), conectado=False, pareado=False,
                           rssi=rssi, classe=0x000704, **kw)


@pytest.fixture()
def a08(monkeypatch: pytest.MonkeyPatch) -> Any:
    from hefesto_dualsense4unix.integrations.mesa_de_radio import Mesa
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

    for nome in ("_FUNDO", "_ABERTO", "_CENA_NA_TELA", "_SALA_NA_TELA", "_CHEGADAS"):
        monkeypatch.setattr(a08_conexoes, nome, {})
    monkeypatch.setattr(a08_conexoes, "LER_NA_HORA", True)
    monkeypatch.setattr(a08_conexoes, "_mesa_do_radio", lambda recarregar=False: Mesa())
    monkeypatch.setattr(a08_conexoes, "_ler_o_historico", lambda: {})
    maquina = MaquinaConfig(adaptadores={_id(ADAPTADORES[i]).lower(): {"nome": NOMES[i]}
                                         for i in range(3)})
    monkeypatch.setattr(a08_conexoes, "_ler_a_maquina", lambda: (maquina, {3: PCI}))
    return a08_conexoes


def _ler(a08: Any, monkeypatch: pytest.MonkeyPatch, aparelhos: tuple[Any, ...] = (),
         varrendo: tuple[bool, bool, bool] = (False, False, False)) -> None:
    """Uma leitura nova do BlueZ: os três adaptadores, e o que eles veem."""
    from hefesto_dualsense4unix.integrations.bluez_dbus import AdaptadorDoBluez

    lidos = tuple(AdaptadorDoBluez(f"/org/bluez/hci{i}", f"hci{i}", ADAPTADORES[i].upper(),
                                   lugar=LUGARES[i], varrendo=varrendo[i])
                  for i in range(3))
    a08._FUNDO.clear()
    monkeypatch.setattr(a08, "_ler_o_bluez", lambda: (lidos, aparelhos))


def _busca(adaptador: int, *, passo: str = "gesto", aparelho: str = "",
           ha_s: float = 2.0) -> dict[str, Any]:
    """Um movimento da central esperando no adaptador ``hci{adaptador}``."""
    return {"aparelho": aparelho, "destino": ADAPTADORES[adaptador], "estado": "esperando",
            "passo": passo, "quando": time.time() - ha_s, "e_controle": bool(aparelho)}


def _campos(a08: Any, *movimentos: dict[str, Any], busca: int | None = None) -> dict[str, Any]:
    """Um tique da seção, com o que a central publicou. ``busca``: o adaptador"""
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    publicada = None if busca is None else {
        "adaptador": ADAPTADORES[busca], "desde": time.time() - 2.0, "ate": time.time() + 118.0}
    estado = {"controllers": [],
              "radio_central": {"movimentos": list(movimentos), "proposta": None,
                                "busca": publicada}}
    return dict(a08.campos_do_radio(Contexto(state=estado, conectados=[], mesa=[])))


def _chip(a08: Any, adaptador: int) -> None:
    """O clique dela no chip (ou na caixa): o adaptador aberto é o destino."""
    a08._ABERTO["lugar"] = _id(ADAPTADORES[adaptador])


def _molde_do_conectar(campos: dict[str, Any]) -> str:
    achado = re.search(r'<template class="painel-molde" data-painel="conectar".*?</template>',
                       str(campos["radio-moldes"]), re.S)
    assert achado, "sem o molde do «Conectar»"
    return achado.group(0)


def _linhas(campos: dict[str, Any]) -> list[tuple[str, int]]:
    """As linhas do «Conectar», na ordem: (endereço, sinal)."""
    molde = _molde_do_conectar(campos)
    return [(alvo, int(forca)) for alvo, forca in re.findall(
        r'<div class="achado" data-alvo="([^"]+)">.*?<span class="forca"[^>]*>(-?\d+) dBm',
        molde, re.S)]


def _chips(campos: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Os chips do «Conectar», por adaptador: os atributos de cada um."""
    chips = {}
    for botao in re.findall(r'<button class="op"[^>]*>', _molde_do_conectar(campos)):
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', botao))
        chips[attrs["data-alvo"]] = attrs
    return chips


def _cartao(sala: str, adaptador: int) -> str:
    achado = re.search(r'<div class="([^"]*)" data-id="' + _id(ADAPTADORES[adaptador]) + '"',
                       sala)
    assert achado, f"sem o cartão do adaptador {adaptador}"
    return achado.group(1)


def test_o_sinal_muda_o_numero_e_nao_a_linha(a08: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A pulseira e a balança com sinais que se cruzam (-60 e -70, depois -70 e"""
    _chip(a08, 0)
    _ler(a08, monkeypatch, (_visto(0, PULSEIRA, -60), _visto(0, BALANCA, -70)))
    antes = _linhas(_campos(a08))
    _ler(a08, monkeypatch, (_visto(0, PULSEIRA, -70), _visto(0, BALANCA, -60)))
    depois = _linhas(_campos(a08))

    assert [a for a, _ in antes] == [a for a, _ in depois] == [_id(PULSEIRA), _id(BALANCA)]
    assert dict(antes) == {_id(PULSEIRA): -60, _id(BALANCA): -70}
    assert dict(depois) == {_id(PULSEIRA): -70, _id(BALANCA): -60}


def test_a_lista_nao_anda_e_recomeca_com_a_busca(
        a08: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A, B e C chegam nessa ordem, com sinais que se invertem a cada leitura:"""
    _chip(a08, 0)
    primeira = _busca(0, ha_s=30.0)
    leituras = (
        ((A, -50),),
        ((A, -70), (B, -50)),
        ((A, -50), (B, -70), (C, -40)),
        ((A, -70), (B, -50), (C, -80)),
        ((A, -40), (B, -80), (C, -60)),
    )
    for n, leitura in enumerate(leituras, start=1):
        _ler(a08, monkeypatch, tuple(_visto(0, quem, rssi) for quem, rssi in leitura))
        vistos = [_id(quem) for quem, _ in leitura]
        assert [a for a, _ in _linhas(_campos(a08, primeira, busca=0))] == vistos, f"leitura {n}"

    todos = tuple(_visto(0, quem, rssi) for quem, rssi in ((A, -70), (B, -60), (C, -40)))
    _ler(a08, monkeypatch, todos)
    _campos(a08)
    segunda = _busca(0, ha_s=1.0)
    assert [a for a, _ in _linhas(_campos(a08, segunda, busca=0))] == [_id(C), _id(B), _id(A)]


def test_a_busca_e_a_varredura_nao_trocam_a_sala(
        a08: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A Esquerda passa a varrer e para; uma busca começa e acaba nela: a"""
    _chip(a08, 0)
    tiques = []
    for varrendo, movimentos, busca in (
            ((False, False, False), (), None),
            ((True, False, False), (), None),
            ((False, False, False), (), None),
            ((False, False, False), (_busca(0),), 0),
            ((False, False, False), (), None),
    ):
        _ler(a08, monkeypatch, varrendo=varrendo)
        tiques.append(_campos(a08, *movimentos, busca=busca))

    salas = {t["radio-sala"] for t in tiques}
    assert len(salas) == 1, "a sala se refez com a varredura ou a busca"
    sala = tiques[0]["radio-sala"]
    assert sala.count('data-campo="radio-varrendo"') == 3
    assert sala.count('data-campo="radio-conectando"') == 3
    assert [t["radio-varrendo"] for t in tiques] == [
        ["", "", ""], ["sim", "", ""], ["", "", ""], ["", "", ""], ["", "", ""]]
    assert [t["radio-conectando"] for t in tiques] == [
        ["", "", ""], ["", "", ""], ["", "", ""], ["sim", "", ""], ["", "", ""]]
    assert [t["radio-ocupado"] for t in tiques] == ["", "", "", "sim", ""]
    # o «Arraste outro para cá» saiu no desenho aprovado de 05/10/2026: a sala não traz o botão
    assert 'class="soltar' not in sala


def test_quem_espera_num_mover_continua_na_sala(
        a08: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """O controle que ela moveu para a Direita, esperando o gesto, é conteúdo"""
    _ler(a08, monkeypatch)
    campos = _campos(a08, _busca(1, aparelho=rm.uniq(VERMELHO)))
    assert "esperando" in _cartao(campos["radio-sala"], 1).split()
    assert "esperando" not in _cartao(campos["radio-sala"], 0).split()


def test_a_lista_e_do_chip_aceso_com_o_sinal_dele(
        a08: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A pulseira vista só pela Esquerda fica fora da lista do Centro, e"""
    _ler(a08, monkeypatch, (_visto(0, PULSEIRA, -60), _visto(0, BALANCA, -50),
                            _visto(2, BALANCA, -80)))
    _chip(a08, 2)
    centro = dict(_linhas(_campos(a08)))
    _chip(a08, 0)
    esquerda = dict(_linhas(_campos(a08)))

    assert centro == {_id(BALANCA): -80}
    assert esquerda == {_id(PULSEIRA): -60, _id(BALANCA): -50}


def test_o_desenho_tem_os_achados_no_painel_do_destino_dele() -> None:
    """A cena do desenho (``aba08``) dá a cada achado o adaptador do destino do"""
    from hefesto_dualsense4unix.interface import aba08

    linhas = _linhas({"radio-moldes": aba08.CAMPOS_DO_RADIO["radio-moldes"]})
    assert len(linhas) == len(aba08.CENA_DO_RADIO["perto"]) >= 3


@pytest.mark.parametrize("passo", ["pareando", "conferindo"])
def test_depois_do_gesto_o_chip_de_outro_adaptador_diz_que_agora_nao(
        a08: Any, monkeypatch: pytest.MonkeyPatch, passo: str) -> None:
    """Com a busca na Esquerda e o controle já pareando ou conferindo, a"""
    _ler(a08, monkeypatch)
    chips = _chips(_campos(a08, _busca(0, passo=passo, aparelho=rm.uniq(VERMELHO))))
    esquerda, direita, centro = (chips[_id(e)] for e in ADAPTADORES)

    assert esquerda["aria-pressed"] == "true"
    assert esquerda.get("data-gesto") == "escolher-adaptador"
    assert "aria-disabled" not in esquerda
    for chip in (direita, centro):
        assert "data-gesto" not in chip
        assert chip["aria-disabled"] == "true"
        assert chip["title"] == a08.ESPERANDO_O_CONTROLE


def test_no_gesto_todo_chip_pede_ao_radio(a08: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """No passo ``gesto`` a central ainda leva a busca junto: nenhum chip apaga."""
    _ler(a08, monkeypatch)
    for chips in (_chips(_campos(a08, _busca(0, passo="gesto"), busca=0)),
                  _chips(_campos(a08))):
        for chip in chips.values():
            assert chip.get("data-gesto") == "escolher-adaptador"
            assert "aria-disabled" not in chip


def test_o_chip_de_um_mover_conferindo_tambem_diz_que_agora_nao(
        a08: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """O chip de outro adaptador com um «Mover» de pé TAMBÉM pede ao rádio: o"""
    _ler(a08, monkeypatch)
    quem = rm.uniq(VERMELHO)
    conferindo = _chips(_campos(a08, _busca(1, passo="conferindo", aparelho=quem)))
    assert conferindo[_id(ADAPTADORES[1])].get("data-gesto") == "escolher-adaptador"
    for outro in (ADAPTADORES[0], ADAPTADORES[2]):
        assert conferindo[_id(outro)]["aria-disabled"] == "true"
    no_gesto = _chips(_campos(a08, _busca(1, passo="gesto", aparelho=quem)))
    assert all("aria-disabled" not in c for c in no_gesto.values())


PASSOS_DO_PAINEL = (
    r"""(function(){
      document.getElementById('rd-b-conectar').click();
      const no = document.querySelector('#rd-painel-corpo .achado[data-alvo="D3"] button');
      window.__r6 = {no: no};
      const painel = document.getElementById('rd-painel');
      return JSON.stringify({aberto: painel.classList.contains('aberto'), tem: !!no});
    })()""",
    r"""(function(){
      const caixa = document.querySelector('.moldes[data-campo="radio-moldes"]');
      const t = document.createElement('div'); t.innerHTML = caixa.innerHTML;
      const m = t.querySelector('template[data-painel="conectar"]');
      m.content.querySelector('.achado[data-alvo="D3"] .forca').textContent = '-61 dBm';
      caixa.innerHTML = t.innerHTML;
      return '{}';
    })()""",
    r"""(function(){
      const linha = document.querySelector('#rd-painel-corpo .achado[data-alvo="D3"]');
      const fora = {mesmo: linha.querySelector('button') === window.__r6.no,
                    forca: linha.querySelector('.forca').textContent};
      const caixa = document.querySelector('.moldes[data-campo="radio-moldes"]');
      const t = document.createElement('div'); t.innerHTML = caixa.innerHTML;
      t.querySelector('template[data-painel="conectar"]').content
        .querySelector('.achado[data-alvo="D2"]').remove();
      caixa.innerHTML = t.innerHTML;
      return JSON.stringify(fora);
    })()""",
    r"""(function(){
      const linha = document.querySelector('#rd-painel-corpo .achado[data-alvo="D3"]');
      const fora = {mesmo: !!linha && linha.querySelector('button') === window.__r6.no,
                    forca: linha ? linha.querySelector('.forca').textContent : '',
                    balanca: !!document.querySelector('#rd-painel-corpo .achado[data-alvo="D2"]'),
                    ordem: [...document.querySelectorAll('#rd-painel-corpo .achado')]
                      .map(a => a.dataset.alvo)};
      const caixa = document.querySelector('.moldes[data-campo="radio-moldes"]');
      const t = document.createElement('div'); t.innerHTML = caixa.innerHTML;
      t.querySelector('template[data-painel="conectar"]').setAttribute('data-titulo', 'Conectar');
      caixa.innerHTML = t.innerHTML;
      return JSON.stringify(fora);
    })()""",
    r"""(function(){
      const linha = document.querySelector('#rd-painel-corpo .achado[data-alvo="D3"]');
      return JSON.stringify({
        mesmo: !!linha && linha.querySelector('button') === window.__r6.no,
        titulo: document.getElementById('rd-painel-titulo').textContent,
        aberto: document.getElementById('rd-painel').classList.contains('aberto')});
    })()""",
)


@pytest.fixture(scope="module")
def painel_no_webkit() -> list[dict[str, Any]]:
    """A bancada da 08 num WebKit offscreen — o motor que ela usa —, com os"""
    import json

    from hefesto_dualsense4unix.interface import onde

    pagina = onde.pagina("08-conexoes.html")
    if not pagina.is_file():
        pytest.skip("a bancada da 08 não está no disco — rode o gerador")
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    saiu: list[str] = []
    janela = Gtk.OffscreenWindow()
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def proximo(v: Any) -> None:
        if len(saiu) == len(PASSOS_DO_PAINEL):
            Gtk.main_quit()
            return
        v.evaluate_javascript(PASSOS_DO_PAINEL[len(saiu)], -1, None, None, None, guardou)

    def guardou(v: Any, res: Any) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:  # pragma: no cover — só quando o roteiro quebra
            saiu.append(f"ERRO {e}")
            Gtk.main_quit()
            return
        GLib.timeout_add(50, lambda: proximo(v) and False)

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            proximo(v)

    view.connect("load-changed", carregou)
    view.load_uri(pagina.as_uri())
    guarda = GLib.timeout_add(30000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
        view = janela = None
        gc.collect()
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
    assert len(saiu) == len(PASSOS_DO_PAINEL), f"o WebKit parou no passo {len(saiu)}: {saiu}"
    erros = [s for s in saiu if s.startswith("ERRO")]
    assert not erros, erros
    return [dict(json.loads(s)) for s in saiu]


def test_o_painel_aberto_se_remenda_no_webkit(painel_no_webkit: list[dict[str, Any]]) -> None:
    """O painel do «Conectar» aberto segue o molde novo SEM refazer as linhas:"""
    aberto, _, sinal, sem_balanca, titulo = painel_no_webkit
    assert aberto == {"aberto": True, "tem": True}
    assert sinal == {"mesmo": True, "forca": "-61 dBm"}
    assert sem_balanca == {"mesmo": True, "forca": "-61 dBm", "balanca": False,
                           "ordem": ["D1", "D3"]}
    assert titulo == {"mesmo": True, "titulo": "Conectar", "aberto": True}


def test_a_linha_da_08_diz_a_parte_em_que_o_tique_gastou(
        a08: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Um mapa de mentira que dorme 120 ms: a linha ``[08 lento]`` diz o mapa"""
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    def mapa_lento() -> str:
        time.sleep(0.12)
        return ""

    for nome, falso in (
            ("_pedir_o_exame_de_entrada", lambda: None), ("_itens_da_tela", lambda: []),
            ("_declaracao", lambda: {}), ("_orcamento_da_mesa", lambda: (None, False)),
            ("_correr_as_esperas", lambda: None), ("_nomes_dos_donos", lambda: {}),
            ("_confissao_do_mapa", lambda: {}), ("campos_do_radio", lambda _ctx: {}),
            ("_html_do_mapa", mapa_lento), ("campos_do_mapear", lambda: {}),
            ("_html_dos_aparelhos", lambda: ""), ("_html_das_dicas", lambda *_a: ""),
            ("_sala_na_tela", lambda *_a: {}), ("_html_dos_externos", lambda _ctx: ""),
    ):
        monkeypatch.setattr(a08, nome, falso)
    monkeypatch.setattr(a08.perfil, "ativo", lambda *_a: None)

    a08.pacote(Contexto(state={}, conectados=[], mesa=[]))

    linhas = [x for x in capsys.readouterr().err.splitlines() if x.startswith("[08 lento]")]
    assert len(linhas) == 1, linhas
    numeros = dict(re.findall(r"(\w+) (\d+)", linhas[0]))
    assert int(numeros["mapa"]) >= 100, linhas[0]
    assert int(numeros["cpu"]) < 20, linhas[0]
    for parte in ("rádio", "exame", "gestão", "resto"):
        assert int(numeros[parte]) < 20, (parte, linhas[0])
