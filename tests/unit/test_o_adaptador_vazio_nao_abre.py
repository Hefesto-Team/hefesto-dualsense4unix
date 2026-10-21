"""O adaptador sem nada dentro não abre (19/10/2026, a foto da aba Conexões).

A foto mostrava a «Direita» aberta, com a seta para baixo e uma faixa em branco no lugar dos
aparelhos. O adaptador vazio pinta a seta apagada e nunca ganha a classe ``aberto``, nem quando a
cena lembra que ele era o aberto.
"""

from __future__ import annotations

from typing import Any


from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08


def _cena(aparelhos: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "lugares": [{"id": "L1", "nome": "Meio"}, {"id": "L2", "nome": "Direita"}],
        "aparelhos": aparelhos,
        "aberto": "L2",
    }


def _classes(cartao: str) -> list[str]:
    return cartao.split('class="', 1)[1].split('"', 1)[0].split()


def test_o_adaptador_vazio_tem_a_seta_apagada_e_nao_abre() -> None:
    cena = _cena([])
    cartao = a08.html_do_lugar(cena["lugares"][1], cena)
    assert "aberto" not in _classes(cartao)
    assert 'aria-expanded="false"' in cartao
    assert " disabled>" in cartao
    assert a08.NADA_NO_ADAPTADOR in cartao


def test_o_adaptador_com_aparelho_continua_abrindo() -> None:
    cena = _cena([{"id": "S1", "tipo": "som", "nome": "Caixa", "lugar": "L2", "conectado": True}])
    cartao = a08.html_do_lugar(cena["lugares"][1], cena)
    assert "aberto" in _classes(cartao)
    assert " disabled>" not in cartao
