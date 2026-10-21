"""O cartão do controle na aba Conexões sem o botão «A luz não acende».

O botão saiu em 19/10/2026, a pedido (D-1910-A-LUZ-NAO-ACENDE-SAI), e com ele a espera pelo PS, o
gesto `luz-nao-acende` e os quatro campos `luz-*`. A conta de slots tinha saído em 23/09/2026
(TRANSPLANTE-DA-SECAO-01) e a régua da conta mora aqui desde então.

MORDE: devolva o botão ao `aba08._gc_item` (ou o gesto ao pacote) e a régua reprova.
"""

from __future__ import annotations

import pytest


from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes, camada

CAMPOS_QUE_SAIRAM = ("luz-trava", "luz-dica", "luz-texto", "luz-espera")


@pytest.mark.parametrize("onde_le", ["mockup", "publicado"])
def test_a_pagina_nao_tem_o_botao_da_luz(onde_le: str) -> None:
    pagina = onde.pagina("08-conexoes.html", publicado=onde_le == "publicado").read_text(
        encoding="utf-8")
    assert 'data-gesto="luz-nao-acende"' not in pagina, (
        f"o botão «A luz não acende» voltou ao cartão ({onde_le})")
    assert "A luz não acende" not in pagina
    for campo in CAMPOS_QUE_SAIRAM:
        assert f'data-campo="{campo}"' not in pagina, (
            f"o campo `{campo}` voltou à página ({onde_le}) sem botão que o use")


def test_o_gesto_e_a_espera_sairam_do_pacote() -> None:
    """D-1910-A-LUZ-NAO-ACENDE-SAI: o gesto e a espera pelo PS saíram com o botão."""
    assert not hasattr(a08_conexoes, "luz_nao_acende")
    assert not hasattr(a08_conexoes, "comecar_a_espera")
    assert ("08-conexoes.html", "luz-nao-acende") not in camada.CAMADA


def test_a_conta_de_slots_saiu_com_o_endereco() -> None:
    """A função e o endereço saíram JUNTOS — nenhum dos dois ficou órfão."""
    assert not hasattr(a08_conexoes, "_conta_de_slots")
    pagina = onde.pagina("08-conexoes.html", publicado=True).read_text(encoding="utf-8")
    assert 'data-campo="conta-de-slots"' not in pagina, (
        "a página voltou a ter `conta-de-slots`, e o pacote não escreve mais nele")
