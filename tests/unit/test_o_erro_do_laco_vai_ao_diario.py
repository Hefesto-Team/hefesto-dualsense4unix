"""O erro do laço de 60 Hz vai ao diário e não derruba a mesa.

O `read_state` real não faz E/S; uma leitura que levanta é defeito de código, e
nenhum handle de P1 a P4 sai da mesa por causa dele. Os passos do laço passam
por um embrulho só (`_PassosDoLaco`): a falha soma `poll.erro.<passo>` e o
`warning` com o nome do passo sai UMA vez por episódio.
"""
from __future__ import annotations

import asyncio
import time
from itertools import pairwise
from typing import Any

import pytest
from structlog.testing import capture_logs

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon import lifecycle
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig, ModoAdiado
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems.coop import get_coop_manager
from hefesto_dualsense4unix.testing import FakeController

PASSOS_RAPIDOS = (
    ("identidade", 0.05, 0.0),
    ("modo_pendente", 0.05, 0.0),
)


def _estados(n: int = 50) -> list[ControllerState]:
    return [
        ControllerState(
            battery_pct=80, l2_raw=i % 256, r2_raw=0, connected=True, transport="usb"
        )
        for i in range(n)
    ]


class _QuatroControles(FakeController):
    """Quatro DualSense na mesa; a leitura do P1 levanta `levantar` vezes seguidas."""

    def __init__(self, levantar: int, depois_de: int = 3) -> None:
        super().__init__(transport="usb", states=_estados())
        self.handles = {"p1", "p2", "p3", "p4"}
        self.disconnects = 0
        self._levantar = levantar
        self._lidas = 0
        self._depois_de = depois_de
        self.hora_do_primeiro_erro: float | None = None

    def disconnect(self) -> None:
        self.disconnects += 1
        self.handles.clear()
        super().disconnect()

    def read_state(self) -> ControllerState:
        self._lidas += 1
        if self._depois_de < self._lidas <= self._depois_de + self._levantar:
            if self.hora_do_primeiro_erro is None:
                self.hora_do_primeiro_erro = time.monotonic()
            raise RuntimeError("defeito de código na leitura")
        return super().read_state()


async def _ate(condicao: Any, prazo_s: float = 5.0) -> bool:
    laco = asyncio.get_running_loop()
    fim = laco.time() + prazo_s
    while not condicao():
        if laco.time() > fim:
            return False
        await asyncio.sleep(0.005)
    return True


def _daemon(fc: FakeController, **over: Any) -> tuple[Daemon, StateStore, EventBus]:
    store = StateStore()
    bus = EventBus()
    base: dict[str, Any] = dict(
        poll_hz=200,
        ipc_enabled=False,
        udp_enabled=False,
        autoswitch_enabled=False,
    )
    base.update(over)
    return Daemon(controller=fc, bus=bus, store=store, config=DaemonConfig(**base)), store, bus


def _buracos(horas: list[float], desde: float | None) -> list[float]:
    """Os intervalos entre dois `forward_all` seguidos, a partir do primeiro erro."""
    assert desde is not None, "a leitura nunca levantou"
    depois = [h for h in horas if h >= desde]
    return [b - a for a, b in pairwise(depois) if b - a > 0.25]


def _espiar_o_coop(daemon: Daemon) -> list[float]:
    """Troca o `forward_all` por um espião que anota a hora de cada chamada."""
    horas: list[float] = []
    manager = get_coop_manager(daemon)
    real = manager.forward_all

    def espiao() -> None:
        horas.append(asyncio.get_running_loop().time())
        real()

    manager.forward_all = espiao  # type: ignore[method-assign]
    return horas


@pytest.mark.asyncio
async def test_a_leitura_que_levanta_tres_vezes_e_volta() -> None:
    """(1) e (2): três leituras que levantam e a quarta volta."""
    fc = _QuatroControles(levantar=3)
    daemon, store, bus = _daemon(fc)
    horas = _espiar_o_coop(daemon)
    quedas = bus.subscribe(EventTopic.CONTROLLER_DISCONNECTED)

    run_task = asyncio.create_task(daemon.run())
    try:
        assert await _ate(lambda: fc._lidas > fc._depois_de + 3), "a leitura não passou do erro"
        ticks_no_erro = store.counter("poll.tick")
        assert await _ate(lambda: store.counter("poll.tick") > ticks_no_erro + 5), (
            "o laço não voltou a contar poll.tick quando a leitura voltou"
        )
        desconexoes = fc.disconnects
        handles = set(fc.handles)
    finally:
        daemon.stop()
        await run_task

    assert desconexoes == 0, "o erro de leitura desconectou a mesa inteira"
    assert handles == {"p1", "p2", "p3", "p4"}
    assert quedas.qsize() == 1, "a borda da queda é uma por episódio, não uma por tique"
    assert store.counter("poll.erro.leitura") == 3
    buracos = _buracos(horas, fc.hora_do_primeiro_erro)
    assert not buracos, f"o co-op ficou sem forward_all por {max(buracos):.2f} s"


@pytest.mark.asyncio
async def test_os_quatro_handles_ficam_abertos_enquanto_a_leitura_levanta() -> None:
    """(1): durante o erro, nenhum `disconnect` e P2 a P4 seguem abertos."""
    fc = _QuatroControles(levantar=10_000)
    daemon, store, _bus = _daemon(fc)
    horas = _espiar_o_coop(daemon)

    run_task = asyncio.create_task(daemon.run())
    try:
        assert await _ate(lambda: store.counter("poll.erro.leitura") >= 5)
        assert fc.disconnects == 0, "o erro de leitura desconectou a mesa inteira"
        assert fc.handles == {"p1", "p2", "p3", "p4"}
        antes = len(horas)
        assert await _ate(lambda: len(horas) > antes + 5), "o co-op parou com o erro de leitura"
    finally:
        daemon.stop()
        await run_task

    buracos = _buracos(horas, fc.hora_do_primeiro_erro)
    assert not buracos, f"o co-op ficou sem forward_all por {max(buracos):.2f} s"


@pytest.mark.asyncio
async def test_o_coop_gamepad_que_levanta_conta_e_loga_uma_vez(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(3): `aplicar_gamepad_para_multiplos_controles` levanta em dois ciclos."""
    monkeypatch.setattr(lifecycle, "RELOGIOS_LENTOS", PASSOS_RAPIDOS)
    fc = FakeController(transport="usb", states=_estados())
    daemon, store, _bus = _daemon(fc)

    def estoura() -> None:
        raise OSError(5, "Input/output error")

    monkeypatch.setattr(daemon, "aplicar_gamepad_para_multiplos_controles", estoura)

    with capture_logs() as diario:
        run_task = asyncio.create_task(daemon.run())
        try:
            assert await _ate(lambda: store.counter("poll.erro.coop_gamepad") >= 2)
        finally:
            daemon.stop()
            await run_task

    avisos = [
        e for e in diario
        if e.get("log_level") == "warning" and e.get("passo") == "coop_gamepad"
    ]
    assert store.counter("poll.erro.coop_gamepad") >= 2
    assert len(avisos) == 1, f"o aviso deveria sair uma vez por episódio: {avisos}"


@pytest.mark.asyncio
async def test_o_apply_do_modo_que_levanta_nao_diz_aplicada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(4): o `apply_profile_mode` levanta dentro da drenagem."""
    monkeypatch.setattr(lifecycle, "RELOGIOS_LENTOS", PASSOS_RAPIDOS)
    fc = FakeController(transport="usb", states=_estados())
    daemon, store, _bus = _daemon(fc)

    def estoura(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("o apply caiu")

    monkeypatch.setattr(daemon, "apply_profile_mode", estoura)
    daemon._mode_pendente = ModoAdiado(
        mode=None,
        profile=None,
        profile_name=None,
        origin="teste",
        carimbo_manual=daemon._emu_manual_ts,
        nao_antes_de=0.0,
    )

    with capture_logs() as diario:
        run_task = asyncio.create_task(daemon.run())
        try:
            assert await _ate(lambda: store.counter("poll.erro.modo_pendente") >= 1)
        finally:
            daemon.stop()
            await run_task

    eventos = [e.get("event") for e in diario]
    assert "profile_mode_pendencia_aplicada" not in eventos, (
        "o diário disse «aplicada» e o apply levantou"
    )
    avisos = [
        e for e in diario
        if e.get("log_level") == "warning" and e.get("passo") == "modo_pendente"
    ]
    assert len(avisos) == 1


def test_o_log_volta_quando_o_passo_da_certo_de_novo() -> None:
    """O aviso é por episódio: depois de um acerto, a próxima falha avisa de novo."""
    store = StateStore()
    passos = lifecycle._PassosDoLaco(store)
    estado = {"quebra": True}

    def passo() -> str:
        if estado["quebra"]:
            raise OSError("x")
        return "ok"

    with capture_logs() as diario:
        assert passos.passo("p", passo) is lifecycle._FALHOU
        assert passos.passo("p", passo) is lifecycle._FALHOU
        estado["quebra"] = False
        assert passos.passo("p", passo) == "ok"
        estado["quebra"] = True
        assert passos.passo("p", passo) is lifecycle._FALHOU

    assert store.counter("poll.erro.p") == 3
    assert len([e for e in diario if e.get("log_level") == "warning"]) == 2


@pytest.mark.asyncio
async def test_o_heal_do_evdev_e_a_reconciliacao_do_grab_que_levantam_vao_ao_diario(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Os outros dois passos antes calados: o heal do evdev e o grab do primário."""
    from hefesto_dualsense4unix.daemon.subsystems import gamepad

    fc = FakeController(transport="usb", states=_estados())

    def heal() -> bool:
        raise OSError("evdev sumiu")

    fc.heal_evdev_if_stale = heal  # type: ignore[attr-defined]

    def grab(_daemon: Any) -> None:
        raise RuntimeError("grab caiu")

    monkeypatch.setattr(gamepad, "reconciliar_grab_do_primario", grab)
    daemon, store, _bus = _daemon(fc)

    with capture_logs() as diario:
        run_task = asyncio.create_task(daemon.run())
        try:
            assert await _ate(
                lambda: store.counter("poll.erro.heal_evdev") >= 1
                and store.counter("poll.erro.grab_do_primario") >= 1
            )
        finally:
            daemon.stop()
            await run_task

    passos = sorted(
        e["passo"] for e in diario
        if e.get("log_level") == "warning" and e.get("event") == "passo_do_laco_falhou"
    )
    assert passos == ["grab_do_primario", "heal_evdev"]
