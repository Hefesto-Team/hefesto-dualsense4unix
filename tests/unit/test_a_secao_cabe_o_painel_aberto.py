"""A seção Rádio cabe o painel aberto — desenho de Conexões de 06/10/2026, item 2.

O painel do «Conectar» é absoluto e seguia a altura da seção: com as entradas fechadas ela tinha
169 px, o painel pedia 488 com oito aparelhos perto, e a lista rolava por dentro com o miolo vazio
embaixo (fotos 3 e 4 dela). A régua abre o mockup no WebKit, na janela do piloto (1212 por 809), com
as entradas fechadas e oito, três e vinte aparelhos perto, e mede o painel e a seção.

MORDIDA: a MESMA página com a conta da seção desligada (`return` no topo de
`aSecaoCabeOPainel`) volta a cortar a lista.

A pergunta 1 (opção A, 06/10/2026): a linha de quem está fora da faixa (o Wi-Fi em 5 GHz) custa
29 px; quando com ela a seção não cabe no miolo, ela sobe para o título «Outros dispositivos sem
fio» como selo. A régua mede, com as linhas da cena do desenho, que a linha sobe a 1212 por 809 e
fica a 1512 por 860, e que o miolo rola, no máximo, o que rolaria sem linha nenhuma do Wi-Fi.
MORDIDA: a página sem a troca (`oQueEstaForaDaFaixaCabe` nunca liga o atributo) volta a rolar a
linha.
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


SELO_NO_TITULO = "if(precisa) pistas.setAttribute('data-fora-no-titulo', '');"

PREPARA_O_AR = r"""
(function(){
  const r = document.getElementById('cx8-3');
  r.checked = true;
  r.dispatchEvent(new Event('change', {bubbles: true}));
  return 'ok';
})()
"""

MEDE_O_AR = r"""
(function(){
  const m = document.querySelector('.miolo'), p = document.querySelector('.radio .pistas');
  const linha = p.querySelector('.ar-linha[data-fora-da-faixa]');
  const selo = p.querySelector('.ar-no-titulo');
  const fora = {
    linha_visivel: !!(linha && linha.offsetParent),
    selo_visivel: !!(selo && selo.offsetParent),
    selo: selo ? selo.textContent : '',
    selo_altura: selo ? Math.round(selo.getBoundingClientRect().height) : -1,
    titulo_altura: Math.round(p.querySelector('.ar-grupo.outros').getBoundingClientRect().height),
    miolo_rola: m.scrollHeight - m.clientHeight,
  };
  linha.remove(); selo.remove();
  fora.sem_o_wifi = m.scrollHeight - m.clientHeight;
  return JSON.stringify(fora);
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
        except Exception as e:  # pragma: no cover — só quando o roteiro quebra
            saiu.append(f"ERRO {e}")
        Gtk.main_quit()

    def preparou(v: Any, res: Any) -> None:
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:  # pragma: no cover
            saiu.append(f"ERRO {e}")
            Gtk.main_quit()
            return
        # a lista cresceu depois de aberto: quem refaz a conta é o observador de tamanho
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


def test_a_1212_a_linha_do_5ghz_sobe_para_o_titulo_e_nao_custa_rolagem() -> None:
    f = _no_webkit(MOCKUP, 0, prepara=PREPARA_O_AR, mede=MEDE_O_AR)
    assert f["selo_visivel"] is True and f["linha_visivel"] is False, f
    assert f["selo"] == "Wi-Fi · 5 GHz · canal 161", f
    assert f["selo_altura"] <= f["titulo_altura"], "o selo engordou o título"
    assert f["miolo_rola"] <= f["sem_o_wifi"], f"a linha do Wi-Fi ainda custa rolagem: {f}"


def test_onde_cabe_a_linha_do_5ghz_fica_na_faixa_e_o_titulo_nao_repete() -> None:
    f = _no_webkit(MOCKUP, 0, prepara=PREPARA_O_AR, mede=MEDE_O_AR, tamanho=(1512, 860))
    assert f["linha_visivel"] is True and f["selo_visivel"] is False, f
    assert f["miolo_rola"] <= 0, f


def test_mordida_sem_a_troca_a_linha_do_5ghz_volta_a_custar_rolagem(tmp_path: Path) -> None:
    pagina = MOCKUP.read_text(encoding="utf-8")
    assert pagina.count(SELO_NO_TITULO) == 1
    cega = tmp_path / "08-sem-o-selo.html"
    cega.write_text(pagina.replace(SELO_NO_TITULO, ""), encoding="utf-8")
    f = _no_webkit(cega, 0, prepara=PREPARA_O_AR, mede=MEDE_O_AR)
    assert f["linha_visivel"] is True and f["miolo_rola"] > f["sem_o_wifi"], f
