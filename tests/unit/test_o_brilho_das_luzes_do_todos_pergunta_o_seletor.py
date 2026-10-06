"""OS-PORTOES-QUE-NINGUEM-CHAMA-01: o «Todos» do brilho das luzes pergunta o seletor.

O `led.player_brightness_set` sem `uniq` escrevia em CADA controle conectado sem
perguntar ao backend para onde as escritas de saída vão. Os irmãos `led.set` e
`led.player_set` perguntam (`get_output_target_uniq` e `alvo_de_output_ausente`),
e a rota do brilho, nascida em 25/09, foi a única a escapar, porque o portão
`check_broadcast_proibido.py`, que a teria pego, não tinha chamador desde 25/08.

A cura: com o seletor mirando UM controle, o pedido sem `uniq` vai só nele; com o
alvo escolhido FORA da mesa, ninguém recebe nada e o valor fica guardado no override
dele (`guardado_em`); sem seletor, é o «Todos» de sempre. Vale nos dois transportes,
com e sem o nó de LED do kernel, de um a quatro controles.
"""
from __future__ import annotations

import pathlib
from typing import Any

import pytest

from tests.unit.test_o_brilho_das_luzes_de_numero import (
    FORTE,
    MACS,
    MATRIZ,
    UNIQS,
    _aplicar,
    _mesa,
    _o_aparelho_fica_em,
    _perfil,
    _servidor,
)


def _quadros(controles: list[Any]) -> list[int]:
    return [len(h.quadros) for h in controles]


@pytest.mark.asyncio
@pytest.mark.parametrize(("transporte", "com_no"), MATRIZ)
async def test_o_todos_com_o_seletor_num_controle_vai_so_nele(
        transporte: str, com_no: bool, tmp_path: pathlib.Path) -> None:
    """D-2409-AS-LUZES-DE-NUMERO-TEM-TRES-BRILHOS, no caminho do seletor global."""
    ctl, controles = _mesa(transporte, com_no=com_no)
    _aplicar(ctl, _perfil(None))
    ctl.set_output_target(1)
    antes = _quadros(controles)
    padrao_antes = ctl._desired_default.player_led_brightness
    resposta = await _servidor(ctl, tmp_path)._handle_led_player_brightness_set(
        {"brilho": "forte"})
    assert resposta["aplicado_em"] == [UNIQS[1]] and resposta["guardado_em"] == []
    assert _o_aparelho_fica_em(controles[1]) == FORTE
    for n in (0, 2, 3):
        assert len(controles[n].quadros) == antes[n], (
            f"o «Todos» com o seletor no P2 escreveu no P{n + 1}")
    assert ctl._desired_default.player_led_brightness == padrao_antes, (
        "o padrão de quem chegar depois não muda quando o pedido mira um controle só")


@pytest.mark.asyncio
@pytest.mark.parametrize(("transporte", "com_no"), MATRIZ)
async def test_o_todos_com_o_alvo_fora_da_mesa_nao_escreve_em_ninguem(
        transporte: str, com_no: bool, tmp_path: pathlib.Path) -> None:
    """O jogador ausente: os três presentes não recebem o pedido que era dele."""
    ctl, controles = _mesa(transporte, com_no=com_no)
    _aplicar(ctl, _perfil(None))
    ctl.set_output_target(1)
    ctl._handles.pop(MACS[1])
    presentes = [controles[n] for n in (0, 2, 3)]
    antes = _quadros(presentes)
    resposta = await _servidor(ctl, tmp_path)._handle_led_player_brightness_set(
        {"brilho": "forte"})
    assert resposta["aplicado_em"] == []
    assert resposta["guardado_em"] == [UNIQS[1]]
    assert _quadros(presentes) == antes, "o pedido do jogador ausente foi para os presentes"
    assert ctl._desired_by_uniq[UNIQS[1]].player_led_brightness == FORTE, (
        "o valor tem de ficar guardado no override do ausente, para quando ele voltar")


@pytest.mark.asyncio
@pytest.mark.parametrize(("transporte", "com_no"), MATRIZ)
async def test_sem_seletor_o_todos_continua_nos_quatro(
        transporte: str, com_no: bool, tmp_path: pathlib.Path) -> None:
    ctl, controles = _mesa(transporte, com_no=com_no)
    _aplicar(ctl, _perfil("fraco"))
    resposta = await _servidor(ctl, tmp_path)._handle_led_player_brightness_set(
        {"brilho": "forte"})
    assert sorted(resposta["aplicado_em"]) == sorted(UNIQS)
    assert [_o_aparelho_fica_em(h) for h in controles] == [FORTE] * 4
    assert ctl._desired_default.player_led_brightness == FORTE
