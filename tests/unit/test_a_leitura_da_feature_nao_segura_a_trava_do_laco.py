"""A leitura de feature (calibração, firmware) de um controle não prende a trava do laço."""
from __future__ import annotations

import threading
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as backend_mod
from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.ds_output_report import BT_FEATURE_CRC_SEED, bt_crc32

_CALIB = bytes([0x05]) + bytes(range(40))
_CORPO_BT = bytes([0x05]) + bytes(range(36))
_CALIB_BT = _CORPO_BT + bt_crc32(_CORPO_BT, seed=BT_FEATURE_CRC_SEED).to_bytes(4, "little")
_LIMITE_S = 2.0


class _Handle:
    connected = True

    def __init__(self, path: bytes, *, bt: bool = False) -> None:
        self._pinned_path = path
        if bt:
            self.conType = SimpleNamespace(name="BT")


def _backend(handles: dict[str, _Handle]) -> PyDualSenseController:
    inst = PyDualSenseController.__new__(PyDualSenseController)
    PyDualSenseController.__init__(inst, evdev_reader=SimpleNamespace())  # type: ignore[arg-type]
    inst._handles = dict(handles)
    inst._primary_key = next(iter(handles))
    return inst


class _Ioctl:
    """`ioctl` de mentira: o caminho de `preso` espera o evento de soltura."""

    def __init__(self, preso: str | None = None, *, bt: bool = False) -> None:
        self.preso = preso
        self.bt = bt
        self.entrou = threading.Event()
        self.solta = threading.Event()

    def __call__(self, path: str, report_id: int, size: int, opener: Any = None) -> bytes:
        if path == self.preso:
            self.entrou.set()
            assert self.solta.wait(_LIMITE_S * 5)
        return _CALIB_BT if path in ("/dev/hidraw3", "/dev/hidraw4") and self.bt else _CALIB


def _em_fio(fn: Any) -> tuple[threading.Thread, list[Any]]:
    saida: list[Any] = []
    fio = threading.Thread(target=lambda: saida.append(fn()), daemon=True)
    fio.start()
    return fio, saida


def _responde(fn: Any) -> Any:
    fio, saida = _em_fio(fn)
    fio.join(_LIMITE_S)
    assert not fio.is_alive(), "a chamada esperou a leitura presa: a trava segurou o ioctl"
    return saida[0]


def test_o_laco_responde_com_a_leitura_presa(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2111-LEITURA-DA-FEATURE-SOLTA-A-TRAVA: is_connected e os leitores do tique não esperam."""
    ioctl = _Ioctl(preso="/dev/hidraw3")
    monkeypatch.setattr(backend_mod, "_read_feature_via_hidraw", ioctl)
    backend = _backend({"a": _Handle(b"/dev/hidraw3")})
    leitura, saida = _em_fio(lambda: backend.read_calibration())
    assert ioctl.entrou.wait(_LIMITE_S)
    try:
        assert _responde(backend.is_connected) is True
        assert _responde(backend.alvos_conectados) == {"a": None}
        assert _responde(backend.hidraw_path) == "/dev/hidraw3"
    finally:
        ioctl.solta.set()
        leitura.join(_LIMITE_S)
    assert saida == [_CALIB]


def test_quatro_controles_um_preso_os_tres_seguem(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2111-LEITURA-DA-FEATURE-SOLTA-A-TRAVA: dois cabos e dois rádios, um preso, três leem."""
    ioctl = _Ioctl(preso="/dev/hidraw1", bt=True)
    monkeypatch.setattr(backend_mod, "_read_feature_via_hidraw", ioctl)
    handles = {
        "p1": _Handle(b"/dev/hidraw1"),
        "p2": _Handle(b"/dev/hidraw2"),
        "p3": _Handle(b"/dev/hidraw3", bt=True),
        "p4": _Handle(b"/dev/hidraw4", bt=True),
    }
    backend = _backend(handles)
    preso, saida = _em_fio(lambda: backend._ler_a_feature("p1", 0x05, 41, "calibration"))
    assert ioctl.entrou.wait(_LIMITE_S)
    try:
        assert _responde(lambda: backend._ler_a_feature("p2", 0x05, 41, "calibration")) == _CALIB
        for chave in ("p3", "p4"):
            lido = _responde(
                lambda chave=chave: backend._ler_a_feature(chave, 0x05, 41, "calibration")
            )
            assert lido == _CALIB_BT
        assert _responde(backend.is_connected) is True
        assert preso.is_alive()
    finally:
        ioctl.solta.set()
        preso.join(_LIMITE_S)
    assert saida == [_CALIB]


@pytest.mark.parametrize("troca", ["outro_handle", "saiu"])
def test_handle_trocado_no_meio_devolve_none(
    monkeypatch: pytest.MonkeyPatch, troca: str
) -> None:
    """D-2111-LEITURA-DA-FEATURE-SOLTA-A-TRAVA: o resultado só vale se o handle é o mesmo."""
    ioctl = _Ioctl(preso="/dev/hidraw3")
    monkeypatch.setattr(backend_mod, "_read_feature_via_hidraw", ioctl)
    backend = _backend({"a": _Handle(b"/dev/hidraw3")})
    leitura, saida = _em_fio(lambda: backend.read_calibration())
    assert ioctl.entrou.wait(_LIMITE_S)
    with backend._io_lock:
        if troca == "saiu":
            backend._handles.pop("a")
        else:
            backend._handles["a"] = _Handle(b"/dev/hidraw3")
    ioctl.solta.set()
    leitura.join(_LIMITE_S)
    assert saida == [None]


def test_com_um_controle_e_leitura_rapida_nada_muda(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2111-LEITURA-DA-FEATURE-SOLTA-A-TRAVA: sem concorrência, devolve o report íntegro."""
    monkeypatch.setattr(backend_mod, "_read_feature_via_hidraw", _Ioctl())
    backend = _backend({"a": _Handle(b"/dev/hidraw3")})
    assert backend.read_calibration() == _CALIB
