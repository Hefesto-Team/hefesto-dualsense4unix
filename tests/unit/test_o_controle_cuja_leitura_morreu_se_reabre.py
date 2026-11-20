"""O controle cuja leitura morreu com o nó ainda no disco se reabre na volta seguinte."""
from __future__ import annotations

import errno
import socket
import threading
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydualsense.enums import ConnectionType
from pydualsense.pydualsense import DSAudio, DSBattery, DSLight, DSState, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core import evdev_reader
from hefesto_dualsense4unix.core import relogio_da_conexao as rel
from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

MESAS = {
    "um-cabo": ("usb",),
    "um-radio": ("bt",),
    "quatro-misturados": ("usb", "bt", "bt", "usb"),
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
def _ambiente(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(evdev_reader, "discover_gamepads", lambda **_k: [])
    monkeypatch.setattr(bp, "TETO_DA_ABERTURA_NA_VOLTA_SEC", 0.5)
    rel.RELOGIO.limpar()
    yield
    rel.RELOGIO.limpar()


def _mesa(de_pe: tuple[str, ...]) -> tuple[PyDualSenseController, list[_Handle]]:
    chaves = [
        (f"aa:bb:cc:00:00:0{n + 1}", f"/ensaio/hidraw{n}".encode(), False)
        for n in range(len(de_pe))
    ]
    transportes = {path: t for (_m, path, _e), t in zip(chaves, de_pe, strict=True)}
    abertos: list[_Handle] = []
    ctl = PyDualSenseController()
    ctl._enumerate_device_keys = lambda: chaves  # type: ignore[method-assign]

    def abrir(path: bytes, *, is_edge: bool) -> _Handle:
        del is_edge
        handle = _Handle(path, transportes[path])
        abertos.append(handle)
        return handle

    ctl._open_one = abrir  # type: ignore[method-assign]
    return ctl, abertos


@pytest.mark.parametrize("mesa", sorted(MESAS))
def test_o_handle_morto_se_troca_e_os_vizinhos_ficam(mesa: str) -> None:
    """D-1911-O-CONTROLE-CUJA-LEITURA-MORREU-SE-REABRE: o morto se reabre, cada um na vez."""
    ctl, abertos = _mesa(MESAS[mesa])
    ctl.connect()
    assert ctl.is_connected()

    for chave in sorted(ctl._handles):
        antes = dict(ctl._handles)
        morto = antes[chave]
        morto.connected = False

        ctl.connect()

        assert morto.closed
        novo = ctl._handles[chave]
        assert novo is not morto and novo.connected
        assert novo._pinned_path == morto._pinned_path
        assert {k: h for k, h in ctl._handles.items() if k != chave} == {
            k: h for k, h in antes.items() if k != chave
        }
        assert ctl.is_connected()
        assert set(ctl.alvos_conectados()) == set(antes)
    assert len(abertos) == 2 * len(MESAS[mesa])


def test_o_handle_que_esta_fechando_nao_se_troca() -> None:
    """D-1911-O-CONTROLE-CUJA-LEITURA-MORREU-SE-REABRE: quem fecha não ganha outro."""
    ctl, abertos = _mesa(MESAS["um-cabo"])
    ctl.connect()
    handle = next(iter(ctl._handles.values()))
    handle.connected = False
    handle._fechando = True  # type: ignore[attr-defined]

    ctl.connect()

    assert ctl._handles[next(iter(ctl._handles))] is handle
    assert len(abertos) == 1


class _Diario:
    def __init__(self) -> None:
        self.linhas: list[tuple[str, dict[str, Any]]] = []

    def _guardar(self, evento: str, **campos: Any) -> None:
        self.linhas.append((evento, campos))

    debug = info = warning = error = _guardar

    def eventos(self, nome: str) -> list[dict[str, Any]]:
        return [campos for evento, campos in self.linhas if evento == nome]


class _NoQueTropeca(bp._DispositivoPorFd):
    """O fd do broker de verdade; a primeira escrita dá ``EPROTO``, como o hidraw passageiro."""

    def __init__(self, fd: int) -> None:
        super().__init__(fd)
        self.tropecou = threading.Event()

    def write(self, data: bytes) -> int:
        if not self.tropecou.is_set():
            self.tropecou.set()
            raise OSError(errno.EPROTO, "Protocol error")
        return super().write(data)


@pytest.fixture
def no_do_disco(tmp_path: Path) -> Iterator[tuple[bytes, socket.socket, int]]:
    caminho = tmp_path / "hidraw7"
    caminho.write_bytes(b"")
    nosso, do_kernel = socket.socketpair()
    yield str(caminho).encode(), do_kernel, nosso.detach()
    do_kernel.close()


def _handle(path: bytes, dispositivo: bp._DispositivoPorFd) -> bp._PinnedPyDualSense:
    h = bp._PinnedPyDualSense(path, is_edge=False, dispositivo=dispositivo)
    h.device = dispositivo
    h.is_edge = False
    h.light = DSLight()
    h.audio = DSAudio()
    h.triggerL = DSTrigger()
    h.triggerR = DSTrigger()
    h.state = DSState()
    h.battery = DSBattery()
    h.conType = ConnectionType.USB
    h.input_report_length = 64
    h.output_report_length = 48
    h.ds_thread = True
    h.connected = True
    h._throttle_sec = 0.002
    return h


def _girar(h: bp._PinnedPyDualSense) -> threading.Thread:
    fio = threading.Thread(target=h.sendReport, daemon=True, name="volta")
    h.report_thread = fio
    fio.start()
    return fio


def test_o_tropeco_no_hidraw_vai_ao_diario(
    monkeypatch: pytest.MonkeyPatch, no_do_disco: tuple[bytes, socket.socket, int]
) -> None:
    """D-1911-O-CONTROLE-CUJA-LEITURA-MORREU-SE-REABRE: a volta que sai deixa a linha."""
    diario = _Diario()
    monkeypatch.setattr(bp, "logger", diario)
    caminho, _kernel, fd = no_do_disco
    dispositivo = _NoQueTropeca(fd)
    h = _handle(caminho, dispositivo)

    _girar(h).join(timeout=5.0)

    assert dispositivo.tropecou.is_set()
    assert h.connected is False
    assert diario.eventos("report_thread_saiu") == [
        {"path": caminho, "tipo": "OSError", "errno": errno.EPROTO}
    ]


def test_o_fecho_e_o_no_que_saiu_ficam_calados(
    monkeypatch: pytest.MonkeyPatch, no_do_disco: tuple[bytes, socket.socket, int],
    tmp_path: Path,
) -> None:
    """D-1911-O-CONTROLE-CUJA-LEITURA-MORREU-SE-REABRE: o fecho e o nó que saiu não falam."""
    diario = _Diario()
    monkeypatch.setattr(bp, "logger", diario)
    caminho, _kernel, fd = no_do_disco
    h = _handle(caminho, bp._DispositivoPorFd(fd))
    montar = h.prepareReport

    def fechar_no_meio_da_volta() -> Any:
        h._baixar_o_sinal()
        return montar()

    h.prepareReport = fechar_no_meio_da_volta  # type: ignore[method-assign]
    _girar(h).join(timeout=5.0)
    h.close()

    nosso, do_kernel = socket.socketpair()
    saiu = _handle(str(tmp_path / "hidraw8").encode(), bp._DispositivoPorFd(nosso.detach()))
    do_kernel.close()
    _girar(saiu).join(timeout=5.0)

    assert saiu.connected is False
    assert diario.eventos("report_thread_saiu") == []
