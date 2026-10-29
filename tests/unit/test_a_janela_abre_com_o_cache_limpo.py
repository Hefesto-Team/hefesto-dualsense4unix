"""A janela abre com o cache das páginas limpo.

Pedido de 29/10/2026: o cache das páginas da janela sobrevivia entre versões
(`~/.cache/hefesto-dualsense4unix/WebKitCache`, com registros de 23/10), e a limpeza era à mão.
A cura (A-JANELA-ABRE-COM-O-CACHE-DAS-PAGINAS-LIMPO-01): a primeira `PonteDaTela` de cada processo
apaga o cache em disco e o da memória (`jn.limpar_o_cache_uma_vez`).

A régua roda num lar de mentira e num Xvfb próprio. Um primeiro processo serve uma página por HTTP
local com `Cache-Control` longo e a carrega num WebView cru: o WebKit grava registros no disco. Um
segundo processo só abre a ponte da janela, e os registros têm de sumir.

MORDIDA (29/10/2026): tirar a chamada a `limpar_o_cache_uma_vez` do `PonteDaTela.__init__` deixa os
registros no disco, e a régua reprova.
"""

from __future__ import annotations

import http.server
import os
import pathlib
import shutil
import subprocess
import sys
import textwrap
import threading
from collections.abc import Iterator

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("A-JANELA-ABRE-COM-O-CACHE-DAS-PAGINAS-LIMPO-01")

from hefesto_dualsense4unix.interface import janela as jn

RAIZ = pathlib.Path(__file__).resolve().parents[2]
NOME_DO_PROGRAMA = "hefesto-regua-do-cache"

FILHO = textwrap.dedent(
    """
    import sys, time
    from gi.repository import GLib
    GLib.set_prgname(sys.argv[2])
    from hefesto_dualsense4unix.interface import janela as jn
    from gi.repository import Gtk, WebKit2

    def bombear(ate, prazo):
        contexto = GLib.MainContext.default()
        fim = time.monotonic() + prazo
        while not ate() and time.monotonic() < fim:
            while contexto.pending():
                contexto.iteration(False)
            time.sleep(0.004)
        return ate()

    if sys.argv[1] == "grava":
        view = WebKit2.WebView()
        janela = Gtk.OffscreenWindow()
        janela.add(view)
        janela.show_all()
        view.load_uri(sys.argv[3])
        bombear(lambda: not view.is_loading() and view.get_uri(), 20.0)
    else:
        ponte = jn.PonteDaTela(folha=None, tema_de_cores=None, meu_css="")
        janela = Gtk.OffscreenWindow()
        janela.add(ponte.view)
        janela.show_all()
    bombear(lambda: False, 3.0)
    print("FILHO-OK")
    """
)


class _PaginaQueSeGuarda(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        corpo = b"<!doctype html><html><body>" + b"a" * 20000 + b"</body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Cache-Control", "max-age=86400")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *_argumentos: object) -> None:
        return


@pytest.fixture
def endereco() -> Iterator[str]:
    servidor = http.server.HTTPServer(("127.0.0.1", 0), _PaginaQueSeGuarda)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{servidor.server_port}/pagina.html"
    finally:
        servidor.shutdown()
        servidor.server_close()


def _registros(lar: pathlib.Path) -> list[pathlib.Path]:
    return [p for p in (lar / "cache").rglob("*") if p.is_file() and "Records" in p.parts]


def _rodar(lar: pathlib.Path, *argumentos: str) -> None:
    script = lar / "filho.py"
    script.write_text(FILHO, encoding="utf-8")
    ambiente = dict(os.environ, PYTHONPATH=str(RAIZ / "src"), GDK_BACKEND="x11",
                    HOME=str(lar), XDG_CONFIG_HOME=str(lar / "config"),
                    XDG_CACHE_HOME=str(lar / "cache"), XDG_DATA_HOME=str(lar / "data"),
                    XDG_STATE_HOME=str(lar / "state"), NO_AT_BRIDGE="1")
    for nome in ("WAYLAND_DISPLAY", "DISPLAY", jn.SEM_JANELA_NA_TELA, "HEFESTO_NA_TELA",
                 "http_proxy", "HTTP_PROXY", "all_proxy", "ALL_PROXY"):
        ambiente.pop(nome, None)
    proc = subprocess.run(
        ["xvfb-run", "-a", sys.executable, str(script), *argumentos],
        env=ambiente, capture_output=True, text=True, timeout=120, check=False,
    )
    assert proc.returncode == 0 and "FILHO-OK" in proc.stdout, (proc.stdout + proc.stderr)[-2000:]


def test_a_ponte_da_janela_apaga_o_cache_que_a_vida_anterior_gravou(
    tmp_path: pathlib.Path, endereco: str,
) -> None:
    if shutil.which("xvfb-run") is None:  # pragma: no cover
        pytest.skip("sem `xvfb-run` não há onde o WebKit desenhe")
    _rodar(tmp_path, "grava", NOME_DO_PROGRAMA, endereco)
    gravados = _registros(tmp_path)
    assert gravados, "o WebKit não gravou cache nenhum: a régua não tem o que medir"
    _rodar(tmp_path, "abre", NOME_DO_PROGRAMA)
    sobra = _registros(tmp_path)
    assert not sobra, (
        f"a janela abriu e {len(sobra)} registro(s) do cache de antes ficaram: "
        f"{[str(p.relative_to(tmp_path)) for p in sobra]}")
