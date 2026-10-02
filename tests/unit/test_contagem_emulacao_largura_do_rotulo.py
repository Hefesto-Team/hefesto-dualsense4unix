"""CONTAGEM-E-COOP-01 (E2) — a frase honesta não pode inflar a largura da aba."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("contagem emulacao: largura do rotulo de gamepads")

import inspect

from hefesto_dualsense4unix.app.actions.emulation_actions import (
    EmulationActionsMixin,
    rotulo_gamepads,
)

FRASE_LONGA = rotulo_gamepads(1, 1, 2, 6)

class TestOTetoDeQuebra:
    """06/09/2026 (`GTK-3`): os DOIS testes de medição saíram com a janela."""

    def test_a_aba_aplica_o_teto(self) -> None:
        """Sem esta chamada a constante existiria e não protegeria nada."""
        fonte = inspect.getsource(EmulationActionsMixin._refresh_emulation_view)
        assert "set_max_width_chars(LARGURA_MAXIMA_DO_ROTULO_DE_GAMEPADS)" in fonte
