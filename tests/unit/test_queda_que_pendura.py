"""QUEDA-QUE-PENDURA-01: controle que some do rádio não pode pendurar o daemon."""
from __future__ import annotations

import threading
import time
import types
from collections.abc import Iterator
from typing import Any

import hidapi
import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import (
    CLOSE_JOIN_TIMEOUT_SEC,
    _PinnedPyDualSense,
)


class _HidDevice:
    """O ponteiro C do handle: só o modo do `hid_read` (nasce bloqueante)."""

    def __init__(self) -> None:
        self.bloqueante = True


def _trocar_o_modo(dev: _HidDevice, nonblock: int) -> int:
    dev.bloqueante = not nonblock
    return 0


class _DeviceMorto:
    """Um `hidapi.Device` cujo `read` não volta até o kernel tirar o nó."""

    def __init__(self) -> None:
        self._device: _HidDevice | None = _HidDevice()
        self.kernel = threading.Event()
        self.dentro = threading.Event()
        self.leitores = 0
        self.fechado = False
        self.liberado_com_leitor_dentro = False

    def _conferir(self) -> None:
        if self._device is None:
            raise OSError("Trying to perform action on closed device.")

    def read(self, _n: int, timeout_ms: int = 0, blocking: bool = False) -> bytes:
        self._conferir()
        self.leitores += 1
        self.dentro.set()
        self.kernel.wait()
        self.leitores -= 1
        if self._device is None:
            raise TypeError(
                "initializer for ctype 'hid_device *' must be a cdata pointer, "
                "not NoneType"
            )
        raise OSError("Failed to read from HID device")

    def write(self, data: bytes) -> None:
        self._conferir()

    def close(self) -> None:
        self._conferir()
        if self.leitores:
            self.liberado_com_leitor_dentro = True
        self.fechado = True
        self._device = None


_CRIADOS: list[tuple[_DeviceMorto, threading.Thread]] = []


@pytest.fixture(autouse=True)
def _o_c_do_hidapi(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """O lado C do `hidapi` no modo do handle; e, no fim, o kernel solta todos."""
    monkeypatch.setattr(
        hidapi, "hidapi", types.SimpleNamespace(hid_set_nonblocking=_trocar_o_modo)
    )
    try:
        yield
    finally:
        for device, thread in _CRIADOS:
            device.kernel.set()
            thread.join(timeout=2.0)
        _CRIADOS.clear()


def _handle_com_thread_pendurada() -> tuple[Any, _DeviceMorto, threading.Thread]:
    """Um `_PinnedPyDualSense` com a `report_thread` DE PRODUÇÃO presa no `read`."""
    ds = _PinnedPyDualSense.__new__(_PinnedPyDualSense)
    device = _DeviceMorto()
    ds.device = device
    ds.input_report_length = 78
    ds._output_muted = True
    ds._throttle_sec = 0.0
    ds._pinned_path = b"/dev/hidraw-da-queda"
    ds.ds_thread = True
    ds.connected = True
    thread = threading.Thread(target=ds.sendReport, daemon=True)
    ds.report_thread = thread
    _CRIADOS.append((device, thread))
    thread.start()
    assert device.dentro.wait(2.0), "a thread não chegou ao read"
    return ds, device, thread


class TestOCloseNaoPendura:
    def test_o_close_volta_mesmo_com_a_thread_travada_no_read(self) -> None:
        """Mordida: devolver o `join()` sem teto do upstream trava aqui."""
        ds, _device, _thread = _handle_com_thread_pendurada()
        inicio = time.monotonic()
        ds.close()
        gasto = time.monotonic() - inicio
        assert gasto < CLOSE_JOIN_TIMEOUT_SEC * 4, (
            f"o close levou {gasto:.2f}s — o join voltou a ser sem teto"
        )

    def test_o_fd_nao_fecha_com_a_thread_dentro_e_fecha_quando_ela_sai(self) -> None:
        """O `hid_device` fecha com quem sai do C por último, nunca por cima dele."""
        ds, device, thread = _handle_com_thread_pendurada()
        ds.close()
        assert device.fechado is False, "o fd fechou com a thread dentro do read"
        device.kernel.set()
        thread.join(timeout=2.0)
        assert not thread.is_alive(), "o OSError não encerrou o laço"
        assert device.fechado is True, "a thread saiu e não fechou"
        assert device.liberado_com_leitor_dentro is False

    def test_o_ds_thread_e_baixado_antes_de_tudo(self) -> None:
        """O sinal cooperativo continua sendo a via NORMAL de encerrar."""
        ds, _device, _thread = _handle_com_thread_pendurada()
        ds.close()
        assert ds.ds_thread is False


class TestOTetoEHonesto:
    def test_o_teto_e_curto_o_bastante_para_nao_ser_notado(self) -> None:
        """Um teto de vários segundos seria trocar 90 s por 10 s — não é cura."""
        assert 0 < CLOSE_JOIN_TIMEOUT_SEC <= 1.0

    def test_close_sem_thread_nao_explode(self) -> None:
        """Handle que nunca chegou a subir a thread (falha no init) fecha igual."""
        ds = _PinnedPyDualSense.__new__(_PinnedPyDualSense)
        device = _DeviceMorto()
        ds.device = device
        ds.ds_thread = True
        ds.report_thread = None
        ds.close()
        assert device.fechado

    def test_close_com_device_que_recusa_fechar_nao_propaga(self) -> None:
        """`close()` roda no caminho de desligamento — não pode levantar."""

        class _Teimoso:
            def close(self) -> None:
                raise OSError("dispositivo já sumiu")

        ds = _PinnedPyDualSense.__new__(_PinnedPyDualSense)
        ds.device = _Teimoso()
        ds.ds_thread = True
        ds.report_thread = None
        ds.close()


@pytest.mark.parametrize("vivos", [1, 2, 4])
def test_varios_handles_mortos_somam_um_teto_cada_e_nao_noventa(vivos: int) -> None:
    """Quatro controles na mesa que caem juntos ainda cabem no desligamento."""
    handles = [_handle_com_thread_pendurada() for _ in range(vivos)]
    inicio = time.monotonic()
    for ds, _device, _thread in handles:
        ds.close()
    gasto = time.monotonic() - inicio
    assert gasto < CLOSE_JOIN_TIMEOUT_SEC * 4 * vivos
    for _ds, device, thread in handles:
        device.kernel.set()
        thread.join(timeout=2.0)
        assert device.fechado
        assert device.liberado_com_leitor_dentro is False
