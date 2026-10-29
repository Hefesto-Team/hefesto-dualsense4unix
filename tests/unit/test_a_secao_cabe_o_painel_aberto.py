"""A seção Rádio cabe o painel aberto — desenho de Conexões de 06/10/2026, item 2.

O painel do «Conectar» é absoluto e seguia a altura da seção: com as entradas fechadas ela tinha
169 px, o painel pedia 488 com oito aparelhos perto, e a lista rolava por dentro com o miolo vazio
embaixo (fotos 3 e 4 dela). A régua abre o mockup no WebKit, na janela do piloto (1212 por 809), com
as entradas fechadas e oito, três e vinte aparelhos perto, e mede o painel e a seção.

MORDIDA: a MESMA página com a conta da seção desligada (`return` no topo de
`aSecaoCabeOPainel`) volta a cortar a lista.

Em 29/10/2026, a pedido, o título «Outros dispositivos sem fio» saiu, e com ele o selo do Wi-Fi
em 5 GHz que subia para o título quando a seção não cabia. A régua mede, com as linhas da cena do
desenho, que a linha do Wi-Fi fica à vista e o miolo não rola a 1212 por 809, 1212 por 790 e 1512
por 860, sem título nenhum. MORDIDA: o título de volta antes dos outros rádios faz o miolo rolar a
1212 por 790.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup/08-conexoes.html"
CONTA = "function aSecaoCabeOPainel(){"

PREPARA = r"""
(function(){
  document.getElementById('cx8-3').checked = true;
  const t = document.createElement('style');
  t.textContent = '.radio .painel{transition:none !important}';
  document.head.appendChild(t);
  const ar = document.querySelector('.radio .pistas');
  if (ar) { ar.innerHTML = ''; }
  window.__natural = document.getElementById('rd-secao').getBoundingClientRect().height;
  document.getElementById('rd-b-conectar').click();
  const lista = document.querySelector('#rd-painel .achados');
  const molde = lista.querySelector('.achado:last-child');
  while (lista.children.length > ACHADOS) { lista.removeChild(lista.lastElementChild); }
  while (lista.children.length < ACHADOS) {
    const c = molde.cloneNode(true);
    c.setAttribute('data-alvo', 'X' + lista.children.length);
    lista.appendChild(c);
  }
  return 'ok';
})()
"""

MEDE = r"""
(function(){
  const s = document.getElementById('rd-secao'), p = document.getElementById('rd-painel');
  const m = s.closest('.miolo'), ult = [...p.querySelectorAll('.achado')].pop();
  const fora = {
    aberto: p.classList.contains('aberto'),
    natural: Math.round(window.__natural),
    secao: Math.round(s.getBoundingClientRect().height),
    secao_fim: Math.round(s.getBoundingClientRect().bottom),
    miolo_fim: Math.round(m.getBoundingClientRect().bottom),
    painel_rola: p.scrollHeight - p.clientHeight,
    ultimo_visivel: ult.getBoundingClientRect().bottom <= p.getBoundingClientRect().bottom + 1,
    pagina_rola: document.documentElement.scrollHeight - innerHeight,
    miolo_rola: m.scrollHeight - m.clientHeight,
  };
  document.getElementById('rd-fechar').click();
  fora.fechado = Math.round(s.getBoundingClientRect().height);
  return JSON.stringify(fora);
})()
"""


PREPARA_O_AR = r"""
(function(){
  const r = document.getElementById('cx8-3');
  r.checked = true;
  r.dispatchEvent(new Event('change', {bubbles: true}));
  return 'ok';
})()
"""

COM_O_TITULO = r"""
  const outros = document.querySelector('.radio .pistas .ar-do.outros');
  const titulo = document.createElement('div');
  titulo.className = 'ar-grupo outros';
  titulo.textContent = 'Outros dispositivos sem fio';
  outros.before(titulo);
  return 'ok';
"""

MEDE_O_AR = r"""
(function(){
  const m = document.querySelector('.miolo'), p = document.querySelector('.radio .pistas');
  const faixa = p.querySelector('.ar-do.outros .ar-faixa.fora');
  const linha = faixa && faixa.closest('.ar-linha');
  return JSON.stringify({
    linha_visivel: !!(linha && linha.offsetParent),
    titulo: p.textContent.includes('Outros dispositivos sem fio'),
    miolo_rola: m.scrollHeight - m.clientHeight,
  });
})()
"""


def _no_webkit(pagina: Path, achados: int, *, prepara: str = PREPARA, mede: str = MEDE,
               tamanho: tuple[int, int] = (1212, 809)) -> dict[str, Any]:
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    saiu: list[str] = []
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(*tamanho)
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def mediu(v: Any, res: Any) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:  # pragma: no cover
            saiu.append(f"ERRO {e}")
        Gtk.main_quit()

    def preparou(v: Any, res: Any) -> None:
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:  # pragma: no cover
            saiu.append(f"ERRO {e}")
            Gtk.main_quit()
            return
        GLib.timeout_add(600, lambda: (v.evaluate_javascript(
            mede, -1, None, None, None, mediu), False)[1])

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            GLib.timeout_add(300, lambda: (v.evaluate_javascript(
                prepara.replace("ACHADOS", str(achados)), -1, None, None, None, preparou),
                False)[1])

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
    return dict(json.loads(saiu[0]))


@pytest.mark.parametrize("achados", [3, 8])
def test_com_o_painel_aberto_a_secao_cresce_e_a_lista_inteira_aparece(achados: int) -> None:
    f = _no_webkit(MOCKUP, achados)
    assert f["aberto"] is True
    assert f["painel_rola"] <= 1 and f["ultimo_visivel"] is True, f
    assert f["secao"] > f["natural"], "a seção não cresceu para o painel"
    assert f["secao_fim"] <= f["miolo_fim"] and f["pagina_rola"] <= 0, f
    assert abs(f["fechado"] - f["natural"]) <= 1, "fechado, a seção não voltou à altura dela"


def test_com_vinte_aparelhos_a_secao_para_no_fim_do_miolo_e_a_pagina_nao_rola() -> None:
    f = _no_webkit(MOCKUP, 20)
    assert f["secao_fim"] <= f["miolo_fim"] and f["pagina_rola"] <= 0 and f["miolo_rola"] <= 0, f
    assert f["painel_rola"] > 0, "vinte aparelhos não cabem a 809 px: a lista rola no painel"


def test_mordida_sem_a_conta_a_lista_volta_a_ser_cortada(tmp_path: Path) -> None:
    """A MESMA página com a conta desligada: se o teste de cima passasse aqui, não mediria nada."""
    pagina = MOCKUP.read_text(encoding="utf-8")
    assert pagina.count(CONTA) == 1
    cega = tmp_path / "08-sem-a-conta.html"
    cega.write_text(pagina.replace(CONTA, CONTA + " return;"), encoding="utf-8")
    f = _no_webkit(cega, 8)
    assert f["painel_rola"] > 0 and f["ultimo_visivel"] is False, f


BAIXA = (1212, 790)


@pytest.mark.parametrize("tamanho", [(1212, 809), BAIXA, (1512, 860)],
                         ids=lambda t: f"{t[0]}x{t[1]}")
def test_a_linha_do_5ghz_fica_sem_titulo_e_o_miolo_nao_rola(tamanho: tuple[int, int]) -> None:
    f = _no_webkit(MOCKUP, 0, prepara=PREPARA_O_AR, mede=MEDE_O_AR, tamanho=tamanho)
    assert f["linha_visivel"] is True and f["titulo"] is False, f
    assert f["miolo_rola"] <= 0, f


def test_mordida_com_o_titulo_de_volta_o_miolo_rola_na_baixa() -> None:
    prepara = PREPARA_O_AR.replace("  return 'ok';", COM_O_TITULO, 1)
    f = _no_webkit(MOCKUP, 0, prepara=prepara, mede=MEDE_O_AR, tamanho=BAIXA)
    assert f["titulo"] is True and f["miolo_rola"] > 0, f
