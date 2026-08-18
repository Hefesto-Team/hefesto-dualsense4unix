"""FEAT-POINT-AND-CLICK-01 — política de `Daemon.apply_profile_suppression`.

Semântica sob teste (docstring do método é a fonte canônica):
  - Perfil com suppress=True liga o modo-jogo (idempotente: sem flush/notify
    repetido quando já ligado por perfil).
  - Perfil sem o campo (False) LIBERA somente supressão que veio de perfil.
  - Toggle MANUAL (hotkey/IPC/GUI) há menos de MANUAL_PROFILE_LOCK_SEC congela
    a supressão nas duas direções (relógio fake).
  - Lock expirado: perfil ADOTA supressão manual antiga (desired=True) e passa
    a poder liberá-la; desired=False sem adoção não reverte o gesto manual.
  - R-02 (23/07): LIBERAR é uma decisão, e um catch-all não tem autoridade para
    tomá-la. Sem essa guarda, o `vitoria` (MatchAny, suppress=False por default)
    soltava a emulação de desktop DENTRO do jogo — mouse/teclado emulado
    voltando a disputar com o jogo enquanto ela jogava. Mesma regra do modo.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import lifecycle as lifecycle_mod
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.state_store import MANUAL_PROFILE_LOCK_SEC
from hefesto_dualsense4unix.testing import FakeController


class _FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def monotonic(self) -> float:
        return self.now

    def advance(self, sec: float) -> None:
        self.now += sec


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _FakeClock:
    """Relógio fake injetado no módulo lifecycle (não toca o time global)."""
    fake = _FakeClock()
    monkeypatch.setattr(
        lifecycle_mod, "time", SimpleNamespace(monotonic=fake.monotonic)
    )
    return fake


@pytest.fixture(autouse=True)
def _stub_notifier(monkeypatch: pytest.MonkeyPatch) -> None:
    """BUG-TEST-DBUS-NOTIFY-NONHERMETIC-01: `set_emulation_suppressed` notifica
    SEMPRE (deliberadamente sem o opt-in de notificações). Sem este stub, cada
    teste abria uma conexão real com o D-Bus de sessão e disparava popups
    'Modo jogo ligado/desligado' na tela da usuária em COSMIC — e podia travar
    até 2s por chamada se o notificador estivesse lento. Stub silencioso por
    padrão; testes que precisam observar a notificação sobrepõem depois."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.desktop_notifications."
        "notify_emulation_suppressed",
        lambda _estado: None,
    )


@pytest.fixture
def daemon() -> Daemon:
    return Daemon(controller=FakeController())


def _perfil(*, catch_all: bool = False) -> Any:
    """Perfil de teste — específico por default (R-02)."""
    from hefesto_dualsense4unix.profiles.schema import MatchAny, MatchCriteria, Profile

    return Profile(
        name="teste_supressao",
        match=MatchAny() if catch_all else MatchCriteria(window_class=["firefox"]),
        priority=10,
    )


def test_perfil_liga_supressao(clock: _FakeClock, daemon: Daemon) -> None:
    daemon.apply_profile_suppression(True)
    assert daemon._emulation_suppressed is True
    assert daemon._suppress_from_profile is True


def test_perfil_sem_campo_libera_supressao_de_perfil(
    clock: _FakeClock, daemon: Daemon
) -> None:
    daemon.apply_profile_suppression(True, profile=_perfil())
    daemon.apply_profile_suppression(False, profile=_perfil())
    assert daemon._emulation_suppressed is False
    assert daemon._suppress_from_profile is False


def test_perfil_false_sem_supressao_ativa_e_noop(
    clock: _FakeClock, daemon: Daemon
) -> None:
    daemon.apply_profile_suppression(False)
    assert daemon._emulation_suppressed is False


def test_idempotente_sem_notificacao_repetida(
    clock: _FakeClock, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Autoswitch reativa o mesmo perfil a cada foco — sem flush/notify em loop."""
    calls: list[bool] = []
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.desktop_notifications."
        "notify_emulation_suppressed",
        lambda estado: calls.append(estado),
    )
    daemon.apply_profile_suppression(True)
    daemon.apply_profile_suppression(True)
    daemon.apply_profile_suppression(True)
    assert calls == [True]


def test_toggle_manual_recente_congela_liga(
    clock: _FakeClock, daemon: Daemon
) -> None:
    """Usuária desligou o modo-jogo na mão; perfil não religa dentro do lock."""
    daemon.set_emulation_suppressed(False)  # gesto manual carimba o timestamp
    clock.advance(MANUAL_PROFILE_LOCK_SEC - 1.0)
    daemon.apply_profile_suppression(True)
    assert daemon._emulation_suppressed is False


def test_toggle_manual_recente_congela_libera(
    clock: _FakeClock, daemon: Daemon
) -> None:
    """Usuária ligou o modo-jogo na mão; perfil não libera dentro do lock."""
    daemon.set_emulation_suppressed(True)
    clock.advance(MANUAL_PROFILE_LOCK_SEC - 1.0)
    daemon.apply_profile_suppression(False)
    assert daemon._emulation_suppressed is True


def test_lock_expira_e_perfil_adota_supressao_manual(
    clock: _FakeClock, daemon: Daemon
) -> None:
    """Após o lock, perfil com suppress=True adota o estado manual — e o
    perfil seguinte (sem o campo) pode liberá-lo (UX do autoswitch dono)."""
    daemon.set_emulation_suppressed(True)
    clock.advance(MANUAL_PROFILE_LOCK_SEC + 1.0)
    daemon.apply_profile_suppression(True, profile=_perfil())
    assert daemon._suppress_from_profile is True
    daemon.apply_profile_suppression(False, profile=_perfil())
    assert daemon._emulation_suppressed is False


def test_lock_expirado_nao_reverte_supressao_manual_sem_adocao(
    clock: _FakeClock, daemon: Daemon
) -> None:
    """Supressão de origem manual (sem perfil que a adote) fica intocada:
    quem ligou na mão, desliga na mão."""
    daemon.set_emulation_suppressed(True)
    clock.advance(MANUAL_PROFILE_LOCK_SEC + 1.0)
    daemon.apply_profile_suppression(False)
    assert daemon._emulation_suppressed is True


def test_toggle_manual_reseta_origem_de_perfil(
    clock: _FakeClock, daemon: Daemon
) -> None:
    """Perfil suprimiu; usuária desligou na mão → perfis param de mexer
    (dentro do lock) e a origem deixa de ser 'perfil'."""
    daemon.apply_profile_suppression(True)
    clock.advance(1.0)
    daemon.set_emulation_suppressed(False)  # gesto manual
    assert daemon._suppress_from_profile is False
    clock.advance(MANUAL_PROFILE_LOCK_SEC + 1.0)
    # Lock expirou; perfil sem o campo não tem o que liberar (origem manual
    # já liberou) e perfil com o campo pode religar normalmente.
    daemon.apply_profile_suppression(True)
    assert daemon._emulation_suppressed is True


def test_boot_sem_gesto_manual_nao_trava_restore(
    clock: _FakeClock, daemon: Daemon
) -> None:
    """_suppress_manual_ts nasce em -inf: o restore no boot aplica direto
    (mesmo com monotonic pequeno — relógios fake/containers)."""
    clock.now = 5.0  # monotonic "recém-ligado"
    daemon.apply_profile_suppression(True)
    assert daemon._emulation_suppressed is True


# --- apply_profile_mouse: lock manual da emulação (BUG-PROFILE-MOUSE-KILLS-GAMEPAD-01)


def test_apply_profile_mouse_respeita_lock_manual(
    clock: _FakeClock, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Um gamepad (ou mouse) ligado NA MÃO há <30s NÃO é mexido por um perfil
    point-and-click focado pelo autoswitch — não sequestra o gamepad no jogo."""
    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        daemon, "set_mouse_emulation", lambda *a, **k: calls.append((a, k)) or True
    )
    daemon._emu_manual_ts = clock.now  # gesto manual AGORA (dentro do lock)
    clock.advance(1.0)  # 1s depois, ainda dentro dos 30s
    daemon.apply_profile_mouse(True, 8, 1)
    assert calls == []  # lock ativo → perfil não tocou na emulação


def test_apply_profile_mouse_aplica_apos_lock_expirar(
    clock: _FakeClock, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lock expirado (>30s): o perfil ADOTA o estado e liga a emulação."""
    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        daemon, "set_mouse_emulation", lambda *a, **k: calls.append((a, k)) or True
    )
    daemon._emu_manual_ts = clock.now
    clock.advance(MANUAL_PROFILE_LOCK_SEC + 1.0)  # lock expirou
    daemon.apply_profile_mouse(True, 8, 1)
    assert len(calls) == 1
    assert calls[0][0] == (True, 8, 1)
    assert calls[0][1].get("origin") == "profile"  # não re-carimba o lock manual


def test_apply_profile_mouse_idempotente_so_ajusta_velocidade(
    clock: _FakeClock, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Com o mouse JÁ ligado (config True + device vivo), ativar um perfil de
    mouse não recria o device — só atualiza a velocidade (evita tear-down)."""
    daemon.config.mouse_emulation_enabled = True  # já ligado…
    daemon._mouse_device = object()  # …e device vivo
    set_calls: list[Any] = []
    speed_calls: list[Any] = []
    monkeypatch.setattr(
        daemon, "set_mouse_emulation", lambda *a, **k: set_calls.append((a, k)) or True
    )
    monkeypatch.setattr(
        daemon, "set_mouse_speed", lambda *a, **k: speed_calls.append((a, k)) or True
    )
    # _emu_manual_ts nasce em -inf → sem lock.
    daemon.apply_profile_mouse(True, 9, 2)
    assert set_calls == []  # não recriou o device
    assert len(speed_calls) == 1  # só ajustou a velocidade


def test_apply_profile_mouse_recupera_config_stale_sem_device(
    clock: _FakeClock, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BUG-PROFILE-MOUSE-IDEMPOTENT-STALE-CONFIG-01: config diz ligado mas o
    device morreu (start falhou no boot) — ativar o perfil (re)liga de fato,
    não trata como idempotente. Auto-recuperação por ativação de perfil."""
    daemon.config.mouse_emulation_enabled = True  # config stale…
    daemon._mouse_device = None  # …mas device morto
    set_calls: list[Any] = []
    speed_calls: list[Any] = []
    monkeypatch.setattr(
        daemon, "set_mouse_emulation", lambda *a, **k: set_calls.append((a, k)) or True
    )
    monkeypatch.setattr(
        daemon, "set_mouse_speed", lambda *a, **k: speed_calls.append((a, k)) or True
    )
    daemon.apply_profile_mouse(True, 8, 1)
    assert len(set_calls) == 1  # (re)ligou de verdade
    assert set_calls[0][0] == (True, 8, 1)
    assert speed_calls == []  # não caiu no ramo idempotente


def test_catch_all_nao_libera_supressao_de_perfil(
    clock: _FakeClock, daemon: Daemon
) -> None:
    """R-02: o perfil do jogo suprimiu; o catch-all não pode soltar.

    Cenário medido: ela abre o Sackboy (perfil com suppress=True), alt-tabeia
    ou abre o Mullet Mad Jack (sem perfil) → o catch-all `vitoria` entrava com
    suppress=False e liberava a emulação de desktop no meio do jogo.
    """
    daemon.apply_profile_suppression(True, profile=_perfil())
    daemon.apply_profile_suppression(False, profile=_perfil(catch_all=True))
    assert daemon._emulation_suppressed is True
    assert daemon._suppress_from_profile is True


def test_janela_de_jogo_em_foco_congela_a_liberacao(
    clock: _FakeClock, daemon: Daemon
) -> None:
    """2ª guarda: nem perfil específico solta a supressão com jogo em foco."""
    daemon.apply_profile_suppression(True, profile=_perfil())
    daemon.store.record_window_detect_read("teste", "steam_app_2111190")
    daemon.apply_profile_suppression(False, profile=_perfil())
    assert daemon._emulation_suppressed is True
