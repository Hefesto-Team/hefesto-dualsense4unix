"""O Mapear lista o que já foi mapeado — O-MAPEAR-LISTA-O-QUE-JA-FOI-MAPEADO-01.

O pedido dela, 29/09/2026 (fotos 8 e 9 da lista das ~17h15): *«Já mapeamos
antes não aparece aqui a lista com rolagem a direita. O Num Hub nenhum em 7
dias começam sem letras maiusculas.»* E a frase do «Entrada encontrada» virou a
que ela ditou. <!-- noqa-acento: citação literal dela -->

O QUE ESTA RÉGUA COBRA, com disco e ``/sys`` sintéticos (faixa forjada
``0000:0a:00.0``, nada da máquina dela):

1. a lista «Já mapeadas» mostra TODA entrada numerada — com nome ou sem —, na
   ordem das faces, e «Nenhuma ainda.» só sem entrada numerada nenhuma;
2. a conta embaixo é a da MESMA lista, e não o ``feitas`` da sessão;
3. no WebKitGTK (o motor dela), a lista com 15 entradas rola por dentro e não
   empurra o diálogo: a coluna da direita acaba onde a da esquerda acaba;
4. cada valor medido começa com maiúscula ou algarismo, e a frase é a dela;
5. o Salvar com os dois campos vazios numera a porta sem número, não mexe na
   numerada, e não apaga o nome de quem tem.

AS MORDIDAS (arranque a cura, veja reprovar, devolva):

* 1 — devolva o filtro ``p.get("nome")`` a ``_mapeadas``;
* 2 — devolva a conta ao ``feitas`` da foto;
* 3 — tire as duas metades da folha no ``aba08.py`` (o ``height:0;min-height:100%``
  da ``.mp-dir`` e o ``flex:1 1 0;min-height:0;overflow-y:auto`` da ``.mp-lista``)
  e regere a bancada: o diálogo vai de 397 a 596 px com as 15. No WebKit cada
  metade sozinha segura o diálogo (medido em 01/10/2026); no Chrome da medida
  da sprint, só o ``height:0`` segurava, e por isso as duas ficam;
* 4 — devolva o «num hub» minúsculo;
* 5 — devolva o ``raise ValueError("nada a gravar…")`` do ``gravar`` (os dois
  primeiros casos reprovam), ou mande ``nome=""`` pelo gesto (o terceiro).
"""
from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee
from hefesto_dualsense4unix.integrations.censo_do_barramento import Censo
from hefesto_dualsense4unix.integrations.mesa_de_radio import Adaptador
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as pac
from hefesto_dualsense4unix.utils.maquina import caminho_da_maquina, carregar_maquina, lugar_de
from tests.unit.test_entrada_a_entrada_02_as_telas_aprovadas import (
    BOOT_1,
    DUALSENSE,
    PCI_A,
    Gabinete,
)

RAIZ = pathlib.Path(__file__).resolve().parents[2]

#: A frase que ela ditou em 29/09, com «porta» → «entrada» (D-A-PALAVRA-ENTRADA)
#: e o nome do botão da 08. Escrita aqui como constante do pedido, e não lida do
#: dono: a régua que lê a frase do dono passaria com qualquer frase.
FRASE_DELA = (
    "Conecte um DualSense em cada entrada USB do seu dispositivo. Nomeie a entrada "
    "(ou deixe vazia para ela ser enumerada). Ao final, valide e, caso necessário, "
    "faça os ajustes na entrada no botão Mapa das Conexões."
)

#: A faixa sintética da casa.
PCI = "0000:0a:00.0"


@pytest.fixture()
def disco(tmp_path: pathlib.Path) -> pathlib.Path:
    """O ``maquina.json`` desta régua mora no ``tmp_path`` — conferido antes."""
    alvo = caminho_da_maquina()
    assert alvo.is_relative_to(tmp_path), f"o maquina.json da régua não está desviado: {alvo}"
    return alvo


def _escrever(disco: pathlib.Path, faces: list[dict[str, Any]],
              portas: dict[str, dict[str, Any]]) -> None:
    disco.write_text(json.dumps({"version": 1, "mapa": {"faces": faces, "portas": portas}}),
                     encoding="utf-8")


def _tres_numeradas(disco: pathlib.Path) -> list[dict[str, Any]]:
    """Três entradas numeradas, uma com nome e duas sem, lidas pelo dono."""
    _escrever(
        disco,
        [{"nome": ee.FACE_FRENTE, "portas": ["1", "2"]},
         {"nome": ee.FACE_ATRAS, "portas": ["3"]}],
        {"1": {"lugar": lugar_de(PCI, "1"), "nos": ["usb1-port1"], "nome": "Frente de cima"},
         "2": {"lugar": lugar_de(PCI, "2"), "nos": ["usb1-port2"]},
         "3": {"lugar": lugar_de(PCI, "3"), "nos": ["usb1-port3"]}},
    )
    mapa = ee.ler_o_mapa(maquina=carregar_maquina(), censo=Censo(), entradas=(),
                         adaptadores=(), storm={})
    return [p.como_dicionario() for p in mapa.portas]


# ---------------------------------------------------------------------------
# 1. a lista é das numeradas
# ---------------------------------------------------------------------------
def test_a_lista_mostra_as_numeradas_sem_nome(disco: pathlib.Path) -> None:
    """MORDIDA: devolva o filtro ``p.get("nome")`` → só a 1 aparece e reprova."""
    portas = _tres_numeradas(disco)
    assert sum(1 for p in portas if p.get("numero")) == 3, "o disco sintético não foi lido"
    lista = pac.html_das_entradas_mapeadas(portas)
    linhas = [linha for linha in lista.split("</li>") if linha]
    assert linhas == [
        f"<li><b>Frente de cima</b><span>Entrada 1 · {ee.FACE_FRENTE}</span>",
        f"<li><b>Entrada 2</b><span>{ee.FACE_FRENTE}</span>",
        f"<li><b>Entrada 3</b><span>{ee.FACE_ATRAS}</span>",
    ], lista
    assert "Nenhuma ainda." not in lista
    assert pac.html_das_entradas_mapeadas([]) == '<li class="vazio">Nenhuma ainda.</li>'
    assert pac.html_das_entradas_mapeadas(
        [{"nome": None, "numero": None, "rotulo": "Entrada 1-4"}]
    ) == '<li class="vazio">Nenhuma ainda.</li>', "a porta sem número ainda não é mapeada"


# ---------------------------------------------------------------------------
# 2. a conta é a da lista
# ---------------------------------------------------------------------------
def test_a_conta_e_a_da_lista_e_nao_a_da_sessao(disco: pathlib.Path) -> None:
    """MORDIDA: devolva a conta ao ``feitas`` da foto → «Nenhuma entrada salva ainda.»."""
    portas = _tres_numeradas(disco)
    campos = pac.campos_do_mapear({"estado": "esperando", "portas": portas, "feitas": 0})
    assert campos["mapear-conta"] == "3 entradas mapeadas."
    assert pac.campos_do_mapear(
        {"estado": "esperando", "portas": portas[:1], "feitas": 5}
    )["mapear-conta"] == "1 entrada mapeada."
    vazio = pac.campos_do_mapear({"estado": "esperando", "portas": [], "feitas": 0})
    assert vazio["mapear-conta"] == "", "sem nenhuma, a lista já diz «Nenhuma ainda.»"
    assert "nenhuma" not in vazio["mapear-conta"].lower()


# ---------------------------------------------------------------------------
# 4. as maiúsculas e a frase
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("porta", [
    {"rotulo": "Entrada 9", "usb": "2.0", "hub": "3-1", "hub_produto": "USB2.1 Hub", "storm": 0},
    {"rotulo": "Entrada 1", "usb": "3.0", "hub": "", "storm": 3},
    {"rotulo": "Entrada 2", "hub": "", "storm": 1, "lugar_no_gabinete": ee.FACE_FRENTE},
], ids=["hub-zero-quedas", "direto-tres-quedas", "uma-queda"])
def test_cada_valor_medido_comeca_com_maiuscula(porta: dict[str, Any]) -> None:
    """MORDIDA: devolva o «num hub» ou o «nenhuma em 7 dias» minúsculos → reprova."""
    fatos = pac.html_da_porta_medida(porta)
    valores = [v.split("</dd>")[0] for v in fatos.split("<dd>")[1:]]
    assert valores, fatos
    for valor in valores:
        assert valor[0].isupper() or valor[0].isdigit(), f"{valor!r} começa minúsculo"
    if porta.get("hub"):
        assert "<dd>Num hub (USB2.1 Hub)</dd>" in fatos
        assert "<dd>Nenhuma em 7 dias</dd>" in fatos
    else:
        assert "<dd>Direto no computador</dd>" in fatos


def test_a_frase_da_entrada_encontrada_e_a_dela() -> None:
    assert pac.MAPEAR_DIZ["porta"] == FRASE_DELA
    assert pac.campos_do_mapear({"estado": "porta", "portas": []})["mapear-diz"] == FRASE_DELA
    bancada = (RAIZ / "mockup/08-conexoes.html").read_text(encoding="utf-8")
    assert FRASE_DELA in bancada, "a cena do desenho não traz a frase — regere a bancada"


def test_a_dica_do_mapear_nao_desdiz_a_frase() -> None:
    """A dica «?» do diálogo mandava «dê um nome e o lugar, e salve» ao lado da
    frase dela, que diz que o nome é opcional, e chamava a Gestão de Controles
    pelo nome velho, «Check-up» (conferência, 02/10/2026).

    MORDIDA: devolva a dica de antes no ``TELA_MAPEAR_PORTAS`` e regere → reprova.
    """
    bancada = (RAIZ / "mockup/08-conexoes.html").read_text(encoding="utf-8")
    inicio = bancada.index('id="mapear-portas"')
    topo = bancada[inicio:bancada.index('id="mp-forma"', inicio)]
    dica = topo[topo.index('class="dica">'):]
    assert "opcionais" in dica, f"a dica do Mapear ainda manda dar nome e lugar: {dica[:300]}"
    assert "Check-up" not in dica and "Gestão de Controles" in dica, dica[:300]


# ---------------------------------------------------------------------------
# 5. o Salvar vazio numera, e não apaga
# ---------------------------------------------------------------------------
def _fluxo(gabinete: Gabinete) -> ee.MapearAsPortas:
    return ee.MapearAsPortas(ler=gabinete.ler, entradas=gabinete.entradas, storm={},
                             adaptadores=lambda: (Adaptador(interface="hci9"),))


def _salvar_vazio(fluxo: ee.MapearAsPortas, monkeypatch: pytest.MonkeyPatch) -> None:
    """O clique dela no «Salvar e ir para a próxima», com os dois campos vazios,
    pelo tratador do gesto `mapear-gravar` da aba."""
    monkeypatch.setattr(pac, "_o_mapa", lambda: fluxo)
    pac.mapear_gravar(None, {"forma": {"nome": "", "lugar": ""}}, None)


def test_o_salvar_vazio_numera_a_porta_sem_numero(
    tmp_path: pathlib.Path, disco: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A porta sem número nasce numerada, sem nome e fora de toda face; um
    segundo Salvar vazio nela (numerada e sem face) não tem o que gravar.

    MORDIDA: devolva o ``raise`` do ``gravar`` → o gesto levanta e reprova;
    tire o retorno «não gravou» de ``_gravar_a_porta`` → a ``Gravacao`` diz
    que gravou sem ter escrito nada, e reprova.
    """
    _escrever(disco, [{"nome": ee.FACE_FRENTE, "portas": ["1"]}],
              {"1": {"lugar": lugar_de(PCI_A, "1"), "nos": ["usb1-port1"], "nome": "Frente"}})
    gabinete = Gabinete(tmp_path / "sys", BOOT_1)
    fluxo = _fluxo(gabinete)
    fluxo.comecar()
    gabinete.plugar(1, "5", DUALSENSE)
    assert fluxo.olhar()["porta"]["numero"] is None, "a porta da vez tinha de nascer sem número"

    _salvar_vazio(fluxo, monkeypatch)

    documento = carregar_maquina()
    assert set(documento.mapa.portas) == {"1", "2"}, "o menor número livre é o 2"
    nova = documento.mapa.portas["2"]
    assert nova.lugar == lugar_de(PCI_A, "5") and nova.nome is None
    assert all("2" not in face.portas for face in documento.mapa.faces), "nasce fora de toda face"
    assert documento.mapa.portas["1"].nome == "Frente", "a outra entrada não muda"
    conta = pac.campos_do_mapear(fluxo.estado())["mapear-conta"]
    assert conta == "2 entradas mapeadas.", conta

    antes = disco.read_bytes()
    _salvar_vazio(fluxo, monkeypatch)
    assert disco.read_bytes() == antes, "o Salvar vazio na entrada sem face escreveu no disco"
    gravacao = fluxo.estado()[ee._CHAVE_DA_ULTIMA]
    assert gravacao is not None, "o dono não guardou a resposta do gesto"
    assert (gravacao["gravou"], gravacao["motivo"]) == (False, ""), gravacao


@pytest.mark.parametrize("nome", [None, "Frente de cima"], ids=["sem-nome", "com-nome"])
def test_o_salvar_vazio_na_numerada_nao_muda_o_que_ela_disse(
    tmp_path: pathlib.Path, disco: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
    nome: str | None,
) -> None:
    """A entrada numerada, com face, com o cabo nela: o Salvar vazio é a
    revisita que o «só o nome» já era — o cabo prova o buraco de novo, e o
    número, o nome e a face ficam. Lido do ``maquina.json`` antes e depois.

    MORDIDA: devolva o ``raise`` do ``gravar`` (os dois casos levantam) ou
    mande ``nome=""`` pelo gesto (o caso com nome perde o nome no disco).
    """
    entrada: dict[str, Any] = {"lugar": lugar_de(PCI_A, "5"), "nos": ["usb1-port5"]}
    if nome:
        entrada["nome"] = nome
    _escrever(disco, [{"nome": ee.FACE_FRENTE, "portas": ["1"]}], {"1": entrada})
    antes = json.loads(disco.read_text(encoding="utf-8"))["mapa"]
    gabinete = Gabinete(tmp_path / "sys", BOOT_1)
    fluxo = _fluxo(gabinete)
    fluxo.comecar()
    gabinete.plugar(1, "5", DUALSENSE)
    assert fluxo.olhar()["porta"]["numero"] == "1"

    _salvar_vazio(fluxo, monkeypatch)

    depois = json.loads(disco.read_text(encoding="utf-8"))["mapa"]
    assert depois["portas"]["1"].get("nome") == nome, "o Salvar vazio mexeu no nome dela"
    assert [(f["nome"], f["portas"]) for f in depois["faces"]] == [
        (f["nome"], f["portas"]) for f in antes["faces"]], "o Salvar vazio mexeu na face"
    assert set(depois["portas"]) == {"1"}, "o Salvar vazio criou outra entrada"
    assert depois["portas"]["1"]["lugar"] == antes["portas"]["1"]["lugar"]


# ---------------------------------------------------------------------------
# 3. no motor dela: a lista rola e não empurra o diálogo
# ---------------------------------------------------------------------------

#: O roteiro no WebKit: pinta os campos do Mapear com o que o pacote devolve e
#: mede o diálogo. Os campos chegam por ``window.__campos`` (JSON).
ROTEIRO = r"""
(function(){
  const out = {};
  function pintar(campos){
    for (const [k, v] of Object.entries(campos)) {
      const el = document.querySelector('#mapear-portas [data-campo="' + k + '"]');
      if (!el) { out.falta = (out.falta || []).concat([k]); continue; }
      if (el.dataset.hefAlvo === 'html') el.innerHTML = v;
      else if (el.dataset.hefAlvo === 'atributo') el.setAttribute(el.dataset.hefAtributo, v);
      else el.textContent = v;
    }
  }
  function medir(){
    const q = s => document.querySelector('#mapear-portas ' + s).getBoundingClientRect();
    const lista = document.querySelector('#mapear-portas .mp-lista');
    return {cx: q('.mp-cx').height, esq: q('.mp-esq').bottom, dir: q('.mp-dir').bottom,
            lista_alt: lista.clientHeight, lista_cheia: lista.scrollHeight,
            visivel: getComputedStyle(document.getElementById('mapear-portas')).display};
  }
  pintar(__CAMPOS_UMA__); out.uma = medir();
  pintar(__CAMPOS_QUINZE__); out.quinze = medir();
  return JSON.stringify(out);
})()
"""


def _campos(quantas: int) -> dict[str, str]:
    portas = [{"nome": "", "numero": str(n), "lugar_no_gabinete": ee.FACE_HUB}
              for n in range(1, quantas + 1)]
    porta = {"rotulo": "Entrada 9", "usb": "2.0", "hub": "3-1", "hub_produto": "USB2.1 Hub",
             "storm": 0, "lugar_no_gabinete": ee.FACE_HUB}
    return pac.campos_do_mapear({"estado": "porta", "porta": porta, "portas": portas})


@pytest.fixture(scope="module")
def no_webkit() -> dict[str, Any]:
    """A bancada da 08 aberta no «Mapear Entradas», num WebKit offscreen."""
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
    roteiro = (ROTEIRO.replace("__CAMPOS_UMA__", json.dumps(_campos(1)))
               .replace("__CAMPOS_QUINZE__", json.dumps(_campos(15))))
    saiu: list[str] = []
    # Offscreen: sob Xvfb não há gerenciador de janelas, e ela tem UMA tela.
    janela = Gtk.OffscreenWindow()
    view = WebKit2.WebView()
    view.set_size_request(1600, 855)
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
            v.evaluate_javascript(roteiro, -1, None, None, None, guardou)

    view.connect("load-changed", carregou)
    view.load_uri(pagina.as_uri() + "#mapear-portas")
    guarda = GLib.timeout_add(30000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert saiu, "o WebKit não respondeu em 30 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    return dict(json.loads(saiu[0]))


def test_a_lista_rola_e_nao_empurra_o_dialogo(no_webkit: dict[str, Any]) -> None:
    """MORDIDA: tire as duas metades da folha (ver o cabeçalho) e regere → com as
    15 o diálogo passa de 397 para 596 px, e a lista não rola."""
    uma, quinze = no_webkit["uma"], no_webkit["quinze"]
    assert "falta" not in no_webkit, f"a bancada não tem onde pintar {no_webkit.get('falta')}"
    assert uma["visivel"] != "none", "o «Mapear Entradas» não abriu pela âncora"
    assert quinze["cx"] - uma["cx"] < 2, (
        f"a lista empurrou o diálogo: {uma['cx']:.0f} px com uma, {quinze['cx']:.0f} com 15")
    assert quinze["cx"] <= 400, f"o diálogo tem {quinze['cx']:.0f} px"
    assert quinze["lista_cheia"] > quinze["lista_alt"] > 0, (
        f"a lista não rola: {quinze['lista_cheia']} de conteúdo em {quinze['lista_alt']} px")
    assert abs(quinze["dir"] - quinze["esq"]) < 2, (
        f"a coluna da direita acaba em {quinze['dir']:.0f} e a da esquerda em {quinze['esq']:.0f}")
