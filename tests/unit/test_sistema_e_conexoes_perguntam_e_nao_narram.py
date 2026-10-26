#!/usr/bin/env python3
"""A RÉGUA DA TELA-CALADA-03 — Sistema e Conexões perguntam, e não narram."""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))


from hefesto_dualsense4unix.interface import onde as _onde
from hefesto_dualsense4unix.interface.pacotes import Contexto, normalizar
from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09


def _ctx() -> Contexto:
    return Contexto(state={"active_profile": "regua"}, mesa=[], conectados=[],
                    estados={})


class PonteDeMentira:
    """Nenhum destes gestos fala com o daemon; a ponte existe pelo contrato."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def chamar(self, metodo: str, *_a: object, **_k: object) -> bool:
        self.chamadas.append(metodo)
        return False


def _zerar() -> None:
    a09._ARMADO.clear()
    a09._LENTO.clear()
    a09._PAINEL[0] = None


@pytest.fixture(autouse=True)
def _limpo():
    """O consentimento e o painel são estado de MÓDULO."""
    _zerar()
    yield
    _zerar()


def _primeiro(gesto: str) -> dict[str, str]:
    """O clique 1: o rótulo do desenho, que não é o do botão armado."""
    return {"gesto": gesto, "texto": "o rótulo do desenho"}


def _confirma(gesto: str) -> dict[str, str]:
    """O clique 2: ele traz o rótulo que só existe no botão armado."""
    return {"gesto": gesto, "texto": a09.CONFIRMA}


def _pergunta_do_restaurar(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """O clique 1 do «Restaurar de fábrica»: a pergunta que o painel guarda."""
    import tempfile

    from hefesto_dualsense4unix.app.actions import footer_actions

    asset = pathlib.Path(tempfile.mkdtemp(prefix="hef-regua-")) / "personalizado.json"
    asset.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(footer_actions, "_meu_perfil_asset", lambda: asset)
    return a09.restaurar_de_fabrica(_ctx(), _primeiro("restaurar-de-fabrica"),
                                    PonteDeMentira())


def _camada_levanta(monkeypatch) -> None:
    """A camada do produto levanta — é o que acontece com o serviço parado."""
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
    for campo in (a09.REGISTRO, "exame-lista"):
        assert campo in carga, (
            f"o ramo de erro não emite `{campo}` — a página continua com o "
            "literal do desenho nesse endereço")
    assert carga[a09.REGISTRO] == "—", carga[a09.REGISTRO]
    assert carga["exame-lista"] == nada


def test_com_o_servico_parado_o_que_ela_pediu_continua_no_painel(monkeypatch) -> None:
    """A pergunta do «Restaurar de fábrica» chega pelo PACOTE, sem o serviço."""
    _camada_levanta(monkeypatch)
    carga = _pergunta_do_restaurar(monkeypatch)
    assert a09.pacote(_ctx())[a09.REGISTRO] == carga["mesa"][a09.REGISTRO]
    a09._PAINEL[0] = "linha do registro que ela pediu"
    assert a09.pacote(_ctx())[a09.REGISTRO] == "linha do registro que ela pediu"


ROTEIRO_09 = """
(function(){
  const r = document.querySelector('[data-campo="registro-texto"]');
  const l = document.querySelector('[data-campo="exame-lista"]');
  if(!r || !l) return JSON.stringify({erro: 'a página não tem os endereços'});
  const fora = {inicial: {registro: r.textContent, lista: l.textContent}};
  for(const [nome, carga] of CARGAS){
    fora[nome] = {
      pintou: window.__hef.pintar(carga),
      registro: r.textContent,
      lista: l.textContent,
      largura: [r.clientWidth, r.scrollWidth],
    };
  }
  return JSON.stringify(fora);
})()
"""


@pytest.fixture(scope="module")
def no_webkit_09():
    """A página PUBLICADA num WebKit oculto, com o `BOOTSTRAP` do piloto."""
    pagina = _onde.pagina("09-sistema.html", publicado=True)
    if not pagina.is_file():
        pytest.skip("a página publicada da 09 não está no disco")

    with pytest.MonkeyPatch.context() as mp:
        _camada_levanta(mp)
        a09._PAINEL[0] = None
        parado = dict(normalizar(a09.pacote(_ctx())))
        a09._ARMADO.clear()
        pergunta = _pergunta_do_restaurar(mp)
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
        except Exception as e:  # pragma: no cover
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


def test_no_pixel_a_pergunta_cabe_no_painel_sem_rolar_de_lado(no_webkit_09) -> None:
    visto = no_webkit_09["pergunta"]
    assert a09.CLIQUE_DE_NOVO in visto["registro"], visto["registro"]
    largura, rolagem = visto["largura"]
    assert largura > 0, "o painel não tem largura — o WebKit não montou a página"
    assert rolagem <= largura, (
        f"a pergunta sai pela direita do painel ({rolagem}px em {largura}px) — "
        "a instrução do segundo tempo fica fora da vista")


def _achado_grave():
    from hefesto_dualsense4unix.profiles.sanidade import Achado

    return Achado(regra="catch_all_vence_especifico", gravidade="erro",
                  mensagem="'Desktop' vale para QUALQUER janela",
                  cura="baixe a prioridade de 'Desktop' para 0",
                  perfis=("Desktop",))


@pytest.fixture
def perfis(monkeypatch, tmp_path):
    """A pasta dos perfis de mentira e o dono dublado, que conta as perguntas."""
    from hefesto_dualsense4unix.profiles import sanidade
    from hefesto_dualsense4unix.utils import xdg_paths

    pasta = tmp_path / "profiles"
    pasta.mkdir()
    (pasta / "desktop.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(xdg_paths, "profiles_dir", lambda ensure=False: pasta)
    estado: dict[str, Any] = {"achados": [_achado_grave()], "perguntas": 0}

    def dono():
        estado["perguntas"] += 1
        if isinstance(estado["achados"], BaseException):
            raise estado["achados"]
        return list(estado["achados"])

    monkeypatch.setattr(sanidade, "verificar_perfis_do_disco", dono)
    a09._PERFIS.clear()
    yield estado
    a09._PERFIS.clear()


def test_o_exame_leva_a_coerencia_dos_perfis(perfis, monkeypatch) -> None:
    """O achado grave dos perfis entra no exame, com o selo AVISO.

    A MORDIDA: tire o `linhas.extend(linhas_dos_perfis(...))` de `_achados` e o
    primeiro `assert` reprova; tire a chave `FAIL` de
    `interface/sistema._SELO_DO_VEREDITO` e o segundo reprova (o achado grave
    sairia como NOTA).
    """
    monkeypatch.setattr(a09._exame, "storm_report", lambda **k: [("[ OK ]", "base")])
    monkeypatch.setattr(a09._exame, "controles_no_cabo", lambda s: 0)
    monkeypatch.setattr(a09._daemon, "medir_guarda_do_steam_input", lambda: None)
    monkeypatch.setattr(a09, "_prontuario", lambda pode=True: None)
    monkeypatch.setattr(a09, "linha_do_som_do_sistema", lambda s: None)
    monkeypatch.setattr(a09, "linha_da_sobreposicao_vulkan", lambda: None)

    linhas = a09._achados({}) or []
    frases = [f for _, f, *_tema in linhas]
    assert any("'Desktop' vale para QUALQUER janela" in f for f in frases), linhas
    selos = {a["txt"]: a["selo"] for a in a09._tela.exame(linhas)["linhas"]}
    grave = next(t for t in selos if "QUALQUER janela" in t)
    assert selos[grave] == "AVISO", selos


def test_perfis_coerentes_nao_ganham_linha(perfis) -> None:
    """Só fala quando há problema, como o vigia e o prontuário."""
    perfis["achados"] = []
    assert a09.linhas_dos_perfis() == []


def test_a_cura_do_terminal_nao_chega_a_tela_dos_perfis(perfis) -> None:
    """A linha do perfil na 09 é o fato, sem o «— Cura: …» do `doctor`."""
    linhas = a09.linhas_dos_perfis()
    assert linhas == [("[FAIL]", "'Desktop' vale para QUALQUER janela")], linhas


def test_a_leitura_que_falha_vira_linha_e_nao_derruba_o_exame(perfis) -> None:
    """O `OSError` é do lado de quem chama, como no `doctor`."""
    perfis["achados"] = PermissionError(13, "Permissão negada")
    assert a09.linhas_dos_perfis() == [
        ("[WARN]", "não deu para ler os perfis (Permissão negada)")]


def test_a_pasta_parada_nao_e_relida(perfis, tmp_path) -> None:
    """A faixa lenta relê a cada 2 s; o disco só é lido quando a pasta muda."""
    primeira = a09.linhas_dos_perfis()
    segunda = a09.linhas_dos_perfis()
    assert primeira == segunda and perfis["perguntas"] == 1, perfis
    (tmp_path / "profiles" / "jogo.json").write_text("{}", encoding="utf-8")
    a09.linhas_dos_perfis()
    assert perfis["perguntas"] == 2, "um perfil novo na pasta não foi conferido"


def test_a_primeira_leitura_no_laco_nao_le_o_disco(perfis) -> None:
    """`pode_perguntar=False` é a leitura dentro do laço do GTK: sai o guardado."""
    assert a09.linhas_dos_perfis(pode_perguntar=False) == []
    assert perfis["perguntas"] == 0
