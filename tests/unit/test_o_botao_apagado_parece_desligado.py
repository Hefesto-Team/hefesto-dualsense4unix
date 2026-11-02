"""O botão apagado parece desligado: a letra dele nunca brilha mais que a do mesmo botão aceso.

O-BOTAO-APAGADO-NAO-TEM-A-LETRA-MAIS-CLARA-QUE-O-ACESO-01. A regra do apagado mora no `CSS_FOLHA`
de `monta.py` e vale para todo `.btn` e todo `.seg button` das dez abas. A regra pintava a letra do
apagado em `--fg` (#f8f8f2) e o `.btn` aceso escreve em `--texto-suave` (#c8ccda): o botão que
não pode agir ficava mais claro que o que pode, e a cara de desligado da
D-09S-BOTAO-SEM-TRABALHO saía invertida. Pela D-1610-O-CINZA-SAI-DA-LETRA, o apagado se
distingue pela opacidade, pela borda ou pelo peso, nunca por uma letra cinza.

A letra do apagado continua `--fg`, a mesma do `.seg button:disabled` (a gramática que
`test_o_botao_cinza_diz_a_razao.py` cobra), e a regra lhe dá `opacity:.45`: a letra e a borda
ficam mais fracas que as do aceso, inclusive no `.btn.vermelho`.

A régua abre o desenho de cada aba num WebKit, mede cada botão visível aceso, veste nele a classe
`apagado` (a mesma que o piloto veste) e mede de novo: o contraste efetivo da letra contra o
fundo (a cor com a opacidade, sobre o primeiro fundo opaco) tem de cair, e o botão tem de mudar
de opacidade, de borda ou de peso.

A MORDIDA (02/11/2026): tirar a `opacity:.45` do `.btn.apagado` do `CSS_FOLHA` e regerar as abas
reprova a letra em sete abas (01, 02, 05, 06, 07, 09 e 10) e a mudança em duas (05 e 09, o
Parar de regra local); a 08 já tinha opacidade na folha própria, e a 03 e a 04 não mostram botão.
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
    "09-sistema.html", "10-perfis.html",
]

COMUM = r"""
window.__apagado = window.__apagado || {
  vis: function(el){ const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; },
  rgba: function(s){ const m = s.match(/[\d.]+/g) || [0, 0, 0, 0];
    return [+m[0], +m[1], +m[2], m.length > 3 ? +m[3] : 1]; },
  lum: function(c){ const f = v => { v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); },
  fundo: function(el){
    for(let e = el; e; e = e.parentElement){
      const c = this.rgba(getComputedStyle(e).backgroundColor);
      if(c[3] >= 0.99) return c;
    }
    return this.rgba(getComputedStyle(document.body).backgroundColor);
  },
  opacidade: function(el){
    let o = 1;
    for(let e = el; e; e = e.parentElement) o *= +getComputedStyle(e).opacity;
    return o;
  },
  medir: function(el){
    const cs = getComputedStyle(el), letra = this.rgba(cs.color), f = this.fundo(el);
    const a = letra[3] * this.opacidade(el);
    const efetiva = [0, 1, 2].map(i => letra[i] * a + f[i] * (1 - a));
    const l1 = this.lum(efetiva), l2 = this.lum(f);
    return {contraste: (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05),
            cor: cs.color, opacidade: cs.opacity, borda: cs.borderTopColor,
            peso: cs.fontWeight};
  },
};
"""

ACESOS = COMUM + r"""
(function(){
  const fora = [];
  document.querySelectorAll('.btn, .seg button').forEach(function(el, i){
    if(el.classList.contains('apagado') || !window.__apagado.vis(el)) return;
    if(!(el.textContent || '').trim()) return;
    el.setAttribute('data-regua-apagado', String(i));
    fora.push(Object.assign({i: i, rotulo: el.textContent.trim().slice(0, 24),
                             classe: el.getAttribute('class')},
                            window.__apagado.medir(el)));
    el.classList.add('apagado');
  });
  return JSON.stringify(fora);
})()
"""

APAGADOS = COMUM + r"""
(function(){
  const fora = {};
  document.querySelectorAll('[data-regua-apagado]').forEach(function(el){
    fora[el.getAttribute('data-regua-apagado')] = window.__apagado.medir(el);
  });
  return JSON.stringify(fora);
})()
"""

_LIDO: dict[str, list[dict[str, Any]]] = {}


def _pares(aba: str) -> list[dict[str, Any]]:
    if aba not in _LIDO:
        uri = onde.pagina(aba, publicado=False).as_uri()
        acesos, apagados = _no_webkit(uri, (1212, 809), [ACESOS, APAGADOS])[-2:]
        assert isinstance(acesos, list) and isinstance(apagados, dict), (acesos, apagados)
        _LIDO[aba] = [dict(aceso, apagado=apagados[str(aceso["i"])]) for aceso in acesos]
    return _LIDO[aba]


@pytest.mark.parametrize("aba", PAGINAS)
def test_a_letra_do_apagado_nunca_brilha_mais_que_a_do_aceso(aba: str) -> None:
    """D-09S-BOTAO-SEM-TRABALHO e D-1610-O-CINZA-SAI-DA-LETRA: o apagado tem a letra mais fraca."""
    invertidos = [
        (par["rotulo"], round(par["contraste"], 2), round(par["apagado"]["contraste"], 2),
         par["cor"], par["apagado"]["cor"], par["apagado"]["opacidade"])
        for par in _pares(aba) if par["apagado"]["contraste"] >= par["contraste"]]
    assert not invertidos, (
        f"{aba}: botões cujo apagado tem a letra tão clara ou mais que o aceso "
        f"(rótulo, contraste aceso, contraste apagado, cor acesa, cor apagada, opacidade): "
        f"{invertidos}")


@pytest.mark.parametrize("aba", PAGINAS)
def test_o_apagado_muda_pela_opacidade_pela_borda_ou_pelo_peso(aba: str) -> None:
    """D-1610-O-CINZA-SAI-DA-LETRA: o apagado muda de opacidade, de borda ou de peso."""
    iguais = [par["rotulo"] for par in _pares(aba)
              if all(par[k] == par["apagado"][k] for k in ("opacidade", "borda", "peso"))]
    assert not iguais, f"{aba}: apagados sem opacidade, borda nem peso próprios: {iguais}"


def test_a_regua_mede_botoes_de_verdade() -> None:
    """A régua sem botão nenhum daria verde sobre o vazio: as abas de botão têm de aparecer."""
    com_botao = [aba for aba in PAGINAS if _pares(aba)]
    for aba in ("09-sistema.html", "10-perfis.html"):
        assert aba in com_botao, f"a régua não achou botão nenhum em {aba}: {com_botao}"
