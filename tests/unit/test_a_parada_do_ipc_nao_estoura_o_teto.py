"""A parada do IPC fecha as conexões aceitas, limpa se a espera estourar e nunca avisa em branco.

A-PARADA-DO-IPC-NAO-ESTOURA-O-TETO-CALADA-01: no Python 3.12 o ``wait_closed`` espera as
conexões abertas, e a interface fica conectada; o teto de 2 s cancelava o ``stop`` ali e o
socket, o escrevente e os sensores ficavam.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.daemon import subsystems
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController

_TETO_S = subsystems._TETO_DA_PARADA_DO_SERVIDOR_S


class _Hub:
    def __init__(self) -> None:
        self.parou = False

    def stop_all(self) -> None:
        self.parou = True


def _o_servidor(tmp_path: Path) -> tuple[IpcServer, _Hub]:
    controle = FakeController(transport="usb")
    controle.connect()
    store = StateStore()
    servidor = IpcServer(
        controller=controle,
        store=store,
        profile_manager=ProfileManager(controller=controle, store=store),
        socket_path=tmp_path / "ipc.sock",
    )
    hub = _Hub()
    servidor._sensor_hub = hub
    return servidor, hub


async def _clientes_presos(
    caminho: Path, quantos: int
) -> list[tuple[asyncio.StreamReader, asyncio.StreamWriter]]:
    return [await asyncio.open_unix_connection(str(caminho)) for _ in range(quantos)]


async def _fechar(presos: list[tuple[asyncio.StreamReader, asyncio.StreamWriter]]) -> None:
    for _, escritor in presos:
        escritor.close()


@pytest.mark.parametrize("quantos", [1, 4])
async def test_a_parada_com_clientes_presos_termina_abaixo_do_teto(
    tmp_path: Path, quantos: int
) -> None:
    servidor, hub = _o_servidor(tmp_path)
    await servidor.start()
    presos = await _clientes_presos(servidor.socket_path, quantos)
    await asyncio.sleep(0.05)
    try:
        inicio = time.monotonic()
        await asyncio.wait_for(servidor.stop(), timeout=_TETO_S)
        gasto = time.monotonic() - inicio
    finally:
        await _fechar(presos)
    assert gasto < _TETO_S / 2
    assert not servidor.socket_path.exists()
    assert hub.parou is True
    assert servidor._escrevente is None


async def test_a_limpeza_roda_mesmo_se_a_espera_estourar(tmp_path: Path) -> None:
    servidor, hub = _o_servidor(tmp_path)
    await servidor.start()

    class _ServidorQueNaoFecha:
        def close(self) -> None:
            pass

        async def wait_closed(self) -> None:
            await asyncio.Event().wait()

    real = servidor._server
    assert real is not None
    servidor._server = _ServidorQueNaoFecha()  # type: ignore[assignment]
    try:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(servidor.stop(), timeout=0.3)
    finally:
        real.close()
    assert not servidor.socket_path.exists()
    assert hub.parou is True
    assert servidor._escrevente is None


async def test_a_parada_que_levanta_sem_texto_avisa_pelo_nome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _estoura(_daemon: Any) -> None:
        raise TimeoutError

    passo = subsystems.Passo(nome="ipc", parada=_estoura, parar_em=1)
    monkeypatch.setattr(subsystems, "SUBSYSTEM_REGISTRY", [passo])
    with structlog.testing.capture_logs() as registros:
        await subsystems.parar(object())
    avisos = [r for r in registros if r.get("event") == "subsystem_parada_falhou"]
    assert len(avisos) == 1
    assert avisos[0]["err"] != ""
    assert "TimeoutError" in avisos[0]["err"]
