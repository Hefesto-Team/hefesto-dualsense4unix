"""PERFIL-REESCRITO-NA-PARTIDA-01 (leva de 05/08) — o perfil do usuário era reescrito"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.daemon import lifecycle as lifecycle_mod
from hefesto_dualsense4unix.daemon.lifecycle import (
    ADIADO_LOCK_MANUAL,
    APLICADO,
    IGNORADO_CATCH_ALL,
    IGNORADO_GESTO_DELA,
    IGNORADO_JANELA_DE_JOGO,
    Daemon,
    DaemonConfig,
)
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import (
    ProfileManager,
)
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)
from hefesto_dualsense4unix.testing import FakeController

JANELA_DO_JOGO = {"wm_class": "steam_app_1599660", "wm_name": "Sackboy"}


@pytest.fixture
def perfis_isolados(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Diretório de perfis em `tmp_path` (mesmo padrão do `test_autoswitch`)."""
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return alvo


@pytest.fixture(autouse=True)
def _sem_notificacao(monkeypatch: pytest.MonkeyPatch) -> None:
    """BUG-TEST-DBUS-NOTIFY-NONHERMETIC-01: `set_emulation_suppressed` notifica"""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.desktop_notifications."
        "notify_emulation_suppressed",
        lambda _estado: None,
    )


def _perfil(
    nome: str,
    *,
    catch_all: bool = False,
    janela: str | None = None,
    **extra: Any,
) -> Profile:
    dados: dict[str, Any] = {
        "match": MatchAny()
        if catch_all
        else MatchCriteria(window_class=[janela or f"{nome}_class"]),
        "priority": 0 if catch_all else 10,
        "triggers": TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Rigid", params=[0, 100]),
        ),
        "leds": LedsConfig(lightbar=(10, 20, 30)),
    }
    dados.update(extra)
    return Profile(name=nome, **dados)


def _bancada(perfis: list[Profile]) -> tuple[ProfileManager, StateStore]:
    for perfil in perfis:
        save_profile(perfil)
    fc = FakeController()
    fc.connect()
    store = StateStore()
    return ProfileManager(controller=fc, store=store), store


def _daemon() -> Daemon:
    return Daemon(controller=FakeController(), config=DaemonConfig())


def test_ativacao_manual_seguida_de_tique_com_o_mesmo_candidato_nao_reativa(
    perfis_isolados: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A MORDIDA do item 1: ela escolhe o perfil na mão, o autoswitch tica com"""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.save_last_profile",
        lambda _nome: None,
    )
    manager, store = _bancada(
        [_perfil("sackboy_nativo", janela="steam_app_1599660")]
    )
    sw = AutoSwitcher(manager=manager, window_reader=lambda: {}, store=store)

    manager.activate("sackboy_nativo", origin="manual")
    assert store.counter("profile.activated") == 1

    sw._tick(dict(JANELA_DO_JOGO), 0.0)
    sw._tick(dict(JANELA_DO_JOGO), 5.0)

    assert store.counter("profile.activated") == 1
    assert sw._current_profile == "sackboy_nativo"


def test_a_crenca_adota_o_perfil_ativo_antes_de_decidir(
    perfis_isolados: Path,
) -> None:
    """O mecanismo do item 1, isolado: basta o store dizer quem está ativo."""
    manager, store = _bancada([_perfil("sackboy_nativo")])
    sw = AutoSwitcher(manager=manager, window_reader=lambda: {}, store=store)
    assert sw._current_profile is None

    store.set_active_profile("sackboy_nativo")

    assert sw._perfil_corrente() == "sackboy_nativo"
    assert sw._current_profile == "sackboy_nativo"


def test_sincronizar_nao_congela_a_troca_para_outro_perfil(
    perfis_isolados: Path,
) -> None:
    """A guarda da cura: sincronizar não pode virar "o autoswitch parou"."""
    manager, store = _bancada(
        [
            _perfil("sackboy_nativo", janela="steam_app_1599660"),
            _perfil("navegacao", janela="firefox"),
        ]
    )
    sw = AutoSwitcher(manager=manager, window_reader=lambda: {}, store=store)
    store.set_active_profile("navegacao")

    sw._tick(dict(JANELA_DO_JOGO), 0.0)
    sw._tick(dict(JANELA_DO_JOGO), 5.0)

    assert store.active_profile == "sackboy_nativo"
    assert store.counter("profile.activated") == 1


def test_catch_all_com_suppress_true_nao_liga_a_supressao() -> None:
    """MORDIDA do item 2, metade A: ausência de regra não é ordem para LIGAR."""
    daemon = _daemon()
    estado = daemon.apply_profile_suppression(
        True, profile=_perfil("sackboy_nativo", catch_all=True)
    )
    assert estado == IGNORADO_CATCH_ALL
    assert daemon._emulation_suppressed is False
    assert daemon._suppress_from_profile is False


def test_o_disco_dela_dois_catch_all_nao_prendem_a_emulacao() -> None:
    """MORDIDA do item 2, metade B: o estado medido no disco do usuário."""
    daemon = _daemon()
    daemon.apply_profile_suppression(
        True, profile=_perfil("sackboy_nativo", catch_all=True)
    )
    daemon.apply_profile_suppression(
        False, profile=_perfil("vitoria", catch_all=True)
    )
    assert daemon._emulation_suppressed is False


def test_perfil_especifico_continua_ligando_e_liberando() -> None:
    """A guarda da cura: quem TEM opinião segue mandando nos dois sentidos."""
    daemon = _daemon()
    assert daemon.apply_profile_suppression(True, profile=_perfil("jogo")) == APLICADO
    assert daemon._emulation_suppressed is True

    assert (
        daemon.apply_profile_suppression(False, profile=_perfil("navegacao"))
        == APLICADO
    )
    assert daemon._emulation_suppressed is False


def test_chamada_direta_sem_perfil_preserva_o_comportamento_historico() -> None:
    """Perfil ausente é o chamador direto (CLI, dublê), não um catch-all."""
    daemon = _daemon()
    assert daemon.apply_profile_suppression(True) == APLICADO
    assert daemon._emulation_suppressed is True


def test_catch_all_nao_reverte_a_politica_de_rumble() -> None:
    """MORDIDA do item 3, guarda A (`catch_all_sem_opiniao`)."""
    daemon = _daemon()
    daemon.apply_profile_rumble_policy("max", None, profile=_perfil("jogo"))
    assert daemon.config.rumble_policy == "max"

    estado = daemon.apply_profile_rumble_policy(
        None, None, profile=_perfil("vitoria", catch_all=True)
    )

    assert estado == IGNORADO_CATCH_ALL
    assert daemon.config.rumble_policy == "max"
    assert daemon._rumble_policy_from_profile is True


def test_janela_de_jogo_em_foco_nao_reverte_a_politica_de_rumble() -> None:
    """MORDIDA do item 3, guarda B (`janela_de_jogo_em_foco`)."""
    daemon = _daemon()
    daemon.apply_profile_rumble_policy("max", None, profile=_perfil("jogo"))
    daemon.store.record_window_detect_read("xlib", "steam_app_1599660")

    estado = daemon.apply_profile_rumble_policy(
        None, None, profile=_perfil("navegacao")
    )

    assert estado == IGNORADO_JANELA_DE_JOGO
    assert daemon.config.rumble_policy == "max"


def test_reversao_legitima_no_desktop_continua_acontecendo() -> None:
    """A guarda da cura: com regra de verdade e sem jogo em foco, reverte."""
    daemon = _daemon()
    antes = daemon.config.rumble_policy
    daemon.apply_profile_rumble_policy("max", None, profile=_perfil("jogo"))

    estado = daemon.apply_profile_rumble_policy(
        None, None, profile=_perfil("navegacao")
    )

    assert estado == APLICADO
    assert daemon.config.rumble_policy == antes
    assert daemon._rumble_policy_from_profile is False


def test_o_lock_de_gesto_manual_continua_vencendo_as_guardas_novas() -> None:
    """Ordem preservada: o lock de 30 s é avaliado ANTES das guardas novas."""
    daemon = _daemon()
    daemon.apply_profile_rumble_policy("max", None, profile=_perfil("jogo"))
    daemon._emu_manual_ts = lifecycle_mod.time.monotonic()

    estado = daemon.apply_profile_rumble_policy(
        None, None, profile=_perfil("vitoria", catch_all=True)
    )

    assert estado == ADIADO_LOCK_MANUAL


def test_o_relatorio_nao_diz_mais_que_uma_secao_foi_travada(
    perfis_isolados: Path,
) -> None:
    """O item 4 mudou de resposta em 14/09/2026, e o teste mudou com ele."""
    manager, _store = _bancada([_perfil("sackboy_nativo")])

    relatorio: dict[str, str] = {}
    manager.activate("sackboy_nativo", origin="autoswitch", relatorio=relatorio)

    assert relatorio["trigger"] == "aplicado"
    assert relatorio["led"] == "aplicado"
    assert "ignorado_trava_manual" not in relatorio.values(), (
        f"o relatório voltou a falar em trava manual: {relatorio!r}"
    )


def test_sem_trava_o_relatorio_nao_inventa_secao_ignorada(
    perfis_isolados: Path,
) -> None:
    """A guarda: o relatório só afirma o que este código de fato silenciou."""
    manager, _store = _bancada([_perfil("sackboy_nativo")])

    relatorio: dict[str, str] = {}
    manager.activate("sackboy_nativo", origin="autoswitch", relatorio=relatorio)

    assert relatorio["trigger"] == "aplicado"
    assert relatorio["led"] == "aplicado"
    assert "ignorado_trava_manual" not in {relatorio["trigger"], relatorio["led"]}


def test_relatorio_do_autoswitch_carrega_o_modo_jogo_padrao(
    perfis_isolados: Path,
) -> None:
    """MORDIDA do item 4, segunda metade: o MODO JOGO PADRÃO deixa rastro."""
    manager, store = _bancada(
        [
            _perfil("navegacao", janela="firefox"),
            _perfil("vitoria", catch_all=True),
        ]
    )
    sw = AutoSwitcher(
        manager=manager,
        window_reader=lambda: {},
        store=store,
        modo_jogo_padrao_applier=lambda **_kw: APLICADO,
        modo_jogo_padrao_reverter=lambda **_kw: IGNORADO_GESTO_DELA,
    )

    sw._tick(dict(JANELA_DO_JOGO), 0.0)
    assert sw._estado_modo_jogo_padrao == APLICADO

    with structlog.testing.capture_logs() as registros:
        sw._tick({"wm_class": "firefox"}, 10.0)
        sw._tick({"wm_class": "firefox"}, 20.0)

    trocas = [r for r in registros if r["event"] == "profile_autoswitch"]
    assert trocas, "o autoswitch não trocou de perfil"
    assert f"modo_jogo_padrao={IGNORADO_GESTO_DELA}" in trocas[-1]["secoes"]


def test_log_do_autoswitch_reporta_estados_ignorados(
    perfis_isolados: Path,
) -> None:
    """MORDIDA do item 5: `ignorado_*` aparece no `profile_autoswitch`."""
    manager, store = _bancada(
        [
            _perfil("navegacao", janela="firefox"),
            _perfil("vitoria", catch_all=True),
        ]
    )
    sw = AutoSwitcher(
        manager=manager,
        window_reader=lambda: {},
        store=store,
        modo_jogo_padrao_applier=lambda **_kw: APLICADO,
        modo_jogo_padrao_reverter=lambda **_kw: IGNORADO_GESTO_DELA,
    )
    sw._tick(dict(JANELA_DO_JOGO), 0.0)

    with structlog.testing.capture_logs() as registros:
        sw._tick({"wm_class": "firefox"}, 10.0)
        sw._tick({"wm_class": "firefox"}, 20.0)

    trocas = [r for r in registros if r["event"] == "profile_autoswitch"]
    assert trocas, "o autoswitch não trocou de perfil"
    assert f"modo_jogo_padrao={IGNORADO_GESTO_DELA}" in trocas[-1]["secoes"], (
        "o log do autoswitch voltou a filtrar os `ignorado_*` e a contar só "
        f"metade do relatório: {trocas[-1]['secoes']!r}"
    )
    assert trocas[-1]["adiado"] == []


def test_sair_do_nativo_restaura_a_politica_de_rumble_do_perfil(
    perfis_isolados: Path,
) -> None:
    """MORDIDA do item 6: a política de rumble do perfil volta ao sair."""
    daemon = _daemon()
    save_profile(_perfil("sackboy_nativo", rumble={"policy": "max"}))
    daemon.store.set_active_profile("sackboy_nativo")
    daemon.config.rumble_policy = "economia"

    daemon._reapply_last_profile()

    assert daemon.config.rumble_policy == "max"


def test_sair_do_nativo_nao_religa_o_modo_nativo_do_perfil(
    perfis_isolados: Path,
) -> None:
    """A decisão da FEAT-PROFILE-MODE-01 continua de pé, e agora tem teste."""
    daemon = _daemon()
    save_profile(_perfil("sackboy_nativo", mode={"kind": "native"}))
    daemon.store.set_active_profile("sackboy_nativo")

    daemon._reapply_last_profile()

    assert daemon._native_mode is False
    assert (
        daemon._mode_applier_ao_sair_do_nativo(
            _perfil("sackboy_nativo", mode={"kind": "native"}).mode
        )
        == IGNORADO_GESTO_DELA
    )


def test_sair_do_nativo_aplica_as_demais_secoes_de_modo(
    perfis_isolados: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O embrulho barra `native` e SÓ ele — `gamepad`/`desktop` passam."""
    daemon = _daemon()
    vistos: list[str | None] = []
    monkeypatch.setattr(
        daemon,
        "apply_profile_mode",
        lambda mode, *, profile=None, origin="autoswitch": (
            vistos.append(getattr(mode, "kind", None)) or APLICADO
        ),
    )
    save_profile(_perfil("coop", mode={"kind": "gamepad"}))
    daemon.store.set_active_profile("coop")

    daemon._reapply_last_profile()

    assert vistos == ["gamepad"]
