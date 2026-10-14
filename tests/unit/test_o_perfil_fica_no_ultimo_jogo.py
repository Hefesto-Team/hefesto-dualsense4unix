"""OS-QUATRO-EM-HARMONIA-01, item 4: o perfil fica no último jogo, e o lançador não escolhe jogo.

A regra (14/10/2026): *«Ele deveria ficar sempre com o perfil do último jogo
aberto ou ativado. Até que eu mude ou outro jogo inicie»*. Medido às 10h24m37:
o Sackboy fechou, o foco foi à Steam e ao terminal, e a volta «à escolha» pôs
o perfil de outro jogo, no modo Navegação, por cima do dele.
"""  # noqa-acento: citação literal

from __future__ import annotations


import pytest
import structlog

from hefesto_dualsense4unix.profiles.schema import MatchCriteria, perfil_e_de_jogo
from hefesto_dualsense4unix.profiles.steam_app import e_janela_de_lancador
from tests.unit.test_foco_errante_01_a_janela_da_steam_nao_tira_o_perfil import (
    CLASSE_DO_JOGO,
    JANELA_DO_JOGO,
    _bancada,
    _perfil,
    _switcher,
    perfis_isolados,  # noqa: F401
)

OUTRO_JOGO = "steam_app_1599660"
JANELAS_SEM_PERFIL = [
    {"wm_class": "steam", "wm_name": ""},
    {"wm_class": "com.heroicgameslauncher.hgl", "wm_name": "Heroic"},
    {"wm_class": "net.lutris.Lutris", "wm_name": "Lutris"},
    {"wm_class": "com.system76.CosmicTerm", "wm_name": "Terminal"},
    {"wm_class": "", "wm_name": ""},
]


def _a_escolha(monkeypatch: pytest.MonkeyPatch, nome: str) -> None:
    from hefesto_dualsense4unix.utils import session

    monkeypatch.setattr(session, "a_escolha_dela", lambda **_k: nome)


def _no_jogo(nome_do_jogo: str = "sackboy") -> tuple[object, object, float]:
    manager, store = _bancada([
        _perfil(nome_do_jogo, janela=CLASSE_DO_JOGO, prioridade=90),
        _perfil("lure", janela=OUTRO_JOGO, prioridade=80),
    ])
    sw = _switcher(manager, store, jogo_vivo=lambda: None)
    sw._tick(dict(JANELA_DO_JOGO), 0.0)
    sw._tick(dict(JANELA_DO_JOGO), 1.0)
    assert store.active_profile == nome_do_jogo, "premissa: o autoswitch entrou no jogo"
    return sw, store, 1.0


@pytest.mark.usefixtures("perfis_isolados")
@pytest.mark.parametrize("janela", JANELAS_SEM_PERFIL, ids=lambda j: j["wm_class"] or "vazia")
def test_o_jogo_fecha_e_o_perfil_dele_fica(
    monkeypatch: pytest.MonkeyPatch, janela: dict[str, str]
) -> None:
    """MORDIDA: tire o ``_fica_no_ultimo_jogo`` do ``_tick`` e a escolha (o «lure») entra."""
    _a_escolha(monkeypatch, "lure")
    sw, store, agora = _no_jogo()
    with structlog.testing.capture_logs() as diario:
        for i in range(60):
            sw._tick(dict(janela), agora + 0.5 * (i + 1))
    assert store.active_profile == "sackboy"
    assert not [r for r in diario if r["event"] == "profile_autoswitch"]
    ficou = [r["current"] for r in diario if r["event"] == "autoswitch_fica_no_ultimo_jogo"]
    assert ficou == (["sackboy"] if janela["wm_class"] else []), "o log diz uma vez por janela"


@pytest.mark.usefixtures("perfis_isolados")
def test_outro_jogo_que_inicia_leva_o_perfil(monkeypatch: pytest.MonkeyPatch) -> None:
    _a_escolha(monkeypatch, "sackboy")
    sw, store, agora = _no_jogo()
    sw._tick({"wm_class": "steam", "wm_name": ""}, agora + 1)
    sw._tick({"wm_class": OUTRO_JOGO, "wm_name": "Lure"}, agora + 2)
    sw._tick({"wm_class": OUTRO_JOGO, "wm_name": "Lure"}, agora + 3)
    assert store.active_profile == "lure"


@pytest.mark.usefixtures("perfis_isolados")
def test_quando_ela_muda_a_escolha_volta_a_valer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ela ativa outro perfil na mão: o «fica» é do jogo, não dela."""
    _a_escolha(monkeypatch, "lure")
    sw, store, agora = _no_jogo()
    store.set_active_profile("lure")
    for i in range(30):
        sw._tick({"wm_class": "steam", "wm_name": ""}, agora + 0.5 * (i + 1))
    assert store.active_profile == "lure"


@pytest.mark.usefixtures("perfis_isolados")
def test_o_perfil_de_jogo_com_a_classe_do_lancador_nao_entra_pela_janela_dele(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O perfil de outro jogo cuja regra traz `steam` não entra pela janela da Steam.

    MORDIDA: tire o filtro do ``e_janela_de_lancador`` em ``select_for_window_ex``.
    """
    _a_escolha(monkeypatch, "sackboy")
    manager, _store = _bancada([
        _perfil("sackboy", janela=CLASSE_DO_JOGO, prioridade=90),
        _perfil("lure", janela=OUTRO_JOGO, prioridade=80).model_copy(
            update={"match": MatchCriteria(window_class=[OUTRO_JOGO, "steam"])}
        ),
    ])
    assert manager.select_for_window({"wm_class": "steam", "wm_name": ""}) is None
    assert manager.select_for_window({"wm_class": OUTRO_JOGO, "wm_name": ""}).name == "lure"


@pytest.mark.usefixtures("perfis_isolados")
def test_o_perfil_do_lancador_que_nao_e_de_jogo_segue() -> None:
    """A Navegação feita para a janela da Steam continua entrando por ela."""
    manager, _store = _bancada([_perfil("navegacao", janela="steam", prioridade=50)])
    assert manager.select_for_window({"wm_class": "steam", "wm_name": ""}).name == "navegacao"


@pytest.mark.parametrize(
    "classe", ["steam", "Steam", "steamwebhelper", "com.valvesoftware.Steam", "heroic",
               "com.heroicgameslauncher.hgl", "lutris", "net.lutris.Lutris", "itch"],
)
def test_as_janelas_de_lancador(classe: str) -> None:
    assert e_janela_de_lancador(classe)


@pytest.mark.parametrize("classe", [CLASSE_DO_JOGO, "gotg.exe", "firefox", "", None])
def test_o_que_nao_e_lancador(classe: str | None) -> None:
    assert not e_janela_de_lancador(classe)


def test_o_perfil_de_jogo_pelo_arquivo() -> None:
    assert perfil_e_de_jogo(_perfil("x", janela=CLASSE_DO_JOGO))
    assert not perfil_e_de_jogo(_perfil("x", janela="steam"))
    assert not perfil_e_de_jogo(_perfil("x"))
