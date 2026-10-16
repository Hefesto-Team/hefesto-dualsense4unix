"""O mapa do controle abre no perfil que a âncora pede e lê a escolha do point and click.

A aba Navegação aponta para o mapa com `#point-and-click` e `#trocar`. A página lê a âncora e o
Python diz a chave que cada uma pede: `ancora-pac` é a escolha do point and click da aba Navegação
(lida pela função dela, sem segunda leitura) e `ancora-trocar` é o perfil ativo, quando ele tem
lugar no seletor. Sem âncora, ou com outra, abre em Navegar. O perfil de um estilo de clicar
(Point and click, Visual novel) é do tipo `pac` pela receita do catálogo de estilos, não por uma
chave escrita no mapa.

MORDIDAS: ignorar o fragmento reprova as duas âncoras no WebKit; ler a escolha do point and click
por conta própria reprova o teste da função única; voltar a reconhecer só `point_and_click` reprova
o Visual novel; esquecer o `hashchange` reprova a troca de âncora com a página aberta.
"""

from __future__ import annotations

import json
import pathlib
import types
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import (
    Contexto,
    pacote_da_pagina,
    perfil,
)
from hefesto_dualsense4unix.interface.pacotes import a06_navegacao as a06
from hefesto_dualsense4unix.interface.pacotes import a13_mapa_do_controle as a13
from hefesto_dualsense4unix.profiles import loader

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PAGINA = a13.PAGINA
ATIVO = "Fora do jogo"


def _ctx(ativo: str = ATIVO) -> Contexto:
    mesa = [{"pref": "p1", "uniq": "aa:bb:cc:00:00:01", "nome": "Cosmic Red", "via": "USB",
             "jogador": 1, "cor": "cosmic-red"}]
    return Contexto(
        state={"active_profile": ativo}, mesa=mesa,
        conectados=[{"uniq": "aa:bb:cc:00:00:01", "inputs": {"buttons": ["cross"]}}])


def _a_escolha_da_06(monkeypatch: pytest.MonkeyPatch, escolha: str | None) -> None:
    """A aba Navegação com a escolha dada em `maquina.json` (`None` é o campo sem valor)."""
    mouse = types.SimpleNamespace(point_and_click=escolha)
    maquina = types.SimpleNamespace(computador=types.SimpleNamespace(
        global_=types.SimpleNamespace(mouse=mouse)))
    monkeypatch.setattr(a06, "_a_maquina", lambda: maquina)


def _o_disco(monkeypatch: pytest.MonkeyPatch, perfis: dict[str, dict[str, Any]]) -> None:
    """Os perfis do disco, sem tocar o disco do usuário."""
    monkeypatch.setattr(perfil, "lista", lambda: [{"nome": n} for n in perfis])
    monkeypatch.setattr(perfil, "ativo", lambda nome=None: dict(perfis.get(str(nome), {})))


@pytest.fixture(autouse=True)
def _edicao_limpa() -> Any:
    a13._largar()
    yield
    a13._largar()


def _mesa(ctx: Contexto) -> dict[str, Any]:
    mesa: dict[str, Any] = (pacote_da_pagina(PAGINA, ctx) or {})["mesa"]
    return mesa


# ---------------------------------------------------------------- o que a âncora pede


@pytest.mark.parametrize("molde", loader.MOLDES_DE_PERFIL, ids=lambda m: m.chave)
def test_o_point_and_click_abre_o_molde_que_a_06_escolheu(
        monkeypatch: pytest.MonkeyPatch, molde: Any) -> None:
    _o_disco(monkeypatch, {})
    _a_escolha_da_06(monkeypatch, f"molde:{molde.chave}")
    ctx = _ctx()
    assert _mesa(ctx)["ancora-pac"] == f"molde:{molde.chave}"
    a13.mapa_perfil(ctx, {"valor": _mesa(ctx)["ancora-pac"]}, None)
    aberto = _mesa(ctx)
    assert aberto["perfil"] == f"molde:{molde.chave}" and aberto["mc-tipo"] == "pac"
    assert aberto["nome"] == molde.nome, "o select e o nome mostram o molde escolhido"


def test_o_point_and_click_abre_o_perfil_do_disco_que_a_06_escolheu(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _o_disco(monkeypatch, {"Meu mouse": {"name": "Meu mouse", "estilo": "point_and_click",
                                         "button_actions": {"cross": "mouse_left"}}})
    _a_escolha_da_06(monkeypatch, "perfil:Meu mouse")
    ctx = _ctx()
    assert _mesa(ctx)["ancora-pac"] == "perfil:Meu mouse"
    a13.mapa_perfil(ctx, {"valor": "perfil:Meu mouse"}, None)
    assert _mesa(ctx)["mc-tipo"] == "pac"


def test_sem_escolha_na_06_vale_o_padrao_dela_e_escolha_que_sumiu_cai_em_navegar(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _o_disco(monkeypatch, {})
    _a_escolha_da_06(monkeypatch, None)
    assert _mesa(_ctx())["ancora-pac"] == a06.PADRAO_DO_POINT_AND_CLICK
    _a_escolha_da_06(monkeypatch, "perfil:Apagado")
    assert _mesa(_ctx())["ancora-pac"] == a13.NAV, "perfil que não existe mais abre em Navegar"
    _a_escolha_da_06(monkeypatch, "molde:que_nao_existe")
    assert _mesa(_ctx())["ancora-pac"] == a13.NAV


def test_o_mapa_le_a_escolha_pela_funcao_da_06_e_nao_pelo_campo(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: ler `mouse.point_and_click` no mapa por conta própria reprova aqui."""
    _o_disco(monkeypatch, {})
    _a_escolha_da_06(monkeypatch, "molde:mouse")
    visto: list[int] = []

    def so_ela() -> str:
        visto.append(1)
        return "molde:visual_novel"

    monkeypatch.setattr(a06, "_o_point_and_click_de_hoje", so_ela)
    assert _mesa(_ctx())["ancora-pac"] == "molde:visual_novel"
    assert visto, "a função da 06 não foi chamada"


def test_o_trocar_abre_o_perfil_ativo_que_tem_trocas(monkeypatch: pytest.MonkeyPatch) -> None:
    _o_disco(monkeypatch, {ATIVO: {"name": ATIVO, "remapeamento": {"triangle": "cross"}}})
    _a_escolha_da_06(monkeypatch, None)
    ctx = _ctx()
    assert _mesa(ctx)["ancora-trocar"] == f"perfil:{ATIVO}"
    a13.mapa_perfil(ctx, {"valor": f"perfil:{ATIVO}"}, None)
    aberto = _mesa(ctx)
    assert aberto["mc-tipo"] == "troca", aberto["mc-tipo"]
    assert aberto["val-triangle"] == "Cruz", "as trocas do perfil ativo aparecem"


def test_o_trocar_sem_perfil_com_botao_proprio_abre_em_navegar(
        monkeypatch: pytest.MonkeyPatch) -> None:
    _o_disco(monkeypatch, {ATIVO: {"name": ATIVO}})
    _a_escolha_da_06(monkeypatch, None)
    assert _mesa(_ctx())["ancora-trocar"] == a13.NAV
    assert _mesa(_ctx(ativo=""))["ancora-trocar"] == a13.NAV


def test_abrir_pela_ancora_nao_grava_nada(monkeypatch: pytest.MonkeyPatch,
                                          tmp_path: pathlib.Path) -> None:
    """O gesto que a âncora dispara só escolhe o perfil na tela: nenhum arquivo, nenhuma edição."""
    _o_disco(monkeypatch, {ATIVO: {"name": ATIVO, "remapeamento": {"triangle": "cross"}}})
    _a_escolha_da_06(monkeypatch, "molde:visual_novel")
    gravou: list[Any] = []

    def anota(nome: str) -> Any:
        return lambda self, *a, **k: gravou.append((nome, str(self)))

    monkeypatch.setattr(pathlib.Path, "write_text", anota("write_text"))
    monkeypatch.setattr(pathlib.Path, "write_bytes", anota("write_bytes"))
    ctx = _ctx()
    for chave in (_mesa(ctx)["ancora-pac"], _mesa(ctx)["ancora-trocar"]):
        a13.mapa_perfil(ctx, {"valor": chave}, None)
    assert gravou == []
    assert a13._estado()["edicoes"] == {}


# ---------------------------------------------------------------- o tipo vem da receita do estilo


def test_o_visual_novel_e_um_perfil_de_clicar_pela_receita_do_catalogo(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: voltar a reconhecer só `estilo == "point_and_click"` reprova o Visual novel."""
    perfis: dict[str, dict[str, Any]] = {
        "Romance": {"name": "Romance", "estilo": "visual_novel",
                    "button_actions": {"cross": "KEY_ENTER"}},
        "Corrida": {"name": "Corrida", "estilo": "esportes"}}
    _o_disco(monkeypatch, perfis)
    ctx = _ctx()
    meus = {c["name"] for c in a13._perfis_do_disco(ctx)}
    assert "Romance" in meus and "Corrida" not in meus
    a13.mapa_perfil(ctx, {"valor": "perfil:Romance"}, None)
    assert _mesa(ctx)["mc-tipo"] == "pac"


def test_nenhuma_chave_de_estilo_de_clicar_mora_no_mapa() -> None:
    """O mapa pergunta ao catálogo: uma lista paralela de chaves aqui seria a segunda verdade."""
    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/pacotes/a13_mapa_do_controle.py"
             ).read_text(encoding="utf-8")
    assert '"point_and_click"' not in fonte and '"visual_novel"' not in fonte


# ---------------------------------------------------------------- a página, no WebKit


def _no_webkit(fragmento: str, passos: list[str]) -> list[Any]:
    """Abre a página do mapa com o fragmento e roda os passos de JavaScript, um de cada vez."""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("abre a página num WebKit")
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    from hefesto_dualsense4unix.interface import hefesto_vivo

    respostas: list[str] = []
    view = WebKit2.WebView()
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(1212, 809)
    view.set_size_request(1212, 809)
    janela.add(view)
    janela.show_all()
    fila = [hefesto_vivo.BOOTSTRAP, *passos]

    def seguinte() -> bool:
        if not fila:
            Gtk.main_quit()
            return False

        def respondeu(v: Any, res: Any, _u: Any = None) -> None:
            try:
                respostas.append(v.evaluate_javascript_finish(res).to_string())
            except Exception as erro:
                respostas.append(f"ERRO {erro}")
            GLib.timeout_add(80, seguinte)

        view.evaluate_javascript(fila.pop(0), -1, None, None, None, respondeu, None)
        return False

    def carregou(_v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            GLib.timeout_add(50, seguinte)

    view.connect("load-changed", carregou)
    view.load_uri(onde.pagina(PAGINA, publicado=_publicada()).as_uri() + fragmento)
    guarda = GLib.timeout_add(40000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert len(respostas) == len(passos) + 1, f"o WebKit parou no meio: {respostas}"
    return [json.loads(x) if x.startswith(("{", "[")) else x for x in respostas[1:]]


def _publicada() -> bool:
    """O desenho, enquanto o `--publicar` não levou a cura para o produto."""
    import importlib.util
    import sys

    alvo = RAIZ / "scripts/check_o_desenho_aprovado.py"
    spec = importlib.util.spec_from_file_location("check_desenho_da_ancora", alvo)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_desenho_da_ancora"] = mod
    spec.loader.exec_module(mod)
    return PAGINA not in set(mod.declaradas())


OUVIR = ("window.__mudou = []; document.addEventListener('change', e => { "
         "if (e.target.id === 'perfil') window.__mudou.push(e.target.value); }, true); 'ok'")

LER = ("(function(){ const s = document.querySelector('#perfil'); "
       "return JSON.stringify({valor: s.value, mudou: window.__mudou, "
       "hash: location.hash}); })()")


def _pintar(ctx: Contexto) -> str:
    """O que o tique escreve na página: a carga do pacote de verdade, pelo pintor do piloto."""
    carga = pacote_da_pagina(PAGINA, ctx) or {}
    return f"String(window.__hef.pintar({json.dumps(carga)}))"


def _preparar(monkeypatch: pytest.MonkeyPatch, escolha: str = "molde:visual_novel") -> Contexto:
    _o_disco(monkeypatch, {ATIVO: {"name": ATIVO, "remapeamento": {"triangle": "cross"}}})
    _a_escolha_da_06(monkeypatch, escolha)
    return _ctx()


@pytest.mark.parametrize("fragmento,esperado", [
    ("#point-and-click", "molde:visual_novel"),
    ("#trocar", f"perfil:{ATIVO}"),
    ("", "nav"),
    ("#nao-conheco", "nav"),
    ("#acessibilidade", "nav"),
])
def test_a_pagina_abre_no_perfil_que_a_ancora_pede(
        monkeypatch: pytest.MonkeyPatch, fragmento: str, esperado: str) -> None:
    """MORDIDA: ignorar o fragmento reprova `#point-and-click` e `#trocar`."""
    ctx = _preparar(monkeypatch)
    lido = _no_webkit(fragmento, [OUVIR, _pintar(ctx), LER])[-1]
    assert lido["valor"] == esperado, lido
    if esperado == "nav":
        assert lido["mudou"] == [], f"a âncora «{fragmento}» não pede perfil nenhum: {lido}"
    else:
        assert lido["mudou"] == [esperado], f"o `change` que leva ao Python não saiu: {lido}"
        a13.mapa_perfil(ctx, {"valor": lido["mudou"][0]}, None)
        assert _mesa(ctx)["perfil"] == esperado, "o gesto da página chegou ao Python"


def test_a_ancora_segue_a_escolha_da_06_no_tempo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Muda a escolha na 06 e volta pela âncora: o seletor acompanha, sem recarregar a página.

    MORDIDA: tirar o `hashchange` da página reprova a segunda e a terceira leitura.
    """
    ctx = _preparar(monkeypatch, "molde:visual_novel")
    primeira = _pintar(ctx)

    def vai(frag: str) -> str:
        return f"location.hash = '{frag}'; 'ok'"

    _a_escolha_da_06(monkeypatch, "molde:mouse")
    segunda = _pintar(ctx)
    lidas = _no_webkit("", [
        OUVIR, primeira, LER,
        vai("#point-and-click"), LER,
        vai("#trocar"), LER,
        segunda, vai("#point-and-click"), LER,
    ])
    assert lidas[2]["valor"] == "nav" and lidas[2]["mudou"] == []
    assert lidas[4]["valor"] == "molde:visual_novel", lidas[4]
    assert lidas[6]["valor"] == f"perfil:{ATIVO}", lidas[6]
    assert lidas[9]["valor"] == "molde:mouse", lidas[9]


def test_o_marcador_da_ancora_nao_aparece_nem_entra_na_tabulacao() -> None:
    """Os dois marcadores são endereço, não elemento da tela: ocultos e fora do foco."""
    ctx = _ctx()
    lido = _no_webkit("", [
        "JSON.stringify([...document.querySelectorAll('[data-campo^=\"ancora-\"]')].map(e => ({"
        "campo: e.dataset.campo, oculto: e.hidden, "
        "caixa: e.getBoundingClientRect().width * e.getBoundingClientRect().height, "
        "tab: e.tabIndex})))"])[-1]
    assert {x["campo"] for x in lido} == {"ancora-pac", "ancora-trocar"}, lido
    assert all(x["oculto"] and x["caixa"] == 0 and x["tab"] == -1 for x in lido), lido
    assert ctx is not None
