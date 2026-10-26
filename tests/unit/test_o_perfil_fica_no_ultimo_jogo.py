"""OS-QUATRO-EM-HARMONIA-01, item 4: o perfil fica no último jogo, e o lançador não escolhe jogo.

A regra (14/10/2026): *«Ele deveria ficar sempre com o perfil do último jogo
aberto ou ativado. Até que eu mude ou outro jogo inicie»*. Medido às 10h24m37:
o Sackboy fechou, o foco foi à Steam e ao terminal, e a volta «à escolha» pôs
o perfil de outro jogo, no modo Navegação, por cima do dele.
"""

from __future__ import annotations

import pytest
import structlog

from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile, perfil_e_de_jogo
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
JANELA_DO_TERMINAL = {"wm_class": "com.system76.CosmicTerm", "wm_name": "Terminal"}
JANELAS_DE_LANCADOR = [
    {"wm_class": "steam", "wm_name": ""},
    {"wm_class": "com.heroicgameslauncher.hgl", "wm_name": "Heroic"},
    {"wm_class": "net.lutris.Lutris", "wm_name": "Lutris"},
]
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
    """D-1410-O-PERFIL-FICA-NO-ULTIMO-JOGO: o jogo fecha e o perfil dele fica.

    MORDIDA: faça o ``_o_ultimo_jogo_que_vale`` devolver ``None`` e a escolha (o «lure») entra.
    """
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
@pytest.mark.parametrize("quem_pos", ["o-lancamento", "o-boot-com-o-jogo-aberto"])
def test_o_perfil_que_outro_pos_e_o_jogo_confirma_tambem_fica(
    monkeypatch: pytest.MonkeyPatch, quem_pos: str
) -> None:
    """D-1410-O-PERFIL-FICA-NO-ULTIMO-JOGO: o perfil do jogo que o lançamento pôs fica.

    Medido às 10h26m49 de 14/10: o Sackboy entrou com ``origin=launch``, e o
    autoswitch só sincronizou a crença; sem a confirmação do tique, o jogo
    fechava e a escolha entrava. O mesmo com o daemon reiniciado com o jogo aberto.
    Depois da Steam vem o terminal, que não é lançador: só a memória segura o jogo.

    MORDIDA: tire o ``_o_ultimo_jogo_passa_a(candidate)`` do ``_tick`` e o «lure» entra.
    """
    _a_escolha(monkeypatch, "lure")
    manager, store = _bancada([
        _perfil("sackboy", janela=CLASSE_DO_JOGO, prioridade=90),
        _perfil("lure", janela=OUTRO_JOGO, prioridade=80),
    ])
    if quem_pos == "o-boot-com-o-jogo-aberto":
        store.set_active_profile("sackboy")
        sw = _switcher(manager, store, jogo_vivo=lambda: None)
    else:
        sw = _switcher(manager, store, jogo_vivo=lambda: None)
        sw._tick({"wm_class": "firefox", "wm_name": ""}, 0.0)
        store.set_active_profile("sackboy")
    sw._tick(dict(JANELA_DO_JOGO), 1.0)
    sw._tick(dict(JANELA_DO_JOGO), 2.0)
    assert store.active_profile == "sackboy", "premissa: o jogo em foco confirma o perfil"
    agora = 3.0
    for janela in ({"wm_class": "steam", "wm_name": ""}, JANELA_DO_TERMINAL):
        for _ in range(30):
            agora += 0.5
            sw._tick(dict(janela), agora)
    assert store.active_profile == "sackboy"


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

    D-1410-O-PERFIL-FICA-NO-ULTIMO-JOGO: janela de lançador não ativa perfil de jogo.

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
@pytest.mark.parametrize("janela", JANELAS_DE_LANCADOR, ids=lambda j: j["wm_class"])
def test_o_perfil_feito_para_a_janela_do_lancador_nao_entra_por_ela(
    janela: dict[str, str],
) -> None:
    """D-1410-O-PERFIL-FICA-NO-ULTIMO-JOGO: nem a Navegação feita para a Steam entra pela Steam.

    Até 14/10 o perfil que não é de jogo seguia pela janela do lançador.

    MORDIDA: devolva o ``candidates = [p for p in candidates if not perfil_e_de_jogo(p)]``.
    """
    manager, _store = _bancada([
        _perfil("navegacao", janela=janela["wm_class"], prioridade=50),
    ])
    assert manager.select_for_window(dict(janela)) is None


def _a_navegacao_dos_lancadores() -> list[Profile]:
    """Um perfil Navegação feito para a janela de cada lançador, de prioridade alta."""
    return [
        _perfil(f"navegacao_{i}", janela=j["wm_class"], prioridade=99)
        for i, j in enumerate(JANELAS_DE_LANCADOR)
    ]


@pytest.mark.usefixtures("perfis_isolados")
def test_jogo_fecha_steam_heroic_e_so_outro_jogo_leva_o_perfil(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-1410-O-PERFIL-FICA-NO-ULTIMO-JOGO: a sequência da tarefa, com a Navegação de cada lançador.

    O jogo fecha, a Steam vem à frente, depois o Heroic e o Lutris: o perfil
    fica no do jogo. Só o outro jogo que abre leva o perfil.
    """
    _a_escolha(monkeypatch, "navegacao_0")
    manager, store = _bancada([
        _perfil("sackboy", janela=CLASSE_DO_JOGO, prioridade=90),
        _perfil("lure", janela=OUTRO_JOGO, prioridade=80),
        *_a_navegacao_dos_lancadores(),
    ])
    sw = _switcher(manager, store, jogo_vivo=lambda: None)
    sw._tick(dict(JANELA_DO_JOGO), 0.0)
    sw._tick(dict(JANELA_DO_JOGO), 1.0)
    assert store.active_profile == "sackboy", "premissa: o autoswitch entrou no jogo"
    agora = 1.0
    with structlog.testing.capture_logs() as diario:
        for janela in JANELAS_DE_LANCADOR:
            for _ in range(60):
                agora += 0.5
                sw._tick(dict(janela), agora)
                assert store.active_profile == "sackboy", janela["wm_class"]
        for _ in range(4):
            agora += 1.0
            sw._tick({"wm_class": OUTRO_JOGO, "wm_name": "Lure"}, agora)
    assert store.active_profile == "lure"
    assert [r for r in diario if r["event"] == "profile_autoswitch"], "premissa: houve troca"
    assert not any(
        str(r.get("to", "")).startswith("navegacao") for r in diario
        if r["event"] == "profile_autoswitch"
    )


@pytest.mark.usefixtures("perfis_isolados")
@pytest.mark.parametrize("janela", JANELAS_DE_LANCADOR, ids=lambda j: j["wm_class"])
@pytest.mark.parametrize("quem", ["ela-a-mao", "o-boot"])
def test_sem_jogo_antes_o_lancador_nao_ativa_nem_a_navegacao_nem_a_escolha(
    monkeypatch: pytest.MonkeyPatch, janela: dict[str, str], quem: str
) -> None:
    """D-1410-O-PERFIL-FICA-NO-ULTIMO-JOGO: sem jogo antes, o lançador também não ativa nada.

    O que ela ativou à mão (ou o que o boot pôs) fica; nem a Navegação do
    lançador nem a volta à escolha entram pela janela dele.

    MORDIDA: tire o ``_o_lancador_nao_ativa`` do ``_tick`` e a escolha entra.
    """
    _a_escolha(monkeypatch, "lure")
    manager, store = _bancada([
        _perfil("lure", janela=OUTRO_JOGO, prioridade=80),
        _perfil("leitura", prioridade=0),
        *_a_navegacao_dos_lancadores(),
    ])
    sw = _switcher(manager, store, jogo_vivo=lambda: None)
    if quem == "ela-a-mao":
        sw._tick({"wm_class": "firefox", "wm_name": ""}, 0.0)
    store.set_active_profile("leitura")
    with structlog.testing.capture_logs() as diario:
        for i in range(60):
            sw._tick(dict(janela), 1.0 + 0.5 * i)
    assert store.active_profile == "leitura"
    assert not [r for r in diario if r["event"] == "profile_autoswitch"]
    ditos = [r for r in diario if r["event"] == "autoswitch_lancador_nao_ativa_perfil"]
    assert [r["wm_class"] for r in ditos] == [janela["wm_class"]], "o log diz uma vez por janela"


@pytest.mark.usefixtures("perfis_isolados")
@pytest.mark.parametrize("janela", JANELAS_DE_LANCADOR, ids=lambda j: j["wm_class"])
def test_o_lancador_nao_solta_o_modo_jogo_padrao(
    monkeypatch: pytest.MonkeyPatch, janela: dict[str, str]
) -> None:
    """D-1410-O-PERFIL-FICA-NO-ULTIMO-JOGO: o jogo sem perfil próprio sai, e a Steam não tira o pad.

    O modo jogo padrão solto é o pad que some, a Navegação de fato. A janela
    do lançador não o solta; a janela que não é de lançador continua soltando.
    """
    _a_escolha(monkeypatch, "")
    manager, store = _bancada([*_a_navegacao_dos_lancadores()])
    soltou: list[str] = []
    ligou: list[str] = []

    def _liga(*, wm_class: str) -> str:
        ligou.append(wm_class)
        return "aplicado"

    def _solta(*, wm_class: str) -> str:
        soltou.append(wm_class)
        return "aplicado"

    sw = AutoSwitcher(
        manager=manager,
        window_reader=lambda: {},
        store=store,
        jogo_vivo_reader=lambda: None,
        modo_jogo_padrao_applier=_liga,
        modo_jogo_padrao_reverter=_solta,
    )
    sw._tick({"wm_class": OUTRO_JOGO, "wm_name": "Lure"}, 0.0)
    assert ligou == [OUTRO_JOGO], "premissa: o jogo sem perfil liga o modo jogo padrão"
    for i in range(30):
        sw._tick(dict(janela), 1.0 + 0.5 * i)
    assert soltou == []
    sw._tick({"wm_class": "com.system76.CosmicTerm", "wm_name": "Terminal"}, 20.0)
    assert soltou == ["com.system76.CosmicTerm"]


@pytest.mark.usefixtures("perfis_isolados")
def test_o_jogo_em_cena_com_a_steam_na_frente_leva_o_perfil(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Outro jogo que inicia com a Steam na frente (a tela de carga) leva o perfil dele."""
    _a_escolha(monkeypatch, "")
    manager, store = _bancada([
        _perfil("sackboy", janela=CLASSE_DO_JOGO, prioridade=90),
        _perfil("lure", janela=OUTRO_JOGO, prioridade=80),
        *_a_navegacao_dos_lancadores(),
    ])
    em_cena: list[int | None] = [None]
    sw = AutoSwitcher(
        manager=manager,
        window_reader=lambda: {},
        store=store,
        jogo_vivo_reader=lambda: None,
        jogo_em_cena_reader=lambda: em_cena[0],
    )
    sw._tick(dict(JANELA_DO_JOGO), 0.0)
    sw._tick(dict(JANELA_DO_JOGO), 1.0)
    assert store.active_profile == "sackboy"
    for i in range(10):
        sw._tick({"wm_class": "steam", "wm_name": ""}, 2.0 + 0.5 * i)
    assert store.active_profile == "sackboy"
    em_cena[0] = int(OUTRO_JOGO.removeprefix("steam_app_"))
    for i in range(10):
        sw._tick({"wm_class": "steam", "wm_name": ""}, 10.0 + 0.5 * i)
    assert store.active_profile == "lure"


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
