"""A aba Toques cabe na janela sem rolagem.

A-TOQUES-CABE-NA-JANELA-SEM-ROLAGEM-01 (26/10/2026, D-2610-A-TOQUES-EM-TRES-COLUNAS). A lista com
glifo (``.tq-lista``) usa quantas colunas couberem, três na largura da bancada, com linhas de
30 px e a Força embaixo; nenhuma aba da janela rola, e nenhum seletor fica cortado.

MORDIDAS (26/10/2026, executadas sobre a cura e devolvidas):

- a lista de volta a duas colunas (``repeat(2,minmax(0,1fr))``) reprova
  ``test_nenhuma_aba_rola_e_nenhum_seletor_corta`` e ``test_a_bancada_tem_tres_colunas``;
- a linha de volta a 32 px reprova ``test_nenhuma_aba_rola_e_nenhum_seletor_corta``;
- a coluna mínima larga demais (``minmax(300px,1fr)``) reprova as duas.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest

from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    ctx,
    lar,
)
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import (  # noqa: F401
    VIVO,
    _Ponte,
    janela,
)
from tests.unit.test_a_linha_sem_aparelho_fica_a_direita_do_parear import (  # noqa: F401
    montada,
    no_webkit,
    pagina_fresca,
)
from tests.unit.test_a_lista_da_janela_configurar_nao_pula_ao_clicar_um_efeito import (
    ENDERECO,
    VISTAS,
)

BANCADA = (1212, 809)
LARGURAS = tuple(dict.fromkeys((*VISTAS, BANCADA)))

_ABRIR = """(function(endereco, h){
  location.hash = endereco;
  window.__hef.pintar({blocos: {'#mod-janela': h}});
  return document.getElementById('mod-janela') ? 'ok' : 'sem janela';
})(%s, %s)"""
_LER = """(function(){
  const j = document.getElementById('mod-janela'), lidos = {};
  for (const rot of j.querySelectorAll('.mj-abas > label')) {
  rot.click();
  const tela = rot.nextElementSibling;
  const colunas = [...tela.querySelectorAll('.tq-lista')].map(l =>
    new Set([...l.querySelectorAll('.tql')]
      .map(r => Math.round(r.getBoundingClientRect().left))).size);
  const altura = [...tela.querySelectorAll('.tql')].map(r => r.getBoundingClientRect().height);
  const cortados = [...tela.querySelectorAll('select')]
    .filter(s => s.scrollWidth > s.clientWidth + 1).map(s => s.dataset.v);
  const forca = tela.querySelector('#mod-op-forca_dos_toques');
  const listas = [...tela.querySelectorAll('.tq-lista')];
  const fundo = listas.length ? listas[listas.length - 1].getBoundingClientRect().bottom : 0;
  lidos[rot.textContent.trim()] = {sh: tela.scrollHeight, ch: tela.clientHeight, colunas, cortados,
    altura: [...new Set(altura)],
    forca_embaixo: forca ? forca.getBoundingClientRect().top >= fundo : null};
  }
  [...j.querySelectorAll('.mj-abas > label')].find(l => l.textContent.trim() === 'Toques').click();
  return JSON.stringify(lidos);
})()"""
_TERCEIRA = """(function(){
  const j = document.getElementById('mod-janela');
  const s = j.querySelector('[data-v="intiface:toques_dos_botoes:square"]');
  const linhas = [...s.closest('.tq-lista').querySelectorAll('.tql')];
  const xs = [...new Set(linhas.map(r => Math.round(r.getBoundingClientRect().left)))]
    .sort((a, b) => a - b);
  const r = s.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2;
  const esquerda = Math.round(s.closest('.tql').getBoundingClientRect().left);
  return JSON.stringify({coluna: xs.indexOf(esquerda),
    alcancavel: document.elementFromPoint(x, y) === s});
})()"""


@pytest.fixture
def medidas(janela: Any, pagina_fresca: pathlib.Path) -> dict[str, Any]:  # noqa: F811
    from hefesto_dualsense4unix.interface import hefesto_vivo

    html = montada(janela, VIVO)
    casos = {}
    for w, h in LARGURAS:
        casos[f"{w}x{h}"] = (w, h, [
            ["js", hefesto_vivo.BOOTSTRAP],
            ["js", _ABRIR % (json.dumps(ENDERECO), json.dumps(html))],
            ["espera", 0.3],
            ["js", _LER], ["js", _TERCEIRA]])
    lidos = no_webkit(pagina_fresca, casos)
    print(json.dumps(lidos, ensure_ascii=False))
    saida: dict[str, Any] = {}
    for caso, (_, abriu, abas, terceira) in lidos.items():
        assert abriu == "ok", (caso, abriu)
        saida[caso] = {"abas": json.loads(abas), "terceira": json.loads(terceira)}
    return saida


def test_nenhuma_aba_rola_e_nenhum_seletor_corta(medidas: dict[str, Any]) -> None:
    falhas = []
    for caso, medida in medidas.items():
        abas = medida["abas"]
        assert {"Brinquedos", "Toques", "Força", "Ligação"} <= set(abas), (caso, list(abas))
        for nome, lido in abas.items():
            if lido["sh"] > lido["ch"]:
                falhas.append(f"{caso} {nome}: rola ({lido['sh']} > {lido['ch']})")
            if lido["cortados"]:
                falhas.append(f"{caso} {nome}: seletores cortados {lido['cortados']}")
            if lido["altura"] and lido["altura"] != [30]:
                falhas.append(f"{caso} {nome}: linhas de {lido['altura']} px, não 30")
        if abas["Toques"].get("forca_embaixo") is not True:
            falhas.append(f"{caso}: a Força não está embaixo da lista")
    assert not falhas, "\n".join(falhas)


def test_a_bancada_tem_tres_colunas(medidas: dict[str, Any]) -> None:
    """Prova da D-2610-A-TOQUES-EM-TRES-COLUNAS."""
    for caso, medida in medidas.items():
        colunas = medida["abas"]["Toques"]["colunas"]
        assert colunas and min(colunas) >= 3, f"{caso}: colunas {colunas}"
    assert medidas["{}x{}".format(*BANCADA)]["abas"]["Toques"]["colunas"][0] == 3


def test_o_seletor_da_terceira_coluna_se_alcanca(medidas: dict[str, Any]) -> None:
    """O quadrado é o terceiro botão: na bancada ele mora na terceira coluna e o clique o acha."""
    terceira = medidas["{}x{}".format(*BANCADA)]["terceira"]
    assert terceira == {"coluna": 2, "alcancavel": True}, terceira
