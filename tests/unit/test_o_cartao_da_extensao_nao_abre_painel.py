"""O cartão da extensão não abre painel: as três ações só no ⋮.

Sprint O-CARTAO-DA-EXTENSAO-NAO-ABRE-PAINEL-01.

Medido em 24/10/2026 no piloto (WebKitGTK, lar de mentira, oito extensões, o «Tema claro» com aviso
e permissão por aceitar): o primeiro clique na chave «Desligada» abria o ⋮ da linha dentro do
cartão, com «Atualizar», «Ver permissões», «Remover» e o pedido; o cartão ia de 52 para 159 px, o
vizinho da fileira ia junto, e a lista rolava (333 > 289). A causa: a chave armava o «sim» abrindo o
menu (`_MEXIDA.menu`), e o menu com as permissões entrava no fluxo do cartão (`position:static`).

A cura: o primeiro clique só arma a chave («Aceitar e ligar», o pedido na dica), e o ⋮ com as
permissões flutua fora da lista, posto pelo `comportamento.js` junto do ⋮.

A sonda abre o desenho num WebKit de verdade, sob a tela de mentira, nas duas vistas, e põe as
linhas como o produto põe (o `innerHTML` de `.ext-lista`, das mesmas funções do desenho).

MORDIDA (executada em 24/10/2026): com o `_MEXIDA.menu = _MEXIDA.permissoes = mod_id` de volta no
primeiro clique da chave, `test_o_primeiro_clique_na_chave_so_arma_sem_abrir_o_menu` reprova; com a
regra `position:static` de volta no CSS (e o desenho regerado),
`test_o_mais_com_as_permissoes_nao_estica_a_fileira` reprova nas quatro medidas (o cartão com
159 px); sem o `oMenuNoLugar` do `comportamento.js`, ela reprova nas quatro pelo ⋮ fora da janela.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest

from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    _a07,
    _entrada,
    _fonte,
    _instalar,
    _Ponte,
    ctx,
    lar,
)

RAIZ = pathlib.Path(__file__).resolve().parents[2]
DESENHO = RAIZ / "mockup" / "07-lancadores.html"
#: A janela maximizada no monitor do usuário e o piso da janela.
VISTAS = ((1918, 840), (1212, 809))
_AVISO = "Extensão independente: troca as cores da interface. Não roda programa nenhum."
_PERMISSAO = "Acrescentar um lançador de jogos e abrir os jogos que ele lista."


def test_o_primeiro_clique_na_chave_so_arma_sem_abrir_o_menu(lar, ctx, tmp_path) -> None:  # noqa: F811
    """A chave armada diz «Aceitar e ligar», com o aviso e as permissões na dica; nada abre."""
    a07 = _a07()
    _instalar(a07, ctx, _fonte(tmp_path, permissoes=("rede:local",), extra={"aviso": _AVISO}))
    primeiro = a07.ligar_modificacao(ctx, {"v": "toque"}, _Ponte())
    lista = primeiro["blocos"][".ext-lista"]
    assert primeiro.get("armou") is True and _entrada(lar, "toque").ligada is False
    assert 'class="ext-menu' not in lista, "o clique na chave abriu o ⋮ dentro do cartão"
    assert "Ver permissões" not in lista and "ext-perm" not in lista
    assert exp.ROTULO_DO_SIM in lista and 'class="nj-tog pede"' in lista
    dica = lista.split('class="nj-tog pede"', 1)[1].split('data-dica="', 1)[1].split('"', 1)[0]
    assert dica.index(_AVISO) < dica.index("Usar a rede desta casa"), dica
    segundo = a07.ligar_modificacao(ctx, {"v": "toque"}, _Ponte())
    assert segundo["recado"] == "Toque ligada." and _entrada(lar, "toque").ligada is True
    assert exp.ROTULO_DO_SIM not in segundo["blocos"][".ext-lista"]


def test_o_mais_continua_com_as_tres_acoes(lar, ctx, tmp_path) -> None:  # noqa: F811
    """O ⋮ é o lugar das três; «Ver permissões» mostra a lista nele."""
    a07 = _a07()
    _instalar(a07, ctx, _fonte(tmp_path, permissoes=("rede:local",)))
    aberto = a07.mais_da_modificacao(ctx, {"v": "toque"}, _Ponte())["blocos"][".ext-lista"]
    for rotulo in ("Atualizar", "Ver permissões", "Remover"):
        assert rotulo in aberto, rotulo
    pedido = {"v": "toque:permissoes"}  # noqa-acento: chave
    com = a07.mais_da_modificacao(ctx, pedido, _Ponte())["blocos"][".ext-lista"]
    assert 'class="ext-perm"' in com and "Usar a rede desta casa" in com


def test_a_chave_armada_e_do_desenho() -> None:
    """A chave com o pedido: a palavra do «sim» e a dica com o pedido inteiro."""
    ext = exp.Extensao("t", "Tema", "Muda as cores.", "#", ligada=False, pede="Usa a rede.")
    html = exp.extensao_html(ext)
    assert f'<span class="txt">{exp.ROTULO_DO_SIM}</span>' in html
    assert 'data-dica="Usa a rede."' in html
    assert "Desligada" in exp.extensao_html(ext._replace(pede=""))


def _extensoes(n: int, aberta: int) -> str:
    """``n`` cartões; o de índice ``aberta`` com o ⋮ aberto e as permissões, e o vizinho armado."""
    exts = []
    for i in range(n):
        menu = exp.menu_html(f"e{i}", [_AVISO, _PERMISSAO]) if i == aberta else ""
        exts.append(exp.Extensao(f"e{i}", f"Extensão {i + 1}", "Uma frase de extensão", "#",
                                 selo="Local", versao="1.0.0", menu=menu, ligada=i != aberta,
                                 pede=_AVISO if i == aberta else ""))
    return str(exp.extensoes_html(exts))


_SONDA = r"""
import json, pathlib, sys
from hefesto_dualsense4unix.utils.tela_de_mentira import garantir_tela_de_mentira
garantir_tela_de_mentira(anunciar=False)
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk
from hefesto_dualsense4unix.interface.janela import PonteDaTela

PAGINA = pathlib.Path(sys.argv[1])
CASOS = json.loads(sys.stdin.read())
POR = "(function(h){ document.querySelector('.ext-lista').innerHTML = h; return 'ok'; })(%s)"
MEDIR = '''(function(){
  const lista = document.querySelector('.ext-lista');
  const menu = lista.querySelector('.ext-pop.aberto');
  const r = e => { const x = e.getBoundingClientRect();
    return [Math.round(x.left), Math.round(x.top), Math.round(x.right), Math.round(x.bottom)]; };
  return JSON.stringify({
    cartoes: [...lista.querySelectorAll('.ext')].map(
      e => Math.round(e.getBoundingClientRect().height)),
    lista: [lista.scrollHeight, lista.clientHeight], janela: [innerWidth, innerHeight],
    menu: menu ? r(menu) : null, posicao: menu ? getComputedStyle(menu).position : null,
    botoes: menu ? [...menu.querySelectorAll('.btn')].map(b => b.textContent.trim()) : []});
})()'''

def esperar(caixa, segundos):
    fim = GLib.get_monotonic_time() + int(segundos * 1_000_000)
    while "v" not in caixa and GLib.get_monotonic_time() < fim:
        Gtk.main_iteration_do(False)

saida = {}
for chave, (largura, altura, lista) in CASOS.items():
    ponte = PonteDaTela(folha=None)
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(largura, altura)
    janela.add(ponte.view)
    janela.show_all()
    ponte.view.load_uri(PAGINA.as_uri())
    esperar({}, 4)
    pos = {}
    ponte.perguntar(POR % json.dumps(lista), lambda v, e: pos.update(v=v, e=repr(e) if e else ""))
    esperar(pos, 8)
    esperar({}, 0.5)
    caixa = {}
    ponte.perguntar(MEDIR, lambda v, e: caixa.update(v=v, e=repr(e) if e else ""))
    esperar(caixa, 8)
    saida[chave] = json.loads(caixa["v"]) if caixa.get("v") else {"erro": caixa, "pos": pos}
    janela.destroy()
print(json.dumps(saida))
"""


@pytest.fixture(scope="module")
def medida() -> dict[str, dict]:
    casos = {}
    for w, h in VISTAS:
        # as oito dela, o ⋮ aberto na última fileira (o «Tema claro» da foto)
        casos[f"{w}x{h}-oito"] = (w, h, _extensoes(8, 7))
        # doze, a lista rola por dentro, o ⋮ aberto numa fileira do meio
        casos[f"{w}x{h}-doze"] = (w, h, _extensoes(12, 4))
    ambiente = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    filho = subprocess.run([sys.executable, "-c", _SONDA, str(DESENHO)], input=json.dumps(casos),
                           env=ambiente, capture_output=True, text=True, timeout=300)
    if filho.returncode != 0:
        pytest.skip(f"o WebKit não subiu na tela de mentira: {filho.stderr.strip()[-300:]}")
    return dict(json.loads(filho.stdout.strip().splitlines()[-1]))


@pytest.mark.parametrize("caso", [f"{w}x{h}-{n}" for w, h in VISTAS for n in ("oito", "doze")])
def test_o_mais_com_as_permissoes_nao_estica_a_fileira(medida: dict[str, dict], caso: str) -> None:
    """Todos os cartões com a mesma altura, a lista das oito sem rolar, o ⋮ inteiro na janela."""
    m = medida[caso]
    cartoes, menu, janela = m.get("cartoes"), m.get("menu"), m.get("janela")
    assert cartoes and menu and janela, f"a sonda não leu: {m}"
    assert max(cartoes) - min(cartoes) <= 1, f"o ⋮ aberto estica o cartão e o vizinho: {m}"
    if caso.endswith("oito"):
        assert m["lista"][0] <= m["lista"][1] + 1, f"o ⋮ aberto faz a lista rolar: {m}"
    assert m["posicao"] == "fixed", f"o ⋮ com as permissões entrou no fluxo do cartão: {m}"
    assert menu[0] >= 0 and menu[2] <= janela[0], f"o ⋮ sai da janela pelo lado: {m}"
    assert menu[1] >= 0 and menu[3] <= janela[1], f"o ⋮ sai da janela por cima ou por baixo: {m}"
    assert m["botoes"] == ["Atualizar", "Ver permissões", "Remover"], m
