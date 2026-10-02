"""FEAT-POINT-AND-CLICK-01 — política de `Daemon.apply_profile_suppression`."""
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
    """BUG-TEST-DBUS-NOTIFY-NONHERMETIC-01: `set_emulation_suppressed` notifica"""
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
    daemon.set_emulation_suppressed(False)
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
    """Após o lock, perfil com suppress=True adota o estado manual — e o"""
    daemon.set_emulation_suppressed(True)
    clock.advance(MANUAL_PROFILE_LOCK_SEC + 1.0)
    daemon.apply_profile_suppression(True, profile=_perfil())
    assert daemon._suppress_from_profile is True
    daemon.apply_profile_suppression(False, profile=_perfil())
    assert daemon._emulation_suppressed is False


def test_lock_expirado_nao_reverte_supressao_manual_sem_adocao(
    clock: _FakeClock, daemon: Daemon
) -> None:
    """Supressão de origem manual (sem perfil que a adote) fica intocada:"""
    daemon.set_emulation_suppressed(True)
    clock.advance(MANUAL_PROFILE_LOCK_SEC + 1.0)
    daemon.apply_profile_suppression(False)
    assert daemon._emulation_suppressed is True


def test_toggle_manual_reseta_origem_de_perfil(
    clock: _FakeClock, daemon: Daemon
) -> None:
    """Perfil suprimiu; usuária desligou na mão → perfis param de mexer"""
    daemon.apply_profile_suppression(True)
    clock.advance(1.0)
    daemon.set_emulation_suppressed(False)
    assert daemon._suppress_from_profile is False
    clock.advance(MANUAL_PROFILE_LOCK_SEC + 1.0)
    daemon.apply_profile_suppression(True)
    assert daemon._emulation_suppressed is True


def test_boot_sem_gesto_manual_nao_trava_restore(
    clock: _FakeClock, daemon: Daemon
) -> None:
    """_suppress_manual_ts nasce em -inf: o restore no boot aplica direto"""
    clock.now = 5.0
    daemon.apply_profile_suppression(True)
    assert daemon._emulation_suppressed is True


def test_apply_profile_mouse_respeita_lock_manual(
    clock: _FakeClock, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Um gamepad (ou mouse) ligado NA MÃO há <30s NÃO é mexido por um perfil"""
    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        daemon, "set_mouse_emulation", lambda *a, **k: calls.append((a, k)) or True
    )
    daemon._emu_manual_ts = clock.now
    clock.advance(1.0)
    daemon.apply_profile_mouse(True, 8, 1)
    assert calls == []


def test_apply_profile_mouse_aplica_apos_lock_expirar(
    clock: _FakeClock, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lock expirado (>30s): o perfil ADOTA o estado e liga a emulação."""
    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        daemon, "set_mouse_emulation", lambda *a, **k: calls.append((a, k)) or True
    )
    daemon._emu_manual_ts = clock.now
    clock.advance(MANUAL_PROFILE_LOCK_SEC + 1.0)
    daemon.apply_profile_mouse(True, 8, 1)
    assert len(calls) == 1
    assert calls[0][0] == (True, 8, 1)
    assert calls[0][1].get("origin") == "profile"


def test_apply_profile_mouse_idempotente_so_ajusta_velocidade(
    clock: _FakeClock, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Com o mouse JÁ ligado (config True + device vivo), ativar um perfil de"""
    daemon.config.mouse_emulation_enabled = True
    daemon._mouse_device = object()
    set_calls: list[Any] = []
    speed_calls: list[Any] = []
    monkeypatch.setattr(
        daemon, "set_mouse_emulation", lambda *a, **k: set_calls.append((a, k)) or True
    )
    monkeypatch.setattr(
        daemon, "set_mouse_speed", lambda *a, **k: speed_calls.append((a, k)) or True
    )
    daemon.apply_profile_mouse(True, 9, 2)
    assert set_calls == []
    assert len(speed_calls) == 1


def test_apply_profile_mouse_recupera_config_stale_sem_device(
    clock: _FakeClock, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BUG-PROFILE-MOUSE-IDEMPOTENT-STALE-CONFIG-01: config diz ligado mas o"""
    daemon.config.mouse_emulation_enabled = True
    daemon._mouse_device = None
    set_calls: list[Any] = []
    speed_calls: list[Any] = []
    monkeypatch.setattr(
        daemon, "set_mouse_emulation", lambda *a, **k: set_calls.append((a, k)) or True
    )
    monkeypatch.setattr(
        daemon, "set_mouse_speed", lambda *a, **k: speed_calls.append((a, k)) or True
    )
    daemon.apply_profile_mouse(True, 8, 1)
    assert len(set_calls) == 1
    assert set_calls[0][0] == (True, 8, 1)
    assert speed_calls == []


def test_catch_all_nao_libera_supressao_de_perfil(
    clock: _FakeClock, daemon: Daemon
) -> None:
    """R-02: o perfil do jogo suprimiu; o catch-all não pode soltar."""
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
