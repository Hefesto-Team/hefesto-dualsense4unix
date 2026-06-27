"""FEAT-HOTKEY-PROFILE-CYCLE-01 — os combos PS+D-pad (next=PS+↑, prev=PS+↓)
ciclam o perfil ativo via ProfileManager.activate (o mesmo caminho do
profile.switch IPC), com feedback de lightbar e lock manual contra o autoswitch.

Antes ficavam disabled_until_wired (on_next/on_prev = None, combos = ()). Estes
testes provam o wiring (start_hotkey_manager liga os combos + callbacks) e a
lógica de ciclo (próximo/anterior com wrap-around, skip com <2 perfis).
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
    build_profile_cycle_callback,
    start_hotkey_manager,
)
from hefesto_dualsense4unix.integrations.hotkey_daemon import (
    DEFAULT_COMBO_NEXT,
    DEFAULT_COMBO_PREV,
)

# --- fakes -----------------------------------------------------------------


class _FakeProfile:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeStore:
    def __init__(self, active: str | None) -> None:
        self.active_profile = active
        self.cleared = False
        self.locked: float | None = None

    def clear_manual_trigger_active(self) -> None:
        self.cleared = True

    def mark_manual_profile_lock(self, t: float) -> None:
        self.locked = t

    def set_active_profile(self, name: str | None) -> None:
        self.active_profile = name


class _FakeController:
    def __init__(self) -> None:
        self.leds: list[tuple[int, int, int]] = []

    def set_led(self, color: tuple[int, int, int]) -> None:
        self.leds.append(color)


class _FakeManager:
    """Substitui ProfileManager: 3 perfis a/b/c, registra activate."""

    profiles = ("a", "b", "c")

    def __init__(
        self, controller: Any = None, store: Any = None, keyboard_device: Any = None
    ) -> None:
        self.store = store
        self.activated: list[str] = []

    def list_profiles(self) -> list[_FakeProfile]:
        return [_FakeProfile(n) for n in self.profiles]

    def activate(self, name: str) -> _FakeProfile:
        self.activated.append(name)
        if self.store is not None:
            self.store.active_profile = name
        return _FakeProfile(name)


class _FakeDaemon:
    def __init__(self, active: str | None) -> None:
        self.controller = _FakeController()
        self.store = _FakeStore(active)
        self._keyboard_device = None

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        return fn(*args)


def _patch_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hefesto_dualsense4unix.profiles.manager.ProfileManager", _FakeManager
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.save_active_marker", lambda _n: None
    )


# --- lógica de ciclo -------------------------------------------------------


@pytest.mark.asyncio
async def test_cycle_next_avanca(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_manager(monkeypatch)
    d = _FakeDaemon(active="a")
    await build_profile_cycle_callback(d, +1)()
    assert d.store.active_profile == "b"


@pytest.mark.asyncio
async def test_cycle_next_da_wrap_around(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_manager(monkeypatch)
    d = _FakeDaemon(active="c")  # último → volta pro primeiro
    await build_profile_cycle_callback(d, +1)()
    assert d.store.active_profile == "a"


@pytest.mark.asyncio
async def test_cycle_prev_retrocede(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_manager(monkeypatch)
    d = _FakeDaemon(active="b")
    await build_profile_cycle_callback(d, -1)()
    assert d.store.active_profile == "a"


@pytest.mark.asyncio
async def test_cycle_arma_lock_e_flasha(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gesto explícito: libera autoswitch + arma lock manual + flasha o lightbar
    (senão o autoswitch desfaz a troca no tick seguinte)."""
    _patch_manager(monkeypatch)
    d = _FakeDaemon(active="a")
    await build_profile_cycle_callback(d, +1)()
    assert d.store.cleared is True
    assert d.store.locked is not None
    assert d.controller.leds, "lightbar não flashou (sem feedback visível)"


@pytest.mark.asyncio
async def test_cycle_skip_com_menos_de_dois_perfis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_manager(monkeypatch)
    monkeypatch.setattr(_FakeManager, "profiles", ("solo",))
    d = _FakeDaemon(active="solo")
    await build_profile_cycle_callback(d, +1)()
    assert d.store.active_profile == "solo"  # inalterado
    assert not d.controller.leds  # nem flasha


@pytest.mark.asyncio
async def test_cycle_ativo_desconhecido_comeca_do_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_manager(monkeypatch)
    d = _FakeDaemon(active=None)  # nenhum ativo → idx 0, next = índice 1
    await build_profile_cycle_callback(d, +1)()
    assert d.store.active_profile == "b"


# --- wiring no subsystem ---------------------------------------------------


class _Cfg:
    ps_long_press_ms = 0
    ps_button_action = "steam"


class _WireDaemon:
    config = _Cfg()
    controller = None
    store = None
    _keyboard_device = None
    _hotkey_manager: Any = None


def test_start_hotkey_manager_liga_combos_e_callbacks() -> None:
    d = _WireDaemon()
    start_hotkey_manager(d)  # type: ignore[arg-type]
    mgr = d._hotkey_manager
    assert mgr is not None
    assert mgr.config.next_profile == DEFAULT_COMBO_NEXT
    assert mgr.config.prev_profile == DEFAULT_COMBO_PREV
    assert mgr.on_next is not None
    assert mgr.on_prev is not None
