"""BT-MIC-REGISTRY-01 — o BtMicSubsystem deixa de ser órfão.

A classe existia (`daemon/subsystems/bt_mic.py`), o gate por env var estava
documentado e a ponte de áudio estava validada ao vivo — mas NINGUÉM iniciava
o subsystem: `SUBSYSTEM_REGISTRY` é declarativo e quem sobe as coisas é o
`Daemon.run()`. Resultado: `HEFESTO_DUALSENSE4UNIX_BT_MIC=1` não ligava nada
no daemon.

Estes testes travam as DUAS metades (a lista e o `run()`) — é a única forma de
o defeito não voltar, já que acertar só uma delas parece certo e não faz nada.
"""
from __future__ import annotations

import asyncio

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import SUBSYSTEM_REGISTRY
from hefesto_dualsense4unix.daemon.subsystems.bt_mic import BtMicSubsystem
from hefesto_dualsense4unix.testing import FakeController


def _state() -> ControllerState:
    return ControllerState(
        battery_pct=80, l2_raw=0, r2_raw=0, connected=True,
        transport="usb", buttons_pressed=frozenset(),
    )


def _config(**over: object) -> DaemonConfig:
    base: dict[str, object] = dict(
        poll_hz=200, auto_reconnect=False, ipc_enabled=False, udp_enabled=False,
        autoswitch_enabled=False, mouse_emulation_enabled=False,
        keyboard_emulation_enabled=False, ps_button_action="none",
        mic_button_toggles_system=False,
    )
    base.update(over)
    return DaemonConfig(**base)  # type: ignore[arg-type]


async def _roda_ate_o_1o_tick(daemon: Daemon, store: StateStore) -> None:
    run_task = asyncio.create_task(daemon.run())
    for _ in range(500):
        if store.counter("poll.tick") >= 1:
            break
        await asyncio.sleep(0.01)
    daemon.stop()
    await run_task


def test_bt_mic_esta_no_registry() -> None:
    """A metade declarativa: a classe consta da lista canônica."""
    assert BtMicSubsystem in SUBSYSTEM_REGISTRY


def test_bt_mic_sobe_antes_dos_plugins_no_registry() -> None:
    """Ordem de start: bt_mic antes de plugins (código de usuário por último).

    Como o stop é a ordem inversa, isso também garante que as pontes de áudio
    — e portanto o MICROFONE de cada controle — sejam desligadas cedo.
    """
    from hefesto_dualsense4unix.daemon.subsystems import (
        MetricsSubsystem,
        PluginsSubsystem,
    )

    idx = SUBSYSTEM_REGISTRY.index
    assert idx(BtMicSubsystem) < idx(PluginsSubsystem) < idx(MetricsSubsystem)


@pytest.mark.asyncio
async def test_boot_nao_sobe_bt_mic_por_padrao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem opt-in, o subsystem fica INERTE — e o boot não registra falha.

    Um microfone que liga sozinho com o daemon é inaceitável; o default tem de
    ser "não sobe" e não "sobe e falha".
    """
    monkeypatch.delenv("HEFESTO_DUALSENSE4UNIX_BT_MIC", raising=False)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.load_paused_state", lambda: False
    )
    store = StateStore()
    daemon = Daemon(
        controller=FakeController(transport="usb", states=[_state()]),
        bus=EventBus(), store=store, config=_config(),
    )
    await _roda_ate_o_1o_tick(daemon, store)

    assert daemon._bt_mic_subsystem is None
    assert "bt_mic" not in daemon._failed_subsystems


@pytest.mark.asyncio
async def test_boot_sobe_bt_mic_com_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """Com `bt_mic_enabled=True` o `run()` de fato inicia o subsystem.

    É ESTA a metade que faltava: sem a linha no `run()`, o teste do registry
    passaria e o daemon continuaria sem ponte de microfone nenhuma.
    """
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.load_paused_state", lambda: False
    )
    iniciados: list[str] = []

    class _GerenciadorFalso:
        def reconciliar(self) -> None:
            iniciados.append("reconciliar")

        def dormir(self, _s: float) -> bool:
            return True  # uma volta e sai — nada de laço vivo em teste

        def parar(self) -> None:
            iniciados.append("parar")

    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.dualsense_bt_audio.GerenciadorMicBluetooth",
        _GerenciadorFalso,
    )
    store = StateStore()
    daemon = Daemon(
        controller=FakeController(transport="usb", states=[_state()]),
        bus=EventBus(), store=store, config=_config(bt_mic_enabled=True),
    )
    run_task = asyncio.create_task(daemon.run())
    for _ in range(500):
        if daemon._bt_mic_subsystem is not None:
            break
        await asyncio.sleep(0.01)
    subiu = daemon._bt_mic_subsystem is not None
    daemon.stop()
    await run_task

    assert subiu, "bt_mic não foi iniciado pelo run() com o opt-in ligado"
    assert "bt_mic" not in daemon._failed_subsystems
    # O shutdown tem de DESLIGAR a ponte (é o que manda o 0x32 de mic off).
    assert daemon._bt_mic_subsystem is None
    assert "parar" in iniciados


@pytest.mark.asyncio
async def test_falha_do_bt_mic_nao_derruba_o_boot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contrato `_failed_subsystems`: bt_mic quebrado é isolado, não fatal."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.load_paused_state", lambda: False
    )
    store = StateStore()
    daemon = Daemon(
        controller=FakeController(transport="usb", states=[_state()]),
        bus=EventBus(), store=store, config=_config(bt_mic_enabled=True),
    )

    async def _boom() -> None:
        raise RuntimeError("libopus ausente")

    monkeypatch.setattr(daemon, "_start_bt_mic", _boom)
    await _roda_ate_o_1o_tick(daemon, store)

    assert "bt_mic" in daemon._failed_subsystems
    assert "libopus" in daemon._failed_subsystems["bt_mic"]
    assert store.counter("poll.tick") >= 1


def test_gate_por_env_var_continua_valendo(monkeypatch: pytest.MonkeyPatch) -> None:
    """`is_enabled` aceita a env var documentada OU o campo novo da config."""
    subsystem = BtMicSubsystem()
    monkeypatch.delenv("HEFESTO_DUALSENSE4UNIX_BT_MIC", raising=False)
    assert subsystem.is_enabled(_config()) is False
    assert subsystem.is_enabled(_config(bt_mic_enabled=True)) is True
    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_BT_MIC", "1")
    assert subsystem.is_enabled(_config()) is True
