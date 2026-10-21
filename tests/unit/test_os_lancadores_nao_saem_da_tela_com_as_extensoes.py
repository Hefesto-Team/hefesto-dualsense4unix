"""Os lançadores não saem da tela com as extensões.

Sprint OS-LANCADORES-NAO-SAEM-DA-TELA-COM-AS-EXTENSOES-01.

Medido em 21/10/2026, no desenho da 07 com doze extensões, a 809 px de altura (o piso da
janela): uma fileira de 63 px por extensão, o conteúdo da aba com 1050 px para 618 à vista, e o
cartão «Lançadores» começando em 1017 px, abaixo da barra do Aplicar. A cura é a variante A
escolhida (`mockup/variantes/2110-extensoes-A-duas-colunas.html`): duas colunas de cartões de meia
largura, teto de cinco fileiras e rolagem só dentro da lista; a coluna do «Para» saiu da linha.

A sonda abre o desenho num WebKit de verdade, sob a tela de mentira, em 1272, 1512 e 1900 px, clona
as linhas até doze e mede. Com uma extensão só, abre o ⋮ com as permissões: dentro da lista que
rola, o menu flutuante seria cortado.

MORDIDA (executada em 21/10/2026): com a lista numa coluna só (`repeat(1,…)`), ou sem o teto
(`max-height:none`), `test_doze_extensoes_cabem_e_os_lancadores_ficam_a_vista` reprova nas três
larguras; sem a regra do ⋮ com as permissões dentro da lista,
`test_o_menu_com_as_permissoes_fica_dentro_da_lista` reprova.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys

import pytest

from hefesto_dualsense4unix.interface import desenho_da_experimental as exp

RAIZ = pathlib.Path(__file__).resolve().parents[2]
DESENHO = RAIZ / "mockup" / "07-lancadores.html"
LARGURAS = (1272, 1512, 1900)
#: Cinco fileiras de 53 px e quatro vãos de 6 px: o teto do desenho escolhido.
TETO = 289

_SONDA = r"""
import json, pathlib, sys
from hefesto_dualsense4unix.utils.tela_de_mentira import garantir_tela_de_mentira
garantir_tela_de_mentira(anunciar=False)
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk
from hefesto_dualsense4unix.interface.janela import PISO_DA_VISTA, PonteDaTela

PAGINA = pathlib.Path(sys.argv[1])
MEDIR = '''
(function(n, abrir){
  const lista = document.querySelector('.ext-lista');
  const modelo = lista.querySelector('.ext');
  while (lista.querySelectorAll('.ext').length < n) {
    const c = modelo.cloneNode(true);
    c.querySelector('.ext-nome').textContent = 'Extensão de mentira';
    lista.appendChild(c);
  }
  while (lista.querySelectorAll('.ext').length > n) {
    lista.querySelector('.ext:last-child').remove();
  }
  const exts = [...lista.querySelectorAll('.ext')];
  if (abrir) {
    const menu = exts[0].querySelector('.ext-menu'); menu.classList.add('aberto');
    const lp = document.createElement('span'); lp.className = 'ext-perm';
    lp.innerHTML = '<span>Trocar as cores da interface</span><span>Ler os jogos das pastas</span>';
    menu.appendChild(lp);
  }
  const m = document.querySelector('.janela > .miolo');
  const lanc = [...document.querySelectorAll('.quadro')].find(
    q => /Lançadores/.test(q.querySelector('.quadro-titulo')?.textContent || ''));
  const r = e => {
    const x = e.getBoundingClientRect();
    return [Math.round(x.top), Math.round(x.bottom)];
  };
  const menu = exts[0].querySelector('.ext-menu');
  return JSON.stringify({miolo: [m.scrollHeight, m.clientHeight], miolo_caixa: r(m), lanc: r(lanc),
    lista: [lista.scrollHeight, lista.clientHeight], lista_caixa: r(lista), menu: r(menu),
    colunas: new Set(exts.map(e => Math.round(e.getBoundingClientRect().left))).size,
    cartao: Math.round(exts[0].getBoundingClientRect().height),
    doc: [document.documentElement.scrollHeight, document.documentElement.clientHeight]});
})(%d, %s)
'''
saida = {}
for largura, n, abrir in [(1272, 12, 0), (1512, 12, 0), (1900, 12, 0), (1272, 1, 1)]:
    ponte = PonteDaTela(folha=None)
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(largura, PISO_DA_VISTA)
    janela.add(ponte.view)
    janela.show_all()
    ponte.view.load_uri(PAGINA.as_uri())
    fim = GLib.get_monotonic_time() + 4_000_000
    while GLib.get_monotonic_time() < fim:
        Gtk.main_iteration_do(False)
    caixa = {}
    ponte.perguntar(MEDIR % (n, "true" if abrir else "false"),
                    lambda v, e: caixa.update(v=v, e=repr(e) if e else ""))
    fim = GLib.get_monotonic_time() + 8_000_000
    while "v" not in caixa and GLib.get_monotonic_time() < fim:
        Gtk.main_iteration_do(False)
    saida[f"{largura}-{n}"] = json.loads(caixa["v"]) if caixa.get("v") else caixa
    janela.destroy()
print(json.dumps(saida))
"""


@pytest.fixture(scope="module")
def medida() -> dict[str, dict[str, list[int] | int]]:
    ambiente = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    filho = subprocess.run([sys.executable, "-c", _SONDA, str(DESENHO)], env=ambiente,
                           capture_output=True, text=True, timeout=240)
    if filho.returncode != 0:
        pytest.skip(f"o WebKit não subiu na tela de mentira: {filho.stderr.strip()[-300:]}")
    return dict(json.loads(filho.stdout.strip().splitlines()[-1]))


@pytest.mark.parametrize("largura", LARGURAS)
def test_doze_extensoes_cabem_e_os_lancadores_ficam_a_vista(
        medida: dict[str, dict[str, list[int] | int]], largura: int) -> None:
    m = medida[f"{largura}-12"]
    miolo, caixa, lanc = m["miolo"], m["miolo_caixa"], m["lanc"]
    lista = m["lista"]
    assert isinstance(miolo, list) and isinstance(caixa, list) and isinstance(lanc, list)
    assert isinstance(lista, list)
    assert miolo[0] <= miolo[1], f"o conteúdo da aba rola: {m}"
    assert caixa[0] <= lanc[0] and lanc[1] <= caixa[1], f"o «Lançadores» sai da vista: {m}"
    assert m["colunas"] == 2, m
    assert lista[1] <= TETO < lista[0], f"a lista não tem o teto e não rola por dentro: {m}"


def test_o_menu_com_as_permissoes_fica_dentro_da_lista(
        medida: dict[str, dict[str, list[int] | int]]) -> None:
    m = medida["1272-1"]
    menu, lista, rola = m["menu"], m["lista_caixa"], m["lista"]
    assert isinstance(menu, list) and isinstance(lista, list) and isinstance(rola, list)
    assert lista[0] <= menu[0] and menu[1] <= lista[1], f"o ⋮ aberto é cortado: {m}"
    assert rola[0] <= rola[1], m


def test_a_linha_nao_tem_mais_a_coluna_do_para() -> None:
    assert "para" not in exp.Extensao._fields
    linha = exp.extensao_html(exp.EXTENSOES[0])
    assert "ext-para" not in linha
    assert not re.search(r'class="ext-para"', DESENHO.read_text(encoding="utf-8"))


def test_a_barra_de_rolagem_da_lista_so_usa_cor_que_o_tema_troca() -> None:
    """A barra fina da lista pinta só com as fichas do `:root` da casa: uma ficha que o `topo.html`
    não define cai na cor crua do recuo, e o trilho fica escuro com o tema claro ligado.

    MORDIDA (executada em 21/10/2026): com o trilho em `var(--panel-2,#21222c)`, como nasceu,
    reprova."""
    raiz = (RAIZ / "src/hefesto_dualsense4unix/interface/topo.html").read_text(encoding="utf-8")
    definidas = set(re.findall(r"(--[\w-]+)\s*:", raiz.split(":root", 1)[1].split("}", 1)[0]))
    regras = re.findall(r"\.ext-lista(?:::-webkit-scrollbar[\w-]*)?\s*\{([^}]*)\}", exp.CSS)
    usadas = {f for r in regras for f in re.findall(r"var\((--[\w-]+)", r)}
    assert usadas, "a regra da lista que rola sumiu do CSS da Experimental"
    assert usadas <= definidas, f"ficha fora do :root da casa: {sorted(usadas - definidas)}"
    assert not any(re.search(r"#[0-9a-fA-F]{3,8}", r) for r in regras), regras
