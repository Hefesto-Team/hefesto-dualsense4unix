"""FEAT-HOTKEY-PROFILE-CYCLE-01 — os combos PS+D-pad (next=PS+↑, prev=PS+↓)
ciclam o perfil ativo via ProfileManager.activate (o mesmo caminho do
profile.switch IPC), com feedback de lightbar e lock manual contra o autoswitch.

Antes ficavam disabled_until_wired (on_next/on_prev = None, combos = ()). Estes
testes provam o wiring (start_hotkey_manager liga os combos + callbacks) e a
lógica de ciclo (próximo/anterior com wrap-around, skip com <2 perfis).
"""
from __future__ import annotations

from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
    build_profile_cycle_callback,
    start_hotkey_manager,
)
from hefesto_dualsense4unix.integrations.hotkey_daemon import (
    DEFAULT_COMBO_NEXT,
    DEFAULT_COMBO_PREV,
)


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
    """A rota do aviso: pinta sem lembrar e devolve a cor resolvida."""

    def __init__(self) -> None:
        self.leds: list[tuple[int, int, int]] = []
        self.devolvidas = 0
        self.gravadas: list[tuple[int, int, int]] = []

    def pintar_lightbar_sem_lembrar(self, color: tuple[int, int, int]) -> int:
        self.leds.append(color)
        return 1

    def restaurar_lightbar_do_perfil(self) -> int:
        self.devolvidas += 1
        return 1

    def set_led(self, color: tuple[int, int, int]) -> None:
        self.gravadas.append(color)


class _FakeManager:
    """Substitui ProfileManager: 3 perfis a/b/c, registra activate."""

    profiles = ("a", "b", "c")
    instances: ClassVar[list[_FakeManager]] = []

    def __init__(
        self,
        controller: Any = None,
        store: Any = None,
        keyboard_device: Any = None,
        **kwargs: Any,
    ) -> None:
        self.store = store
        self.activated: list[str] = []
        self.origins: list[str] = []
        self.mouse_applier = kwargs.get("mouse_applier")
        self.suppression_applier = kwargs.get("suppression_applier")
        self.keyboard_device_provider = kwargs.get("keyboard_device_provider")
        _FakeManager.instances.append(self)

    def list_profiles(self) -> list[_FakeProfile]:
        return [_FakeProfile(n) for n in self.profiles]

    def activate(self, name: str, *, origin: str = "manual") -> _FakeProfile:
        self.activated.append(name)
        self.origins.append(origin)
        if self.store is not None:
            self.store.active_profile = name
        return _FakeProfile(name)


class _FakeDaemon:
    def __init__(self, active: str | None) -> None:
        self.controller = _FakeController()
        self.store = _FakeStore(active)
        self._keyboard_device = None
        self.mouse_applied: list[tuple[bool, int, int]] = []
        self.suppressed: list[bool] = []

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        return fn(*args)

    def apply_profile_mouse(self, enabled: bool, speed: int, scroll_speed: int) -> None:
        self.mouse_applied.append((enabled, speed, scroll_speed))

    def apply_profile_suppression(self, desired: bool) -> None:
        self.suppressed.append(desired)


def _patch_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeManager.instances = []
    monkeypatch.setattr(
        "hefesto_dualsense4unix.profiles.manager.ProfileManager", _FakeManager
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.save_active_marker", lambda _n: None
    )


@pytest.mark.asyncio
async def test_cycle_next_avanca(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_manager(monkeypatch)
    d = _FakeDaemon(active="a")
    await build_profile_cycle_callback(d, +1)()
    assert d.store.active_profile == "b"


@pytest.mark.asyncio
async def test_cycle_injeta_appliers_do_daemon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BUG-PROFILE-MOUSE-KILLS-GAMEPAD-01: o callsite de hotkey injeta os appliers"""
    _patch_manager(monkeypatch)
    d = _FakeDaemon(active="a")
    await build_profile_cycle_callback(d, +1)()

    mgr = _FakeManager.instances[-1]
    assert mgr.mouse_applier is not None
    assert mgr.suppression_applier is not None
    assert callable(mgr.keyboard_device_provider)
    mgr.mouse_applier(True, 8, 1)
    mgr.suppression_applier(True)
    assert d.mouse_applied == [(True, 8, 1)]
    assert d.suppressed == [True]


@pytest.mark.asyncio
async def test_cycle_next_da_wrap_around(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_manager(monkeypatch)
    d = _FakeDaemon(active="c")
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
    """Gesto explícito: arma o lock manual + pisca a barra sem gravar e a devolve."""
    _patch_manager(monkeypatch)
    d = _FakeDaemon(active="a")
    await build_profile_cycle_callback(d, +1)()
    assert d.store.locked is not None
    assert d.controller.leds == [(255, 255, 255)], "lightbar não piscou (sem retorno visível)"
    assert d.controller.devolvidas == 1, "a cor do perfil não foi devolvida"
    assert not d.controller.gravadas, "o pisca gravou a cor no estado desejado"


class _SoGrava:
    """Backend sem a rota do aviso: só o `set_led`, que grava no desejado."""

    def __init__(self) -> None:
        self.gravadas: list[tuple[int, int, int]] = []

    def set_led(self, color: tuple[int, int, int]) -> None:
        self.gravadas.append(color)


@pytest.mark.asyncio
async def test_cycle_sem_a_rota_do_aviso_troca_sem_piscar_pelo_set_led(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem `pintar_lightbar_sem_lembrar`, a troca acontece e o branco não sai pelo `set_led`."""
    _patch_manager(monkeypatch)
    d = _FakeDaemon(active="a")
    d.controller = _SoGrava()  # type: ignore[assignment]
    await build_profile_cycle_callback(d, +1)()
    assert d.store.active_profile == "b"
    assert not d.controller.gravadas, "o pisca voltou a gravar pelo set_led"


@pytest.mark.asyncio
async def test_cycle_que_falha_devolve_o_lock_e_a_cor_e_a_falha_sobe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ativação que levanta não deixa o lock armado nem a barra no branco."""
    _patch_manager(monkeypatch)

    def _levanta(self: _FakeManager, name: str, *, origin: str = "manual") -> _FakeProfile:
        raise RuntimeError("o perfil não abriu")

    monkeypatch.setattr(_FakeManager, "activate", _levanta)
    d = _FakeDaemon(active="a")
    with pytest.raises(RuntimeError):
        await build_profile_cycle_callback(d, +1)()
    assert d.store.locked == 0.0, "o lock manual ficou armado depois da falha"
    assert d.controller.leds == [(255, 255, 255)]
    assert d.controller.devolvidas == 1, "a cor do perfil não voltou depois da falha"
    assert d.store.active_profile == "a"


@pytest.mark.asyncio
async def test_cycle_skip_com_menos_de_dois_perfis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_manager(monkeypatch)
    monkeypatch.setattr(_FakeManager, "profiles", ("solo",))
    d = _FakeDaemon(active="solo")
    await build_profile_cycle_callback(d, +1)()
    assert d.store.active_profile == "solo"
    assert not d.controller.leds


@pytest.mark.asyncio
async def test_cycle_ativo_desconhecido_comeca_do_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_manager(monkeypatch)
    d = _FakeDaemon(active=None)
    await build_profile_cycle_callback(d, +1)()
    assert d.store.active_profile == "b"


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
