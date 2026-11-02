"""A janela da extensão ganha a página que a extensão desenha (02/11/2026).

A janela da extensão era toda declarativa: onze tipos de opção, quatro blocos ao vivo e as
ações. Uma extensão que precisa de tela própria (o estúdio de mapear) não tinha onde desenhá-la.
Agora o manifesto declara a página, um HTML da pasta do código, que a janela mostra num
``iframe`` isolado (só ``allow-scripts``, CSP sem rede) e que fala só com a própria extensão:
``extensao.mensagem`` na ida, ``extensao.resposta`` na volta, até 64 000 bytes e 30 por segundo.
"""
from __future__ import annotations

import asyncio
import json
import os
import pathlib
import re
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.mods import manifesto as mf
from hefesto_dualsense4unix.mods import porta as pt
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    ctx,
    lar,
)
from tests.unit.test_a_coluna_agora_e_o_parar_tudo_vem_do_servico import (  # noqa: F401
    _entrar,
    _porta,
    curto,
)
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import (
    _instalada,
    _servico,
)

PAGINA = {"arquivo": "estudio/pagina.html", "rotulo": "Estúdio", "altura_max": 240}
HTML_DA_EXTENSAO = "<!doctype html><p>estúdio</p>"


def _pasta_com_a_pagina(raiz: pathlib.Path, **pagina: Any) -> pathlib.Path:
    pasta = raiz / "toque"
    (pasta / "estudio").mkdir(parents=True)
    (pasta / "estudio" / "pagina.html").write_text(HTML_DA_EXTENSAO, encoding="utf-8")
    (pasta / "hefesto-mod.json").write_text(json.dumps({
        "id": "toque", "nome": "Toque", "versao": "0.1", "api": ">=1,<3",  # (noqa-acento)
        "licenca": "MIT", "tipos": ["tema"], "tema": {},
        **dict(pagina={**PAGINA, **pagina})}), encoding="utf-8")
    return pasta


def test_o_manifesto_aceita_a_pagina_dentro_da_pasta(tmp_path: pathlib.Path) -> None:
    m = mf.ler_manifesto(_pasta_com_a_pagina(tmp_path))
    assert m.pagina == mf.Pagina(**PAGINA)


@pytest.mark.parametrize(("arquivo", "frase"), [
    ("../fora.html", "fora da pasta"),
    ("/etc/fora.html", "fora da pasta"),
    ("estudio/pagina.js", "arquivo .html"),
])
def test_o_manifesto_recusa_a_pagina_fora_da_pasta_ou_que_nao_e_html(
        tmp_path: pathlib.Path, arquivo: str, frase: str) -> None:
    pasta = _pasta_com_a_pagina(tmp_path, arquivo=arquivo)
    with pytest.raises(mf.ManifestoRecusadoError, match=frase):
        mf.ler_manifesto(pasta)


def test_o_manifesto_recusa_o_link_que_sai_da_pasta_e_o_arquivo_que_falta(
        tmp_path: pathlib.Path) -> None:
    pasta = _pasta_com_a_pagina(tmp_path)
    fora = tmp_path / "fora.html"
    fora.write_text("<p>fora</p>", encoding="utf-8")
    (pasta / "estudio" / "pagina.html").unlink()
    (pasta / "estudio" / "pagina.html").symlink_to(fora)
    with pytest.raises(mf.ManifestoRecusadoError, match="fora da pasta"):
        mf.ler_manifesto(pasta)
    (pasta / "estudio" / "pagina.html").unlink()
    with pytest.raises(mf.ManifestoRecusadoError, match="não está na pasta"):
        mf.ler_manifesto(pasta)
    (pasta / "estudio" / "pagina.html").write_bytes(b"\xff\xfe<p>")
    with pytest.raises(mf.ManifestoRecusadoError, match="UTF-8"):
        mf.ler_manifesto(pasta)


def test_a_area_da_pagina_e_isolada_e_sem_rede() -> None:
    html = exp.pagina_html("toque", exp.PaginaDaJanela(HTML_DA_EXTENSAO, "Estúdio", 240))
    assert 'sandbox="allow-scripts"' in html, "o iframe perdeu o sandbox"
    assert "allow-same-origin" not in html and "allow-top-navigation" not in html
    assert 'id="mod-pagina"' in html and "height:240px" in html
    documento = exp.documento_da_pagina(HTML_DA_EXTENSAO)
    assert documento.startswith("<!doctype html>") and documento.count("<!doctype") == 1
    assert f'content="{exp.CSP_DA_PAGINA}"' in documento
    assert exp.CSP_DA_PAGINA.startswith("default-src 'none';")
    assert documento.endswith("<p>estúdio</p>")


def test_a_janela_mostra_a_pagina_abaixo_das_opcoes_e_sem_o_vazio() -> None:
    pagina = exp.PaginaDaJanela(HTML_DA_EXTENSAO, "Estúdio", 240)
    so_a_pagina = exp.modificacao_miolo_html("Toque", [], mod="toque", pagina=pagina)
    assert 'id="mod-pagina"' in so_a_pagina and exp.VAZIO_DA_JANELA not in so_a_pagina
    sem = exp.modificacao_miolo_html("Toque", [], mod="toque")
    assert exp.VAZIO_DA_JANELA in sem and "mod-pagina" not in sem
    raiz, pedacos = exp.pedacos_da_janela(so_a_pagina)
    assert "mod-pagina" in pedacos and "mj-pagina-quadro" not in raiz, (
        "o iframe ficou fora do pedaço próprio: todo tique o recarregaria")


def test_os_tetos_da_janela_sao_os_da_porta() -> None:
    assert exp.TETO_DA_MENSAGEM_DA_PAGINA == pt.TETO_DA_MENSAGEM == 64_000
    assert exp.MENSAGENS_DA_PAGINA_POR_SEGUNDO == pt.MENSAGENS_POR_SEGUNDO == 30
    assert exp.PRAZO_DA_PAGINA_MS / 1000 > pt.PRAZO_DA_RESPOSTA_S
    assert f"'{exp.GESTO_DA_PAGINA}'" in exp.SCRIPT_DA_PAGINA
    assert "<style" in exp.telas() and exp.SCRIPT_DA_PAGINA in exp.telas()


def test_a_mensagem_vai_so_a_dona_e_a_resposta_volta(curto: pathlib.Path) -> None:  # noqa: F811
    async def corrida() -> tuple[dict[str, Any], dict[str, Any], Any, Any]:
        porta = await _porta(curto, EventBus())
        a = await _entrar(curto, "ficha-a", {"ligado": True})
        b = await _entrar(curto, "ficha-b", {"ligado": True})
        try:
            pedido = asyncio.ensure_future(porta.mensagem("acessorios", {"pergunta": "oi"}))
            evento = await asyncio.to_thread(a.esperar_evento, 1.0)
            assert evento is not None and evento["params"]["nome"] == pt.EVENTO_DA_MENSAGEM
            ident = evento["params"]["dados"]["id"]
            alheia = await asyncio.to_thread(b.pedir, "extensao.resposta",
                                             {"para": ident, "dados": "roubo"})
            certa = await asyncio.to_thread(a.pedir, "extensao.resposta",
                                            {"para": ident, "dados": {"eco": "oi"}})
            volta = await pedido
            vazou = await asyncio.to_thread(b.esperar_evento, 0.2)
            return evento["params"]["dados"], volta, alheia, (certa, vazou)
        finally:
            a.fechar()
            b.fechar()
            await porta.parar()

    dados, volta, alheia, (certa, vazou) = asyncio.run(corrida())
    assert dados["mod"] == "acessorios" and dados["dados"] == {"pergunta": "oi"}
    assert alheia["error"]["code"] == pt.CODE_INVALID_PARAMS, "outra extensão respondeu"
    assert certa["result"] == {"entregue": True}
    assert volta == {"enviada": True, "respondeu": True, "resposta": {"eco": "oi"}}
    assert vazou is None, f"a outra extensão recebeu a mensagem: {vazou}"


def test_sem_resposta_a_tempo_a_mensagem_volta_sem_resposta(curto: pathlib.Path) -> None:  # noqa: F811
    async def corrida() -> tuple[dict[str, Any], dict[str, Any]]:
        porta = await _porta(curto, EventBus())
        a = await _entrar(curto, "ficha-a", {"ligado": True})
        try:
            calada = await porta.mensagem("acessorios", 1)
            fora = await porta.mensagem("ninguem", 1)
            return calada, fora
        finally:
            a.fechar()
            await porta.parar()

    calada, fora = asyncio.run(corrida())
    assert calada == {"enviada": True, "respondeu": False, "resposta": None}
    assert fora == {"enviada": False, "respondeu": False, "resposta": None}


def test_acima_de_64_kb_e_de_30_por_segundo_recusa(curto: pathlib.Path) -> None:  # noqa: F811
    async def corrida() -> tuple[str, str, int]:
        porta = await _porta(curto, EventBus())
        a = await _entrar(curto, "ficha-a", {"ligado": True})
        agora = [100.0]
        porta._relogio = lambda: agora[0]
        try:
            with pytest.raises(pt.RecusaError) as grande:
                await porta.mensagem("acessorios", "x" * (pt.TETO_DA_MENSAGEM - 1))
            await porta.mensagem("acessorios", "x" * (pt.TETO_DA_MENSAGEM - 2))
            passaram = 1
            with pytest.raises(pt.RecusaError) as ritmo:
                for _ in range(pt.MENSAGENS_POR_SEGUNDO):
                    await asyncio.wait_for(porta.mensagem("acessorios", 1), 3)
                    passaram += 1
            return grande.value.frase, ritmo.value.frase, passaram
        finally:
            a.fechar()
            await porta.parar()

    pt.PRAZO_DA_RESPOSTA_S, antes = 0.01, pt.PRAZO_DA_RESPOSTA_S
    try:
        grande, ritmo, passaram = asyncio.run(corrida())
    finally:
        pt.PRAZO_DA_RESPOSTA_S = antes
    assert "64 KB" in grande
    assert "30 mensagens por segundo" in ritmo and passaram == pt.MENSAGENS_POR_SEGUNDO


def test_o_ipc_so_leva_a_mensagem_de_quem_declara_pagina(lar: Any) -> None:  # noqa: F811
    _instalada(lar)
    levadas: list[tuple[str, Any]] = []

    async def mensagem(mod: str, dados: Any) -> dict[str, Any]:
        levadas.append((mod, dados))
        if dados == "grande":
            raise pt.RecusaError(pt.CODE_INVALID_PARAMS, "a mensagem da página passa de 64 KB")
        return {"enviada": True, "respondeu": True, "resposta": {"eco": dados}}

    servico = _servico(SimpleNamespace(lugares=lar, porta=SimpleNamespace(mensagem=mensagem)))

    def mandar(dados: Any) -> Any:
        return asyncio.run(IpcHandlersMixin._handle_mods_mensagem(
            servico, {"mod": "toque", "dados": dados}))

    with pytest.raises(ValueError, match="não declara página"):
        mandar(1)
    pasta = lar.codigo / "toque"
    manifesto = json.loads((pasta / "hefesto-mod.json").read_text(encoding="utf-8"))
    (pasta / "estudio").mkdir()
    (pasta / "estudio" / "pagina.html").write_text(HTML_DA_EXTENSAO, encoding="utf-8")
    manifesto.update(pagina=PAGINA)
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    assert mandar({"a": 1}) == {"enviada": True, "respondeu": True, "resposta": {"eco": {"a": 1}}}
    assert mandar("grande")["recusa"] == "a mensagem da página passa de 64 KB"
    assert levadas == [("toque", {"a": 1}), ("toque", "grande")]
    sem = asyncio.run(IpcHandlersMixin._handle_mods_mensagem(_servico(None), {"mod": "toque"}))
    assert sem["enviada"] is False


class _PonteDaPagina:
    def __init__(self, corpo: Any) -> None:
        self.corpo = corpo
        self.chamadas: list[tuple[str, dict[str, Any]]] = []

    def resultado(self, metodo: str, timeout: float | None = None, **params: Any) -> Any:
        self.chamadas.append((metodo, {"timeout": timeout, **params}))
        if isinstance(self.corpo, Exception):
            raise self.corpo
        return self.corpo


def _a07() -> Any:
    acao = pacotes.gesto_da_pagina("07-lancadores.html", exp.GESTO_DA_PAGINA)
    assert acao is not None, "o gesto da página não tem dono"
    import sys

    return sys.modules[acao.__module__]


def test_o_gesto_leva_a_mensagem_e_devolve_a_resposta_pelo_campo(ctx: Any) -> None:  # noqa: F811
    a07 = _a07()

    def pedir(corpo: Any, valor: str = '{"n": 7, "dados": {"oi": 1}}') -> Any:
        ponte = _PonteDaPagina(corpo)
        volta = a07.mensagem_da_pagina_da_modificacao(ctx, {"v": "toque", "valor": valor}, ponte)
        return ponte, volta

    ponte, volta = pedir({"enviada": True, "respondeu": True, "resposta": {"eco": 1}})
    assert ponte.chamadas == [("mods.mensagem", {"timeout": a07.PRAZO_DA_MENSAGEM_S,
                                                 "mod": "toque", "dados": {"oi": 1}})]
    assert json.loads(volta["mesa"][exp.CAMPO_DA_RESPOSTA]) == {"n": 7, "ok": True,
                                                                "dados": {"eco": 1}}
    _p, recusada = pedir({"enviada": False, "recusa": "a página manda até 30"})
    assert json.loads(recusada["mesa"][exp.CAMPO_DA_RESPOSTA])["erro"] == "a página manda até 30"
    _p, calada = pedir({"enviada": True, "respondeu": False, "resposta": None})
    assert json.loads(calada["mesa"][exp.CAMPO_DA_RESPOSTA])["erro"] == (
        "A extensão não respondeu a tempo.")
    _p, caiu = pedir(RuntimeError("o daemon não respondeu"))
    assert json.loads(caiu["mesa"][exp.CAMPO_DA_RESPOSTA])["ok"] is False
    assert pedir({}, valor="não é json")[1] == {}
    assert exp.GESTO_DA_PAGINA in a07.SEM_ECO and "mods.mensagem" in a07.METODOS


def test_a_janela_le_a_pagina_da_pasta_instalada(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    a07 = _a07()
    pasta = _pasta_com_a_pagina(tmp_path)
    monkeypatch.setattr(a07, "_lugares", lambda: SimpleNamespace(codigo=tmp_path))
    m = mf.ler_manifesto(pasta)
    assert a07._pagina_da_janela(m, "toque") == exp.PaginaDaJanela(HTML_DA_EXTENSAO, "Estúdio",
                                                                   240)
    (pasta / "estudio" / "pagina.html").unlink()
    recusada = a07._pagina_da_janela(m, "toque")
    assert recusada is not None and "não está na pasta" in recusada.recusa
    area = exp.pagina_html("toque", recusada)
    assert "<iframe" not in area and "não está na pasta" in area


PAGINA_DE_PROVA = """<script>
(async function(){
  var r = {};
  try{ r.dom = !!window.parent.document.body; }catch(e){ r.dom = false; }
  try{ await fetch('data:text/plain,oi'); r.rede = true; }catch(e){ r.rede = false; }
  try{ r.eco = await hefesto.enviar({oi: 'página'}); }catch(e){ r.eco = 'ERRO ' + e.message; }
  try{ await hefesto.enviar('x'.repeat(70000)); r.grande = 'passou'; }
  catch(e){ r.grande = e.message; }
  r.cor = getComputedStyle(document.documentElement).getPropertyValue('--cyan').trim();
  r.tema = document.documentElement.dataset.tema || '';
  hefesto.enviar({fim: r});
})();
</script>"""


@pytest.fixture(scope="module")
def no_webkit() -> dict[str, Any]:
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica: o WebKit não abre")
    area = exp.pagina_html("toque", exp.PaginaDaJanela(PAGINA_DE_PROVA, "Prova", 120))
    pagina = (f"<html><head><style>:root{{--cyan:#8be9fd}}body{{background:#282a36}}</style>"
              f"</head><body><div id=\"mod-janela\">{area}</div>"
              f"<script>{exp.SCRIPT_DA_PAGINA}</script></body></html>")
    gestos: list[dict[str, Any]] = []
    fim: list[Any] = []
    janela = Gtk.OffscreenWindow()
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()
    gerente = view.get_user_content_manager()
    gerente.register_script_message_handler("hefesto")

    def recebeu(_g: Any, resultado: Any) -> None:
        o = json.loads(resultado.get_js_value().to_string())
        gestos.append(o)
        pedido = json.loads(o["valor"])
        if isinstance(pedido["dados"], dict) and "fim" in pedido["dados"]:
            fim.append(pedido["dados"]["fim"])
            Gtk.main_quit()
            return
        volta = json.dumps({"n": pedido["n"], "ok": True, "dados": {"eco": pedido["dados"]}})
        js = (f"document.querySelector('output[data-campo=\"{exp.CAMPO_DA_RESPOSTA}\"]')"
              f".textContent = {json.dumps(volta)};")
        view.evaluate_javascript(js, -1, None, None, None, None)

    gerente.connect("script-message-received::hefesto", recebeu)
    view.load_html(pagina, "file:///07-lancadores.html")
    guarda = GLib.timeout_add(20000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert fim, f"a página não terminou em 20 s; gestos: {gestos}"
    return {"fim": fim[0], "gestos": gestos}


@pytest.mark.skipif(not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"),
                    reason="sem sessão gráfica: o WebKit não abre")
def test_no_webkit_a_pagina_nao_alcanca_o_hefesto_nem_a_rede(no_webkit: dict[str, Any]) -> None:
    fim = no_webkit["fim"]
    assert fim["dom"] is False, "a página alcançou o DOM do Hefesto: o sandbox caiu"
    assert fim["rede"] is False, "o fetch de dentro da página passou: a CSP caiu"


@pytest.mark.skipif(not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"),
                    reason="sem sessão gráfica: o WebKit não abre")
def test_no_webkit_a_mensagem_vai_e_volta_e_acima_de_64_kb_recusa(
        no_webkit: dict[str, Any]) -> None:
    fim, gestos = no_webkit["fim"], no_webkit["gestos"]
    assert fim["eco"] == {"eco": {"oi": "página"}}, fim["eco"]
    assert fim["grande"] == "A mensagem passa de 64 KB.", fim["grande"]
    assert fim["cor"] == "#8be9fd" and fim["tema"] == "escuro", "as cores da casa não chegaram"
    assert all(g["gesto"] == exp.GESTO_DA_PAGINA and g["v"] == "toque" for g in gestos)
    assert len(gestos) == 2, f"a mensagem grande saiu da janela: {len(gestos)} gestos"


PAGINA_QUE_FORJA = """<script>
var h = window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.hefesto;
if(h){ h.postMessage(JSON.stringify({gesto: 'instalar-modificacao', v: 'forjado',
                                     pagina: '07-lancadores.html'})); }
hefesto.enviar({oi: 1}).catch(function(){});
</script>"""

CASA_DEPOIS_DO_LIXO = """setTimeout(function(){
  for(var k = 0; k < 20; k++){ var a = []; for(var i = 0; i < 300000; i++){ a.push({x: i}); } }
  window.webkit.messageHandlers.hefesto.postMessage(JSON.stringify({gesto: 'clique', v: 'casa'}));
}, 300);"""


@pytest.mark.skipif(not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"),
                    reason="sem sessão gráfica: o WebKit não abre")
def test_no_webkit_a_pagina_nao_forja_gesto_pela_ponte_da_casa() -> None:
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk

    from hefesto_dualsense4unix.interface import janela as jn

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica: o WebKit não abre")
    recebidos: list[dict[str, Any]] = []
    recusas: list[str] = []
    ponte = jn.PonteDaTela(ao_receber=recebidos.append,
                           ao_recusar=lambda motivo, bruto: recusas.append(bruto),
                           folha=None, tema_de_cores=None, meu_css="")
    area = exp.pagina_html("toque", exp.PaginaDaJanela(PAGINA_QUE_FORJA, "Prova", 120))
    pagina = (f"<html><body><div id=\"mod-janela\">{area}</div>"
              f"<script>{exp.SCRIPT_DA_PAGINA}</script><script>{CASA_DEPOIS_DO_LIXO}</script>"
              "</body></html>")
    janela = Gtk.OffscreenWindow()
    janela.add(ponte.view)
    janela.show_all()
    ponte.view.load_html(pagina, "file:///07-lancadores.html")
    guarda = GLib.timeout_add(4000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert sorted(str(r.get("v")) for r in recebidos) == ["casa", "toque"], (
        f"a página forjou gesto, ou a casa perdeu o selo depois do coletor: {recebidos}")
    assert next(r for r in recebidos if r.get("v") == "toque")["gesto"] == exp.GESTO_DA_PAGINA
    assert any("forjado" in r for r in recusas), recusas


def test_no_arranjo_c_a_pagina_e_a_ultima_aba_e_nao_rouba_altura() -> None:
    pagina = exp.PaginaDaJanela(HTML_DA_EXTENSAO, "Estúdio", 240)

    def janela(aba: str = "") -> str:
        return exp.modificacao_miolo_html(
            "Toque", exp.OPCOES_DO_DESENHO_DAS_PECAS, mod="toque", agora=exp.AGORA_DO_DESENHO,
            acoes=exp.ACOES_DO_DESENHO, aba=aba, pagina=pagina)

    html = janela()
    rotulos = re.findall(r'<label for="mj-aba-(\d+)">([^<]*)', html)
    assert rotulos and rotulos[-1][1] == "Estúdio", f"a página não virou a última aba: {rotulos}"
    ultima = rotulos[-1][0]
    tela = html.split(f'id="mod-tela-{ultima}"', 1)[1]
    assert tela.index('id="mod-pagina"') < tela.index("</iframe>"), (
        "a página ficou fora da própria aba: a janela cresce e as outras abas rolam")
    assert html.count('id="mod-pagina"') == 1
    assert f'id="mj-aba-{ultima}" checked' in janela("Estúdio"), (
        "a aba da página aberta volta à primeira ao redesenhar")
