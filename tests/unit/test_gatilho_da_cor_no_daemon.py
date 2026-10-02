"""GATILHO-DA-COR-01 — o gatilho dentro do laço que já existe."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

import hefesto_dualsense4unix.daemon.connection as conn_mod
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.connection import (
    armar_gatilho_da_cor_por_evento,
    reconnect_loop,
    registro_de_gatilhos_de,
)

ATRASO_CURTO = 0.05


class _Controller:
    """Controller sempre online que conta conexões novas e repinturas."""

    def __init__(self) -> None:
        self.connect_calls = 0
        self.pendentes = 0
        self.repinturas = 0
        self.online = True

    def connect(self) -> None:
        self.connect_calls += 1

    def is_connected(self) -> bool:
        return self.online

    def get_transport(self) -> str:
        return "bt"

    def chegou_controle(self, quantos: int = 1) -> None:
        """Simula o que o `connect()` do backend real faz ao abrir handle BT novo."""
        self.pendentes += quantos

    def consumir_conexoes_bt_novas(self) -> int:
        n = self.pendentes
        self.pendentes = 0
        return n

    def reescrever_lightbar_por_hidraw(self) -> dict[str, bool]:
        self.repinturas += 1
        return {"aa:bb": True, "cc:dd": True}


class _FakeWatch:
    def __init__(self) -> None:
        self._changed = False

    def trip(self) -> None:
        self._changed = True

    def poll(self) -> bool:
        changed = self._changed
        self._changed = False
        return changed


class _StubDaemon:
    """Superfície mínima do DaemonProtocol que o reconnect_loop toca."""

    def __init__(self, controller: _Controller) -> None:
        self.controller = controller
        self.bus = EventBus()
        self.config = SimpleNamespace(reconnect_backoff_sec=0.01, auto_reconnect=True)
        self._stop_event = asyncio.Event()
        self._registro_de_gatilhos: Any = None

    def _is_stopping(self) -> bool:
        return self._stop_event.is_set()

    async def _run_blocking(self, fn: Callable[..., Any], *args: Any) -> Any:
        return fn(*args)

    def _arm_input_grace(self) -> None:
        pass

    def stop(self) -> None:
        self._stop_event.set()


async def _until(cond: Callable[[], bool], timeout: float = 3.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not cond():
        if loop.time() > deadline:
            raise AssertionError("condição não alcançada dentro do prazo")
        await asyncio.sleep(0.005)


async def _por_um_tempo(segundos: float) -> None:
    await asyncio.sleep(segundos)


def _fatias_curtas(monkeypatch: pytest.MonkeyPatch) -> None:
    """Encolhe as esperas do laço para o teste caber em milissegundos."""
    monkeypatch.setattr(conn_mod, "RECONNECT_HOTPLUG_POLL_INTERVAL_SEC", 0.01)
    monkeypatch.setattr(conn_mod, "RECONNECT_ONLINE_CHECK_INTERVAL_SEC", 30.0)
    monkeypatch.setattr(conn_mod, "PASSO_ENQUANTO_O_GATILHO_ESTA_ARMADO_SEC", 0.01)


async def _laco(daemon: _StubDaemon, watch: _FakeWatch) -> asyncio.Task[None]:
    task = asyncio.create_task(
        reconnect_loop(daemon, input_watch=watch)  # type: ignore[arg-type]
    )
    await _until(lambda: daemon.controller.connect_calls >= 1)
    gatilho = registro_de_gatilhos_de(daemon).obter("lightbar")  # type: ignore[arg-type]
    assert gatilho is not None, "o laço não registrou o gatilho da lightbar"
    gatilho._atraso_s = ATRASO_CURTO
    return task


@pytest.mark.asyncio
async def test_uma_conexao_nova_repinta_depois_do_atraso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Conexão nova → armou → sossegou → repintou. Uma vez."""
    _fatias_curtas(monkeypatch)
    ctrl = _Controller()
    daemon = _StubDaemon(ctrl)
    watch = _FakeWatch()
    task = await _laco(daemon, watch)
    try:
        ctrl.chegou_controle()
        watch.trip()
        await _until(lambda: ctrl.repinturas >= 1)
        await _por_um_tempo(ATRASO_CURTO * 4)
        assert ctrl.repinturas == 1, "repintou mais de uma vez pela mesma sequência"
    finally:
        daemon.stop()
        await task


@pytest.mark.asyncio
async def test_conexao_durante_a_espera_readia_e_a_repintura_sai_uma_vez_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A CURA, ponta a ponta."""
    _fatias_curtas(monkeypatch)
    ctrl = _Controller()
    daemon = _StubDaemon(ctrl)
    watch = _FakeWatch()
    task = await _laco(daemon, watch)
    try:
        for _ in range(3):
            ctrl.chegou_controle()
            watch.trip()
            await _por_um_tempo(ATRASO_CURTO / 2)
            assert ctrl.repinturas == 0, "repintou no meio da rajada"
        await _until(lambda: ctrl.repinturas >= 1)
        await _por_um_tempo(ATRASO_CURTO * 4)
        assert ctrl.repinturas == 1
    finally:
        daemon.stop()
        await task


@pytest.mark.asyncio
async def test_sem_conexao_nova_o_laco_nunca_repinta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nada de reafirmação periódica — ela recusou essa opção explicitamente."""
    _fatias_curtas(monkeypatch)
    ctrl = _Controller()
    daemon = _StubDaemon(ctrl)
    watch = _FakeWatch()
    task = await _laco(daemon, watch)
    try:
        await _por_um_tempo(ATRASO_CURTO * 10)
        assert ctrl.repinturas == 0
    finally:
        daemon.stop()
        await task


@pytest.mark.asyncio
async def test_evento_de_jogo_tambem_arma_o_gatilho(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Escolha dela, 12/08: reafirmar depois de CADA evento que faz a Steam pintar."""
    _fatias_curtas(monkeypatch)
    ctrl = _Controller()
    daemon = _StubDaemon(ctrl)
    watch = _FakeWatch()
    task = await _laco(daemon, watch)
    try:
        armar_gatilho_da_cor_por_evento(daemon, "game_signal:game->daemon")  # type: ignore[arg-type]
        await _until(lambda: ctrl.repinturas >= 1)
        await _por_um_tempo(ATRASO_CURTO * 4)
        assert ctrl.repinturas == 1
    finally:
        daemon.stop()
        await task


@pytest.mark.asyncio
async def test_um_evento_de_jogo_no_meio_da_rajada_nao_dobra_a_repintura(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Um só gatilho: conexão e evento de jogo entram na MESMA sequência."""
    _fatias_curtas(monkeypatch)
    ctrl = _Controller()
    daemon = _StubDaemon(ctrl)
    watch = _FakeWatch()
    task = await _laco(daemon, watch)
    try:
        ctrl.chegou_controle()
        watch.trip()
        await _por_um_tempo(ATRASO_CURTO / 2)
        armar_gatilho_da_cor_por_evento(daemon, "game_signal:daemon->game")  # type: ignore[arg-type]
        await _until(lambda: ctrl.repinturas >= 1)
        await _por_um_tempo(ATRASO_CURTO * 4)
        assert ctrl.repinturas == 1
    finally:
        daemon.stop()
        await task


@pytest.mark.asyncio
async def test_a_mesa_esvaziando_desarma_sem_disparar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Offline não há barra para pintar — e a sequência não pode ficar pendurada."""
    _fatias_curtas(monkeypatch)
    monkeypatch.setattr(conn_mod, "RECONNECT_PROBE_INTERVAL_SEC", 0.01)
    ctrl = _Controller()
    daemon = _StubDaemon(ctrl)
    watch = _FakeWatch()
    task = await _laco(daemon, watch)
    try:
        ctrl.chegou_controle()
        ctrl.online = False
        await _por_um_tempo(ATRASO_CURTO * 6)
        assert ctrl.repinturas == 0
        ctrl.online = True
        await _por_um_tempo(ATRASO_CURTO * 6)
        assert ctrl.repinturas == 0, "disparou uma sequência velha na volta"
    finally:
        daemon.stop()
        await task
