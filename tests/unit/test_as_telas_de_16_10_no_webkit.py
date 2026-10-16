"""As telas de 16/10 medidas no motor que o produto usa: o WebKit, numa janela fora da tela
(AS-TELAS-QUE-ELA-PEDIU-EM-16-10-01).

A Navegação (N1 a N9) e o mapa do controle, nas duas larguras da régua (1212x809 e 1920x1080):
nada rola na vertical, os três botões de «Permitir navegação» ficam numa linha, e os dez gestos do
PS (os cinco de fábrica e os cinco novos) cabem em «Opções» sem empurrar a fila de baixo. O mapa
abre com o título da âncora e sem botão aceso.

TUDO É DE MENTIRA: a página do desenho (`mockup/`) com o pintor do piloto, sem daemon.

A Sistema (S1, S2 e S4): as oito notas do produto saem 3, 3 e 2 sem rolar; o «Parar» tem borda e
letra vermelhas (verdes no «Retomar»), o «Restaurar» o amarelo do padrão; a pílula da bandeja fica
no canto do quadro, inteira, na altura do «Modo Freestyle».

MORDIDAS (feitas à mão, 16/10/2026): tirar o `justify-content:space-evenly` e o `min-height:0` do
`.nav2-ops` (as opções param de ceder altura) reprova `test_os_dez_gestos_cabem_em_opcoes` nas
duas larguras; devolver o `padding:0 14px` ao `.seg.mini button` do «Permitir» quebra o «Uso
geral» em duas linhas a 1212 e reprova `test_a_navegacao_nao_rola`; tirar a regra
`.quadro-topo > .cadeado` da `aba09.py` reprova `test_a_sistema_tem_a_bandeja_e_as_cores`.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("abre a página num WebKit")

from hefesto_dualsense4unix.interface import onde

TAMANHOS = [(1212, 809), (1920, 1080)]

MEDIR_06 = r"""
(function(){
  const m = document.querySelector('.miolo');
  const op = document.querySelector('.nav2-opcoes');
  const fila = document.querySelector('.fila2');
  const seg = [...document.querySelectorAll('[data-gesto="permitir-navegacao"]')];
  const linhas = [...document.querySelectorAll('.tab.ges2 tr[data-vale]')];
  const antes = linhas.map(r => r.dataset.vale);
  const fundo = () => Math.max(...linhas.filter(r => r.dataset.vale === 'sim')
      .map(r => r.getBoundingClientRect().bottom));
  const visto = {
    rola: [m.scrollHeight - m.clientHeight, document.scrollingElement.scrollHeight - innerHeight],
    seg: seg.map(b => { const r = document.createRange(); r.selectNodeContents(b);
      const linhas = new Set([...r.getClientRects()].map(x => Math.round(x.top))).size;
      return [b.textContent.trim(), Math.round(b.getBoundingClientRect().top), linhas]; }),
    vistos: linhas.filter(r => getComputedStyle(r).display !== 'none').length,
  };
  linhas.forEach(r => { r.dataset.vale = 'sim'; });
  visto.dez = {n: linhas.length, rola: m.scrollHeight - m.clientHeight,
               transborda: op.scrollHeight - op.clientHeight,
               fundo: Math.round(fundo()), op: Math.round(op.getBoundingClientRect().bottom),
               fila: Math.round(fila.getBoundingClientRect().top)};
  linhas.forEach((r, i) => { r.dataset.vale = antes[i]; });
  return JSON.stringify(visto);
})()
"""

MEDIR_09 = r"""
(function(){
  const m = document.querySelector('.miolo');
  const cor = (el) => { const c = getComputedStyle(el); return [c.borderTopColor, c.color]; };
  const parar = document.querySelector('[data-gesto="parar-ou-retomar"]');
  const rest = document.querySelector('[data-gesto="restaurar-de-fabrica"]');
  const pil = document.querySelector('.quadro-topo > .cadeado');
  const topo = pil.parentElement.getBoundingClientRect();
  const r = pil.getBoundingClientRect();
  const rg = document.createRange(); rg.selectNodeContents(pil.lastChild);
  const visto = {
    rola: [m.scrollHeight - m.clientHeight, document.scrollingElement.scrollHeight - innerHeight],
    parar: cor(parar), restaurar: cor(rest),
    pilula: {gesto: pil.dataset.gesto, h: Math.round(r.height), w: Math.round(r.width),
             direita: Math.round(topo.right - r.right),
             corta: pil.scrollWidth - pil.clientWidth,
             linhas: new Set([...rg.getClientRects()].map(x => Math.round(x.top))).size,
             texto: pil.textContent.trim(), fonte: getComputedStyle(pil).fontSize},
  };
  parar.classList.add('verde'); visto.retomar = cor(parar); parar.classList.remove('verde');
  document.querySelector('[data-campo="status-lista"]').innerHTML = NOTAS[0];
  document.querySelector('[data-campo="exame-lista"]').innerHTML = NOTAS[1];
  const cols = [...document.querySelectorAll('.status3 .col-lista')];
  visto.notas = cols.map(c => c.querySelectorAll(':scope > .saude').length);
  visto.topos = cols.map(c => Math.round(c.getBoundingClientRect().top));
  visto.rola_com_oito = m.scrollHeight - m.clientHeight;
  return JSON.stringify(visto);
})()
"""

MEDIR_MAPA = r"""
(function(){
  return JSON.stringify({h1: document.querySelector('#mc-titulo').textContent.trim(),
    titulo: document.title,
    acesos: [...document.querySelectorAll('.b2[data-estado~="on"]')].map(b => b.dataset.b),
    rola: document.scrollingElement.scrollHeight - innerHeight});
})()
"""


def _no_webkit(uri: str, tamanho: tuple[int, int], passos: list[str]) -> list[Any]:
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
    janela.set_default_size(*tamanho)
    view.set_size_request(*tamanho)
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
            GLib.timeout_add(250, seguinte)

        view.evaluate_javascript(fila.pop(0), -1, None, None, None, respondeu, None)
        return False

    def carregou(_v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            GLib.timeout_add(400, seguinte)

    view.connect("load-changed", carregou)
    view.load_uri(uri)
    guarda = GLib.timeout_add(40000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert len(respostas) == len(passos) + 1, f"o WebKit parou no meio: {respostas}"
    return [json.loads(x) if x.startswith(("{", "[")) else x for x in respostas[1:]]


_LIDO: dict[tuple[int, int], dict[str, Any]] = {}


def _a_06(tamanho: tuple[int, int]) -> dict[str, Any]:
    if tamanho not in _LIDO:
        uri = onde.pagina("06-navegacao.html", publicado=False).as_uri()
        lido = _no_webkit(uri, tamanho, [MEDIR_06])[0]
        assert isinstance(lido, dict), lido
        _LIDO[tamanho] = lido
    return _LIDO[tamanho]


@pytest.mark.parametrize("tamanho", TAMANHOS)
def test_a_navegacao_nao_rola(tamanho: tuple[int, int]) -> None:
    lido = _a_06(tamanho)
    assert lido["rola"][0] <= 0 and lido["rola"][1] <= 0, lido
    topos = {t for _n, t, _h in lido["seg"]}
    assert [n for n, _t, _h in lido["seg"]] == ["Interna", "Steam", "Uso geral"]
    assert len(topos) == 1, f"«Permitir navegação» quebrou em duas linhas: {lido['seg']}"
    assert all(n == 1 for _n, _t, n in lido["seg"]), f"um rótulo quebrou: {lido['seg']}"


@pytest.mark.parametrize("tamanho", TAMANHOS)
def test_os_dez_gestos_cabem_em_opcoes(tamanho: tuple[int, int]) -> None:
    dez = _a_06(tamanho)["dez"]
    assert dez["n"] == 10, dez
    assert dez["rola"] <= 0 and dez["transborda"] <= 0, dez
    assert dez["fundo"] <= dez["op"] and dez["op"] <= dez["fila"], dez


@pytest.mark.parametrize("tamanho", TAMANHOS)
@pytest.mark.parametrize(("ancora", "titulo"), [("trocar", "Trocar os botões"),
                                                ("point-and-click", "Point and click")])
def test_o_mapa_diz_qual_tela_e_e_nasce_sem_botao_aceso(
        tamanho: tuple[int, int], ancora: str, titulo: str) -> None:
    uri = onde.pagina("mapa-do-controle.html", publicado=False).as_uri() + f"#{ancora}"
    lido = _no_webkit(uri, tamanho, [MEDIR_MAPA])[0]
    assert lido["h1"] == titulo and lido["titulo"] == f"Hefesto — {titulo}", lido
    assert lido["acesos"] == [], f"o mapa nasceu com botão aceso: {lido['acesos']}"
    assert lido["rola"] <= 0, lido


VERMELHO, VERDE, AMARELO = "rgb(255, 85, 85)", "rgb(80, 250, 123)", "rgb(241, 250, 140)"


@pytest.mark.parametrize("tamanho", TAMANHOS)
def test_a_sistema_tem_a_bandeja_e_as_cores(tamanho: tuple[int, int]) -> None:
    import sys

    sys.path.insert(0, str(onde.pagina("09-sistema.html").parents[1]
                           / "src/hefesto_dualsense4unix/interface"))
    import pacotes
    from pacotes import a09_sistema as a09

    pacotes._carregar_tudo()
    status = [{"id": f"s{i}", "selo": "LIGADO", "cls": "ok", "txt": f"Status {i}"}
              for i in range(2)]
    achados = [{"selo": "AVISO", "cls": "aviso", "txt": f"Aviso do exame {i}"} for i in range(6)]
    notas = json.dumps(list(a09._notas_em_tercos(status, achados)))
    uri = onde.pagina("09-sistema.html", publicado=False).as_uri()
    lido = _no_webkit(uri, tamanho, [f"const NOTAS = {notas};" + MEDIR_09])[0]
    assert lido["rola"][0] <= 0 and lido["rola"][1] <= 0, lido
    assert lido["parar"] == [VERMELHO, VERMELHO], lido["parar"]
    assert lido["retomar"] == [VERDE, VERDE], lido["retomar"]
    assert lido["restaurar"] == [AMARELO, AMARELO], lido["restaurar"]
    pil = lido["pilula"]
    assert pil["gesto"] == "bandeja" and pil["texto"] == "Ícone na bandeja", pil
    assert pil["h"] == 34 and 166 <= pil["w"] <= 240 and pil["direita"] <= 20, pil
    assert pil["fonte"] == "13.5px", f"a pílula não tem a letra do «Modo Freestyle»: {pil}"
    assert pil["corta"] <= 0 and pil["linhas"] == 1, f"a pílula da bandeja corta o nome: {pil}"
    assert lido["notas"] == [3, 3, 2], lido["notas"]
    assert len(set(lido["topos"])) == 1, lido["topos"]
    assert lido["rola_com_oito"] <= 0, "as oito notas empurraram a Sistema para a rolagem"
