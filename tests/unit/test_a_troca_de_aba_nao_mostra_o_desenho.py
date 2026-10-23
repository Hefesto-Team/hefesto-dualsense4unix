"""A troca de aba não mostra o desenho antes da pintura — 22/09/2026."""

from __future__ import annotations

import ast
import os
import pathlib
import re
import time
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("a troca de aba que não mostra o desenho")

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PILOTO = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "hefesto_vivo.py"

from hefesto_dualsense4unix.interface.folha_da_casa import (
    CLASSE_DA_ESPERA,
    FOLHA_DA_CASA,
    seletores_escondidos,
)

ESCONDIDOS = ("div.miolo", ".fita", ".conectado", ".perfil-ativo")
MOLDURA = (".tira", ".logo", ".marca-nome", ".rodape")


def test_a_folha_esconde_o_que_carrega_dado_e_so_isso() -> None:
    """A regra da espera zera a opacidade do miolo e das três peças vivas."""
    regra = re.search(rf"([^{{}}]*\.{CLASSE_DA_ESPERA}[^{{}}]*)\{{([^{{}}]*)\}}", FOLHA_DA_CASA)
    assert regra, "a folha da casa perdeu a regra da espera"
    seletores = {s.strip() for s in regra.group(1).split(",")}
    assert seletores == {f".{CLASSE_DA_ESPERA} {s}" for s in ESCONDIDOS}, seletores
    assert re.search(r"opacity:\s*0\b", regra.group(2)), (
        "a regra da espera tem de ser OPACIDADE: `visibility` é furada pelos "
        "filhos com `visibility:visible` de três páginas")
    assert not any(CLASSE_DA_ESPERA in s for s in seletores_escondidos())


def test_o_roteiro_acende_e_tem_prazo() -> None:
    from hefesto_dualsense4unix.interface import janela as pt

    assert f"classList.add('{CLASSE_DA_ESPERA}')" in pt.ROTEIRO_DA_ESPERA
    assert f"classList.remove('{CLASSE_DA_ESPERA}')" in pt.ROTEIRO_DA_ESPERA
    assert str(pt.PRAZO_DA_ESPERA_MS) in pt.ROTEIRO_DA_ESPERA


def _corpo_do_pintar() -> str:
    from hefesto_dualsense4unix.interface import hefesto_vivo

    js = hefesto_vivo.BOOTSTRAP
    i = js.index("window.__hef.pintar = function(p){")
    return js[i:js.index("\n    return n;\n  };", i)]


def test_quem_apaga_a_espera_e_o_fim_do_pintar() -> None:
    """E NÃO o início: apagar antes de escrever mostraria o desenho de novo."""
    corpo = _corpo_do_pintar()
    linha = f"document.documentElement.classList.remove('{CLASSE_DA_ESPERA}');"
    assert linha in corpo, "o `pintar` não devolve mais a página à tela"
    assert corpo.rstrip().endswith(linha), (
        "a espera tem de sair DEPOIS de tudo escrito, na última linha do `pintar`")
    assert f"if(document.documentElement.classList.contains('{CLASSE_DA_ESPERA}'))" in corpo


def test_o_piloto_liga_a_espera() -> None:
    """Só o piloto único pinta a página inteira a cada troca — só ele liga."""
    arvore = ast.parse(PILOTO.read_text(encoding="utf-8"))
    ligados = [
        kw for no in ast.walk(arvore) if isinstance(no, ast.Call)
        and getattr(no.func, "id", "") == "JanelaDaAba"
        for kw in no.keywords if kw.arg == "esperar_a_pintura"
    ]
    assert ligados and all(getattr(k.value, "value", None) is True for k in ligados), (
        "o `hefesto_vivo` abriu a janela sem `esperar_a_pintura=True`")


def _bombear(ate: Any, prazo: float) -> bool:
    from gi.repository import GLib

    contexto = GLib.MainContext.default()
    fim = time.monotonic() + prazo
    while time.monotonic() < fim:
        while contexto.pending():
            contexto.iteration(False)
        if ate():
            return True
        time.sleep(0.01)
    return bool(ate())


class _Aba:
    def __init__(self, esperar: bool) -> None:
        from hefesto_dualsense4unix.interface import janela as ponte_da_tela
        from hefesto_dualsense4unix.interface import onde

        arquivo = onde.pagina("04-iluminacao.html", publicado=True)
        titulo = re.search(r"<title>(.*?)</title>", arquivo.read_text(encoding="utf-8")).group(1)
        self.carregou = False
        self.janela = ponte_da_tela.JanelaDaAba(
            arquivo=arquivo, titulo_esperado=titulo, oculta=True,
            ao_carregar=self._carregou, esperar_a_pintura=esperar)
        assert _bombear(lambda: self.carregou, 20.0), "a página não carregou"

    def _carregou(self) -> None:
        self.carregou = True

    def ler(self, js: str) -> Any:
        caixa: dict[str, Any] = {}
        self.janela.ponte.perguntar(js, lambda v, e: caixa.update(v=v, e=e))
        assert _bombear(lambda: bool(caixa), 10.0), f"a página não respondeu: {js}"
        assert caixa["e"] is None, caixa["e"]
        return caixa["v"]

    def opacidades(self) -> dict[str, str]:
        import json

        todos = ESCONDIDOS + MOLDURA
        return json.loads(self.ler(
            "JSON.stringify(Object.fromEntries(" + repr(list(todos)) + ".map(s => "
            "[s, getComputedStyle(document.querySelector(s)).opacity])))"))


@pytest.fixture
def _tela_de_teste() -> None:
    if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
        pytest.skip("sem servidor gráfico: não há WebView para medir")


@pytest.mark.usefixtures("_tela_de_teste")
def test_a_pagina_nasce_sem_o_desenho_e_aparece_na_primeira_pintura() -> None:
    """O arquivo carregou e o miolo NÃO está na tela; o `pintar` real o devolve."""
    from hefesto_dualsense4unix.interface import hefesto_vivo

    aba = _Aba(esperar=True)
    try:
        antes = aba.opacidades()
        for s in ESCONDIDOS:
            assert antes[s] == "0", f"{s} apareceu antes da pintura: {antes}"
        for s in MOLDURA:
            assert antes[s] == "1", f"a moldura sumiu junto ({s}): {antes}"
        aba.ler(hefesto_vivo.BOOTSTRAP)
        aba.ler("String(window.__hef.pintar({}))")
        depois = aba.opacidades()
        assert all(v == "1" for v in depois.values()), (
            f"a primeira pintura não devolveu a página: {depois}")
    finally:
        aba.janela.janela.destroy()


@pytest.mark.usefixtures("_tela_de_teste")
def test_sem_pintura_a_pagina_aparece_no_prazo() -> None:
    """A rede de segurança: piloto travado não deixa a janela sem miolo."""
    from hefesto_dualsense4unix.interface import janela as pt

    aba = _Aba(esperar=True)
    try:
        prazo = pt.PRAZO_DA_ESPERA_MS / 1000 + 1.0
        assert _bombear(lambda: aba.opacidades()["div.miolo"] == "1", prazo), (
            "sem pintura a página ficou escondida depois do prazo")
    finally:
        aba.janela.janela.destroy()


@pytest.mark.usefixtures("_tela_de_teste")
def test_quem_nao_pede_a_espera_ve_a_pagina_como_antes() -> None:
    """As outras janelas da biblioteca (ensaios, pilotos por aba) não mudam."""
    aba = _Aba(esperar=False)
    try:
        assert all(v == "1" for v in aba.opacidades().values())
    finally:
        aba.janela.janela.destroy()


class _Lenta:
    """Um servidor local que segura a imagem da página além do prazo: o `load` chega tarde."""

    def __init__(self, segundos: float) -> None:
        import http.server
        import threading

        class _Resposta(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                time.sleep(segundos)
                self.send_response(204)
                self.end_headers()

            def log_message(self, *_a: Any) -> None:
                pass

        self.servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Resposta)
        self.porta = self.servidor.server_address[1]
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()

    def fechar(self) -> None:
        self.servidor.shutdown()
        self.servidor.server_close()


@pytest.mark.usefixtures("_tela_de_teste")
def test_a_carga_lenta_nao_gasta_o_prazo(tmp_path: pathlib.Path) -> None:
    """O prazo conta do `load`, não do início do documento: a carga que passa do prazo não
    devolve o desenho antes de o piloto poder pintar, e a rede ainda vale depois dela."""
    import json

    from hefesto_dualsense4unix.interface import janela as pt

    prazo = pt.PRAZO_DA_ESPERA_MS / 1000
    lenta = _Lenta(prazo + 1.0)
    arquivo = tmp_path / "lenta.html"
    arquivo.write_text(
        "<!doctype html><html><head><meta charset='utf-8'><title>Carga lenta</title></head>"
        "<body><div class='miolo'>miolo</div>"
        f"<img src='http://127.0.0.1:{lenta.porta}/lenta.png' alt=''></body></html>",
        encoding="utf-8")
    carregou: list[float] = []
    janela = pt.JanelaDaAba(
        arquivo=arquivo, titulo_esperado="Carga lenta", oculta=True,
        ao_carregar=lambda: carregou.append(time.monotonic()), esperar_a_pintura=True)
    try:
        assert _bombear(lambda: bool(carregou), 20.0), "a página não carregou"
        caixa: dict[str, Any] = {}
        janela.ponte.perguntar(
            "JSON.stringify({op:getComputedStyle(document.querySelector('div.miolo')).opacity,"
            "load:performance.getEntriesByType('navigation')[0].loadEventEnd})",
            lambda v, e: caixa.update(v=v, e=e))
        assert _bombear(lambda: bool(caixa), 10.0) and caixa["e"] is None, caixa
        lido = json.loads(caixa["v"])
        assert lido["load"] > pt.PRAZO_DA_ESPERA_MS, (
            f"a carga não passou do prazo ({lido}): o teste não mediria nada")
        assert lido["op"] == "0", f"a carga lenta gastou o prazo e o desenho voltou: {lido}"

        def miolo() -> str:
            resposta: dict[str, Any] = {}
            janela.ponte.perguntar(
                "getComputedStyle(document.querySelector('div.miolo')).opacity",
                lambda v, e: resposta.update(v=v, e=e))
            _bombear(lambda: bool(resposta), 10.0)
            return str(resposta.get("v"))

        assert _bombear(lambda: miolo() == "1", prazo + 1.0), (
            "depois da carga lenta, sem pintura, a página ficou escondida além do prazo")
    finally:
        janela.janela.destroy()
        lenta.fechar()
