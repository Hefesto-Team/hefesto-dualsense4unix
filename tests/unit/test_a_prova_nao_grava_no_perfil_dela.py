"""A prova botão a botão não pode gravar no perfil DELA.

O DEFEITO, MEDIDO EM 03/09/2026 e não deduzido: a leva que clicou as dez abas
deixou **dez gravações** em ``~/.config/hefesto-dualsense4unix/profiles/
meu_perfil.json``, entre 07:14 e 07:47 — uma por aba provada. O rodapé registra
o botão como ``@gesto("*", "salvar")``, um gesto só vivo nas dez páginas, e
``PERIGOSOS`` só sabia casar ``(página, gesto)``.

**Nada dela se perdeu naquela vez** — as dez foram re-salvamentos do mesmo
conteúdo, conferidos campo a campo contra o backup. Mas o caminho para perder
está nomeado no próprio pacote: desligar a barra de luz e salvar copia a cor
apagada por cima da que ela escolheu, e isso não se desfaz.

**A MORDIDA:** tire ``("*", "salvar")`` de :data:`hefesto_vivo.PERIGOSOS`, ou
tire o ramo do coringa de :func:`regua_do_mockup._alvos_a_clicar`, e o primeiro
teste reprova. As duas metades são uma cura só: a lista sem o casamento não
alcança as dez abas, e o casamento sem a lista não isenta ninguém.
"""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.interface import hefesto_vivo, regua_do_mockup

#: AS DEZ PÁGINAS, e a lista é literal de propósito: escrever
#: ``for n in range(1, 11)`` faria o teste passar numa árvore onde uma aba
#: sumiu do produto. O que se prova aqui é que o isento vale em TODA aba que
#: existe hoje, e uma aba nova entra aqui junto com o resto dela.
PAGINAS = (
    "01-jogar.html", "02-controles.html", "03-gatilhos.html",
    "04-iluminacao.html", "05-vibracao.html", "06-navegacao.html",
    "07-lancadores.html", "08-conexoes.html", "09-sistema.html",
    "10-perfis.html",
)


class _Gesto:
    """O mínimo que ``_alvos_a_clicar`` lê de um gesto da página."""

    def __init__(self, nome: str) -> None:
        self.nome = nome


# O nome do parâmetro abaixo é o de `_alvos_a_clicar`, não prosa.
@pytest.mark.parametrize("pagina", PAGINAS)  # (noqa-acento)
def test_o_salvar_fica_de_fora_em_toda_aba(pagina: str) -> None:
    """Em qualquer das dez, a prova pula o ``salvar`` em vez de clicá-lo."""
    vistos, pulados = regua_do_mockup._alvos_a_clicar(
        [_Gesto("salvar"), _Gesto("aplicar")], {"salvar", "aplicar"},
        pagina, hefesto_vivo.PERIGOSOS)
    assert "salvar" in pulados, (
        f"a prova clicaria `salvar` na {pagina} — e esse clique grava no "
        "perfil dela, sem diálogo e sem perguntar")
    assert "salvar" not in vistos


def test_o_coringa_nao_isenta_o_que_nao_pediu() -> None:
    """O ``("*", …)`` isenta o gesto NOMEADO, e nada mais.

    Uma isenção coringa que vazasse para os vizinhos apagaria a prova de botões
    inócuos — e a régua voltaria a dar verde sobre botão que nunca apertou, que
    é o defeito de 29/08/2026 que ela existe para não repetir.
    """
    vistos, pulados = regua_do_mockup._alvos_a_clicar(
        [_Gesto("aplicar"), _Gesto("exportar"), _Gesto("importar")],
        {"aplicar", "exportar", "importar"},
        "01-jogar.html", hefesto_vivo.PERIGOSOS)
    assert pulados == [], f"o coringa vazou para {pulados}"
    assert set(vistos) == {"aplicar", "exportar", "importar"}


def test_a_isencao_por_pagina_continua_valendo() -> None:
    """O casamento novo não pode ter apagado o velho.

    ``("06-navegacao.html", "modo")`` liga a emulação de mouse e MEXE NO CURSOR
    DELA; o mesmo ``modo`` nos Gatilhos é inócuo. Se o coringa tivesse
    substituído o casamento por página em vez de somar-se a ele, os dois
    passariam a ser tratados igual — e a escolha seria entre não provar o
    seguro ou estragar o trabalho dela.
    """
    _, pulados_nav = regua_do_mockup._alvos_a_clicar(
        [_Gesto("modo")], {"modo"}, "06-navegacao.html", hefesto_vivo.PERIGOSOS)
    vistos_gat, _ = regua_do_mockup._alvos_a_clicar(
        [_Gesto("modo")], {"modo"}, "03-gatilhos.html", hefesto_vivo.PERIGOSOS)
    assert pulados_nav == ["modo"], "a emulação de mouse deixou de ser isenta"
    assert vistos_gat == ["modo"], "o `modo` dos Gatilhos deixou de ser provado"


def test_incluir_perigosos_continua_alcancando_o_salvar() -> None:
    """Isento não é inalcançável — quem roda com ``--incluir-perigosos`` clica.

    É a outra metade do contrato de ``PERIGOSOS``, e sem ela a isenção viraria
    um botão que régua nenhuma cobre. O ``set()`` vazio é exatamente o que
    ``hefesto_vivo`` passa quando a flag está ligada.
    """
    vistos, pulados = regua_do_mockup._alvos_a_clicar(
        [_Gesto("salvar")], {"salvar"}, "10-perfis.html", set())
    assert vistos == ["salvar"] and pulados == []
