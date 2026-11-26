"""A página da extensão não navega para fora (A-PAGINA-DA-EXTENSAO-NAO-NAVEGA-PARA-FORA-01).

Medido em 19/11/2026 no WebKit2 4.1 (2.52.6) e de novo em 26/11/2026 por este teste com a política
arrancada: a página da extensão, no ``iframe`` ``sandbox="allow-scripts"`` da janela, levava dados a
um servidor em ``127.0.0.1`` pelo ``location.href``, pelo ``meta refresh``, pela âncora clicada por
script, pelo formulário e por um ``.html`` local de fora da pasta das páginas; e o quadro de cima ia
a ``file:///etc/hostname``. O ``decide-policy`` da ``JanelaDaAba`` passa a seguir uma lista fechada
de destino, em qualquer quadro: ``about:srcdoc``, ``about:blank`` e os arquivos da pasta das
páginas, pelo caminho resolvido.

MORDIDAS (26/11/2026, executadas sobre a cura e devolvidas):

- sem o ``connect("decide-policy", ...)``: seis dos oito casos de
  ``test_a_pagina_hostil_nao_alcanca_nada`` (``location``, ``refresh``, ``ancora``, ``arquivo`` e
  ``vizinha`` entre eles; o ``abrir`` não reprova: sem quem crie a janela, o WebKit não a abre);
- a lista trocada por «deixa todo ``file://``»: ``topo`` e ``test_o_destino_da_janela`` (o
  ``arquivo`` segue preso pela recusa na RESPONSE);
- sem a recusa na RESPONSE: ``vizinha`` (a página da extensão que vai a uma página da pasta carrega
  dentro do quadro e o pedido chega).

Tudo roda num filho sob ``xvfb-run``, num lar de mentira, com o servidor dentro do filho.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("A-PAGINA-DA-EXTENSAO-NAO-NAVEGA-PARA-FORA-01")

from hefesto_dualsense4unix.interface import janela as jn

RAIZ = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(
    shutil.which("xvfb-run") is None,
    reason="sem `xvfb-run` a janela nasceria na tela de quem roda",
)

_FILHO = textwrap.dedent(
    """
    import http.server, json, pathlib, socketserver, sys, threading
    from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
    from hefesto_dualsense4unix.interface import janela as jn
    from gi.repository import GLib, Gtk

    pasta, modo = pathlib.Path(sys.argv[1]), sys.argv[2]
    pedidos = []

    class Ouvinte(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            pedidos.append(self.path.split("?")[0])
            corpo = b"<script>fetch('/de-dentro').catch(function(){})</script>ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, *_a):
            pass

    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Ouvinte)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    B = f"http://127.0.0.1:{srv.server_address[1]}"
    fora = pasta.parent / "fora.html"
    fora.write_text(f"<img src='{B}/pelo-arquivo-img'><script>fetch('{B}/pelo-arquivo')"
                    ".catch(function(){})</script>", encoding="utf-8")
    corpos = {
        "location": f"<script>location.href='{B}/pela-navegacao?dado=segredo'</script>",
        "refresh": f"<meta http-equiv='refresh' content='0;url={B}/pelo-refresh'>",
        "ancora": f"<a id=a href='{B}/pela-ancora'>x</a>"
                  "<script>document.getElementById('a').click()</script>",
        "abrir": f"<script>window.open('{B}/pelo-open')</script>",
        "form": f"<form id=f action='{B}/pelo-form'><input name=d value=segredo></form>"
                "<script>document.getElementById('f').submit()</script>",
        "arquivo": f"<script>location.href='{fora.as_uri()}'</script>",
        "vizinha": f"<script>location.href='{(pasta / '01-jogar.html').as_uri()}'</script>",
        "fala": "<script>hefesto.enviar({oi: 1})</script>",
        "topo": "<p>quieta</p>",
        "aba": "<p>quieta</p>",
    }
    area = exp.pagina_html("toque", exp.PaginaDaJanela(corpos[modo], "Prova", 120))
    casa = "<button data-gesto='ir'>Ir</button>"
    alvo = pasta / "07-lancadores.html"
    alvo.write_text(f"<!doctype html><meta charset='utf-8'><title>Prova</title><body>{casa}"
                      f"<div id='mod-janela'>{area}</div><script>{exp.SCRIPT_DA_PAGINA}</script>"
                      "</body>", encoding="utf-8")
    vizinha = f"<img src='{B}/pela-vizinha'>" if modo == "vizinha" else ""
    (pasta / "01-jogar.html").write_text(
        f"<!doctype html><meta charset='utf-8'><title>Outra</title><body>{casa}{vizinha}</body>",
        encoding="utf-8")
    recebidos, fim = [], {}

    def carregou():
        if fim.setdefault("cargas", 0) == 0:
            if modo == "topo":
                tela.ponte.rodar("location.href='file:///etc/hostname'")
            if modo == "aba":
                tela.view.load_uri((pasta / "01-jogar.html").as_uri())
        fim["cargas"] += 1

    tela = jn.JanelaDaAba(arquivo=alvo, titulo_esperado=None, ao_carregar=carregou,
                          ao_receber=recebidos.append, ao_falhar=lambda m: None, oculta=True,
                          tema_de_cores=None)
    GLib.timeout_add(5000, Gtk.main_quit)
    Gtk.main()
    fim.update(pedidos=pedidos, recebidos=[r.get("gesto") for r in recebidos],
               fim=pathlib.Path(tela.view.get_uri() or "").name)
    print("FIM " + json.dumps(fim), flush=True)
    """
)


@pytest.fixture
def lar() -> Iterator[Path]:
    pasta = Path(tempfile.mkdtemp(prefix="nav-"))
    yield pasta
    shutil.rmtree(pasta, ignore_errors=True)


def _ambiente_do_lar(lar: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items()
           if k not in {"DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "PULSE_SERVER",
                        "PIPEWIRE_REMOTE", "HEFESTO_SEM_JANELA", "HEFESTO_NA_TELA",
                        "http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"}}
    env.update(
        HOME=str(lar), XDG_CONFIG_HOME=str(lar / "c"), XDG_DATA_HOME=str(lar / "d"),
        XDG_STATE_HOME=str(lar / "s"), XDG_CACHE_HOME=str(lar / "k"),
        XDG_RUNTIME_DIR=str(lar / "r"), GDK_BACKEND="x11", no_proxy="*",
        DBUS_SYSTEM_BUS_ADDRESS=f"unix:path={lar / 'r' / 'sem-barramento'}",
        HEFESTO_BROKER_SOCKET=str(lar / "r" / "sem-broker.sock"),
        PYTHONPATH=str(RAIZ / "src"), PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1",
    )
    for pasta in ("c", "d", "s", "k", "r", "telas"):
        (lar / pasta).mkdir(exist_ok=True)
    (lar / "r").chmod(0o700)
    return env


def _abrir(lar: Path, modo: str) -> dict[str, object]:
    script = lar / "filho.py"
    script.write_text(_FILHO, encoding="utf-8")
    feito = subprocess.run(
        ["xvfb-run", "-a", "-s", "-screen 0 1280x800x24", sys.executable, str(script),
         str(lar / "telas"), modo],
        env=_ambiente_do_lar(lar), capture_output=True, text=True, timeout=90, check=False)
    linhas = [x for x in feito.stdout.splitlines() if x.startswith("FIM ")]
    assert linhas, f"o filho não terminou: rc {feito.returncode}\n{feito.stderr[-2000:]}"
    resultado: dict[str, object] = json.loads(linhas[-1][4:])
    return resultado


@pytest.mark.parametrize("modo", ["location", "refresh", "ancora", "abrir", "form", "arquivo",
                                  "vizinha", "topo"])
def test_a_pagina_hostil_nao_alcanca_nada(lar: Path, modo: str) -> None:
    fim = _abrir(lar, modo)
    assert fim["pedidos"] == [], fim
    assert fim["fim"] == "07-lancadores.html", fim


def test_a_pagina_segue_falando_pelo_post_message(lar: Path) -> None:
    from hefesto_dualsense4unix.interface import desenho_da_experimental as exp

    fim = _abrir(lar, "fala")
    assert exp.GESTO_DA_PAGINA in fim["recebidos"], fim  # type: ignore[operator]


def test_a_troca_de_aba_segue_carregando(lar: Path) -> None:
    fim = _abrir(lar, "aba")
    assert fim["fim"] == "01-jogar.html" and fim["cargas"] == 2, fim


def test_o_destino_da_janela(tmp_path: Path) -> None:
    pasta = tmp_path / "telas"
    pasta.mkdir()
    (pasta / "07-lancadores.html").write_text("x", encoding="utf-8")
    (tmp_path / "fora.html").write_text("x", encoding="utf-8")
    dentro = (pasta / "07-lancadores.html").as_uri()
    assert jn.destino_da_janela(dentro, pasta)
    assert jn.destino_da_janela(dentro + "#trocar", pasta)
    assert jn.destino_da_janela("about:srcdoc", pasta)
    assert jn.destino_da_janela("about:blank", pasta)
    assert jn.destino_da_janela((pasta / "sumida.html").as_uri(), pasta), "a falha de sempre"
    for fora in (None, "", "http://127.0.0.1:9/x", "https://exemplo.org/",
                 "data:text/html,oi", "blob:null/abc", (tmp_path / "fora.html").as_uri(),
                 f"file://{pasta}/../fora.html", "file:///etc/hostname", f"file://outra-maquina{pasta}/07-lancadores.html"):
        assert not jn.destino_da_janela(fora, pasta), fora
