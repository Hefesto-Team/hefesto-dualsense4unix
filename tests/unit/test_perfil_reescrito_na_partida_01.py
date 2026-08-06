"""PERFIL-REESCRITO-NA-PARTIDA-01 (leva de 05/08) — o perfil dela era reescrito
sozinho no meio da partida.

Seis defeitos medidos no journal dela, um bloco de testes cada. Todos herméticos:
`FakeController`, `StateStore` real, `ProfileManager` real e o diretório de
perfis isolado em `tmp_path` — nenhum toca hardware, D-Bus ou a `~/.config` dela.

1. **a crença do autoswitch nunca era sincronizada.** `_current_profile` só era
   escrito pelo commit do próprio `_activate`; uma troca MANUAL dela não o
   atualizava, e o autoswitch "entrava" num perfil que já era o ativo, pisando
   tudo de novo. Prova no journal: `profile_autoswitch from_=None
   to=sackboy_nativo` com outro perfil ativo havia horas.
2. **a supressão de emulação era uma armadilha de mão única.** O ramo que LIGA
   não tinha o gate de catch-all que o ramo que LIBERA tem. `sackboy_nativo`
   (catch-all, `suppress_desktop_emulation: true`, o disco dela hoje) ligava a
   supressão e nenhum outro catch-all conseguia desligá-la.
3. **a política de rumble não tinha guarda nenhuma** — nem `catch_all_sem_opiniao`
   nem `janela_de_jogo_em_foco`, que o `mode` e a supressão já tinham. Medido:
   `profile_rumble_policy_reverted` DENTRO da sessão de jogo dela.
4. **o relatório da ativação omitia o que não entrou** — as categorias travadas
   na mão e o modo jogo padrão. A janela respondia "ativado" e a usuária não
   tinha como saber que o gatilho dela não fora aplicado.
5. **o log só contava metade**: `profile_autoswitch` filtrava por `adiado*`, e
   `ignorado_*`/`falhou` nunca apareciam no journal.
6. **sair do Modo Nativo não restaurava modo, política de rumble nem
   alto-falante** — a rota do `_reapply_last_profile` era a única das quatro que
   montava o `ProfileManager` sem esses appliers.

**Mordida verificada em 05/08**, arrancando cada cura e devolvendo. Reprovam com
o produto de ontem, nesta ordem: item 1 →
`test_ativacao_manual_seguida_de_tique_com_o_mesmo_candidato_nao_reativa`;
item 2 → `test_catch_all_com_suppress_true_nao_liga_a_supressao` e
`test_o_disco_dela_dois_catch_all_nao_prendem_a_emulacao`; item 3 →
`test_catch_all_nao_reverte_a_politica_de_rumble` e
`test_janela_de_jogo_em_foco_nao_reverte_a_politica_de_rumble`; item 4 →
`test_relatorio_registra_as_categorias_travadas_na_mao` e
`test_relatorio_do_autoswitch_carrega_o_modo_jogo_padrao`; item 5 →
`test_log_do_autoswitch_reporta_estados_ignorados`; item 6 →
`test_sair_do_nativo_restaura_a_politica_de_rumble_do_perfil` e
`test_sair_do_nativo_aplica_as_demais_secoes_de_modo`.

**Honestidade sobre o resto.** Os demais casos deste arquivo passam nos DOIS
estados, e não é esquecimento: são GUARDAS da cura — o que ela não pode ter
quebrado (a troca automática continua acontecendo, quem tem opinião continua
mandando, a reversão legítima no desktop continua ocorrendo, o lock de gesto
manual continua vencendo, o relatório não inventa seção, e sair do Modo Nativo
continua sem religar o nativo). Estão marcados como tal na docstring de cada um.
"""
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
    IGNORADO_TRAVA_MANUAL,
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

#: A janela do jogo dela no journal (Sackboy, `steam_app_1599660`).
JANELA_DO_JOGO = {"wm_class": "steam_app_1599660", "wm_name": "Sackboy"}


@pytest.fixture
def perfis_isolados(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Diretório de perfis em `tmp_path` (mesmo padrão do `test_autoswitch`).

    Obrigatório em todo teste que carregue ou salve perfil: `xdg_paths` resolve
    o `config_dir` num `PlatformDirs` de módulo, avaliado no import, e o
    isolamento XDG do `conftest` não o alcança — sem este monkeypatch a suíte
    escreve `.lock` no diretório de perfis REAL dela (CANÁRIO-FS-01).
    """
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
    """BUG-TEST-DBUS-NOTIFY-NONHERMETIC-01: `set_emulation_suppressed` notifica
    SEMPRE. Sem este stub, cada teste abre uma conexão real com o D-Bus de
    sessão e joga um popup na tela dela no meio da suíte."""
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


# ---------------------------------------------------------------------------
# 1) A crença do autoswitch é sincronizada com o estado REAL
# ---------------------------------------------------------------------------


def test_ativacao_manual_seguida_de_tique_com_o_mesmo_candidato_nao_reativa(
    perfis_isolados: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A MORDIDA do item 1: ela escolhe o perfil na mão, o autoswitch tica com
    o MESMO candidato e não reescreve nada.

    Sem a cura, `_current_profile` continua `None` (o autoswitch nunca ativou
    nada nesta sessão) e o tique estável ativa `sackboy_nativo` de novo —
    gatilhos, LEDs, modo e política de rumble por cima do que ela acabou de
    escolher. É o `profile_autoswitch from_=None to=sackboy_nativo` do journal.
    """
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
    """A guarda da cura: sincronizar não pode virar "o autoswitch parou".

    Com OUTRO perfil ativo no store, focar a janela do jogo continua trocando —
    senão a cura do item 1 teria matado o automatismo inteiro.
    """
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


# ---------------------------------------------------------------------------
# 2) A armadilha de mão única da supressão
# ---------------------------------------------------------------------------


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
    """MORDIDA do item 2, metade B: o estado medido no disco dela.

    `sackboy_nativo` é catch-all e pede `suppress: true`; `vitoria` é catch-all
    e não pede nada. Antes da cura, o primeiro ligava a supressão e o segundo
    era barrado pelo gate de reversão (R-02) — a emulação de mouse/teclado
    ficava morta até um gesto manual dela. Simétrico, o estado nem chega a
    existir.
    """
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


# ---------------------------------------------------------------------------
# 3) A política de rumble ganha as guardas dos irmãos
# ---------------------------------------------------------------------------


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
    """MORDIDA do item 3, guarda B (`janela_de_jogo_em_foco`).

    O evento medido: `profile_rumble_policy_reverted` DENTRO da sessão de jogo,
    com a vibração mudando por causa de um perfil que só passou por ali.
    """
    daemon = _daemon()
    daemon.apply_profile_rumble_policy("max", None, profile=_perfil("jogo"))
    # A leitura CRUA da janela é o que `_janela_de_jogo_em_foco` consulta
    # (NUMA-01) — o mesmo caminho por onde o poll do autoswitch a grava.
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


# ---------------------------------------------------------------------------
# 4) O relatório conta o que NÃO entrou
# ---------------------------------------------------------------------------


def test_relatorio_registra_as_categorias_travadas_na_mao(
    perfis_isolados: Path,
) -> None:
    """MORDIDA do item 4: o que a trava manual silencia entra no relatório.

    `ProfileManager.apply` já sabia quais categorias iria pular — emitia `None`
    no `OutputSpec` e seguia. Nada disso chegava a quem pergunta pelo resultado
    da ativação, e a janela respondia "ativado" sem poder dizer que o gatilho e
    a cor do perfil não entraram.
    """
    manager, store = _bancada([_perfil("sackboy_nativo")])
    store.mark_manual_trigger_active("trigger")
    store.mark_manual_trigger_active("led")

    relatorio: dict[str, str] = {}
    manager.activate("sackboy_nativo", origin="autoswitch", relatorio=relatorio)

    assert relatorio["trigger"] == IGNORADO_TRAVA_MANUAL
    assert relatorio["led"] == IGNORADO_TRAVA_MANUAL


def test_sem_trava_o_relatorio_nao_inventa_secao_ignorada(
    perfis_isolados: Path,
) -> None:
    """A guarda: o relatório só afirma o que este código de fato silenciou."""
    manager, _store = _bancada([_perfil("sackboy_nativo")])

    relatorio: dict[str, str] = {}
    manager.activate("sackboy_nativo", origin="autoswitch", relatorio=relatorio)

    assert "trigger" not in relatorio
    assert "led" not in relatorio


def test_relatorio_do_autoswitch_carrega_o_modo_jogo_padrao(
    perfis_isolados: Path,
) -> None:
    """MORDIDA do item 4, segunda metade: o MODO JOGO PADRÃO deixa rastro.

    É o único eixo que o tique mexe fora do `ProfileManager` — o daemon liga o
    vpad quando é jogo e ninguém opina. O estado devolvido pelo par era jogado
    fora; agora entra no relatório da ativação, com o mesmo vocabulário.
    """
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

    # Tique 1: jogo sem perfil próprio — o veto R-21 recusa o catch-all e o
    # daemon liga o modo jogo padrão.
    sw._tick(dict(JANELA_DO_JOGO), 0.0)
    assert sw._estado_modo_jogo_padrao == APLICADO

    # Ela sai do jogo: o par SOLTA o modo, e o estado entra no relatório da
    # ativação que acontece neste mesmo tique.
    with structlog.testing.capture_logs() as registros:
        sw._tick({"wm_class": "firefox"}, 10.0)
        sw._tick({"wm_class": "firefox"}, 20.0)

    trocas = [r for r in registros if r["event"] == "profile_autoswitch"]
    assert trocas, "o autoswitch não trocou de perfil"
    assert f"modo_jogo_padrao={IGNORADO_GESTO_DELA}" in trocas[-1]["secoes"]


# ---------------------------------------------------------------------------
# 5) O log do autoswitch para de esconder metade do relatório
# ---------------------------------------------------------------------------


def test_log_do_autoswitch_reporta_estados_ignorados(
    perfis_isolados: Path,
) -> None:
    """MORDIDA do item 5: `ignorado_*` aparece no `profile_autoswitch`.

    O filtro só deixava passar `adiado*` — justamente os estados em que a
    ativação "deu certo" sem aplicar a seção ficavam invisíveis no journal.
    """
    manager, store = _bancada([_perfil("navegacao", janela="firefox")])
    store.mark_manual_trigger_active("trigger")
    sw = AutoSwitcher(manager=manager, window_reader=lambda: {}, store=store)
    # A trava suprimiria o `_activate` inteiro (BUG-MOUSE-TRIGGERS-01); aqui
    # interessa o RELATÓRIO, então o gate de supressão fica fora do caminho.
    store.clear_manual_trigger_active()
    manager.store.mark_manual_trigger_active("trigger")
    sw.store = None

    with structlog.testing.capture_logs() as registros:
        sw._tick({"wm_class": "firefox"}, 0.0)
        sw._tick({"wm_class": "firefox"}, 5.0)

    trocas = [r for r in registros if r["event"] == "profile_autoswitch"]
    assert trocas, "o autoswitch não trocou de perfil"
    assert f"trigger={IGNORADO_TRAVA_MANUAL}" in trocas[-1]["secoes"]
    # O campo histórico continua onde estava (é o que a leitura do journal já
    # procura), e continua sendo só o subconjunto dos adiamentos.
    assert trocas[-1]["adiado"] == []


# ---------------------------------------------------------------------------
# 6) Sair do Modo Nativo restaura as seções que faltavam
# ---------------------------------------------------------------------------


def test_sair_do_nativo_restaura_a_politica_de_rumble_do_perfil(
    perfis_isolados: Path,
) -> None:
    """MORDIDA do item 6: a política de rumble do perfil volta ao sair.

    Sem os appliers injetados, `_reapply_last_profile` reaplicava só gatilhos,
    LEDs e teclado — a política de rumble ficava como o jogo a deixou.
    """
    daemon = _daemon()
    save_profile(_perfil("sackboy_nativo", rumble={"policy": "max"}))
    daemon.store.set_active_profile("sackboy_nativo")
    daemon.config.rumble_policy = "economia"

    daemon._reapply_last_profile()

    assert daemon.config.rumble_policy == "max"


def test_sair_do_nativo_nao_religa_o_modo_nativo_do_perfil(
    perfis_isolados: Path,
) -> None:
    """A decisão da FEAT-PROFILE-MODE-01 continua de pé, e agora tem teste.

    Este caminho roda ao DESLIGAR o Modo Nativo (`_native_mode` já é False
    quando chegamos aqui): um perfil com `mode.kind=native` seria religado no
    mesmo instante, desfazendo o gesto dela. O embrulho barra só esse caso.
    """
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
