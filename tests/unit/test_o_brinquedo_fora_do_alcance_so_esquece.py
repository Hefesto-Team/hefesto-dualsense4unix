"""O brinquedo pareado que está fora do alcance só esquece, como o controle desconectado na aba
Conexões (D-2810-OS-BRINQUEDOS-PAREADOS-FICAM-NA-LISTA).

A extensão 2.8.0 mantém na lista o brinquedo que o adaptador conhece e que não está anunciado,
«Procurando» enquanto volta e «Desligado» depois. O «Testar» nele era um botão morto: a ordem não
tem a quem chegar. Fora do alcance, só o «Esquecer» age, com a confirmação de sempre; o desligado
pela chave dele segue com as ações, e a chave da extensão desligada apaga todas.
"""
from __future__ import annotations

import re
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import desenho_da_experimental as exp


def _cartao(ap: dict[str, Any], *, desligada: bool = False,
            armada: tuple[str, ...] = ()) -> dict[str, str]:
    gestao = exp.Gestao("lovense", exp.APARELHOS_DO_DESENHO, {"aparelhos": [ap]},
                        armada=armada, desligada=desligada)
    html = exp.aparelhos_geridos_html(gestao)
    vivos = dict.fromkeys(re.findall(
        r'<button class="btn mj-acao[^"]*" data-gesto="[^"]+" data-v="lovense:([a-z]+):',
        html), "age")
    apagados = dict.fromkeys(
        r.lower() for r in re.findall(
            r'<span class="btn mj-acao apagado[^"]*" aria-disabled="true">.*?<span>([^<]+)</span>',
            html))
    return {**{a: "apagado" for a in apagados}, **vivos}


def _ap(estado: str, ligado: bool = True) -> dict[str, Any]:
    return {"id": "lush:0", "nome": "Lush", "estado": estado, "ligado": ligado, "forca": 0.0}


def test_o_brinquedo_ligado_testa_e_esquece() -> None:
    assert _cartao(_ap("ligado")) == {"testar": "age", "esquecer": "age"}


@pytest.mark.parametrize("estado", ["procurando", "desligado", "falhou"])
def test_fora_do_alcance_so_o_esquecer_age(estado: str) -> None:
    """Prova da D-2810-OS-BRINQUEDOS-PAREADOS-FICAM-NA-LISTA."""
    assert _cartao(_ap(estado)) == {"testar": "apagado", "esquecer": "age"}


def test_o_esquecer_fora_do_alcance_pede_o_segundo_clique() -> None:
    gestao = exp.Gestao("lovense", exp.APARELHOS_DO_DESENHO, {"aparelhos": [_ap("desligado")]},
                        armada=("esquecer", "lush:0"))
    assert exp.ROTULO_DE_CONFIRMAR in exp.aparelhos_geridos_html(gestao)


def test_o_desligado_pela_chave_dele_segue_com_as_acoes() -> None:
    assert _cartao(_ap("ligado", ligado=False)) == {"testar": "age", "esquecer": "age"}


def test_a_chave_da_extensao_desligada_apaga_tudo() -> None:
    assert _cartao(_ap("procurando"), desligada=True) == {"testar": "apagado",
                                                          "esquecer": "apagado"}
