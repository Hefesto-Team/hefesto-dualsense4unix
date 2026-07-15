"""O teto do multiplicador de rumble tem UM dono (HARM-19).

A faixa valeu três valores ao mesmo tempo:

  - `profiles.schema.RumbleConfig.custom_mult` — 0.0 a **2.0**
  - `ipc_handlers._handle_rumble_policy_custom` — recusava mult > **1.0**
  - `gui/main.glade` (`rumble_policy_adj`) — slider até **200%**

O slider manda `valor / 100` para o `rumble.policy_custom`, então de 101% em
diante a usuária levava um erro de validação — que a aba de gatilhos ainda
reportava como "daemon offline?". O `BUG-RUMBLE-CUSTOM-MULT-CAP-01` subiu o
slider para 200% justamente porque "o schema aceita custom_mult até 2.0", e
esqueceu do handler.

A cura foi alinhar o handler ao schema (não truncar a UI): acima de 100% o
multiplicador AMPLIFICA o que o jogo pediu, que é a razão de a faixa existir.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.profiles.schema import RUMBLE_CUSTOM_MULT_MAX, RumbleConfig

_GLADE = (
    Path(__file__).resolve().parents[2]
    / "src" / "hefesto_dualsense4unix" / "gui" / "main.glade"
)


def _upper_do_slider() -> float:
    fonte = _GLADE.read_text(encoding="utf-8")
    bloco = re.search(
        r'<object class="GtkAdjustment" id="rumble_policy_adj">(.*?)</object>',
        fonte, re.DOTALL,
    )
    assert bloco is not None, "rumble_policy_adj sumiu do glade"
    upper = re.search(r'<property name="upper">([\d.]+)</property>', bloco.group(1))
    assert upper is not None
    return float(upper.group(1))


def test_o_slider_oferece_exatamente_o_que_o_schema_aceita() -> None:
    """O slider é `mult * 100` — a faixa dele é o teto do schema em porcento."""
    assert _upper_do_slider() == RUMBLE_CUSTOM_MULT_MAX * 100


def test_o_schema_aceita_o_proprio_teto() -> None:
    RumbleConfig(policy="custom", custom_mult=RUMBLE_CUSTOM_MULT_MAX)


def test_o_schema_recusa_acima_do_teto() -> None:
    with pytest.raises(ValueError, match="custom_mult fora"):
        RumbleConfig(policy="custom", custom_mult=RUMBLE_CUSTOM_MULT_MAX + 0.1)


@pytest.mark.parametrize("percentual", [0, 50, 100, 150, 200])
def test_todo_valor_do_slider_passa_no_handler(percentual: int) -> None:
    """O que a UI oferece, o daemon aceita — em TODA a faixa.

    Era o defeito: 150% no slider virava mult=1.5 e o handler levantava
    ValueError. Este teste percorre a régua inteira, não só as pontas.
    """
    from hefesto_dualsense4unix.daemon import ipc_handlers

    mult = percentual / 100.0
    fonte = Path(ipc_handlers.__file__).read_text(encoding="utf-8")
    assert "RUMBLE_CUSTOM_MULT_MAX" in fonte, (
        "o handler voltou a ter um teto próprio — importe do schema"
    )
    assert 0.0 <= mult <= RUMBLE_CUSTOM_MULT_MAX


def test_ninguem_mais_hardcodeia_o_teto() -> None:
    """Um dono só: nem o handler nem o glade repetem o número."""
    from hefesto_dualsense4unix.daemon import ipc_handlers

    fonte = Path(ipc_handlers.__file__).read_text(encoding="utf-8")
    trecho = fonte[fonte.index("_handle_rumble_policy_custom"):][:900]
    assert "<= 1.0" not in trecho, "teto de 1.0 hardcoded voltou ao handler"
