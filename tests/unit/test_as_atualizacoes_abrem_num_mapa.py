"""A seção Atualizações da aba Sistema é só o botão do mapa, o «Atualizar sozinho» e o prazo.

AS-ATUALIZACOES-ABREM-NUM-MAPA-COMO-O-DAS-CONEXOES-01 (09/11/2026). A grade das peças saiu da aba:
as peças moram no mapa que o botão abre (``interface/atualizacoes.html_da_pergunta``).

A MORDIDA: a grade de volta na seção (uma linha de peça, ou a marca, ou as «Versões anteriores»)
reprova ``test_a_secao_e_so_o_botao`` nomeando o que sobrou; o próprio teste a prova com a grade
de antes enxertada (``test_a_regua_morde_a_grade_de_volta``).
"""
from __future__ import annotations

import re
from pathlib import Path

from hefesto_dualsense4unix.interface import aba09
from hefesto_dualsense4unix.interface import atualizacoes as tela

RAIZ = Path(__file__).resolve().parents[2]
GESTOS_DA_SECAO = {"atualizacoes-abrir", "atualizar-sozinho", "prazo-da-atualizacao"}
GRADE_DE_ANTES = ('<div class="at-grade"><div class="col-lista"><div class="saude">'
                  '<input type="checkbox" class="at-marca" data-gesto="peca-da-atualizacao" '
                  'data-v="proton"><span class="selo nova">NOVA</span><span class="txt">'
                  '<span>GE-Proton</span></span></div></div></div>')


def _secao(pagina: str) -> str:
    inicio = pagina.index('<div class="atualiza">')
    fim = pagina.index('<div class="sec-rot sr-log', inicio)
    return pagina[inicio:fim]


def o_que_sobra(pagina: str) -> list[str]:
    secao = _secao(pagina)
    sobra = sorted(set(re.findall(r'data-gesto="([^"]+)"', secao)) - GESTOS_DA_SECAO)
    abrir = secao.count('data-gesto="atualizacoes-abrir"')
    if abrir != 1:
        sobra.append(f"{abrir} botões do mapa")
    sobra += [classe for classe in ("saude", "at-grade", "at-marca", "selo")
              if re.search(rf'class="[^"]*\b{classe}\b', secao)]
    return sobra


def test_a_secao_e_so_o_botao() -> None:
    """D-0911-AS-ATUALIZACOES-ABREM-NUM-MAPA: a seção é o botão, o sozinho e o prazo."""
    for pagina in (aba09.MIOLO, (RAIZ / "mockup/09-sistema.html").read_text(encoding="utf-8")):
        assert o_que_sobra(pagina) == [], o_que_sobra(pagina)


def test_a_regua_morde_a_grade_de_volta() -> None:
    com_a_grade = aba09.MIOLO.replace(
        '<div class="sec-rot sr-log', GRADE_DE_ANTES + '<div class="sec-rot sr-log', 1)
    assert o_que_sobra(com_a_grade) == ["peca-da-atualizacao", "saude", "at-grade", "at-marca",
                                        "selo"]


def test_o_botao_leva_o_numero_do_que_ha_para_baixar() -> None:
    botao = re.search(r'<button class="btn at-mapa" data-gesto="atualizacoes-abrir">.*?</button>',
                      aba09.MIOLO, re.S)
    assert botao is not None
    assert "Atualizações" in botao.group(0) and 'data-campo="atualizacoes-novas"' in botao.group(0)
    assert aba09.NOVAS_DO_DESENHO == tela.quantas_novas(aba09.EXEMPLO_DAS_PECAS) == 3


def test_o_desenho_do_mapa_e_o_que_o_produto_pinta() -> None:
    desenho = (RAIZ / "mockup" / aba09.DESENHO_DO_MAPA).read_text(encoding="utf-8")
    corpo = tela.html_da_pergunta(aba09.EXEMPLO_DAS_PECAS, {"sozinho": False, "dias": 7},
                                  jogo_aberto=False)
    assert corpo in desenho
    assert '<span class="mp-v"><span class="nv">1.11.0</span></span>' in corpo
