"""A letra cinza saiu das abas, o respiro é igual e o «Perfil ativo» tem o tamanho do nome.

De 16/10/2026.

O pedido de 16/10 tem três itens da interface inteira que não tinham régua: o T1 (o bloco de
dentro não encosta na borda da direita), o T3 (*«Esse cinza some da interface se tratando de
fonte. Não usamos ele»*) e o T4 (o «Perfil ativo» do tamanho do nome do jogo, em branco).

Medido na conferência, com zero controles: a Jogar escrevia «P1 • Desconectado» e a Controles
«P1», «Microfone» e «Bateria» em `--linha` (#53576f), um terceiro cinza de letra que a troca de
`--comment` e `--texto-mudo` por `--fg` não alcançou. A Iluminação e a Vibração, no mesmo estado,
já escreviam o nome em branco. O lugar vazio se distingue pela palavra «Desconectado», pela borda
e pelo travessão; o travessão sozinho continua na cor da linha, porque é marca de ausência, não
letra.

A régua lê o mockup de cada aba num WebKit, onde o P3 e o P4 nascem vazios (na Jogar, quem os
esvazia é o piloto, pela classe `off`, e a régua faz o mesmo): toda letra ou algarismo visível em um
dos três cinzas reprova.

MORDIDA (16/10/2026): devolver `color:var(--linha)` ao `.cartao.off .rotulo` da `aba01.py` e
regerar a 01 reprova `test_nenhuma_letra_e_cinza[01-jogar.html]`; o mesmo no `.ctl.off .leia` da
`aba02.py` reprova `[02-controles.html]`. Trocar o `.miolo` do `topo.html` para
`padding:16px 3px 18px 18px` reprova o respiro, e o `.pa-rot` para `11px` em `--comment` reprova o
«Perfil ativo».
"""
from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("abre a página num WebKit")

from hefesto_dualsense4unix.interface import onde
from tests.unit.test_as_telas_de_16_10_no_webkit import _no_webkit

PAGINAS = [
    "01-jogar.html", "02-controles.html", "03-gatilhos.html", "04-iluminacao.html",
    "05-vibracao.html", "06-navegacao.html", "07-lancadores.html", "08-conexoes.html",
    "09-sistema.html", "10-perfis.html", "mapa-do-controle.html",
]

#: `--comment`, `--texto-mudo` e `--linha` do `topo.html`, como o WebKit os devolve.
CINZAS = ["rgb(136, 150, 196)", "rgb(154, 158, 184)", "rgb(83, 87, 111)"]

#: O que o piloto faz antes da medida, onde o mockup nasce com os lugares cheios.
#: Na Jogar, o piloto põe a classe `off` e escreve o travessão em cada campo do cartão vazio.
PREPARO = {"01-jogar.html": (
    "document.querySelectorAll('.cartao').forEach(c => { c.classList.add('off');"
    " c.querySelectorAll('[data-campo]')"
    ".forEach(e => { if (!e.children.length) e.textContent = '—'; });"
    " });")}

MEDIR = r"""
(function(CINZAS){
  %s
  const vis = el => { const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
  const letra = /[A-Za-zÀ-ÿ0-9]/;
  const cinzas = [];
  for (const el of document.querySelectorAll('body *')) {
    if (el.closest('svg, script, style')) continue;
    const texto = [...el.childNodes].filter(n => n.nodeType === 3)
      .map(n => n.textContent).join('').trim();
    if (!texto || !letra.test(texto) || !vis(el)) continue;
    const cor = getComputedStyle(el).color;
    if (CINZAS.includes(cor)) cinzas.push([texto.slice(0, 30), cor, el.getAttribute('class')]);
  }
  const m = document.querySelector('.miolo'), q = m && m.querySelector('.quadro');
  let respiro = null;
  if (m && q) { const a = m.getBoundingClientRect(), b = q.getBoundingClientRect();
    respiro = [Math.round(b.left - a.left), Math.round(a.right - b.right)]; }
  const pa = document.querySelector('.pa-rot'), pn = document.querySelector('.pa-nome');
  const perfil = pa && pn ? [getComputedStyle(pa).fontSize, getComputedStyle(pn).fontSize,
                             getComputedStyle(pa).color] : null;
  return JSON.stringify({cinzas, respiro, perfil});
})(%s)
"""

_LIDO: dict[str, dict[str, Any]] = {}


def _ler(aba: str) -> dict[str, Any]:
    import json

    if aba not in _LIDO:
        uri = onde.pagina(aba, publicado=False).as_uri()
        passo = MEDIR % (PREPARO.get(aba, ""), json.dumps(CINZAS))
        lido = _no_webkit(uri, (1212, 809), [passo])[0]
        assert isinstance(lido, dict), lido
        _LIDO[aba] = lido
    return _LIDO[aba]


@pytest.mark.parametrize("aba", PAGINAS)
def test_nenhuma_letra_e_cinza(aba: str) -> None:
    assert _ler(aba)["cinzas"] == []


@pytest.mark.parametrize("aba", [p for p in PAGINAS if p[:2].isdigit()])
def test_o_quadro_respira_igual_dos_dois_lados(aba: str) -> None:
    respiro = _ler(aba)["respiro"]
    assert respiro is not None, "a página perdeu o .miolo ou o .quadro"
    esquerda, direita = respiro
    assert esquerda == direita == 18, respiro


@pytest.mark.parametrize("aba", ["01-jogar.html", "06-navegacao.html", "09-sistema.html"])
def test_o_perfil_ativo_tem_o_tamanho_do_nome_e_e_branco(aba: str) -> None:
    perfil = _ler(aba)["perfil"]
    assert perfil is not None
    rotulo, nome, cor = perfil
    assert rotulo == nome
    assert cor == "rgb(248, 248, 242)"
