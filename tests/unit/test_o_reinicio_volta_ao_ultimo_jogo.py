"""D-1410-O-PERFIL-FICA-NO-ULTIMO-JOGO: o reinício do serviço volta ao perfil do último jogo.

A regra (14/10/2026): *«Ele deveria ficar sempre com o perfil do último jogo
aberto ou ativado. Até que eu mude ou outro jogo inicie»*. Medido no mesmo dia:
depois do reinício, o daemon subiu na escolha à mão («Lure Of Passion»), com o
gamepad desligado, por cima do perfil do jogo que valia. O reinício não é
mudança dela nem jogo novo.
"""  # noqa-acento: citação literal

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.daemon.connection import (
    _o_nome_que_o_boot_restaura,
    perfil_que_o_boot_restaura,
)
from hefesto_dualsense4unix.profiles.loader import NOME_DO_PADRAO
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

OUTRO_JOGO = "steam_app_1599660"
JANELA_DO_TERMINAL = {"wm_class": "com.system76.CosmicTerm", "wm_name": "Terminal"}
JANELA_DA_STEAM = {"wm_class": "steam", "wm_name": ""}


def _os_perfis() -> list:
    jogo = _perfil("sackboy", janela=CLASSE_DO_JOGO, prioridade=90)
    jogo.mode = ProfileModeConfig(kind="gamepad", gamepad_flavor="xbox")
    return [jogo, _perfil("lure", janela=OUTRO_JOGO, prioridade=80)]


def _a_escolha_a_mao_e_o_lure() -> None:
    session.gravar_a_escolha("lure")
    assert session.a_escolha_dela() == "lure", "premissa: a escolha à mão é o «lure»"


def _jogou_e_fechou() -> None:
    """O autoswitch entra no jogo pela janela dele, e o jogo fecha com a Steam na frente."""
    manager, store = _bancada(_os_perfis())
    _a_escolha_a_mao_e_o_lure()
    sw = _switcher(manager, store, jogo_vivo=lambda: None)
    sw._tick(dict(JANELA_DO_JOGO), 0.0)
    sw._tick(dict(JANELA_DO_JOGO), 1.0)
    assert store.active_profile == "sackboy", "premissa: o autoswitch entrou no jogo"
    for i in range(10):
        sw._tick(dict(JANELA_DA_STEAM), 2.0 + 0.5 * i)
    assert store.active_profile == "sackboy", "premissa: o perfil do jogo ficou"


@pytest.mark.usefixtures("perfis_isolados")
def test_o_boot_depois_do_jogo_restaura_o_perfil_do_jogo_e_o_modo_dele() -> None:
    """O serviço reinicia sem jogo aberto: volta o do último jogo, e o pad nasce no modo dele.

    MORDIDA: tire o ``o_ultimo_jogo()`` do ``_o_nome_que_o_boot_restaura`` e volta o «lure».
    """
    _jogou_e_fechou()
    assert _o_nome_que_o_boot_restaura(None) == "sackboy"
    perfil = perfil_que_o_boot_restaura(None)
    assert perfil is not None and perfil.name == "sackboy"
    assert perfil.mode is not None, "o modo do jogo volta junto"
    assert perfil.mode.kind == "gamepad", "o gamepad volta ligado"


@pytest.mark.usefixtures("perfis_isolados")
def test_depois_do_boot_a_janela_sem_perfil_nao_devolve_a_escolha() -> None:
    """Depois do reinício, o terminal em foco não põe a escolha por cima do jogo restaurado.

    MORDIDA: tire o ``_o_boot_veio_do_ultimo_jogo`` do ``_fica_no_ultimo_jogo`` e o «lure» entra.
    """
    _jogou_e_fechou()
    manager, store = _bancada(_os_perfis())
    store.set_active_profile(_o_nome_que_o_boot_restaura(None))
    sw = _switcher(manager, store, jogo_vivo=lambda: None)
    for i in range(60):
        sw._tick(dict(JANELA_DO_TERMINAL), 0.5 * i)
    assert store.active_profile == "sackboy"


@pytest.mark.usefixtures("perfis_isolados")
def test_o_gesto_dela_depois_do_jogo_e_o_que_o_boot_restaura() -> None:
    """Ela ativa outro perfil à mão depois do jogo: o boot abre na escolha do usuário.

    MORDIDA: tire o ``esquecer_o_ultimo_jogo()`` do ``gravar_a_escolha`` e volta o «sackboy».
    """
    _jogou_e_fechou()
    manager, _store = _bancada(_os_perfis())
    manager.activate("lure", origin="manual")
    assert _o_nome_que_o_boot_restaura(None) == "lure"


@pytest.mark.usefixtures("perfis_isolados")
def test_o_lancamento_grava_o_ultimo_jogo() -> None:
    """O jogo que entrou pelo lançamento (``origin=launch``) também é o que o boot restaura.

    MORDIDA: tire o ``lembrar_o_ultimo_jogo`` do ramo ``launch`` do ``_ativar`` e volta o «lure».
    """
    manager, _store = _bancada(_os_perfis())
    _a_escolha_a_mao_e_o_lure()
    manager.activate("sackboy", origin="launch")
    assert _o_nome_que_o_boot_restaura(None) == "sackboy"


@pytest.mark.usefixtures("perfis_isolados")
def test_o_perfil_apagado_sai_da_memoria_e_o_freestyle_manda() -> None:
    """O perfil do jogo apagado não volta, e o Freestyle ligado vence o último jogo."""
    _jogou_e_fechou()
    session.save_freestyle_ligado(True)
    assert _o_nome_que_o_boot_restaura(None) == NOME_DO_PADRAO
    session.save_freestyle_ligado(False)
    manager, _store = _bancada(_os_perfis())
    manager.delete("sackboy")
    assert session._ultimo_jogo_cru() is None, "o apagado sai da memória, não só deixa de carregar"
    assert _o_nome_que_o_boot_restaura(None) == "lure"


@pytest.mark.usefixtures("perfis_isolados")
def test_o_tique_nao_regrava_o_disco_a_cada_volta(monkeypatch: pytest.MonkeyPatch) -> None:
    """A memória do disco só se escreve na troca, nunca a cada tique do jogo em foco."""
    gravados: list[str] = []
    original = session.lembrar_o_ultimo_jogo
    monkeypatch.setattr(
        session, "lembrar_o_ultimo_jogo", lambda nome: (gravados.append(nome), original(nome))
    )
    manager, store = _bancada(_os_perfis())
    sw = _switcher(manager, store, jogo_vivo=lambda: None)
    for i in range(40):
        sw._tick(dict(JANELA_DO_JOGO), 0.5 * i)
    assert store.active_profile == "sackboy"
    assert gravados == ["sackboy"]
