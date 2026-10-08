"""ONDA0-Z5/T2+T3 — as três rotas, com a mesma mesa vazia, no mesmo daemon.

Antes desta sprint, `daemon.status` e o topo de `daemon.state_full` liam a
última leitura do laço de poll (que só ESCREVIA enquanto havia controle),
enquanto `controller.list` já lia certo, direto dos handles abertos do
backend. Duas fontes para o mesmo fato — medido em 23/08/2026 (ONDA0-Z5
§2.2): `connected: true, transport: "bt", battery_pct: 75` em `daemon.status`
e no topo de `state_full`, com ZERO controles na bancada.

**Achado durante a execução, registrado por transparência**: o T2 original
propunha uma função `mesa_do_daemon()`, dona única, lendo os handles abertos
para os TRÊS handlers. Implementada e testada, ela reprovou TRÊS testes já
medidos: `test_conserto_1_7_o_ramo_sem_mesa_e_o_plural_do_doctor.py` (duas
vezes) e `test_ipc_state_full_live.py::test_state_full_neutro_quando_ambos_none`.
O motivo: o topo de `state_full` tem propósito PRÓPRIO, testado — é a leitura
do PRIMÁRIO no último tick do poll (`daemon._last_state`), e pode DIVERGIR de
`controllers` (que vem dos handles) DE PROPÓSITO: `native_bt_fragil` usa essa
divergência para saber quando confiar na lista por-controle e quando cair na
regra antiga (só o primário, sem `describe_controllers`). Colapsar as duas
fontes teria apagado essa distinção sem nota — o oposto da regra da casa.

A cura real é só a T1 (`lifecycle.py` escreve `None` na BORDA de queda, uma
vez): com `store.controller` e `daemon._last_state` corretamente `None`
depois da queda, `daemon.status` e o topo de `state_full` JÁ respondem
`connected: false` — o código dos dois handlers não mudou nesta sprint.
Este arquivo prova que as três rotas concordam numa queda REAL, com o mesmo
daemon (poll loop de verdade), não com um estado montado à mão.
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController


def _mk_states(n: int, transport: str = "bt") -> list[ControllerState]:
    return [
        ControllerState(
            battery_pct=80, l2_raw=0, r2_raw=0, connected=True,
            transport=transport,  # type: ignore[arg-type]
        )
        for _ in range(n)
    ]


PRAZO_S = 5.0


async def _esperar(
    condicao: Callable[[], bool],
    o_que: str,
    prazo_s: float = PRAZO_S,
    a_cada_volta: Callable[[], None] | None = None,
) -> None:
    """Espera a CONDIÇÃO, não o relógio: sob carga o laço de poll chega tarde, e 0,2 s fixos
    desmentiam o teste (6 de 10 corridas com a CPU saturada). Estourou o prazo, a mensagem
    diz o que não aconteceu."""
    limite = time.monotonic() + prazo_s
    while not condicao():
        if time.monotonic() >= limite:
            pytest.fail(f"em {prazo_s:.0f} s não aconteceu: {o_que}")
        if a_cada_volta is not None:
            a_cada_volta()
        await asyncio.sleep(0.01)


def _desplugar(fc: FakeController) -> None:
    """O controle sai da mesa e NÃO volta: o `connect()` de quem sonda acha o aparelho ausente.

    O dublê religava sozinho: o `reconnect_loop` do daemon sonda com `controller.connect()`, e
    o `connect()` do `FakeController` põe `_connected = True` sem aparelho nenhum. Medido sob
    carga (disconnect em 0,113 s, connect em 0,114 s): a queda era desfeita antes de o laço de
    poll a ver. Um controle de verdade desplugado faz o `connect()` falhar.
    """

    def sem_aparelho() -> None:
        raise RuntimeError("sem dispositivo: o controle foi desplugado")

    fc.connect = sem_aparelho  # type: ignore[method-assign]
    fc.disconnect()


@pytest.mark.asyncio
async def test_as_tres_rotas_concordam_depois_da_queda_real(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mordida do aceite §9.1 da ONDA0-Z5, com uma queda de verdade."""
    target = tmp_path / "perfis"

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)

    fc = FakeController(transport="bt", states=_mk_states(60, "bt"))
    bus = EventBus()
    store = StateStore()
    daemon = Daemon(
        controller=fc, bus=bus, store=store,
        config=DaemonConfig(
            poll_hz=200, auto_reconnect=False,
            ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False,
        ),
    )

    run_task = asyncio.create_task(daemon.run())
    try:
        # a borda de queda só dispara se houve ao menos um tique conectado (`was_connected`
        # no laço do `lifecycle.py`), e a queda só vale depois de o laço a ter publicado
        await _esperar(
            lambda: store.snapshot().controller is not None,
            "o laço de poll publicar um tique com o controle conectado (store.controller)",
        )
        _desplugar(fc)
        await _esperar(
            lambda: store.snapshot().controller is None and daemon._last_state is None,
            "o laço de poll publicar a queda (store.controller e _last_state vazios)",
            # um connect() que já estava no ar quando o controle saiu ainda pode religar o
            # dublê: o controle desplugado segue desplugado até o laço ver
            a_cada_volta=fc.disconnect,
        )
    except BaseException:
        daemon.stop()
        await run_task
        raise

    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=ProfileManager(controller=fc, store=store),
        socket_path=tmp_path / "hefesto-dualsense4unix.sock",
        daemon=daemon,
    )

    status = await server._handle_daemon_status({})
    state_full = await server._handle_daemon_state_full({})
    controller_list = await server._handle_controller_list({})

    daemon.stop()
    await run_task

    assert status["connected"] is False, "daemon.status"
    assert status["transport"] is None, "daemon.status"
    assert status["battery_pct"] is None, "daemon.status"

    assert state_full["connected"] is False, "daemon.state_full (topo)"
    assert state_full["transport"] is None, "daemon.state_full (topo)"
    assert state_full["battery_pct"] is None, "daemon.state_full (topo)"

    primeira = controller_list["controllers"][0]
    assert primeira["connected"] is False, "controller.list"
    assert primeira["transport"] is None, "controller.list"
