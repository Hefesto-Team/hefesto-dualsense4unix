"""O cadeado da moldura nunca sai da janela (26/10/2026).

O-BOTAO-QUE-TRAVA-A-NAVEGACAO-DOS-CONTROLES-01. Medido na conferência, no piloto em lar de
mentira: com quatro controles na fita e o piso de 1212 px, o botão com rótulo («Travar
navegação») passava da janela; só com o cadeado, os quatro plásticos de nome mais longo
(«Galactic Purple», «Starlight Blue») ainda o empurravam 39 px para fora. A cura mora no
``topo.html``: o perfil ativo cede primeiro (``flex-shrink`` mil vezes maior), e depois o nome
do plástico nos chips, com reticências.

MORDIDAS (26/10/2026, executadas aqui): tirar o ``.fita{min-width:0}`` da 01 reprova
``test_com_quatro_plasticos_longos_o_cadeado_fica_na_janela``; tirar o ``flex-shrink:1000`` do
perfil ativo reprova ``test_o_nome_longo_do_perfil_corta_o_dele_e_nao_o_dos_controles``.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("abre a página num WebKit")

import json
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import onde
from tests.unit.test_as_telas_de_16_10_no_webkit import _no_webkit

MEDIR = r"""
(function(PLASTICOS, PERFIL, LARGA){
  if (LARGA) {
    const t = document.createElement('style'); t.textContent = LARGA; document.head.appendChild(t);
  }
  const f = document.querySelector('.fita');
  const modelo = f.querySelector('.chip.plastico');
  f.querySelectorAll('.chip.plastico').forEach(c => c.remove());
  const pt = ' <span class="pt">•</span> ';
  PLASTICOS.forEach((p, i) => { const c = modelo.cloneNode(true);
    c.innerHTML = 'P' + (i + 1) + pt + p + pt + (i % 2 ? 'BT' : 'USB'); f.appendChild(c); });
  document.querySelector('.pa-nome').textContent = PERFIL;
  const b = document.querySelector('[data-gesto="travar-navegacao"]').getBoundingClientRect();
  const de = document.documentElement;
  const cortados = [...f.querySelectorAll('.chip.plastico')]
    .filter(c => c.scrollWidth > c.clientWidth).length;
  const nome = document.querySelector('.pa-nome');
  return JSON.stringify({direita: Math.round(b.right), largura: b.width, vista: de.clientWidth,
    rola: de.scrollWidth - de.clientWidth, cortados: cortados,
    perfil_corta: nome.scrollWidth > nome.clientWidth,
    entreletra: getComputedStyle(document.body).letterSpacing});
})(PLASTICOS_AQUI, PERFIL_AQUI, LARGA_AQUI)
"""


LETRA = {"comum": "", "larga": "*{letter-spacing:.5px !important}"}


def _medir(plasticos: list[str], perfil: str, letra: str) -> dict[str, Any]:
    uri = onde.pagina("01-jogar.html", publicado=False).as_uri()
    passo = (MEDIR.replace("PLASTICOS_AQUI", json.dumps(plasticos))
             .replace("PERFIL_AQUI", json.dumps(perfil))
             .replace("LARGA_AQUI", json.dumps(LETRA[letra])))
    lido: dict[str, Any] = _no_webkit(uri, (1212, 809), [passo])[0]
    if letra == "larga":
        assert lido["entreletra"] == "0.5px", f"a letra larga não pegou: {lido}"
    return lido


@pytest.mark.parametrize("letra", LETRA)
def test_com_quatro_plasticos_longos_o_cadeado_fica_na_janela(letra: str) -> None:
    lido = _medir(["Galactic Purple", "Starlight Blue"] * 2, "—", letra)
    assert lido["largura"] > 0, f"o cadeado não está na moldura: {lido}"
    assert lido["direita"] <= lido["vista"] and lido["rola"] <= 0, (
        f"com quatro controles de nome longo o cadeado saiu da janela: {lido}")


@pytest.mark.parametrize("letra", LETRA)
def test_o_nome_longo_do_perfil_corta_o_dele_e_nao_o_dos_controles(letra: str) -> None:
    """Quem cede é o nome do perfil, nunca o do controle, também com a letra de outro computador.

    A letra ``larga`` põe meio pixel a mais por letra em todo texto: é o que a pilha de texto do
    ubuntu-26.04 faz com a mesma Space Grotesk (cerca de +0,24 px por letra), com folga
    (O-CABECALHO-TEM-FOLGA-PARA-A-LETRA-DE-QUALQUER-COMPUTADOR-01).
    """
    lido = _medir(["DualSense"] * 4, "The Legend of Heroes: Trails through Daybreak", letra)
    assert lido["direita"] <= lido["vista"], f"o cadeado saiu da janela: {lido}"
    assert lido["perfil_corta"] and lido["cortados"] == 0, (
        f"o nome longo do perfil cortou o nome de um controle: {lido}")
