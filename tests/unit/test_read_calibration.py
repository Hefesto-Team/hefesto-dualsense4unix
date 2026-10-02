"""`read_calibration` do backend (GYRO-01) — feature 0x05 por unidade, fail-safe."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as backend_mod
from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.ds_output_report import BT_FEATURE_CRC_SEED, bt_crc32

_CALIB_USB = bytes([0x05]) + bytes(range(40))


def _calib_bt(*, corrupt: bool = False) -> bytes:
    """Feature 0x05 como chega por BT: 37 B de dado + CRC-32 (seed 0xA3)."""
    corpo = bytes([0x05]) + bytes(range(36))
    crc = bt_crc32(corpo, seed=BT_FEATURE_CRC_SEED)
    report = corpo + crc.to_bytes(4, "little")
    if corrupt:
        report = report[:10] + bytes([report[10] ^ 0xFF]) + report[11:]
    return report


class _FakeHandle:
    """Handle mínimo: `_pinned_path` (fonte do hidraw) + transporte."""

    def __init__(self, path: bytes = b"/dev/hidraw3", *, bt: bool = False) -> None:
        self._pinned_path = path
        if bt:
            self.conType = SimpleNamespace(name="BT")


def _backend(handle: _FakeHandle | None) -> PyDualSenseController:
    inst = PyDualSenseController.__new__(PyDualSenseController)
    PyDualSenseController.__init__(inst, evdev_reader=SimpleNamespace())  # type: ignore[arg-type]
    if handle is not None:
        inst._ds = handle
    return inst


@pytest.fixture()
def hidraw(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Dubla `_read_feature_via_hidraw` — payload por path ou exceção."""
    estado: dict[str, Any] = {"pedidos": []}

    def _fake(
        path: str,
        report_id: int,
        size: int,
        opener: Any = None,
    ) -> bytes:
        estado["pedidos"].append((path, report_id, size))
        estado["openers"] = [*estado.get("openers", []), opener]
        payload = estado.get(path, estado.get("payload"))
        if isinstance(payload, Exception):
            raise payload
        assert payload is not None, f"payload não configurado para {path}"
        return payload

    monkeypatch.setattr(backend_mod, "_read_feature_via_hidraw", _fake)
    return estado


class TestReadCalibration:
    def test_usb_devolve_o_report_integro(self, hidraw: dict[str, Any]) -> None:
        hidraw["payload"] = _CALIB_USB
        backend = _backend(_FakeHandle())
        assert backend.read_calibration() == _CALIB_USB
        assert hidraw["pedidos"] == [("/dev/hidraw3", 0x05, 41)]

    def test_sem_handle_devolve_none(self, hidraw: dict[str, Any]) -> None:
        assert _backend(None).read_calibration() is None
        assert hidraw["pedidos"] == []

    def test_handle_sem_hidraw_devolve_none(self, hidraw: dict[str, Any]) -> None:
        backend = _backend(_FakeHandle(path=b"0001:0002:00"))
        assert backend.read_calibration() is None
        assert hidraw["pedidos"] == []

    def test_eio_do_bt_ocioso_vira_none(self, hidraw: dict[str, Any]) -> None:
        hidraw["payload"] = OSError(5, "Input/output error")
        backend = _backend(_FakeHandle())
        assert backend.read_calibration() is None

    def test_report_curto_vira_none(self, hidraw: dict[str, Any]) -> None:
        hidraw["payload"] = bytes([0x05]) + bytes(30)
        backend = _backend(_FakeHandle())
        assert backend.read_calibration() is None

    def test_report_com_id_errado_vira_none(self, hidraw: dict[str, Any]) -> None:
        hidraw["payload"] = bytes([0x17]) + bytes(40)
        backend = _backend(_FakeHandle())
        assert backend.read_calibration() is None

    def test_bt_com_crc_valido_e_aceito(self, hidraw: dict[str, Any]) -> None:
        hidraw["payload"] = _calib_bt()
        backend = _backend(_FakeHandle(bt=True))
        assert backend.read_calibration() == _calib_bt()

    def test_bt_com_crc_corrompido_vira_none(self, hidraw: dict[str, Any]) -> None:
        hidraw["payload"] = _calib_bt(corrupt=True)
        backend = _backend(_FakeHandle(bt=True))
        assert backend.read_calibration() is None

    def test_usb_nao_exige_crc(self, hidraw: dict[str, Any]) -> None:
        hidraw["payload"] = _CALIB_USB
        backend = _backend(_FakeHandle())
        assert backend.read_calibration() == _CALIB_USB

    def test_por_uniq_mira_o_hidraw_daquele_controle(
        self, hidraw: dict[str, Any]
    ) -> None:
        hidraw["/dev/hidraw7"] = _CALIB_USB
        backend = _backend(None)
        backend._handles = {
            "aabbcc000001": _FakeHandle(path=b"/dev/hidraw3"),
            "aabbcc000002": _FakeHandle(path=b"/dev/hidraw7"),
        }
        backend._primary_key = "aabbcc000001"
        assert backend.read_calibration("aabbcc000002") == _CALIB_USB
        assert hidraw["pedidos"] == [("/dev/hidraw7", 0x05, 41)]

    def test_uniq_desconhecido_devolve_none(self, hidraw: dict[str, Any]) -> None:
        hidraw["payload"] = _CALIB_USB
        backend = _backend(_FakeHandle())
        assert backend.read_calibration("aabbcc000099") is None


class TestIoctlHelper:
    def test_monta_o_hidiocgfeature_e_devolve_o_report(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        chamadas: dict[str, Any] = {}

        monkeypatch.setattr(backend_mod.os, "open", lambda p, f: 99)
        monkeypatch.setattr(
            backend_mod.os, "close", lambda fd: chamadas.setdefault("closed", fd)
        )

        def _fake_ioctl(fd: int, request: int, buf: bytearray, mutate: bool) -> int:
            chamadas["fd"] = fd
            chamadas["request"] = request
            assert buf[0] == 0x05
            buf[: len(_CALIB_USB)] = _CALIB_USB
            return len(_CALIB_USB)

        monkeypatch.setattr(backend_mod.fcntl, "ioctl", _fake_ioctl)
        data = backend_mod._read_feature_via_hidraw("/dev/hidraw3", 0x05, 41)
        assert data == _CALIB_USB
        assert chamadas["closed"] == 99
        assert chamadas["request"] == (3 << 30) | (41 << 16) | (ord("H") << 8) | 0x07


class TestS5FeatureOpener:
    """S-5 (auditoria 21/07): a calibração 0x05 vai pelo opener broker-aware"""

    def test_opener_injetado_e_repassado(self, hidraw: dict[str, Any]) -> None:
        hidraw["payload"] = _CALIB_USB
        backend = _backend(_FakeHandle())
        sentinela = object()
        backend.set_feature_opener(sentinela)  # type: ignore[arg-type]
        assert backend.read_calibration() == _CALIB_USB
        assert hidraw["openers"] == [sentinela]

    def test_sem_opener_passa_none(self, hidraw: dict[str, Any]) -> None:
        hidraw["payload"] = _CALIB_USB
        backend = _backend(_FakeHandle())
        assert backend.read_calibration() == _CALIB_USB
        assert hidraw["openers"] == [None]

    def test_set_feature_opener_none_reverte(self, hidraw: dict[str, Any]) -> None:
        hidraw["payload"] = _CALIB_USB
        backend = _backend(_FakeHandle())
        backend.set_feature_opener(lambda _p: 7)
        backend.set_feature_opener(None)
        backend.read_calibration()
        assert hidraw["openers"] == [None]
