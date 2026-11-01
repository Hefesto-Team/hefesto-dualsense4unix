"""O gerenciador de tema cumpre as seis promessas
(O-GERENCIADOR-DE-TEMA-CUMPRE-AS-SEIS-PROMESSAS-01).

- D1: o glifo dos botões da barra é o mesmo com o pacote de ícones de traço e com o Adwaita.
- D2: no Escuro, a barra é a mesma com e sem o destaque: a da interface.
- D3: fora de foco, os botões da barra pintada esmaecem, em todo tema.
- D4: o tema importado recusado diz a marca na linha do tema, com a frase inteira na dica.
- D5: a janela aberta segue o desligar feito de fora; o foco que o código dá à janela que abre
  (e a quem a abriu, quando a janela fecha) não abre a dica.

Extensões FALSAS num lar de mentira; a barra no ``Gtk.OffscreenWindow`` da sonda da sprint
anterior; a dica no WebKit do produto, com o X de mentira.

MORDIDAS (01/11/2026, executadas sobre a cura e devolvidas, md5 conferido):

- o ``GLIFOS.get`` do ``GlifoDaBarra`` trocado por ``None`` (volta o ícone da sessão) reprova
  ``test_d1_o_glifo_e_o_mesmo_com_o_traco_e_com_o_adwaita``;
- o ``css_da_cor_da_barra`` vazio para a folha vazia reprova
  ``test_d2_o_escuro_da_a_mesma_barra_com_e_sem_destaque``;
- a regra ``button.titlebutton:backdrop`` arrancada reprova
  ``test_d3_fora_de_foco_os_botoes_esmaecem_em_todo_tema``;
- o ``except`` do ``importar_na_modificacao`` arrancado reprova
  ``test_d4_o_tema_importado_ilegivel_diz_ilegivel_na_linha_do_tema``,
  ``test_d4_o_tema_que_nao_serve_diz_nao_ligou_com_a_frase`` e
  ``test_d4_a_logo_recusada_diz_na_linha_da_logo``;
- o ``_pinta`` fora da comparação do ``_seguir_o_meu_css`` reprova
  ``test_d5_a_janela_aberta_segue_o_desligar_de_fora``; o ``pinta`` ignorado no ``retratar``
  também;
- o ``focarSemDica`` trocado por ``focus()`` na base comum, e a guarda
  ``__hefFocoDoCodigo`` arrancada da camada da dica do produto, reprovam cada um
  ``test_d5_o_foco_que_a_janela_da_nao_abre_a_dica``.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.mods import importados, instalador, opcoes, tema
from hefesto_dualsense4unix.mods.instalador import Lugares
from tests.unit.test_o_gerenciador_de_tema_nasce_ligado import _sondar, _tema_de_icones_de_traco
from tests.unit.test_o_tema_por_escolha_importa_e_personaliza import (
    CLARO,
    NOVA,
    _arquivo,
    _ligada,
    _manifesto,
    _pasta,
    _png,
)

RAIZ = Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
ICONES = ("TemaDeTraco", "Adwaita")
DESTAQUE = "#9ef0d2"
ILEGIVEL = CLARO.replace("--fg:#1c1e29", "--fg:#f4f5f8")


def _lugares(raiz: Path) -> Lugares:
    return Lugares(codigo=raiz / "codigo", dados=raiz / "dados",  # (noqa-acento)
                   registro=raiz / "config" / "mods.json",
                   estado=raiz / "run" / "mods-estado.json")


@pytest.fixture(scope="module")
def folhas(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    raiz = tmp_path_factory.mktemp("folhas")
    lg = _lugares(raiz)
    manifesto = _ligada(lg, _pasta(raiz, _manifesto()))
    saida = {"escuro": tema.tema_da_casa(lg).folha}
    opcoes.guardar(manifesto, "destaque", True, lg)
    opcoes.guardar(manifesto, "cor_de_destaque", DESTAQUE, lg)
    saida["escuro-com-destaque"] = tema.tema_da_casa(lg).folha
    opcoes.guardar(manifesto, "tema", "Claro", lg)
    saida["claro-com-destaque"] = tema.tema_da_casa(lg).folha
    opcoes.guardar(manifesto, "destaque", False, lg)
    saida["claro"] = tema.tema_da_casa(lg).folha
    return saida


@pytest.fixture(scope="module")
def sondas(tmp_path_factory: pytest.TempPathFactory,
           folhas: dict[str, str]) -> dict[tuple[str, str], dict[str, Any]]:
    raiz = tmp_path_factory.mktemp("icones")
    _tema_de_icones_de_traco(raiz)
    return {(nome, icones): _sondar(raiz, folha, icones)["botoes"]
            for nome, folha in folhas.items() for icones in ICONES}


def test_as_folhas_sao_as_que_a_casa_pinta(folhas: dict[str, str]) -> None:
    assert folhas["escuro"] == ""
    assert tema.tokens_da_folha(folhas["escuro-com-destaque"]) == {tema.TOKEN_DO_DESTAQUE: DESTAQUE}
    assert tema.tokens_da_folha(folhas["claro"])["--panel"] == "#ffffff"
    assert tema.tokens_da_folha(folhas["claro-com-destaque"])["--panel"] == "#ffffff"


def test_d1_o_glifo_e_o_mesmo_com_o_traco_e_com_o_adwaita(
        sondas: dict[tuple[str, str], dict[str, Any]], folhas: dict[str, str]) -> None:
    for nome in folhas:
        traco, adwaita = sondas[(nome, "TemaDeTraco")], sondas[(nome, "Adwaita")]
        for chave, lido in traco.items():
            assert lido["mapa"] == adwaita[chave]["mapa"], (nome, chave)
            assert lido["tinta"], f"{nome} {chave}: o botão saiu sem glifo"
        assert traco["False|False|maximizar"]["meio"] == traco["False|False|maximizar"]["fundo"]


def test_d2_o_escuro_da_a_mesma_barra_com_e_sem_destaque(
        sondas: dict[tuple[str, str], dict[str, Any]]) -> None:
    casa = tema.tokens_da_casa()
    for icones in ICONES:
        sem, com = sondas[("escuro", icones)], sondas[("escuro-com-destaque", icones)]
        for chave, lido in sem.items():
            assert (lido["fundo"], lido["tinta"]) == (com[chave]["fundo"], com[chave]["tinta"]), (
                icones, chave)
            assert lido["fundo"] == casa["--panel"], (icones, chave)
        assert sondas[("claro", icones)]["False|False|fechar"]["fundo"] == "#ffffff"


def test_d3_fora_de_foco_os_botoes_esmaecem_em_todo_tema(
        sondas: dict[tuple[str, str], dict[str, Any]], folhas: dict[str, str]) -> None:
    for nome in folhas:
        for icones in ICONES:
            lidos = sondas[(nome, icones)]
            for chave, lido in lidos.items():
                maximizada, fora, gesto = chave.split("|")
                if fora == "True":
                    continue
                apagado = lidos[f"{maximizada}|True|{gesto}"]
                assert apagado["fundo"] == lido["fundo"], (nome, icones, chave)
                assert set(apagado["tinta"]) != set(lido["tinta"]), (
                    f"{nome} {icones} {chave}: o fora de foco ficou igual ao em foco")


@pytest.fixture
def lg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Lugares:
    lugares = _lugares(tmp_path)
    monkeypatch.setattr(Lugares, "do_xdg", classmethod(lambda cls: lugares))
    return lugares


@pytest.fixture
def a07(lg: Lugares, monkeypatch: pytest.MonkeyPatch) -> Any:
    sys.path.insert(0, str(INTERFACE))
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores

    monkeypatch.setattr(a07_lancadores.VIGIA, "_disparar", lambda: None)
    a07_lancadores.REGISTRO.esquecer()
    a07_lancadores._MEXIDA.limpar()
    yield a07_lancadores
    a07_lancadores.REGISTRO.esquecer()
    a07_lancadores._MEXIDA.limpar()


@pytest.fixture
def ctx() -> Any:
    sys.path.insert(0, str(INTERFACE))
    import pacotes

    return pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})


class _Ponte:
    def __init__(self, escolhido: Path) -> None:
        self.escolhido = escolhido

    def escolher_arquivo(self, titulo: str, padrao: str = "*", **_: Any) -> str:
        return str(self.escolhido)


def _secao(html: str, opcao: str) -> str:
    achado = re.search(rf'id="mod-op-{opcao}".*?(?=class="tm-sec"|class="mj-faixa|$)', html, re.S)
    assert achado, f"a seção da opção {opcao} não está na janela"
    return achado.group(0)


def test_d4_o_tema_importado_ilegivel_diz_ilegivel_na_linha_do_tema(
        a07: Any, ctx: Any, lg: Lugares, tmp_path: Path) -> None:
    manifesto = _ligada(lg, _pasta(tmp_path, _manifesto()))
    a07._montar_a_janela_da_extensao(NOVA)
    assert "tm-recusa" not in a07._MEXIDA.html_mod
    ruim = _arquivo(tmp_path, "ruim.css", ILEGIVEL)
    with pytest.raises(RuntimeError, match="ilegível"):
        a07.importar_na_modificacao(ctx, {"v": f"{NOVA}:tema_importado"}, _Ponte(ruim))
    secao = _secao(a07._MEXIDA.html_mod, "tema")
    assert re.search(r'class="tm-recusa" data-dica="O texto ficaria ilegível[^"]*">Ilegível<',
                     secao), secao[-600:]
    assert a07._MEXIDA.html_mod.count("tm-recusa") == 1
    assert a07._MEXIDA.aba == "Cores"
    assert opcoes.ler(manifesto, lg)["tema"] == "Escuro"
    assert not importados.caminho(NOVA, "tema_importado", lg).exists()
    bom = _arquivo(tmp_path, "bom.css", CLARO)
    a07.importar_na_modificacao(ctx, {"v": f"{NOVA}:tema_importado"}, _Ponte(bom))
    assert "tm-recusa" not in a07._MEXIDA.html_mod, "a recusa ficou depois do importar bom"
    assert opcoes.ler(manifesto, lg)["tema"] == "Importado"


def test_d4_o_tema_que_nao_serve_diz_nao_ligou_com_a_frase(
        a07: Any, ctx: Any, lg: Lugares, tmp_path: Path) -> None:
    _ligada(lg, _pasta(tmp_path, _manifesto()))
    a07._montar_a_janela_da_extensao(NOVA)
    grande = _arquivo(tmp_path, "grande.css", "x" * (17 * 1024))
    with pytest.raises(RuntimeError, match="16 KB"):
        a07.importar_na_modificacao(ctx, {"v": f"{NOVA}:tema_importado"}, _Ponte(grande))
    assert re.search(r'class="tm-recusa" data-dica="O arquivo passa de 16 KB[^"]*">Não ligou<',
                     _secao(a07._MEXIDA.html_mod, "tema"))
    a07._seguir_o_meu_css(a07.REGISTRO.ler())
    assert "tm-recusa" in a07._MEXIDA.html_mod, "a recusa sumiu no tique seguinte"


def test_d4_a_logo_recusada_diz_na_linha_da_logo(
        a07: Any, ctx: Any, lg: Lugares, tmp_path: Path) -> None:
    _ligada(lg, _pasta(tmp_path, _manifesto()))
    a07._montar_a_janela_da_extensao(NOVA)
    falsa = _arquivo(tmp_path, "logo.png", b"<svg onload=alert(1)>")
    with pytest.raises(RuntimeError, match="PNG, JPEG ou WebP"):
        a07.importar_na_modificacao(ctx, {"v": f"{NOVA}:logo"}, _Ponte(falsa))
    assert re.search(r'class="tm-recusa" data-dica="[^"]*PNG, JPEG ou WebP[^"]*">Não ligou<',
                     _secao(a07._MEXIDA.html_mod, "logo"))
    assert "tm-recusa" not in _secao(a07._MEXIDA.html_mod, "tema")


def _coluna(html: str) -> dict[str, str]:
    linhas = re.findall(r'<span class="ja-rot">([^<]+)</span>(.*?)</div>', html)
    return {rotulo: re.sub(r"<[^>]+>", "", miolo) for rotulo, miolo in linhas}


def _faixa(html: str) -> str:
    achado = re.search(r'class="tm-paleta">(.*?)</div>', html, re.S)
    assert achado, "a faixa «Ao vivo» não está na janela"
    return achado.group(1)


def test_d5_a_janela_aberta_segue_o_desligar_de_fora(
        a07: Any, lg: Lugares, tmp_path: Path) -> None:
    manifesto = _ligada(lg, _pasta(tmp_path, _manifesto()))
    opcoes.guardar(manifesto, "destaque", True, lg)
    opcoes.guardar(manifesto, "cor_de_destaque", DESTAQUE, lg)
    opcoes.guardar(manifesto, "botoes", "Esquerda", lg)
    importados.importar(manifesto, "logo", _arquivo(tmp_path, "logo.png", _png()), lg)
    a07._montar_a_janela_da_extensao(NOVA)
    ligada = a07._MEXIDA.html_mod
    assert _coluna(ligada) == {"Destaque": DESTAQUE, "Botões": "Esquerda", "Logo": "Importada",
                               "CSS": "Desligado"}
    assert DESTAQUE in _faixa(ligada)
    instalador.desligar(NOVA, lugares=lg)
    a07.REGISTRO.esquecer()
    a07._seguir_o_meu_css(a07.REGISTRO.ler())
    desligada = a07._MEXIDA.html_mod
    assert _coluna(desligada) == {"Destaque": "—", "Botões": "—", "Logo": "Da casa",
                                  "CSS": "Desligado"}, "a janela não seguiu o desligar de fora"
    assert DESTAQUE not in _faixa(desligada)
    assert tema.tokens_da_casa()[tema.TOKEN_DO_DESTAQUE] in _faixa(desligada)
    assert f'value="{DESTAQUE}"' in _secao(desligada, "cor_de_destaque"), "a escolha guardada sumiu"
    instalador.ligar(NOVA, permissoes_vistas=manifesto.permissoes, lugares=lg)
    a07.REGISTRO.esquecer()
    a07._seguir_o_meu_css(a07.REGISTRO.ler())
    assert a07._MEXIDA.html_mod == ligada, "religar não devolveu a janela de antes"


JS_DA_BASE = (INTERFACE / "base-comum.js").read_text(encoding="utf-8")
CSS_DA_BASE = (INTERFACE / "base-comum.css").read_text(encoding="utf-8")

_PAGINA_DA_JANELA = """<!doctype html><html><head><meta charset="utf-8">
<style id="base-comum">
{css}</style>
<style>.tela-nova{{position:fixed;top:120px;left:120px}}</style></head><body>
<a id="abre" href="#tn-teste" data-dica="Configurar">Configurar</a>
<div class="tela-nova" id="tn-teste"><div class="tn-cx">
<a class="tn-x" href="#" data-dica="Fechar">&times;</a>
<button id="aplicar" data-dica="Aplicar o tema">Aplicar</button>
</div></div>
<script id="base-comum">
{js}</script></body></html>"""

_JS_DA_JANELA = """(function(){
  const abre = document.getElementById('abre'), r = {};
  const aberta = () => !!(window.__hefDica && window.__hefDica.aberta());
  abre.focus();
  setTimeout(() => {
    r.foco_do_controle_abre = aberta();
    location.hash = '#tn-teste';
    setTimeout(() => {
      r.foco_inicial = document.activeElement && document.activeElement.className;
      r.dica_no_foco_inicial = aberta();
      document.getElementById('aplicar').focus();
      setTimeout(() => {
        r.dica_no_aplicar = window.__hefDica ? window.__hefDica.texto() : '';
        location.hash = '';
        setTimeout(() => {
          r.foco_de_volta = document.activeElement && document.activeElement.id;
          r.dica_na_volta = aberta();
          window.__resultado = JSON.stringify(r);
        }, 200);
      }, 200);
    }, 200);
  }, 200);
  return 'iniciado';
})()"""


def _janela_no_webkit(tmp_path: Path, js: str = JS_DA_BASE, dica: str | None = None
                      ) -> dict[str, Any]:
    if (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("HEFESTO_NA_TELA")
            or not os.environ.get("DISPLAY")):
        pytest.skip("sem o X de mentira: o WebKit abriria na tela de quem usa ou não abriria")
    from tests.conftest import exigir_gi_real

    exigir_gi_real("abre o WebKit da camada da dica")
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    from hefesto_dualsense4unix.interface import hefesto_vivo

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    pagina = tmp_path / "janela.html"
    pagina.write_text(_PAGINA_DA_JANELA.format(css=CSS_DA_BASE, js=js), encoding="utf-8")
    saiu: list[str] = []
    janela = Gtk.Window()
    janela.set_default_size(900, 600)
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()
    janela.present()
    view.grab_focus()

    def leu(_v: Any, res: Any) -> None:
        try:
            saiu.append(view.evaluate_javascript_finish(res).to_string())
        except Exception as e:
            saiu.append(json.dumps({"erro": str(e)}))
        Gtk.main_quit()

    def camada(_v: Any, _res: Any) -> None:
        view.evaluate_javascript(_JS_DA_JANELA, -1, None, None, None, None)
        GLib.timeout_add(
            1600, lambda: (view.evaluate_javascript(
                "window.__resultado || '{\"erro\": \"sem resultado\"}'",
                -1, None, None, None, leu), False)[1])

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(dica or hefesto_vivo.DICA_DA_CASA, -1, None, None, None, camada)

    view.connect("load-changed", carregou)
    view.load_uri(pagina.as_uri())
    guarda = GLib.timeout_add(20000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
    assert saiu, "o WebKit não respondeu"
    return dict(json.loads(saiu[0]))


def test_d5_o_foco_que_a_janela_da_nao_abre_a_dica(tmp_path: Path) -> None:
    m = _janela_no_webkit(tmp_path)
    assert not m.get("erro"), m
    assert m["foco_do_controle_abre"], f"o foco dado de fora deixou de abrir a dica: {m}"
    assert m["foco_inicial"] == "tn-x", m
    assert not m["dica_no_foco_inicial"], f"a dica «Fechar» nasceu aberta: {m}"
    assert m["dica_no_aplicar"] == "Aplicar o tema", f"o foco seguinte não abriu a dica: {m}"
    assert m["foco_de_volta"] == "abre" and not m["dica_na_volta"], m
