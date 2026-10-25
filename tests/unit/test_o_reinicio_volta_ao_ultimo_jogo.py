"""D-1410-O-PERFIL-FICA-NO-ULTIMO-JOGO: o reinício do serviço volta ao perfil do último jogo.

A regra (14/10/2026): *«Ele deveria ficar sempre com o perfil do último jogo
aberto ou ativado. Até que eu mude ou outro jogo inicie»*. Medido no mesmo dia:
depois do reinício, o daemon subiu na escolha à mão («Lure Of Passion»), com o
gamepad desligado, por cima do perfil do jogo que valia. O reinício não é
mudança dela nem jogo novo.
"""  # (noqa-acento) citação literal

from __future__ import annotations

import pytest
import structlog

from hefesto_dualsense4unix.daemon.connection import (
    _o_nome_que_o_boot_restaura,
    perfil_que_o_boot_restaura,
)
from hefesto_dualsense4unix.profiles.loader import NOME_DO_PADRAO
from hefesto_dualsense4unix.profiles.manager import esquecer_o_perfil_apagado
from hefesto_dualsense4unix.profiles.schema import ProfileModeConfig, perfil_e_de_jogo
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

    MORDIDA: troque o ``o_ultimo_jogo()`` do ``_o_ultimo_jogo_que_vale`` por ``None``
    e o «lure» entra.
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
    _bancada(_os_perfis())
    esquecer_o_perfil_apagado("sackboy")
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


@pytest.mark.usefixtures("perfis_isolados")
def test_depois_do_boot_a_janela_com_perfil_proprio_tira_a_memoria_do_disco() -> None:
    """Depois do reinício, a janela com perfil próprio que não é de jogo tira o último jogo.

    O boot restaura o jogo pelo disco, com a crença do autoswitch vazia; a primeira
    janela é a do Kodi, com perfil próprio. Dentro do processo o jogo saiu, então o
    reinício seguinte não pode voltar a ele.

    MORDIDA: devolva o ``elif anterior is not None:`` no ``_o_ultimo_jogo_passa_a`` e
    o disco segue no «sackboy».
    """
    _jogou_e_fechou()
    kodi = _perfil("kodi", janela="kodi", prioridade=50)
    manager, store = _bancada([*_os_perfis(), kodi])
    store.set_active_profile(_o_nome_que_o_boot_restaura(None))
    assert store.active_profile == "sackboy", "premissa: o boot voltou ao último jogo"
    sw = _switcher(manager, store, jogo_vivo=lambda: None)
    for i in range(10):
        sw._tick({"wm_class": "kodi", "wm_name": "Kodi"}, 0.5 * i)
    assert store.active_profile == "kodi", "premissa: a janela com perfil próprio entrou"
    assert session._ultimo_jogo_cru() is None, "a memória do jogo ficou no disco"
    assert _o_nome_que_o_boot_restaura(None) == "lure"


def _espiar_o_disco(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Anota cada gravação do `ultimo_jogo.json`, e grava de verdade."""
    gravados: list[str] = []
    original = session.lembrar_o_ultimo_jogo

    def _grava(nome: str) -> None:
        gravados.append(nome)
        original(nome)

    monkeypatch.setattr(session, "lembrar_o_ultimo_jogo", _grava)
    return gravados


@pytest.mark.usefixtures("perfis_isolados")
def test_o_primeiro_tique_antes_do_boot_escolhe_o_ultimo_jogo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A CORRIDA: o tique do autoswitch chega antes do restauro do boot, com a crença vazia.

    Medido às 20h52 de 14/10/2026: o primeiro tique (``from_=None``, o terminal em
    foco) pôs a escolha à mão («Lure Of Passion») 1,8 s antes de o boot restaurar
    o Sackboy, e o tique seguinte pôs o «Lure» de novo, por cima. O último jogo
    vale com a crença ``None``, em qualquer ordem, e o disco não se regrava.

    MORDIDA: faça o ``_o_ultimo_jogo_que_vale`` devolver ``None`` e o «lure» entra.
    """
    _jogou_e_fechou()
    gravados = _espiar_o_disco(monkeypatch)
    manager, store = _bancada(_os_perfis())
    assert store.active_profile is None, "premissa: o boot ainda não restaurou nada"
    sw = _switcher(manager, store, jogo_vivo=lambda: None)
    with structlog.testing.capture_logs() as diario:
        for i in range(4):
            sw._tick(dict(JANELA_DO_TERMINAL), 0.5 * i)
        assert store.active_profile == "sackboy", "o primeiro tique pôs a escolha"
        manager.activate(_o_nome_que_o_boot_restaura(store), origin="system")
        for i in range(60):
            sw._tick(dict(JANELA_DO_TERMINAL), 2.0 + 0.5 * i)
    assert store.active_profile == "sackboy"
    assert not [r for r in diario if r.get("to") == "lure"], "a escolha passou por cima"
    assert gravados == [], "o tique regravou o disco com o que já estava lá"
    assert session._ultimo_jogo_cru() == "sackboy"


@pytest.mark.usefixtures("perfis_isolados")
def test_o_boot_antes_do_primeiro_tique_tambem_fica_no_ultimo_jogo() -> None:
    """A outra ordem da corrida: o restauro primeiro, e o tique acha o último jogo ativo."""
    _jogou_e_fechou()
    manager, store = _bancada(_os_perfis())
    manager.activate(_o_nome_que_o_boot_restaura(store), origin="system")
    sw = _switcher(manager, store, jogo_vivo=lambda: None)
    for i in range(60):
        sw._tick(dict(JANELA_DO_TERMINAL), 0.5 * i)
    assert store.active_profile == "sackboy"
    assert session._ultimo_jogo_cru() == "sackboy"


@pytest.mark.usefixtures("perfis_isolados")
def test_a_escolha_que_e_perfil_de_jogo_nao_vira_o_ultimo_jogo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A MEMÓRIA CONTAMINADA: a escolha entra pelo «sem candidato» e não grava o último jogo.

    Medido às 20h52 de 14/10/2026: o «Lure Of Passion» (regra ``steam_app_3851570``)
    entrou como escolha à mão, e o ``o_ultimo_jogo_lembrado`` o gravou por cima do
    Sackboy. O perfil que entra pela escolha nunca grava nem apaga a memória do jogo.

    MORDIDA: tire o ``if not veio_da_escolha`` do ``_activate`` e o disco diz «lure».
    """
    gravados = _espiar_o_disco(monkeypatch)
    manager, store = _bancada(_os_perfis())
    _a_escolha_a_mao_e_o_lure()
    assert perfil_e_de_jogo(manager.get("lure")), "premissa: a escolha é perfil de jogo"
    sw = _switcher(manager, store, jogo_vivo=lambda: None)
    for i in range(10):
        sw._tick(dict(JANELA_DO_TERMINAL), 0.5 * i)
    assert store.active_profile == "lure", "premissa: a escolha entrou pelo «sem candidato»"
    assert gravados == []
    assert session._ultimo_jogo_cru() is None


@pytest.mark.usefixtures("perfis_isolados")
def test_o_jogo_que_o_lancamento_pos_fica_mesmo_sem_a_janela_dele() -> None:
    """O lançamento troca o último jogo por fora do autoswitch: a memória dele segue o disco.

    O boot abriu na escolha, e o autoswitch passou a lembrar o Sackboy (ele o pôs
    pela janela); o lançamento pôs o
    «lure» (``origin=launch``, que grava o disco). Com o terminal em foco e a
    janela do jogo nunca vista, a memória velha não casava com o perfil que vale,
    e a escolha entrava.

    MORDIDA: tire a releitura do disco que a crença sincronizada arma no
    ``_perfil_corrente`` e a escolha («leitura») entra.
    """
    leitura = _perfil("leitura")
    manager, store = _bancada([*_os_perfis(), leitura])
    session.gravar_a_escolha("leitura")
    manager.activate("leitura", origin="system")
    sw = _switcher(manager, store, jogo_vivo=lambda: None)
    sw._tick(dict(JANELA_DO_TERMINAL), 0.0)
    sw._tick(dict(JANELA_DO_JOGO), 0.5)
    sw._tick(dict(JANELA_DO_JOGO), 1.0)
    assert store.active_profile == "sackboy", "premissa: o autoswitch entrou no jogo"
    manager.activate("lure", origin="launch")
    for i in range(60):
        sw._tick(dict(JANELA_DO_TERMINAL), 2.0 + 0.5 * i)
    assert store.active_profile == "lure"
    assert session._ultimo_jogo_cru() == "lure"


@pytest.mark.usefixtures("perfis_isolados")
def test_o_gesto_dela_depois_do_boot_fica_com_a_janela_sem_perfil() -> None:
    """O boot volta ao último jogo, ela ativa outro perfil à mão, e o terminal não devolve o jogo.

    O gesto do usuário é o que tira o último jogo (D-1410-O-PERFIL-FICA-NO-ULTIMO-JOGO):
    o ``gravar_a_escolha`` apaga o disco, e a memória do autoswitch se relê vazia.
    Com a memória velha, o jogo voltava pela queda do «sem candidato» e, por
    declarar o modo gamepad, ainda soltava a trava da troca à mão.

    MORDIDA: tire a releitura do disco que a crença sincronizada arma no
    ``_perfil_corrente`` e o «sackboy» volta por cima do gesto.
    """
    _jogou_e_fechou()
    okular = _perfil("okular", janela="okular", prioridade=40)
    manager, store = _bancada([*_os_perfis(), okular])
    manager.activate(_o_nome_que_o_boot_restaura(store), origin="system")
    sw = _switcher(manager, store, jogo_vivo=lambda: None)
    for i in range(10):
        sw._tick(dict(JANELA_DO_TERMINAL), 0.5 * i)
    assert store.active_profile == "sackboy", "premissa: o boot voltou ao último jogo"
    manager.activate("okular", origin="manual")
    for i in range(60):
        sw._tick(dict(JANELA_DO_TERMINAL), 10.0 + 0.5 * i)
    assert store.active_profile == "okular", "o último jogo voltou por cima do gesto dela"
    assert session._ultimo_jogo_cru() is None
    assert _o_nome_que_o_boot_restaura(None) == "okular"
