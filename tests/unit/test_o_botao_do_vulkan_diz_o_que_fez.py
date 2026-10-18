"""O-BOTAO-DO-VULKAN-NAO-RESPONDE-01 — a pílula e o recibo que sobraram.

O botão «Corrigir Vulkan» (gesto `corrigir-vulkan`) saiu em 17/10/2026: nenhum elemento da
página o chamava, e o interruptor das correções grava a escolha das camadas. Ficam a pílula, que
segue a escolha, e a lista dos recibos que ficam na tela.
"""

from __future__ import annotations

from typing import Any

import pytest

pytest_plugins = ["tests.unit.test_a_09_sistema_fecha_a_paridade"]


def test_a_pilula_segue_a_escolha_que_o_lancador_le(a09: Any) -> None:
    """Acesa é «o jogo nasce sem as camadas da Steam», e nada mais."""
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

    cv.gravar_camadas_da_steam_fora(False)
    assert a09.vulkan_corrigido() is False
    cv.gravar_camadas_da_steam_fora(True)
    assert a09.vulkan_corrigido() is True


def test_a_lista_do_recibo_que_fica_e_curta_e_declarada() -> None:
    """A TELA-CALADA-03 continua valendo para os outros destrutivos."""
    from pacotes import a09_sistema as a09

    assert a09.RECIBO_QUE_FICA_NA_TELA == ("correcoes-automaticas",)
    for gesto_ in a09.DESTRUTIVOS:
        assert gesto_ not in a09.RECIBO_QUE_FICA_NA_TELA


def test_o_recibo_dos_outros_continua_fora_da_tela(
        a09: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDE: ponha o gesto do serviço na lista e esta régua reprova."""
    a09._PAINEL[0] = None
    a09._relatar_o_recibo(a09.DESLIGAR, "parei o serviço")
    assert a09._PAINEL[0] is None
