"""Coexistência entre emulação de mouse e triggers manuais (BUG-MOUSE-TRIGGERS-01).

Reproduz o bug reportado na issue #69: usuário aplica efeito de gatilho
(ex.: Galloping no R2) via aba Gatilhos, depois liga o toggle da aba Mouse;
o cursor passa a responder, mas o gatilho volta a `Off` ou deixa de atuar.

Causa raiz identificada: mover o cursor via emulação de mouse muda o foco
de janela X11 -> o `AutoSwitcher` reavalia o perfil e reaplica o `fallback`
(que tem `triggers.{left,right} = "Off"`), pisando no trigger manual.

Correção: `trigger.set` marca `store.manual_trigger_active = True`. Enquanto
estiver ligado, o `AutoSwitcher._activate` respeita o override e não
reaplica perfis por mudança de janela. O override é limpo por `trigger.reset`
ou `profile.switch` explícito.

Este módulo cobre dois contratos:

1. `UinputMouseDevice.dispatch()` executado N vezes não chama
   `controller.set_trigger(...)` como side-effect (hipótese #2 do spec
   descartada empiricamente).
2. `AutoSwitcher` respeita `store.manual_trigger_active` e não pisa no
   trigger manual quando a janela muda.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hefesto.core.controller import TriggerEffect
from hefesto.core.trigger_effects import build_from_name
from hefesto.daemon.state_store import StateStore
from hefesto.integrations.uinput_mouse import UinputMouseDevice
from hefesto.profiles import loader as loader_module
from hefesto.profiles.autoswitch import AutoSwitcher
from hefesto.profiles.loader import save_profile
from hefesto.profiles.manager import ProfileManager
from hefesto.profiles.schema import (
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)
from tests.fixtures.fake_controller import FakeController, FakeControllerCommand

# --- infra ---------------------------------------------------------------


def _fake_uinput_module() -> MagicMock:
    """Módulo uinput fake com constantes mínimas para os emits."""
    mod = MagicMock()
    for name in (
        "REL_X", "REL_Y", "REL_WHEEL", "REL_HWHEEL",
        "BTN_LEFT", "BTN_RIGHT", "BTN_MIDDLE",
        "KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT",
    ):
        setattr(mod, name, (1, hash(name) & 0xFFFF))
    return mod


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return target


# --- contrato 1: dispatch do mouse não mexe em triggers ------------------


def test_mouse_dispatch_nao_chama_set_trigger_no_controller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UinputMouseDevice.dispatch N vezes: zero side-effects em triggers.

    Bate direto na hipótese 2 do spec BUG-MOUSE-TRIGGERS-01: prova via
    assert que o path de dispatch do mouse não toca o controle pelos
    caminhos de output (set_trigger, set_led, set_rumble).
    """
    fake_mod = _fake_uinput_module()
    fake_device = MagicMock()
    fake_mod.Device.return_value = fake_device
    monkeypatch.setitem(sys.modules, "uinput", fake_mod)

    fc = FakeController()
    fc.connect()

    # Aplica um trigger manual ANTES de ligar o mouse — simula sequência
    # do usuário na GUI.
    effect: TriggerEffect = build_from_name("Galloping", [0, 9, 7, 7, 10])
    fc.set_trigger("right", effect)

    mouse = UinputMouseDevice()
    assert mouse.start() is True

    # N ticks de dispatch com stick fora de deadzone + triggers pressionados
    # (valores que cruzariam TRIGGER_PRESS_THRESHOLD).
    for tick in range(120):
        mouse.dispatch(
            lx=200,
            ly=60,
            rx=128,
            ry=128,
            l2=100,
            r2=200,
            buttons=frozenset({"cross", "dpad_up"}),
            now=0.1 * tick,
        )

    # Conta set_trigger nos comandos do controller. Deve haver exatamente 1
    # (o aplicado antes do loop). Nenhum extra emitido pelo dispatch.
    trigger_cmds = [
        c for c in fc.commands
        if isinstance(c, FakeControllerCommand) and c.kind == "set_trigger"
    ]
    assert len(trigger_cmds) == 1, (
        f"UinputMouseDevice.dispatch chamou set_trigger como side-effect "
        f"(hipótese 2 confirmada). Comandos: {trigger_cmds!r}"
    )
    # E também nem set_led, nem set_rumble.
    for kind in ("set_led", "set_rumble"):
        extras = [c for c in fc.commands if c.kind == kind]
        assert not extras, f"{kind} foi chamado pelo dispatch: {extras!r}"


# --- contrato 2: autoswitch respeita override manual ---------------------


def _mk_profile_with_trigger(name: str, wm_class: list[str] | None = None) -> Profile:
    return Profile(
        name=name,
        match=MatchCriteria(window_class=wm_class or [f"{name}_class"]),
        priority=10,
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Rigid", params=[0, 100]),
        ),
        leds=LedsConfig(lightbar=(10, 20, 30)),
    )


def _mk_fallback_off() -> Profile:
    return Profile(
        name="fallback",
        match=MatchAny(),
        priority=-1000,
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Off"),
        ),
        leds=LedsConfig(lightbar=(40, 40, 40)),
    )


@pytest.mark.asyncio
async def test_autoswitch_suspende_quando_override_manual_ligado(
    isolated_profiles_dir: Path,
) -> None:
    """Com `manual_trigger_active=True`, autoswitch não reaplica fallback.

    Reproduz o cenário do bug: usuário aplica Galloping (override ON),
    ligar mouse move cursor e muda foco de janela 'estranha' sem perfil
    especifico, autoswitch quer cair no fallback (que zera triggers) mas
    DEVE respeitar o override e não fazer nada.
    """
    save_profile(_mk_fallback_off())

    fc = FakeController()
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)

    # Estado do bug: usuário já aplicou trigger manual
    store.mark_manual_trigger_active()

    # Janela 'estranha' — só fallback daria match
    def reader() -> dict:
        return {"wm_class": "SemPerfilEspecifico"}

    switcher = AutoSwitcher(
        manager=manager,
        window_reader=reader,
        poll_interval_sec=0.02,
        debounce_sec=0.02,
        store=store,
    )
    switcher.start()
    await asyncio.sleep(0.15)
    switcher.stop()
    assert switcher._task is not None
    await switcher._task

    # Autoswitch não deve ter ativado nada: o override manual manda.
    assert switcher._current_profile is None
    # Nenhum set_trigger extra foi emitido pelo autoswitch.
    trigger_cmds = [c for c in fc.commands if c.kind == "set_trigger"]
    assert trigger_cmds == [], (
        f"Autoswitch pisou no override manual: {trigger_cmds!r}"
    )
    # Nenhum profile.activated foi bumped.
    assert store.counter("profile.activated") == 0


@pytest.mark.asyncio
async def test_autoswitch_volta_a_funcionar_apos_clear_override(
    isolated_profiles_dir: Path,
) -> None:
    """`clear_manual_trigger_active()` reabilita o autoswitch.

    Simula o usuário resetando o trigger (ou trocando de perfil) —
    autoswitch volta a respeitar a janela ativa.
    """
    save_profile(_mk_profile_with_trigger("shooter", wm_class=["Doom"]))

    fc = FakeController()
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)

    # Override ligado inicialmente
    store.mark_manual_trigger_active()

    def reader() -> dict:
        return {"wm_class": "Doom"}

    switcher = AutoSwitcher(
        manager=manager,
        window_reader=reader,
        poll_interval_sec=0.02,
        debounce_sec=0.02,
        store=store,
    )
    switcher.start()
    await asyncio.sleep(0.1)

    # Até aqui, override ativo impediu autoswitch
    assert switcher._current_profile is None

    # Usuário zera override (trigger.reset ou profile.switch explícito)
    store.clear_manual_trigger_active()
    await asyncio.sleep(0.15)
    switcher.stop()
    assert switcher._task is not None
    await switcher._task

    # Agora autoswitch ativou o shooter
    assert switcher._current_profile == "shooter"


def test_state_store_manual_trigger_lifecycle() -> None:
    """StateStore expõe flag `manual_trigger_active` com getter/setter limpos."""
    store = StateStore()
    assert store.manual_trigger_active is False
    assert store.snapshot().manual_trigger_active is False

    store.mark_manual_trigger_active()
    assert store.manual_trigger_active is True
    assert store.snapshot().manual_trigger_active is True

    store.clear_manual_trigger_active()
    assert store.manual_trigger_active is False
    assert store.snapshot().manual_trigger_active is False


# --- contrato 3: IPC hooks marcam/zeram a flag ---------------------------


@pytest.mark.asyncio
async def test_ipc_trigger_set_marca_override(
    isolated_profiles_dir: Path,
) -> None:
    """`trigger.set` via IPC liga `manual_trigger_active`."""
    from hefesto.daemon.ipc_server import IpcServer

    fc = FakeController()
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    server = IpcServer(
        controller=fc, store=store, profile_manager=manager,
        socket_path=isolated_profiles_dir / "sock",
    )
    server.__post_init__()  # garante _handlers populado

    assert store.manual_trigger_active is False
    await server._handle_trigger_set(
        {"side": "right", "mode": "Galloping", "params": [0, 9, 7, 7, 10]}
    )
    assert store.manual_trigger_active is True


@pytest.mark.asyncio
async def test_ipc_trigger_reset_zera_override(
    isolated_profiles_dir: Path,
) -> None:
    """`trigger.reset` via IPC desliga `manual_trigger_active`."""
    from hefesto.daemon.ipc_server import IpcServer

    fc = FakeController()
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    server = IpcServer(
        controller=fc, store=store, profile_manager=manager,
        socket_path=isolated_profiles_dir / "sock",
    )
    server.__post_init__()

    store.mark_manual_trigger_active()
    assert store.manual_trigger_active is True
    await server._handle_trigger_reset({"side": "both"})
    assert store.manual_trigger_active is False


@pytest.mark.asyncio
async def test_ipc_profile_switch_zera_override(
    isolated_profiles_dir: Path,
) -> None:
    """`profile.switch` via IPC desliga `manual_trigger_active`."""
    from hefesto.daemon.ipc_server import IpcServer

    save_profile(_mk_profile_with_trigger("shooter"))

    fc = FakeController()
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    server = IpcServer(
        controller=fc, store=store, profile_manager=manager,
        socket_path=isolated_profiles_dir / "sock",
    )
    server.__post_init__()

    store.mark_manual_trigger_active()
    await server._handle_profile_switch({"name": "shooter"})
    assert store.manual_trigger_active is False


# "Consciência do próprio estado é o primeiro passo para evitar cair em
# contradição consigo mesmo." — Sócrates (parafraseado)
