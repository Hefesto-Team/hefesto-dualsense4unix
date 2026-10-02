"""O contrato MARCAR e APLICAR, escrito no disco — I12 da INÍCIO NÃO MENTE-01."""
from __future__ import annotations

from typing import Final

from hefesto_dualsense4unix.app.actions.home_actions import (
    _FLAVOR_ITEMS,
    _MODE_ITEMS,
    RECONCILIAR_LABEL,
)

GESTO_MARCAR: Final[str] = "marcar"
GESTO_APLICAR: Final[str] = "aplicar"

SUPERFICIE_QUE_APLICA: Final[str] = "app/actions/footer_actions.py"

MECANISMO_DA_TRANSICAO: Final[str] = "app/actions/mode_transition.py"

SUPERFICIES_QUE_MARCAM: Final[tuple[str, ...]] = (
    "app/actions/home_actions.py",
)

#: portão `test_home_contrato_marcar_e_aplicar.py` cobra as duas coisas — que
EXCECOES_QUE_APLICAM_HOJE: Final[dict[str, str]] = {
    "app/actions/emulation_actions.py": (
        "MEDIDO em 24/08/2026 (§4/I12 da INÍCIO NÃO MENTE-01): a aba Emulação "
        "chama `apply_mode` no clique (`_apply_mode`, :1311-1337) — aplica na "
        "hora. Não é descuido: foi a cura da HARM-01, que tirou dali um "
        "`gamepad.emulation.set` CRU e o fez passar pela sequência completa da "
        "transição. O que sobrou é que duas abas mandam no MESMO valor por "
        "caminhos diferentes, e o rodapé desfaz o clique da Emulação em "
        "silêncio no gesto seguinte. "
        "O QUE A FECHA: a onda da aba Emulação, que a faz MARCAR como a "
        "Início. Não se fecha daqui: são duas abas, dois donos, e escolher por "
        "ela é o fato consumado que esta casa recusa."
    ),
}

ITENS_DE_MODO: Final = _MODE_ITEMS
ITENS_DE_MASCARA: Final = _FLAVOR_ITEMS
ROTULO_RECONCILIAR: Final[str] = RECONCILIAR_LABEL

__all__ = [
    "EXCECOES_QUE_APLICAM_HOJE",
    "GESTO_APLICAR",
    "GESTO_MARCAR",
    "ITENS_DE_MASCARA",
    "ITENS_DE_MODO",
    "MECANISMO_DA_TRANSICAO",
    "ROTULO_RECONCILIAR",
    "SUPERFICIES_QUE_MARCAM",
    "SUPERFICIE_QUE_APLICA",
]
