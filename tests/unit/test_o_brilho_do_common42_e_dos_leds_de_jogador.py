"""O `common[42]` é o brilho dos LEDS DE JOGADOR — e o produto manda ali o da BARRA.

MEDIDO POR ELA EM 09/09/2026, na bancada, com um DualSense no cabo e outro no
rádio, mexendo um controle deslizante e olhando o aparelho. Palavra dela:

    "o que o slicer altera não são as cores do lightbar mas os leds que indicam
    qual player é o dono daquele controle, tipo player 1...2 e tanto no cabo
    quanto bt eles tem o mesmo impacto e precisam da autorização do byte"

Até esse dia esta casa chamava o byte de *brilho da lightbar* — no comentário
de `ds_output_report.py`, na chave `luz.lightbar.brilho` do mapa e na sprint
BRILHO-DE-HARDWARE-01. A fonte externa já dizia o certo e ninguém tinha olhado:
`flag_2: SET_PLAYER_LED_BRIGHTNESS 0x01` (RPCS3 `.h:26-44`).

O QUE ESTE TESTE GUARDA
----------------------
A DÍVIDA FECHOU EM 24/09/2026 (O-BRILHO-DAS-LUZES-DE-NUMERO-01, decisão dela
`D-2409-AS-LUZES-DE-NUMERO-TEM-TRES-BRILHOS`): o `common[42]` ganhou campo
próprio — o degrau que o perfil escolheu para aquele controle
(`_brilho_das_luzes`), e não o `light.brightness` da pydualsense. A régua tem
DUAS metades, e a segunda é a que morde:

1. a constante do bit diz de qual LED ela é (o fato substituído fica escrito);
2. com o bit ligado, o byte é o do campo próprio — perguntado ao
   `_build_common`, e não ao texto do backend. Devolver o `light.brightness`
   como fonte reprova aqui, nomeando a dívida. O caminho inteiro, nos dois
   transportes, é de `test_o_brilho_das_luzes_de_numero.py`.

A prova do aparelho não mora num teste: mora em `docs/data/ensaios.csv`
(`painel-do-brilho-*-0909`), porque quem a produziu foi o olho dela.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[2]
REPORT = RAIZ / "src/hefesto_dualsense4unix/core/ds_output_report.py"


def _handle_sem_aparelho(*, led_gravavel: bool) -> Any:
    """Um handle da pydualsense sem device, nascido pelo `__init__` de produção.

    `led_gravavel` é o `_suppress_leds`: com o nó de LED do kernel gravável o
    fluxo é LED-neutro (no rádio, sempre).
    """
    from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

    from hefesto_dualsense4unix.core.backend_pydualsense import _PinnedPyDualSense

    h = _PinnedPyDualSense(b"/dev/hidraw-de-bancada", is_edge=False)
    h.audio, h.light = DSAudio(), DSLight()
    h.triggerL, h.triggerR = DSTrigger(), DSTrigger()
    h._suppress_leds = led_gravavel
    return h


def test_a_constante_diz_de_qual_led_ela_e() -> None:
    """O fato substituído fica escrito onde alguém vai lê-lo antes de usar."""
    fonte = REPORT.read_text(encoding="utf-8")
    trecho = fonte.split("VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE")[0][-1200:]
    assert "LEDS DE JOGADOR" in trecho.upper(), (
        "o comentário da VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE tem de dizer que o "
        "byte é dos LEDs de jogador. Ele dizia «BRILHO da lightbar» até 09/09/2026, e "
        "foi por isso que a chave do mapa nasceu com o dono errado."
    )
    assert "NÃO É O BRILHO DA LIGHTBAR" in trecho.upper(), (
        "o desmentido tem de estar junto da constante: quem lê o nome dela em inglês "
        "conclui «lightbar» sozinho, que foi o que esta casa fez por um mês."
    )


def test_a_constante_existe_e_e_o_bit_zero() -> None:
    """Régua que não acha o alvo dá verde sobre o vazio."""
    arvore = ast.parse(REPORT.read_text(encoding="utf-8"))
    valores = {
        alvo.id: no.value.value
        for no in ast.walk(arvore)
        if isinstance(no, ast.Assign) and isinstance(no.value, ast.Constant)
        for alvo in no.targets
        if isinstance(alvo, ast.Name)
    }
    assert valores.get("VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE") == 0x01
    assert valores.get("COMMON_VALID_FLAG2") == 38


def test_o_bit_fica_desligado_enquanto_a_fonte_do_valor_for_a_barra() -> None:
    """A METADE QUE MORDE — e desde 24/09/2026 ela pergunta ao PRODUTO.

    Ligar o bit mandando o `light.brightness` da pydualsense faz o produto
    atenuar as lâmpadas com um degrau que ninguém escolheu. O nome do caso
    ficou (o mapa o cita em `luz.lightbar.brilho`); o que ele cobra agora é que,
    com o bit ligado, o byte seja o do campo próprio — o `_brilho_das_luzes`,
    que o perfil escreve — e nunca o da pydualsense.

    MORDIDA (24/09/2026): devolva `common[42] = int(self.light.brightness.value)`
    ao `_build_common` e o degrau Forte (0) do campo sai como o Fraco (2) da
    pydualsense — reprova na segunda asserção.
    """
    from pydualsense.enums import Brightness

    from hefesto_dualsense4unix.core import ds_output_report as rep

    bit = rep.VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE
    h = _handle_sem_aparelho(led_gravavel=False)
    h.light.brightness = Brightness.low
    h._brilho_das_luzes = 0
    common = h._build_common(rumble_asserted=False)
    assert common[rep.COMMON_VALID_FLAG2] & bit, (
        "o fluxo do cabo sem nó não autorizou o brilho das lâmpadas — o campo "
        "próprio (`_brilho_das_luzes`) deixou de ligar o `flag2` bit0")
    assert common[42] == 0, (
        f"o `common[42]` saiu {common[42]} com o campo próprio no Forte (0): o "
        f"byte voltou a vir do `light.brightness` da pydualsense. Ele é o brilho "
        f"dos LEDS DE JOGADOR (medido por ela em 09/09/2026), e quem o escolhe é "
        f"o perfil dela.")
    suprimido = _handle_sem_aparelho(led_gravavel=True)
    suprimido._brilho_das_luzes = 0
    neutro = suprimido._build_common(rumble_asserted=False)
    assert neutro[rep.COMMON_VALID_FLAG2] & bit == 0, (
        "sob supressão o fluxo tem de ficar LED-neutro — o brilho vai ao lado "
        "do número, fora do fluxo (`_levar_o_brilho_das_luzes`)")
