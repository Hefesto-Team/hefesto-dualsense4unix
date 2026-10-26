"""A lista da janela «Configurar» não rola além do último controle.

A-LISTA-DA-JANELA-CONFIGURAR-NAO-ROLA-ALEM-DO-FIM-01 (26/10/2026). As telas das abas moram
empilhadas na mesma célula (a janela não muda de tamanho ao trocar de aba), e a rolagem da lista
herdava a altura da MAIOR delas: numa aba curta, a barra descia por um vazio depois do último
controle. A régua rola cada aba até o fim e mede a folga que sobra embaixo.

Medido antes: a lista tinha 605 px para toda aba (a da Força tem 176) e rolava 198 px em todas.
A cura faz da tela marcada a caixa que rola, com a mesma janela e a mesma tira de abas.

MORDIDAS (26/10/2026, executadas sobre a cura e devolvidas): a rolagem devolvida à lista
(``.ja-opcoes:has(> .mj-abas)`` arrancada) reprova a rolagem de cada aba e a aba que cabe; o
``overflow:auto`` tirado da tela reprova a aba que não cabe e precisa rolar; a tela com
``height:0`` reprova a altura da tela; o ``padding-right`` da tela arrancado reprova a barra que
cobre a borda dos controles.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    ctx,
    lar,
)
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import (  # noqa: F401
    VIVO,
    janela,
)
from tests.unit.test_a_lista_da_janela_configurar_nao_pula_ao_clicar_um_efeito import (
    ENDERECO,
    VISTAS,
)
from tests.unit.test_a_linha_sem_aparelho_fica_a_direita_do_parear import (  # noqa: F401
    SEM_APARELHOS,
    montada,
    no_webkit,
    pagina_fresca,
)

FOLGA_MAXIMA = 16
FOLGA_DA_BARRA = 8
ALTURA_MINIMA_DA_TELA = 150
QUANTAS_ABAS = 5

_ABRIR = """(function(endereco, h){
  location.hash = endereco;
  window.__hef.pintar({blocos: {'#mod-janela': h}});
  return document.querySelectorAll('#mod-janela .mj-abas > label').length;
})(%s, %s)"""
_ABA = """(function(n){
  const j = document.getElementById('mod-janela');
  j.querySelectorAll('.mj-abas > label')[n].click();
  const o = j.querySelector('.ja-opcoes');
  const tela = j.querySelectorAll('.mj-abas > .mj-tela')[n];
  const fundo = e => { let b = 0;
    for (const f of e.querySelectorAll('*')) { const r = f.getBoundingClientRect();
      if (r.width > 0 && r.height > 0 && r.bottom > b) b = r.bottom; } return b; };
  const direita = e => { let d = 0;
    for (const f of e.querySelectorAll('*')) { const r = f.getBoundingClientRect();
      if (r.width > 0 && r.height > 0 && r.right > d) d = r.right; } return d; };
  const rolam = [o, tela].filter(e => e.scrollHeight > e.clientHeight + 1);
  const caixa = rolam[0] || o;
  caixa.scrollTop = 0;
  const fim = fundo(tela) - o.getBoundingClientRect().top;
  caixa.scrollTop = caixa.scrollHeight;
  const r = caixa.getBoundingClientRect();
  const jr = j.getBoundingClientRect();
  const rotulo = j.querySelectorAll('.mj-abas > label')[n].getBoundingClientRect();
  return JSON.stringify({aba: j.querySelectorAll('.mj-abas > label')[n].textContent,
    visivel: caixa.clientHeight, total: caixa.scrollHeight, rolou: caixa.scrollTop,
    rola: rolam.length > 0, lado: tela.getBoundingClientRect().right - direita(tela),
    alta: tela.clientHeight,    folga: r.bottom - fundo(tela), fim: fim,
    janela: [Math.round(jr.top), Math.round(jr.bottom)], aba_y: Math.round(rotulo.top)});
})(%d)"""


@pytest.fixture
def abas(janela: Any, pagina_fresca: Any) -> dict[str, list[dict[str, Any]]]:  # noqa: F811
    from hefesto_dualsense4unix.interface import hefesto_vivo

    html = montada(janela, SEM_APARELHOS)
    casos = {}
    for w, h in VISTAS:
        passos: list[list[Any]] = [["js", hefesto_vivo.BOOTSTRAP],
                                   ["js", _ABRIR % (json.dumps(ENDERECO), json.dumps(html))],
                                   ["espera", 0.3]]
        for n in range(QUANTAS_ABAS):
            passos += [["js", _ABA % n], ["espera", 0.1]]
        casos[f"{w}x{h}"] = (w, h, passos)
    lidos = no_webkit(pagina_fresca, casos)
    saida = {}
    for caso, resultados in lidos.items():
        quantas = int(resultados[1])
        assert 3 <= quantas <= QUANTAS_ABAS, (caso, quantas)
        saida[caso] = [json.loads(x) for x in resultados[2:2 + quantas]]
    print(json.dumps(saida, ensure_ascii=False))
    return saida


def test_a_rolagem_de_cada_aba_acaba_no_ultimo_controle(
        abas: dict[str, list[dict[str, Any]]]) -> None:
    falhas = []
    for caso, lidas in abas.items():
        for a in lidas:
            if a["rola"] and a["folga"] > FOLGA_MAXIMA:
                falhas.append(f"{caso} · {a['aba']}: sobram {a['folga']:.0f} px depois do último "
                              f"controle (a lista tem {a['total']} px e mostra {a['visivel']})")
    assert not falhas, "\n".join(falhas)


def test_a_aba_que_cabe_nao_ganha_barra_de_rolagem(
        abas: dict[str, list[dict[str, Any]]]) -> None:
    falhas = [f"{caso} · {a['aba']}: rola {a['rolou']} px com o conteúdo cabendo"
              for caso, lidas in abas.items() for a in lidas
              if a["fim"] <= a["visivel"] and a["rola"]]
    assert not falhas, "\n".join(falhas)


def test_a_tela_de_cada_aba_tem_altura_para_mostrar_os_controles(
        abas: dict[str, list[dict[str, Any]]]) -> None:
    falhas = [f"{caso} · {a['aba']}: a tela tem {a['alta']} px de altura"
              for caso, lidas in abas.items() for a in lidas
              if a["alta"] < ALTURA_MINIMA_DA_TELA]
    assert not falhas, "\n".join(falhas)


def test_a_barra_de_rolagem_nao_cobre_a_borda_dos_controles(
        abas: dict[str, list[dict[str, Any]]]) -> None:
    falhas = [f"{caso} · {a['aba']}: o último controle chega a {a['lado']:.0f} px da borda "
              f"da tela, a barra (de {FOLGA_DA_BARRA} px) o cobre"
              for caso, lidas in abas.items() for a in lidas if a["lado"] < FOLGA_DA_BARRA]
    assert not falhas, "\n".join(falhas)


def test_a_janela_e_as_abas_ficam_no_mesmo_lugar_ao_trocar_de_aba(
        abas: dict[str, list[dict[str, Any]]]) -> None:
    falhas = []
    for caso, lidas in abas.items():
        caixas = {(a["janela"][0], a["janela"][1], a["aba_y"]) for a in lidas}
        if len(caixas) != 1:
            falhas.append(f"{caso}: a janela e a tira das abas mudam de lugar entre as abas: "
                          f"{[(a['aba'], a['janela'], a['aba_y']) for a in lidas]}")
    assert not falhas, "\n".join(falhas)


def test_a_aba_que_nao_cabe_rola_e_alcanca_o_ultimo_controle(
        abas: dict[str, list[dict[str, Any]]]) -> None:
    falhas = []
    for caso, lidas in abas.items():
        compridas = [a for a in lidas if a["fim"] > a["visivel"] + 1]
        if not compridas:
            falhas.append(f"{caso}: nenhuma aba excede a caixa; a régua não mede a rolagem")
        for a in compridas:
            if not a["rola"] or a["folga"] > FOLGA_MAXIMA or a["folga"] < -1:
                falhas.append(f"{caso} · {a['aba']}: não alcança o último controle "
                              f"(rola={a['rola']}, folga {a['folga']:.0f} px)")
    assert not falhas, "\n".join(falhas)
