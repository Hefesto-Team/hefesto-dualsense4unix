"""O ícone do cartão da 08 é de traço, como o resto da aba.

Sprint: O-ICONE-DO-CARTAO-DA-08-E-DE-TRACO-01.

Medido em 25/10/2026, no WebKit, no desenho da 08: o `svg.i` de todo cartão de dica saía com `fill`
preto e `stroke` `none`, e os símbolos do sprite (`rd-ajuda`, `rd-hub`…) são só de traço: o da ajuda
virava um disco preto, e o do hub, uma barra. A regra do cartão (`aba08.py`, `.cartao-dica .cd-ic
svg.i`) dava só o tamanho; `.radio .i` e `.ferramentas .i` davam o traço.

A régua pinta um cartão por símbolo que um cartão usa (tirado do módulo das dicas, não de uma lista
daqui) e confere o estilo COMPUTADO de cada `svg.i`: `fill` `none`, `stroke` na cor do `.cd-ic`, e
a espessura e as pontas de `.radio .i`.

TUDO É DE MENTIRA: a página num WebKit fora da tela, com o pintor do piloto; nada chega a daemon.

MORDIDA (25/10/2026): sem o `fill:none` na regra do cartão, a régua reprova com o nome de cada
símbolo; sem o `stroke:currentColor`, também.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import dicas_da_conexao as dicas
from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.conexoes import html_das_dicas
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08
from tests.conftest import skip_sem_gi_real
from tests.unit.test_a_conexoes_cabe_na_tela import (  # noqa: F401 -- a fixture de módulo vem junto
    _no_webkit,
    _pintar_as_dicas,
    um_webview_por_modulo,
)

RAIZ = Path(__file__).resolve().parents[2]
DESENHO = RAIZ / "mockup" / "08-conexoes.html"
PUBLICADA = onde.pagina("08-conexoes.html", publicado=True)
TAMANHO = (1280, 860)
_REGRA = re.compile(r"\.cartao-dica \.cd-ic svg\.i\{([^}]*)\}")


def _a_regra(pagina: Path) -> str:
    achada = _REGRA.search(pagina.read_text(encoding="utf-8"))
    return re.sub(r"\s+", "", achada.group(1)) if achada else ""


def _icones_dos_cartoes() -> list[str]:
    """Todo símbolo do sprite que um cartão desenha: as constantes `ICONE_*` do módulo das dicas,
    menos o pulso (um `span`, não SVG)."""
    nomes = {v for k, v in vars(dicas).items() if k.startswith("ICONE_") and isinstance(v, str)}
    nomes.discard(dicas.ICONE_PULSO)
    return sorted(nomes)


def _cartoes(icones: list[str]) -> str:
    acao = dicas.Acao(dicas.MAPA, dicas.ROTULO_VER_NO_MAPA, href=dicas.PAGINA_DO_MAPA)
    painel = dicas.montar([dicas.Dica(chave=f"ic-{i}", icone=i, titulo=i, nivel=dicas.AJUSTE,
                                      acao=acao) for i in icones])
    return html_das_dicas(painel, a08.icone_da_dica)


_LER = r"""(function(){
const ref = document.querySelector('.radio svg.i:not(.cheio)');
const cr = ref ? getComputedStyle(ref) : null;
return JSON.stringify({
  ref: cr ? {w: cr.strokeWidth, cap: cr.strokeLinecap, join: cr.strokeLinejoin} : null,
  icones: [...document.querySelectorAll('.cartao-dica .cd-ic svg.i')].map(s => {
    const c = getComputedStyle(s), u = s.querySelector('use');
    const nome = ((u && u.getAttribute('href')) || '').replace('#', '');
    return {nome, existe: !!document.getElementById(nome), fill: c.fill, stroke: c.stroke,
            cor: getComputedStyle(s.closest('.cd-ic')).color, w: c.strokeWidth,
            cap: c.strokeLinecap, join: c.strokeLinejoin};
  })});
})()"""


def _medir(pagina: Path) -> list[dict[str, Any]]:
    icones = _icones_dos_cartoes()
    assert len(icones) >= 4, icones
    passos = []
    for i in range(0, len(icones), dicas.CARTOES_VISIVEIS):
        passos += [_pintar_as_dicas(_cartoes(icones[i:i + dicas.CARTOES_VISIVEIS])), _LER]
    lidas = _no_webkit(pagina, TAMANHO, passos)
    vistos: list[dict[str, Any]] = []
    for leitura in lidas[1::2]:
        assert isinstance(leitura, dict), leitura
        assert leitura["ref"], "a régua perdeu a referência: nenhum `.radio svg.i` na página"
        vistos += [dict(ic, ref=leitura["ref"]) for ic in leitura["icones"]]
    # a régua não passa por vazio: todo símbolo de cartão foi pintado e lido
    assert sorted(ic["nome"] for ic in vistos) == [f"rd-{i}" for i in icones], vistos
    return vistos


def _defeitos(vistos: list[dict[str, Any]]) -> list[str]:
    defeitos = []
    for ic in vistos:
        nome, ref = ic["nome"], ic["ref"]
        if not ic["existe"]:
            defeitos.append(f"{nome}: o símbolo não está no sprite da página")
        if ic["fill"] != "none":
            defeitos.append(f"{nome}: fill {ic['fill']} (o símbolo é de traço)")
        if ic["stroke"] != ic["cor"]:
            defeitos.append(f"{nome}: stroke {ic['stroke']}, a cor do ícone é {ic['cor']}")
        for k in ("w", "cap", "join"):
            if ic[k] != ref[k]:
                defeitos.append(f"{nome}: {k} {ic[k]}, o de `.radio .i` é {ref[k]}")
    return defeitos


def test_a_regra_do_cartao_da_o_traco_no_desenho() -> None:
    """Sem tela, o piso: a regra do ícone do cartão diz o traço no HTML do desenho."""
    regra = _a_regra(DESENHO)
    assert regra, "a regra `.cartao-dica .cd-ic svg.i` sumiu do desenho da 08"
    for pedaco in ("fill:none", "stroke:currentColor", "stroke-linecap:round",
                   "stroke-linejoin:round"):
        assert pedaco in regra, f"a regra do ícone do cartão não diz {pedaco}: {regra}"


@skip_sem_gi_real
def test_o_icone_de_todo_cartao_e_de_traco_no_desenho() -> None:
    defeitos = _defeitos(_medir(DESENHO))
    assert defeitos == [], "\n".join(defeitos)


@skip_sem_gi_real
def test_o_icone_de_todo_cartao_e_de_traco_na_pagina_publicada() -> None:
    if "fill:none" not in _a_regra(PUBLICADA):
        pytest.skip("o publicado da 08 ainda é o de antes; o `--publicar` é da costura")
    defeitos = _defeitos(_medir(PUBLICADA))
    assert defeitos == [], "\n".join(defeitos)


def test_o_pintor_dos_cartoes_desenha_cada_simbolo_pelo_sprite() -> None:
    """O que a régua pinta é o que o produto pinta: `icone_da_dica` dá o `svg.i` do sprite."""
    html = _cartoes(_icones_dos_cartoes()[:dicas.CARTOES_VISIVEIS])
    assert html.count('<svg class="i" aria-hidden="true"><use href="#rd-') == \
        dicas.CARTOES_VISIVEIS, html
