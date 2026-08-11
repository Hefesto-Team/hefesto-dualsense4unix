"""PARIDADE-BYTE-01 — o LED de jogador, por número de jogador, nos dois.

O padrão de LED de jogador é o que diz, na mesa dela, **quem é o Controle 1**.
Ele mora em common[43] e é autorizado pelo bit 0x10 do flag1 — e, como toda
feature deste projeto até 10/08/2026, era provado num transporte só.

Os quatro valores canônicos do `PlayerID` da pydualsense (4, 10, 21, 27) não são
um bitmask sequencial: são o desenho FÍSICO dos cinco LEDs da barra, com o
Player 1 no LED central. Um teste que só usasse `PLAYER_1` passaria com o byte
truncado; por isso os quatro estão aqui, mais o `ALL` (31).

MORDIDA PROVADA (11/08/2026, `src/` copiado para fora da árvore, `PYTHONPATH`
apontado para a cópia — a árvore de trabalho nunca foi mutada): zerando
`common[43]` só quando `conType == BT`, reprovam **7** casos da leva inteira —
os cinco `[bt]` daqui, o caso daqui que compara os dois lados, e o caso
equivalente do arquivo da lightbar, que compara o common INTEIRO e por isso
também pega. Os `[usb]` seguem verdes.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep

from tests.conftest import EnvelopeDeTransporte

#: Offset do padrão de player-LED dentro do common.
PLAYER_LED = 43

#: (nome do jogador, bitmask que o firmware entende). Os quatro canônicos do
#: `PlayerID` mais o `ALL` — nenhum deles é 1, 2 ou 3, o que é justamente o
#: ponto: um byte truncado ou deslocado não sobrevive a esta lista.
JOGADORES = [
    ("PLAYER_1", 4),
    ("PLAYER_2", 10),
    ("PLAYER_3", 21),
    ("PLAYER_4", 27),
    ("ALL", 31),
]


def _com_leds_do_hefesto(handle: Any) -> Any:
    """Tira a supressão de LED — a rota do report volta a ser a que vale.

    `_suppress_leds` nasce True em produção (LIGHTBAR-BT-ADOPT-01); quando o
    sysfs do kernel não é gravável, `_refresh_sysfs_leds` o desliga e o
    player-LED sai pelo report. É esse o estado que este arquivo mede, e ele
    está declarado aqui em vez de escondido numa fixture.
    """
    handle._suppress_leds = False
    return handle


@pytest.mark.parametrize(("jogador", "bitmask"), JOGADORES)
def test_o_padrao_do_jogador_sai_no_byte_certo_nos_dois(
    ds5_de_bancada: Any,
    transporte: EnvelopeDeTransporte,
    jogador: str,
    bitmask: int,
) -> None:
    """common[43] leva o padrão, no cabo E no rádio."""
    from pydualsense.enums import PlayerID

    handle = _com_leds_do_hefesto(ds5_de_bancada)
    handle.light.playerNumber = getattr(PlayerID, jogador)

    report = handle.prepareReport()
    assert transporte.problemas_do_envelope(report) == []
    common = transporte.extrair_common(report)

    assert common[PLAYER_LED] == bitmask, (
        f"{transporte.nome}: o {jogador} saiu {common[PLAYER_LED]:#04x} em "
        f"common[43], esperado {bitmask:#04x}"
    )
    assert common[1] & rep.VALID_FLAG1_PLAYER_INDICATOR_CONTROL_ENABLE, (
        f"{transporte.nome}: o padrão foi escrito sem o bit 0x10 do flag1"
    )


def test_o_padrao_do_jogador_e_identico_nos_dois_e_so_o_envelope_muda(
    transportes: tuple[EnvelopeDeTransporte, ...], fabrica_de_bancada: Any
) -> None:
    """O mesmo jogador pinta o mesmo padrão no cabo e no rádio."""
    from pydualsense.enums import PlayerID

    vistos: dict[str, int] = {}
    for envelope in transportes:
        handle = _com_leds_do_hefesto(fabrica_de_bancada(envelope))
        handle.light.playerNumber = PlayerID.PLAYER_3
        vistos[envelope.nome] = envelope.extrair_common(handle.prepareReport())[
            PLAYER_LED
        ]

    assert vistos["usb"] == 21, "o Player 3 não saiu no cabo"
    assert vistos["usb"] == vistos["bt"], (
        f"o padrão de jogador divergiu entre cabo e rádio: {vistos} — quem "
        "está na mesa vê números diferentes conforme o cabo estar plugado"
    )


def test_sob_supressao_o_player_led_nao_sai_em_nenhum_dos_dois(
    ds5_de_bancada: Any, transporte: EnvelopeDeTransporte
) -> None:
    """Com o kernel dono dos LED, nem o byte nem a autorização saem.

    LIGHTBAR-ISOLAR-OS-PLAYERS-01: com o instrumento ligado NENHUMA escrita de
    player-LED pode vazar, senão a numeração do co-op escreve por trás e a
    medição perde a variável única — e isso tem de valer nos dois transportes.
    """
    from pydualsense.enums import PlayerID

    ds5_de_bancada._suppress_leds = True
    ds5_de_bancada.light.playerNumber = PlayerID.PLAYER_4
    common = transporte.extrair_common(ds5_de_bancada.prepareReport())

    assert common[PLAYER_LED] == 0, (
        f"{transporte.nome}: o player-LED vazou sob supressão"
    )
    assert common[1] & rep.VALID_FLAG1_PLAYER_INDICATOR_CONTROL_ENABLE == 0
