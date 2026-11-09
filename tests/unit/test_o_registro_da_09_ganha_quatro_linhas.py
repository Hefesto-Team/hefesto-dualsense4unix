"""O registro da aba Sistema mostra quatro linhas a mais, e a aba não rola.

D-0911-AS-ATUALIZACOES-SOBEM-PARA-O-TOPO (09/11/2026): a altura sai dos espaços entre os blocos,
das margens e da entrelinha do registro, com a letra em 12 px. Medido no WebKit, no desenho, em
1212x700 e 1212x809 sem zoom e no zoom que a janela põe em cada tamanho da interface
(``folha_da_casa.tamanho_que_cabe``). ``LINHAS_ANTES`` é o que o registro comportava no commit
76ed3fbfa, medido do mesmo jeito.

A MORDIDA: devolver os espaços de antes (o vão de 6 px das colunas, o ``padding`` de 10 px do
registro, a entrelinha 1.6 e as margens de 10 px da folha do piso) deixa cada caso com as linhas
de antes, e a régua reprova.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.folha_da_casa import tamanho_que_cabe

LINHAS_ANTES = {
    ((1212, 700), None): 3,
    ((1212, 809), None): 9,
    ((1212, 700), 100): 9, ((1212, 700), 125): 9, ((1212, 700), 150): 9,
    ((1212, 809), 100): 9, ((1212, 809), 125): 9, ((1212, 809), 150): 9,
    ((1918, 1080), 100): 13, ((1918, 1080), 125): 12, ((1918, 1080), 150): 9,
}

MEDIR = r"""
(function () {
  const log = document.querySelector('.registro > .log');
  const s = getComputedStyle(log);
  const lh = parseFloat(s.lineHeight);
  const util = log.getBoundingClientRect().height - parseFloat(s.paddingTop)
    - parseFloat(s.paddingBottom) - parseFloat(s.borderTopWidth) - parseFloat(s.borderBottomWidth);
  const q = document.querySelector('.quadro.estica').getBoundingClientRect();
  return JSON.stringify({linhas: Math.floor((util + 0.5) / lh), letra: parseFloat(s.fontSize),
    fundo: log.getBoundingClientRect().bottom, quadro: q.bottom, innerH: innerHeight,
    scrollH: document.documentElement.scrollHeight});
})()
"""


def _zoom(vista: tuple[int, int], tamanho: int | None) -> int:
    return 100 if tamanho is None else tamanho_que_cabe(tamanho, *vista)


def _medir(casos: list[tuple[int, int, int]]) -> dict[tuple[int, int, int], dict[str, Any]]:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("abre a aba Sistema num WebKit")
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    pagina = onde.pagina("09-sistema.html", publicado=False).as_uri()
    lidos: dict[tuple[int, int, int], dict[str, Any]] = {}
    for largura, altura, zoom in casos:
        view = WebKit2.WebView()
        janela = Gtk.OffscreenWindow()
        janela.set_default_size(largura, altura)
        view.set_size_request(largura, altura)
        janela.add(view)
        janela.show_all()
        view.set_zoom_level(zoom / 100)
        resposta: list[str] = []

        def respondeu(v: Any, res: Any, _u: Any = None, saida: list[str] = resposta) -> None:
            saida.append(v.evaluate_javascript_finish(res).to_string())
            Gtk.main_quit()

        def carregou(v: Any, evento: Any) -> None:
            if evento == WebKit2.LoadEvent.FINISHED:
                GLib.timeout_add(300, lambda: v.evaluate_javascript(
                    MEDIR, -1, None, None, None, respondeu, None) and False)

        view.connect("load-changed", carregou)
        view.load_uri(pagina)
        guarda = GLib.timeout_add(30000, Gtk.main_quit)
        try:
            Gtk.main()
        finally:
            GLib.source_remove(guarda)
            janela.destroy()
        assert resposta, f"o WebKit não respondeu em {largura}x{altura} a {zoom} %"
        lidos[(largura, altura, zoom)] = json.loads(resposta[0])
    return lidos


def test_o_registro_mostra_quatro_linhas_a_mais_sem_a_aba_rolar() -> None:
    casos = sorted({(*vista, _zoom(vista, tamanho)) for vista, tamanho in LINHAS_ANTES})
    lidos = _medir(casos)
    faltam = []
    for (vista, tamanho), antes in LINHAS_ANTES.items():
        lido = lidos[(*vista, _zoom(vista, tamanho))]
        nome = f"{vista[0]}x{vista[1]} no tamanho {tamanho or 'sem zoom'}"
        assert round(lido["letra"], 1) >= 12, f"{nome}: a letra do registro é {lido['letra']} px"
        assert lido["scrollH"] <= lido["innerH"] + 1, f"{nome}: a aba rola na vertical: {lido}"
        assert lido["fundo"] <= lido["quadro"] + 0.5, f"{nome}: o registro passa do quadro: {lido}"
        if lido["linhas"] < antes + 4:
            faltam.append(f"{nome}: {lido['linhas']} linhas, e o pedido é {antes + 4}")
    assert not faltam, "o registro não ganhou as quatro linhas:\n" + "\n".join(faltam)
