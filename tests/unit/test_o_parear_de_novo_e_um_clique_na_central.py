"""O «Parear de Novo» é UM clique na central (O-CONTROLE-JA-PAREADO-...-01, o resto).

O roxo tinha par no quarto, a ponte o esqueceu e ele entra em PS + Create depois: o
clique dela chegou ANTES de a janela o ver. A central aceita a escolha e pareia o
endereço dela quando a janela o vir, e nenhum outro. O dublê do BlueZ é o de sempre
(``radio_de_mentira``): nunca o BlueZ dela.

MORDIDAS, uma por vez: o ``visto`` e o ``janela_aberta`` fora do ``if`` de
``_a_escolha_dela`` (a escolha antes de ver deixa de existir, ou vale em qualquer passo);
o ``_onde_esta`` tirado da condição (o «Mover» do que está no ar passa a valer escolha).
"""

from __future__ import annotations

from typing import Any

from hefesto_dualsense4unix.integrations import central_do_radio as cr
from tests.unit import radio_de_mentira as rm
from tests.unit.radio_de_mentira import AZUL, QUARTO, ROXO, SALA, VERDE, VERMELHO
from tests.unit import test_o_parear_espera_o_clique_dela as _base

#: as mesmas fixtures do dublê da escolha dela (o dono vivo e a central reais)
diario, relogio, mesa = _base.diario, _base.relogio, _base.mesa


def _o_roxo_com_par_velho_no_quarto() -> rm.RadioDeMentira:
    """O roxo pareado e fora do ar no quarto; o VERDE só anda por perto."""
    mundo = rm.RadioDeMentira()
    mundo.pareado(SALA, VERMELHO)
    mundo.pareado(SALA, AZUL)
    mundo.pareado(QUARTO, ROXO, conectado=False)
    mundo.fisicos[VERDE] = rm.Fisico(VERDE, rm.CLASSE_DE_CONTROLE)
    return mundo


def test_um_clique_esquece_e_o_roxo_pareia_quando_a_janela_o_ve(
        mesa: Any, relogio: rm.Relogio) -> None:
    """O gesto inteiro como a tela o faz: esquece o par velho, abre a busca (o
    «Conectar») e o clique no roxo vem aos 1,5 s, antes de ele anunciar (PS +
    Create aos 3 s). Um ``Pair``, no roxo, no quarto — e o verde, que também
    anuncia, fica sem."""
    mundo = _o_roxo_com_par_velho_no_quarto()
    mundo.esquecer_na_ponte(QUARTO, ROXO)
    _dono, central = mesa(mundo)
    respostas: list[cr.Movimento] = []
    relogio.agendar(1.5, lambda: respostas.append(central.comecar_a_mover(ROXO, QUARTO)))
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(VERDE))
    relogio.agendar(3.0, lambda: mundo.segurar_ps_create(ROXO))

    feito = central.conectar(QUARTO)

    (resposta,) = respostas
    assert resposta.motivo != cr.MOTIVO_OCUPADO
    assert (resposta.aparelho, resposta.passo) == (cr.CONECTANDO, cr.PASSO_GESTO)
    assert [c for c, _a in mundo.metodos("Pair")] == [rm.no_de(QUARTO, ROXO)]
    assert (feito.estado, feito.aparelho, feito.destino) == (cr.CHEGOU, ROXO, QUARTO)
    verde = mundo.objeto(QUARTO, VERDE)
    assert verde is None or verde.get("Paired") is False


def test_a_escolha_antes_de_ver_que_nunca_chega_nao_pareia_ninguem(
        mesa: Any, relogio: rm.Relogio) -> None:
    """Ela escolheu o roxo, mas ele nunca entra em PS + Create; o verde, de outra
    pessoa, entra aos 3 s. A janela vê o verde e NÃO o pareia: nenhum ``Pair``, e
    a janela acaba sem gesto."""
    mundo = _o_roxo_com_par_velho_no_quarto()
    mundo.esquecer_na_ponte(QUARTO, ROXO)
    _dono, central = mesa(mundo)
    relogio.agendar(1.5, lambda: central.comecar_a_mover(ROXO, QUARTO))
    relogio.agendar(3.0, lambda: mundo.segurar_ps_create(VERDE))

    feito = central.conectar(QUARTO)

    assert mundo.metodos("Pair") == []
    assert (feito.estado, feito.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_SEM_GESTO)


def test_o_que_esta_no_ar_noutro_adaptador_nao_e_escolha(
        mesa: Any, relogio: rm.Relogio) -> None:
    """O azul está no ar na sala: pedi-lo no quarto antes de a janela vê-lo é um
    «Mover», não uma escolha — segue ``ocupado`` (a mesma régua do ``ver``)."""
    mundo = _o_roxo_com_par_velho_no_quarto()
    _dono, central = mesa(mundo)
    respostas: list[cr.Movimento] = []
    relogio.agendar(1.5, lambda: respostas.append(central.comecar_a_mover(AZUL, QUARTO)))
    relogio.agendar(3.0, lambda: mundo.segurar_ps_create(VERDE))

    central.conectar(QUARTO)

    assert [r.motivo for r in respostas] == [cr.MOTIVO_OCUPADO]
    assert mundo.metodos("Pair") == []
    assert mundo.onde_esta(rm.uniq(AZUL)) == SALA

