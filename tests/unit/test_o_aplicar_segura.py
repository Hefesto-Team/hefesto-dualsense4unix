"""D-1410-O-APLICAR-SEGURA: o «Aplicar» de outro perfil segura contra o autoswitch.

A queixa (14/10/2026): *«Usar o «Aplicar» em outro perfil não segura: em uns 12 s
a escolha feita à mão volta por cima dele.»* A regra de produto: *«Ele deveria ficar
sempre com o perfil do último jogo aberto ou ativado. Até que eu mude ou outro
jogo inicie»*. O «Aplicar» e o «Voltar à de ontem» passam pelo mesmo
`ProfileManager.reaplicar`, que arma a trava da troca à mão sem gravar a escolha.
"""  # noqa-acento: citação literal

from __future__ import annotations

import time

import pytest

from hefesto_dualsense4unix.profiles.schema import ProfileModeConfig
from hefesto_dualsense4unix.utils import session
from tests.unit.test_foco_errante_01_a_janela_da_steam_nao_tira_o_perfil import (
    CLASSE_DO_JOGO,
    JANELA_DO_JOGO,
    _bancada,
    _perfil,
    _switcher,
    perfis_isolados,  # noqa: F401
)

JANELA_DO_TERMINAL = {"wm_class": "com.system76.CosmicTerm", "wm_name": "Terminal"}


def _a_montagem():  # type: ignore[no-untyped-def]
    """O terminal em foco, o último jogo no disco, a escolha no `session.json`, e o «Aplicar»."""
    jogo = _perfil("sackboy", janela=CLASSE_DO_JOGO, prioridade=90)
    jogo.mode = ProfileModeConfig(kind="gamepad", gamepad_flavor="xbox")
    manager, store = _bancada([
        jogo,
        _perfil("lure", janela="steam_app_1599660", prioridade=80),
        _perfil("fliperama", janela="retroarch", prioridade=40),
    ])
    session.gravar_a_escolha("lure")
    session.lembrar_o_ultimo_jogo("sackboy")
    store.set_active_profile("sackboy")
    sw = _switcher(manager, store, jogo_vivo=lambda: None)
    for i in range(4):
        sw._tick(dict(JANELA_DO_TERMINAL), 0.5 * i)
    assert store.active_profile == "sackboy", "premissa: o terminal fica no último jogo"

    manager.reaplicar("fliperama")
    assert store.active_profile == "fliperama"
    return manager, store, sw


def _terminal(sw, de: float, ate: float) -> None:  # type: ignore[no-untyped-def]
    t = de
    while t <= ate:
        sw._tick(dict(JANELA_DO_TERMINAL), t)
        t += 0.5


@pytest.mark.usefixtures("perfis_isolados")
def test_o_aplicar_segura_aos_12_e_aos_60_segundos() -> None:
    """D-1410-O-APLICAR-SEGURA: o terminal não devolve a escolha nem o último jogo por cima.

    MORDIDA: tire o ``armar_a_trava_da_mao`` do ramo da reaplicação no ``_ativar``
    (`profiles/manager.py`) e, aos 12 s, o «lure» da escolha passa por cima.
    """
    _manager, store, sw = _a_montagem()
    _terminal(sw, 2.0, 2.0 + 12.5)
    assert store.active_profile == "fliperama", "aos 12 s a escolha passou por cima do «Aplicar»"
    _terminal(sw, 15.0, 2.0 + 60.0)
    assert store.active_profile == "fliperama", "aos 60 s a escolha passou por cima do «Aplicar»"
    assert session.a_escolha_dela() == "lure", "o «Aplicar» virou a escolha"
    assert session.o_ultimo_jogo() == "sackboy", "o último jogo saiu do disco"


@pytest.mark.usefixtures("perfis_isolados")
def test_o_jogo_com_perfil_em_foco_solta_a_trava_do_aplicar() -> None:
    """D-1410-O-APLICAR-SEGURA: outro jogo com perfil entrando em foco solta a trava e entra."""
    _manager, store, sw = _a_montagem()
    _terminal(sw, 2.0, 20.0)
    sw._tick(dict(JANELA_DO_JOGO), 20.5)
    sw._tick(dict(JANELA_DO_JOGO), 21.5)
    assert store.active_profile == "sackboy", "o jogo com perfil não entrou"
    assert not store.manual_profile_lock_active(time.monotonic()), "a trava não soltou"


@pytest.mark.usefixtures("perfis_isolados")
def test_o_ativar_de_outro_perfil_troca_depois_do_aplicar() -> None:
    """D-1410-O-APLICAR-SEGURA: o próximo gesto («Ativar» de outro perfil) troca, e fica."""
    manager, store, sw = _a_montagem()
    _terminal(sw, 2.0, 10.0)
    manager.activate("lure", origin="manual")
    _terminal(sw, 10.5, 70.0)
    assert store.active_profile == "lure"


@pytest.mark.usefixtures("perfis_isolados")
def test_o_jogo_lancado_solta_a_trava_do_aplicar() -> None:
    """D-1410-O-APLICAR-SEGURA: outro jogo lançado solta a trava, entra, e o terminal o mantém.

    MORDIDA: tire o ``soltar_a_trava_da_mao`` do ramo ``origin == "launch"`` no ``_ativar``
    (`profiles/manager.py`) e a trava do «Aplicar» sobrevive ao lançamento.
    """
    manager, store, sw = _a_montagem()
    _terminal(sw, 2.0, 10.0)
    manager.activate("lure", origin="launch")
    assert not store.manual_profile_lock_active(time.monotonic()), "o lançamento não soltou a trava"
    _terminal(sw, 10.5, 70.0)
    assert store.active_profile == "lure", "o jogo lançado não ficou"
    assert session.o_ultimo_jogo() == "lure", "o lançamento não virou o último jogo"
