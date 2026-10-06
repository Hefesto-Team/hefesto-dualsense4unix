"""BT-MIC-REGISTRY-01 — o BtMicSubsystem deixa de ser órfão."""
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
    """Ordem de start: bt_mic antes de plugins (código de usuário por último)."""
    from hefesto_dualsense4unix.daemon.subsystems import (
        MetricsSubsystem,
        PluginsSubsystem,
    )

    idx = SUBSYSTEM_REGISTRY.index
    assert idx(BtMicSubsystem) < idx(PluginsSubsystem) < idx(MetricsSubsystem)


@pytest.mark.asyncio
async def test_o_supervisor_sobe_sem_declaracao_e_o_boot_nao_falha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Em máquina NOVA, o supervisor sobe — e é isso que faz a inversão valer.

    **DOIS FATOS MUDARAM AQUI, e o segundo é um instrumento falso.**

    (1) O CONTRATO, 18/09/2026,  Este teste se chamava
    `test_boot_nao_sobe_bt_mic_por_padrao` e dizia *"um microfone que liga
    sozinho com o daemon é inaceitável"*. Era o desenho da casa, e o preço dele
    foi medido: numa máquina onde ninguém declarou nada — que é TODA máquina
    nova — o microfone do DualSense simplesmente não existia, e a aba dizia
    *"o sistema não vê um microfone neste controle"*.

    (2) **ELE NÃO MEDIA O QUE PROMETIA.** A asserção era
    `daemon._bt_mic_subsystem is None` DEPOIS de `_roda_ate_o_1o_tick`, que
    chama `daemon.stop()` — e o stop zera esse atributo sempre. O teste dava
    verde com o subsystem subindo e com ele não subindo: o irmão de baixo
    (`test_boot_sobe_bt_mic_com_opt_in`) captura o valor ANTES do stop
    justamente por isso, e a diferença entre os dois passou um mês sem
    ninguém ver. Aqui a captura passou a ser antes também.

    **Ligado não quer dizer capturando**, e essa parte não mudou: sem nó de
    rádio na varredura não há ponte, não há `0x32` e a libopus nem é importada.
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
    run_task = asyncio.create_task(daemon.run())
    for _ in range(500):
        if daemon._bt_mic_subsystem is not None:
            break
        await asyncio.sleep(0.01)
    subiu = daemon._bt_mic_subsystem is not None
    daemon.stop()
    await run_task

    assert subiu, (
        "sem declaração nenhuma o supervisor não subiu: "
        "a inversão não alcança máquina nova"
    )
    assert "bt_mic" not in daemon._failed_subsystems
    assert daemon._bt_mic_subsystem is None, "o stop tem de derrubar a ponte"


@pytest.mark.asyncio
async def test_boot_sobe_bt_mic_com_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """Com um `uniq` na fonte, o `run()` de fato inicia o subsystem."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.load_paused_state", lambda: False
    )
    iniciados: list[str] = []

    class _GerenciadorFalso:
        def reconciliar(self, nos: object = None) -> None:
            iniciados.append("reconciliar")

        def dormir(self, _s: float) -> bool:
            return True

        def parar(self) -> None:
            iniciados.append("parar")

    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.dualsense_bt_audio.GerenciadorMicBluetooth",
        _GerenciadorFalso,
    )
    store = StateStore()
    daemon = Daemon(
        controller=FakeController(transport="usb", states=[_state()]),
        bus=EventBus(), store=store,
        config=_config(bt_mic_uniqs=lambda: frozenset({"aabbcc000001"})),
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
        bus=EventBus(), store=store,
        config=_config(bt_mic_uniqs=lambda: frozenset({"aabbcc000001"})),
    )

    async def _boom() -> None:
        raise RuntimeError("libopus ausente")

    monkeypatch.setattr(daemon, "_start_bt_mic", _boom)
    await _roda_ate_o_1o_tick(daemon, store)

    assert "bt_mic" in daemon._failed_subsystems
    assert "libopus" in daemon._failed_subsystems["bt_mic"]
    assert store.counter("poll.tick") >= 1


def test_o_supervisor_fica_de_pe_e_quem_filtra_e_o_alvos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CONTRATO SUBSTITUÍDO — CANAL-POR-CONTROLE-01, 03/09/2026.

    Este teste tratava `is_enabled` como o gate da privacidade: sem declaração e
    sem env, `False`. Era essa resposta que trancava o rádio — sem subsystem
    não havia a quem PEDIR canal, e o primeiro toque no botão do microfone caía
    no vazio.

    **E O "NASCE DESLIGADO" CAIU EM 18/09/2026**, por  Ele foi o
    desenho desta casa por um mês e tinha razão escrita — *"um microfone que
    sobe sozinho com o daemon é inaceitável"* —, e o preço dele foi medido no
    mesmo dia: dos quatro DualSense da bancada, DOIS não tinham microfone,
    porque ninguém sabia que era preciso declarar. Vinte e sete recusas *"o
    sistema não vê um microfone neste controle"* no diário.

    **O que esta régua mede agora é o par que substituiu o gate:** o supervisor
    fica de pé, `alvos()` devolve os nós do rádio, e quem cala é a RECUSA — que
    é mais forte do que a ausência era, porque `false` no disco sobrevive ao
    boot e "não pedi" nunca sobreviveu a nada.
    """
    from hefesto_dualsense4unix.daemon.subsystems.bt_mic import (
        RegistroDePedidosDeCanal,
    )

    subsystem = BtMicSubsystem(registro=RegistroDePedidosDeCanal())
    monkeypatch.delenv("HEFESTO_DUALSENSE4UNIX_BT_MIC", raising=False)
    assert subsystem.is_enabled(_config()) is True
    assert subsystem.is_enabled(_config(bt_mic_uniqs=frozenset)) is True

    class _No:
        uniq = "aabbcc000001"
        caminho = "/dev/hidraw9"

    subsystem._config = _config()
    assert [n.uniq for n in subsystem.alvos([_No()])] == ["aabbcc000001"]
    subsystem._config = _config(bt_mic_recusados=lambda: frozenset({"aabbcc000001"}))
    assert subsystem.alvos([_No()]) == []
    subsystem._config = _config(bt_mic_uniqs=lambda: frozenset({"aabbcc000001"}))
    assert [no.uniq for no in subsystem.alvos([_No()])] == ["aabbcc000001"]
    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_BT_MIC", "1")
    assert len(subsystem.alvos([_No()])) == 1
