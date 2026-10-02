#!/usr/bin/env python3
"""ver.py — a interface nova, para ela clicar."""
from __future__ import annotations

import pathlib
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("WebKit2", "4.1")

from gi.repository import Gtk, WebKit2  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import onde  # noqa: E402

D = onde.BANCADA

ABAS = [
    ("Jogar", "01-jogar.html"),
    ("Controles", "02-controles.html"),
    ("Gatilhos", "03-gatilhos.html"),
    ("Iluminação", "04-iluminacao.html"),
    ("Vibração", "05-vibracao.html"),
    ("Navegação", "06-navegacao.html"),
    ("Lançadores", "07-lancadores.html"),
    ("Conexões", "08-conexoes.html"),
    ("Sistema", "09-sistema.html"),
    ("Perfis", "10-perfis.html"),
]

LARGURA, ALTURA = 1180, 757


def _pagina(arquivo: str) -> Gtk.Widget:
    """O `WebView` com o HTML, sem cromo de navegador."""
    view = WebKit2.WebView()
    caminho = D / arquivo

    folha = WebKit2.UserStyleSheet(
        ".nota{display:none !important}",
        WebKit2.UserContentInjectedFrames.TOP_FRAME,
        WebKit2.UserStyleLevel.USER,
        None,
        None,
    )
    view.get_user_content_manager().add_style_sheet(folha)

    view.get_user_content_manager().add_style_sheet(
        WebKit2.UserStyleSheet(
            "select{appearance:none;-webkit-appearance:none}",
            WebKit2.UserContentInjectedFrames.TOP_FRAME,
            WebKit2.UserStyleLevel.USER,
            None,
            None,
        )
    )

    from hefesto_dualsense4unix.interface.hefesto_vivo import DICA_DA_CASA

    view.get_user_content_manager().add_script(
        WebKit2.UserScript(
            DICA_DA_CASA,
            WebKit2.UserContentInjectedFrames.TOP_FRAME,
            WebKit2.UserScriptInjectionTime.END,
            None,
            None,
        )
    )

    view.load_uri(caminho.as_uri())
    return view


def main() -> int:
    inicial = "01-jogar.html"
    if len(sys.argv) > 1:
        alvo = sys.argv[1].zfill(2)
        for _, arquivo in ABAS:
            if arquivo.startswith(alvo):
                inicial = arquivo
                break

    if not (D / inicial).exists():
        print(f"não achei {inicial}", file=sys.stderr)
        print("rode antes: src/hefesto_dualsense4unix/interface/regerar.py", file=sys.stderr)
        return 1

    from hefesto_dualsense4unix.interface.janela import (
        SEM_JANELA_NA_TELA,
        janela_proibida_na_tela,
    )

    if janela_proibida_na_tela():
        print(
            f"recusado: {SEM_JANELA_NA_TELA} está no ambiente, e este visor só "
            "serve aberto na tela dela.\n"
            "Para OLHAR sem aparecer, use o piloto com `--oculta --foto`:\n"
            "  src/hefesto_dualsense4unix/interface/hefesto_vivo.py "
            f"--oculta --abre {inicial} --segundos 8 --foto /tmp/aba.png",
            file=sys.stderr,
        )
        return 2

    janela = Gtk.Window(title="Hefesto — a interface nova (mockup no motor de verdade)")
    janela.set_default_size(LARGURA, ALTURA)
    janela.connect("destroy", Gtk.main_quit)

    barra = Gtk.HeaderBar()
    barra.set_show_close_button(True)
    # janela não conseguimos deixar Hefesto - DualSense4Unix ao invés de só
    # hefesto?"*  (noqa-acento) citação literal dela
    # `utils/identidade.py` escrevia o `S` do DualSense em minúscula, em 427
    from hefesto_dualsense4unix.utils import identidade

    barra.set_title(identidade.atual().nome_longo)
    barra.set_subtitle("a interface nova · mockup no motor de verdade")
    janela.set_titlebar(barra)

    view = _pagina(inicial)
    janela.add(view)
    janela.show_all()
    Gtk.main()
    return 0
