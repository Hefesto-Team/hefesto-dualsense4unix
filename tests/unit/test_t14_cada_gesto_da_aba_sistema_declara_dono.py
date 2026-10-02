"""T-14 (SISTEMA-O-VIGIA-VIVO-01) — receita da máquina, ou perfil do jogo?"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_t14_cada_gesto_da_aba_sistema_declara_dono: importa código da janela GTK")

from pathlib import Path

import pytest

from hefesto_dualsense4unix.app.actions.daemon_actions import (
    DA_MAQUINA,
    DO_JOGO,
    DONO_DO_GESTO,
)

RAIZ = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("gesto", sorted(DONO_DO_GESTO))
def test_a_declaracao_tem_valor_valido_e_evidencia(gesto: str) -> None:
    """Declarar "máquina" sem dizer por quê é declarar nada."""
    dono, evidencia = DONO_DO_GESTO[gesto]

    assert dono in (DO_JOGO, DA_MAQUINA), (gesto, dono)
    assert len(evidencia) >= 20, f"{gesto}: evidência curta demais: {evidencia!r}"


def test_os_tres_gestos_que_a_sprint_leu_como_do_jogo() -> None:
    """A leitura da sprint, travada: marca do Steam Input, Proton, camadas."""
    do_jogo = {g for g, (dono, _) in DONO_DO_GESTO.items() if dono == DO_JOGO}

    assert do_jogo == {
        "btn_steam_game_broken",
        "btn_proton_lock",
        "btn_camadas_engasgo",
    }


def test_o_perfil_continua_sem_um_campo_desta_aba() -> None:
    """A medição que dá sentido a tudo isto — e que vai caducar um dia."""
    from hefesto_dualsense4unix.profiles import schema

    fonte = Path(schema.__file__).read_text(encoding="utf-8")

    assert "class PonteConfirmada" in fonte
    for gesto in DONO_DO_GESTO:
        assert gesto not in fonte, (
            f"{gesto} apareceu em profiles/schema.py — a aba Sistema entrou "
            "no perfil. Se foi decisão dela, atualize a leitura de "
            "`DONO_DO_GESTO` e este teste; se não foi, é a decisão D-A "
            "sendo tomada sem ela."
        )
