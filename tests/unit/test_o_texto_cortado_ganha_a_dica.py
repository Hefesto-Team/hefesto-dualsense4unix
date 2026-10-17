"""O texto que a reticência corta ganha a dica com ele inteiro, no WebKit (16/10/2026).

Medido na conferência das telas de 16/10: a nota «Você está em "Controlar o PC", mas o mou…» do
Status da Sistema cortava sem dica, e o fim da frase não se lia em lugar nenhum. A cura é da base
comum (`base-comum.js`): na passagem do ponteiro, o elemento com `text-overflow:ellipsis` que corta
ganha o `data-dica` com o texto todo, e o perde quando deixa de cortar; a dica própria fica.

MORDIDA (16/10/2026): arrancar o ouvinte de `mousemove` do «texto cortado» da `base-comum.js` e
regerar a 09 reprova `test_a_nota_cortada_do_status_ganha_a_dica`.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("abre a página num WebKit")

from hefesto_dualsense4unix.interface import onde
from tests.unit.test_as_telas_de_16_10_no_webkit import _no_webkit

LONGA = ('Você está em "Controlar o PC", mas o mouse do controle está desligado; '
         'ligue-o na aba Navegação')

MEDIR = r"""
(function(LONGA){
  const el = document.querySelector('.saude .txt span:last-child');
  const passar = () => el.dispatchEvent(new MouseEvent('mousemove', {bubbles: true}));
  el.textContent = LONGA; passar();
  const cortada = [el.scrollWidth > el.clientWidth, el.getAttribute('data-dica')];
  el.textContent = 'Curta'; passar();
  const curta = el.hasAttribute('data-dica');
  el.textContent = LONGA; el.setAttribute('data-dica', 'Própria'); passar();
  const dona = el.getAttribute('data-dica');
  return JSON.stringify({cortada, curta, dona});
})(%s)
"""


def test_a_nota_cortada_do_status_ganha_a_dica() -> None:
    import json

    uri = onde.pagina("09-sistema.html", publicado=False).as_uri()
    lido = _no_webkit(uri, (1212, 809), [MEDIR % json.dumps(LONGA)])[0]
    assert lido["cortada"] == [True, LONGA], f"a nota cortada ficou sem a dica inteira: {lido}"
    assert lido["curta"] is False, f"a nota que cabe guardou a dica do corte: {lido}"
    assert lido["dona"] == "Própria", f"a regra do corte trocou a dica própria: {lido}"


TOPO = r"""
(function(NOME){
  const f = document.querySelector('.fita');
  const modelo = f.querySelector('.chip.plastico');
  f.querySelectorAll('.chip.plastico').forEach(c => c.remove());
  ['USB', 'BT', 'USB', 'BT'].forEach((v, i) => { const c = modelo.cloneNode(true);
    const pt = ' <span class="pt">•</span> ';
    c.innerHTML = 'P' + (i + 1) + pt + 'DualSense' + pt + v;
    f.appendChild(c); });
  const caixa = document.querySelector('.perfil-ativo');
  const nome = document.querySelector('.pa-nome');
  const linhas = el => { const r = document.createRange(); r.selectNodeContents(el);
    return new Set([...r.getClientRects()].map(x => Math.round(x.top))).size; };
  nome.textContent = '—';
  const vazio = Math.round(caixa.getBoundingClientRect().height);
  nome.textContent = NOME;
  nome.dispatchEvent(new MouseEvent('mousemove', {bubbles: true}));
  return JSON.stringify({vazio, h: Math.round(caixa.getBoundingClientRect().height),
    rotulo: linhas(document.querySelector('.pa-rot')), nome: linhas(nome),
    corta: nome.scrollWidth > nome.clientWidth, dica: nome.getAttribute('data-dica')});
})(%s)
"""


def test_o_perfil_ativo_fica_numa_linha_com_quatro_controles_e_nome_longo() -> None:
    """MORDIDA (16/10/2026): tirar o `white-space:nowrap` do `.pa-rot` e do `.pa-nome` no
    `topo.html` e regerar a 01 quebra o «Perfil ativo» em duas linhas e estica o topo."""
    import json

    nome = "The Legend of Heroes: Trails through Daybreak"
    uri = onde.pagina("01-jogar.html", publicado=False).as_uri()
    lido = _no_webkit(uri, (1212, 809), [TOPO % json.dumps(nome)])[0]
    assert lido["rotulo"] == 1 and lido["nome"] == 1, f"o «Perfil ativo» quebrou: {lido}"
    assert lido["h"] == lido["vazio"], f"o nome do perfil esticou o topo: {lido}"
    assert lido["corta"] and lido["dica"] == nome, f"o nome cortado ficou sem a dica: {lido}"
