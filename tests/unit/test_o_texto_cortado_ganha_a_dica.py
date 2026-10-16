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
