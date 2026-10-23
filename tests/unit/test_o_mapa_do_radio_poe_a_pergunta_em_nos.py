"""A pergunta do mapa do rádio monta a frase em nós, não em `innerHTML`
(OS-ALERTAS-DO-CODEQL-ZERAM-01).

O CodeQL acusava `js/xss-through-dom` no `perguntar` do `mapa-do-radio.html`: a frase, que leva o
nome do lugar que alguém digitou, entrava por `innerHTML`. A cura é o `poeFrase`, que só conhece
`<b>`, `</b>` e `<br>` e põe cada pedaço de texto por `textContent`. A página não tem gerador: o
`mockup/` e o publicado são o mesmo arquivo, e esta régua lê os dois.

MORDIDA: devolver `caixa.querySelector('.diz').innerHTML = diz;` reprova o caso textual; trocar o
`createTextNode` do `poeFrase` por `insertAdjacentHTML` faz o `<img>` nascer no WebKit.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import onde as _onde

_PAGINAS = (
    _onde.pagina("mapa-do-radio.html"),
    _onde.pagina("mapa-do-radio.html", publicado=True),
)
_FRASE = "<b>Sala &lt;img src=x&gt;</b> &amp; cia<br>outra linha"


def _corpo_de(pagina: str, assinatura: str) -> str:
    inicio = pagina.index(assinatura)
    achou = re.match(r" *", pagina[pagina.rfind("\n", 0, inicio) + 1:])
    recuo = achou.group(0) if achou else ""
    return pagina[inicio:pagina.index("\n" + recuo + "}", inicio) + len(recuo) + 2]


@pytest.mark.parametrize("caminho", _PAGINAS, ids=("desenho", "publicado"))
def test_a_pergunta_poe_a_frase_pelo_poe_frase(caminho: Path) -> None:
    pagina = caminho.read_text(encoding="utf-8")
    assert ".innerHTML = diz" not in pagina, f"{caminho.name}: a frase voltou ao innerHTML"
    assert "poeFrase(caixa.querySelector('.diz'), diz);" in _corpo_de(pagina, "function perguntar(")
    corpo = _corpo_de(pagina, "function poeFrase(")
    assert "createTextNode" in corpo and "innerHTML" not in corpo


def _no_webkit(pagina: str, tmp_path: Path) -> dict[str, Any]:
    if (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("HEFESTO_NA_TELA")
            or not os.environ.get("DISPLAY")):
        pytest.skip("sem o X de mentira: o WebKit abriria na tela dela ou não abriria")
    from tests.conftest import exigir_gi_real

    exigir_gi_real("abre o mapa do rádio no WebKit")
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    js = (
        "(function () { const _LETRA_DA_ENTIDADE = { amp: '&', lt: '<', gt: '>' };\n"
        + _corpo_de(pagina, "function poeFrase(")
        + "\nconst d = document.createElement('div'); poeFrase(d, FRASE);"
        " return JSON.stringify({b: d.querySelectorAll('b').length,"
        " img: d.querySelectorAll('img').length, br: d.querySelectorAll('br').length,"
        " negrito: d.querySelector('b') ? d.querySelector('b').textContent : null,"
        " texto: d.textContent}); })()"
    ).replace("FRASE", json.dumps(_FRASE))
    copia = tmp_path / "mapa-do-radio.html"
    copia.write_text(pagina, encoding="utf-8")
    saiu: list[str] = []
    janela = Gtk.OffscreenWindow()
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def leu(v: Any, res: Any) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except GLib.Error as erro:
            saiu.append(json.dumps({"erro": str(erro)}))
        Gtk.main_quit()

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(js, -1, None, None, None, leu)

    view.connect("load-changed", carregou)
    view.load_uri(copia.as_uri())
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


def test_no_webkit_o_nome_com_marca_vira_letra_na_pergunta(tmp_path: Path) -> None:
    lido = _no_webkit(_PAGINAS[0].read_text(encoding="utf-8"), tmp_path)
    assert "erro" not in lido, lido
    assert lido == {
        "b": 1, "img": 0, "br": 1, "negrito": "Sala <img src=x>",
        "texto": "Sala <img src=x> & ciaoutra linha",
    }, lido
