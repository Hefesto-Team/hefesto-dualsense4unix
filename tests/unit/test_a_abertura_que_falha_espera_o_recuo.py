"""A abertura que falha espera o recuo: só a abertura deixada em voo que abriu acorda a volta.

O ensaio roda o `reconnect_loop` e o `PyDualSenseController` de verdade; o dublê faz só o papel
do `init` do pydualsense, que falha na hora como o broker fora do ar ou a recusa da tela de entrada.
"""
from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import Any

import pytest
from structlog.testing import capture_logs

from hefesto_dualsense4unix.core import backend_pydualsense as backend_mod
from hefesto_dualsense4unix.core import evdev_reader
from hefesto_dualsense4unix.core import relogio_da_conexao as rel
from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.evdev_reader import InputDirWatch
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon import connection as conn

JANELA_S = 3.0
TETO_DE_CONNECTS = 6
ACORDA_EM_S = 0.1
PASSO_S = 0.005
NO_QUE_FALHA = b"/ensaio/hidraw9"
QUEM_FALHA = "aa:bb:cc:00:00:09"
MESAS = {
    "mesa-vazia": (),
    "um-cabo-de-pe": ("usb",),
    "um-radio-de-pe": ("bt",),
    "tres-de-pe": ("usb", "bt", "usb"),
}


class _Handle:
    def __init__(self, path: bytes, transporte: str) -> None:
        self._pinned_path = path
        self.closed = False
        self.conType = SimpleNamespace(name=transporte.upper())
        self.state = SimpleNamespace()
        self.connected = True

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def _ambiente(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(evdev_reader, "discover_gamepads", lambda **_k: [])
    monkeypatch.setattr(backend_mod, "TETO_DA_ABERTURA_NA_VOLTA_SEC", 0.1)

    async def _nada(*_a: Any, **_k: Any) -> int:
        return 0

    for nome in ("vigiar_escritor_cru", "carimbar_o_nascimento", "restore_last_profile",
                 "reaplicar_som_em_todos_os_alvos", "reapply_speaker_after_connect",
                 "reapply_mic_after_connect"):
        monkeypatch.setattr(conn, nome, _nada)
    monkeypatch.setattr(conn, "anunciar_a_chegada", lambda *_a, **_k: 0)
    rel.RELOGIO.limpar()
    yield
    rel.RELOGIO.limpar()


def _backend(
    de_pe: tuple[str, ...], abrir_o_que_falha: Callable[[], _Handle | None]
) -> tuple[PyDualSenseController, list[float]]:
    chaves = [
        (f"aa:bb:cc:00:00:0{n + 1}", f"/ensaio/hidraw{n}".encode(), False)
        for n in range(len(de_pe))
    ]
    transportes = {path: t for (_m, path, _e), t in zip(chaves, de_pe, strict=True)}
    chaves.append((QUEM_FALHA, NO_QUE_FALHA, False))
    ctl = PyDualSenseController()
    ctl._enumerate_device_keys = lambda: chaves  # type: ignore[method-assign]

    def abrir(path: bytes, *, is_edge: bool) -> _Handle | None:
        del is_edge
        if path == NO_QUE_FALHA:
            return abrir_o_que_falha()
        return _Handle(path, transportes[path])

    ctl._open_one = abrir  # type: ignore[method-assign]
    connects: list[float] = []
    original = ctl.connect

    def contar() -> None:
        connects.append(time.monotonic())
        original()

    ctl.connect = contar  # type: ignore[method-assign]
    return ctl, connects


async def _girar(ctl: PyDualSenseController, ate: Callable[[], bool], prazo_s: float) -> None:
    fios = ThreadPoolExecutor(2)
    parar = asyncio.Event()

    async def _bloqueante(funcao: Any, *args: Any) -> Any:
        return await asyncio.get_running_loop().run_in_executor(fios, funcao, *args)

    daemon = SimpleNamespace(
        controller=ctl,
        bus=EventBus(),
        store=None,
        _stop_event=parar,
        _is_stopping=parar.is_set,
        _run_blocking=_bloqueante,
        _arm_input_grace=lambda: None,
        is_native_mode=lambda: False,
        _tasks=[],
        _hidraw_broker_executor=fios,
    )
    tarefa = asyncio.create_task(
        conn.reconnect_loop(daemon, input_watch=InputDirWatch(root="/nao-existe"))
    )
    fim = time.monotonic() + prazo_s
    while not ate() and time.monotonic() < fim:
        await asyncio.sleep(PASSO_S)
    parar.set()
    tarefa.cancel()
    await asyncio.gather(tarefa, return_exceptions=True)
    fios.shutdown(wait=False)
    ctl.disconnect()


@pytest.mark.parametrize("mesa", list(MESAS))
def test_a_abertura_que_falha_espera_o_recuo_e_vai_ao_diario_uma_vez(mesa: str) -> None:
    """D-1911-A-ABERTURA-QUE-FALHA-ESPERA-O-RECUO: a falha espera o recuo e cala no diário."""

    def recusa() -> _Handle | None:
        raise OSError("peer_rejected")

    ctl, connects = _backend(MESAS[mesa], recusa)
    with capture_logs() as linhas:
        asyncio.run(_girar(ctl, lambda: False, JANELA_S))
    falhas = [linha for linha in linhas if linha["event"] == "backend_open_one_failed"]
    assert len(connects) <= TETO_DE_CONNECTS, f"a volta girou sem recuo: {len(connects)}"
    assert len(falhas) == 1, f"uma linha por volta no diário: {len(falhas)}"


def test_a_falha_que_muda_de_erro_volta_ao_diario_com_a_contagem() -> None:
    erros = iter(["broker_fora", "broker_fora", "broker_fora", "peer_rejected"])

    def recusa() -> _Handle | None:
        raise OSError(next(erros, "peer_rejected"))

    ctl, _connects = _backend((), recusa)
    ctl.ouvir_as_aberturas(lambda: None)
    with capture_logs() as linhas:
        for _ in range(5):
            ctl.connect()
    falhas = [linha for linha in linhas if linha["event"] == "backend_open_one_failed"]
    assert [(f["err"], f["repeticoes"]) for f in falhas] == [
        ("broker_fora", 0),
        ("peer_rejected", 3),
    ]
    ctl.disconnect()


@pytest.mark.parametrize("mesa", ["mesa-vazia", "tres-de-pe"])
def test_a_abertura_lenta_que_abre_depois_da_colheita_acorda_a_volta(mesa: str) -> None:
    solto = threading.Event()
    soltou_em: list[float] = []

    def demora() -> _Handle | None:
        solto.wait(JANELA_S * 2)
        return _Handle(NO_QUE_FALHA, "bt")

    ctl, connects = _backend(MESAS[mesa], demora)

    def soltar_na_terceira_volta() -> bool:
        if len(connects) >= 3 and not soltou_em:
            soltou_em.append(time.monotonic())
            solto.set()
        return bool(soltou_em) and QUEM_FALHA in ctl._handles

    asyncio.run(_girar(ctl, soltar_na_terceira_volta, JANELA_S * 2))
    assert soltou_em, f"a volta não chegou à terceira tentativa: {len(connects)}"
    depois = [t - soltou_em[0] for t in connects if t >= soltou_em[0]]
    assert depois and depois[0] < ACORDA_EM_S, f"a abertura não acordou a volta: {depois}"


def test_so_a_abertura_deixada_em_voo_que_abriu_toca_o_sino() -> None:
    solto = threading.Event()
    toques: list[float] = []

    def demora() -> _Handle | None:
        solto.wait(JANELA_S)
        return _Handle(NO_QUE_FALHA, "usb")

    ctl, _connects = _backend(("usb", "bt"), demora)
    ctl.ouvir_as_aberturas(lambda: toques.append(time.monotonic()))
    ctl.connect()
    assert not toques, "a abertura colhida pelo próprio connect tocou o sino"
    solto.set()
    fim = time.monotonic() + JANELA_S
    while not toques and time.monotonic() < fim:
        time.sleep(PASSO_S)
    assert len(toques) == 1
    ctl.connect()
    assert QUEM_FALHA in ctl._handles
    ctl.disconnect()
