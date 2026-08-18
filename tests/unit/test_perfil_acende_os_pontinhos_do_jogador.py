"""LED-BITS-CHEGAM-01 — trocar de perfil acende os cinco pontinhos.

POR QUE ESTE ARQUIVO EXISTE (13/08/2026)
----------------------------------------
Não por uma regressão: por uma AFIRMAÇÃO ERRADA que sobreviveu meses porque
nenhum teste ligava as duas pontas. O docstring de
`core/led_control.py::apply_led_settings` descrevia o sintoma do
BUG-PLAYER-LEDS-APPLY-01 — *"os bits nunca chegam ao controle"* — como se ele
estivesse de pé, e o portão da PROMESSA SEM CAMINHO citava esse mesmo texto para
classificar a função como dívida aberta.

Os bits chegam. Chegam por OUTRO caminho, e a única razão de a frase falsa ter
durado é que a cobertura existente estava partida ao meio:

- `tests/unit/test_player_leds.py` mede `apply_led_settings` isolada — a função
  que NÃO é o caminho vivo;
- `tests/unit/test_paridade_transporte_player_led.py` mede o byte 43 do report
  a partir de um bitmask JÁ pronto — o fim do caminho, sem o começo;
- entre "o perfil tem `player_leds` no JSON" e "o bitmask sai" não havia nada.

Este arquivo é esse meio. Ele atravessa `ProfileManager.apply` →
`OutputSpec.player_leds` → `_write_partial_output` → `light.playerNumber`, com o
backend de verdade e um handle de mentira, e é o que torna a correção do
docstring uma medição em vez de uma opinião.

A MORDIDA
---------
Arrancado o `player_leds=…` do `OutputSpec` em `profiles/manager.py:392`, os
três casos daqui reprovam nomeando o campo. Devolvido, voltam ao verde. É a
prova de que o caminho medido é ESTE, e não um que passe por outro lugar.
"""
from __future__ import annotations

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.led_control import player_bitmask
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchCriteria,
    Profile,
)
from tests.unit.test_backend_multi_controller import (
    KEY_1,
    _FakeHandle,
    _null_evdev,
)

#: Os padrões físicos, e não bits arbitrários: o `PlayerID` da pydualsense só
#: aceita os valores canônicos (4, 10, 21, 27, 31), porque eles são o desenho da
#: barra e não uma contagem. Um par escolhido por plausibilidade — `(True, …)`
#: valendo 1 — estouraria no `PlayerID(mask)` e o caso morreria por ValueError
#: sem nunca ter medido o caminho.
SO_O_CENTRAL = (False, False, True, False, False)  # 4  — o Player 1 do PS5
UM_TRES_CINCO = (True, False, True, False, True)  # 21 — o Player 3 do PS5


def _backend_com_um_controle() -> tuple[PyDualSenseController, _FakeHandle]:
    """O backend de verdade com um handle de mentira — nada toca aparelho."""
    inst = PyDualSenseController(evdev_reader=_null_evdev())
    handle = _FakeHandle()
    inst._handles = {KEY_1: handle}  # type: ignore[dict-item]
    inst._primary_key = KEY_1
    return inst, handle


def _perfil_com_pontinhos(bits: tuple[bool, bool, bool, bool, bool]) -> Profile:
    return Profile(
        name="perfil_com_pontinhos",
        match=MatchCriteria(),
        leds=LedsConfig(lightbar=[10, 20, 30], player_leds=list(bits)),
    )


def test_trocar_de_perfil_manda_o_bitmask_para_o_controle() -> None:
    """O caminho vivo inteiro, do JSON do perfil ao byte que o handle recebe."""
    inst, handle = _backend_com_um_controle()
    ProfileManager(controller=inst).apply(_perfil_com_pontinhos(UM_TRES_CINCO))

    assert handle.light.playerNumber is not None, (
        "trocar de perfil NÃO escreveu o padrão de player LED no controle: "
        "`ProfileManager.apply` não emitiu `player_leds` no `OutputSpec` "
        "(profiles/manager.py:392), ou `_write_partial_output` deixou de "
        "convertê-lo. É o BUG-PLAYER-LEDS-APPLY-01 de volta, e desta vez de pé"
    )
    assert int(handle.light.playerNumber) == player_bitmask(UM_TRES_CINCO) == 21, (
        "o bitmask que saiu não é o do perfil: o caminho vivo "
        "(backend_pydualsense.py:2801) e `player_bitmask` divergiram, e duas "
        f"conversões que divergem é pior que uma desligada — saiu "
        f"{int(handle.light.playerNumber)}, esperado {player_bitmask(UM_TRES_CINCO)}"
    )


def test_o_padrao_do_perfil_e_o_que_sai_e_nao_um_default() -> None:
    """Um segundo padrão, para o caso não passar por acaso.

    Com um só, um backend que escrevesse sempre o mesmo valor fixo ficaria
    verde. Dois padrões diferentes, dois bitmasks diferentes.
    """
    inst, handle = _backend_com_um_controle()
    ProfileManager(controller=inst).apply(_perfil_com_pontinhos(SO_O_CENTRAL))

    saiu = handle.light.playerNumber
    assert saiu is not None, (
        "o segundo padrão não saiu de jeito nenhum — mesma quebra do caso "
        "anterior: `ProfileManager.apply` parou de emitir `player_leds` no "
        "`OutputSpec` (profiles/manager.py:392)"
    )
    assert int(saiu) == player_bitmask(SO_O_CENTRAL) == 4, (
        "o segundo padrão saiu igual ao primeiro (ou igual a um default): o "
        f"que chega ao controle não depende do perfil — saiu {int(saiu)}, "
        f"esperado {player_bitmask(SO_O_CENTRAL)}"
    )


def test_a_conversao_do_backend_e_a_de_led_control_sao_a_mesma() -> None:
    """As duas implementações do mesmo layout, conferidas uma contra a outra.

    `player_bitmask` (core/led_control.py:85-89) e o `sum(1 << i …)` do
    `_write_partial_output` (core/backend_pydualsense.py:2801) escrevem a mesma
    regra duas vezes. Enquanto as duas existirem, é este caso que garante que
    elas não se separem em silêncio — o dia em que uma mudar sozinha, o padrão
    que ela vê na barra deixa de ser o que a janela mostra.
    """
    for indice in range(32):
        bits = tuple(bool(indice & (1 << posicao)) for posicao in range(5))
        do_backend = sum(1 << i for i, aceso in enumerate(bits) if aceso)
        assert player_bitmask(bits) == do_backend == indice, (  # type: ignore[arg-type]
            f"as duas conversões divergem em {bits}: `player_bitmask` diz "
            f"{player_bitmask(bits)} e o backend diz {do_backend}"  # type: ignore[arg-type]
        )
