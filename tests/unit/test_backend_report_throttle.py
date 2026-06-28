"""BUG-MULTI-CONTROLLER-BT-CRC-CONTENTION-01 — o loop sendReport da pydualsense
roda sem pausa (na taxa do controle), e com 2+ controles as threads saturam o
controlador USB compartilhado, degradando o link Bluetooth (CRC fails → output do
BT morre). `_PinnedPyDualSense` sobrescreve sendReport para throttlar o ciclo
read+write a ~125Hz (REPORT_THREAD_THROTTLE_SEC), o que basta para o output e
elimina a contenção. Como o INPUT vem do evdev, throttlar não custa nada.

Estes testes garantem que o throttle não regrida (o flush de output continua
acontecendo, o sleep usa a constante, e o loop encerra ao baixar ds_thread).
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as bp


def test_throttle_default_positivo() -> None:
    """O throttle vem ligado por default (>0) para já proteger o caso multi."""
    assert bp.REPORT_THREAD_THROTTLE_SEC > 0


def test_pinned_override_de_sendreport() -> None:
    """`_PinnedPyDualSense` sobrescreve o sendReport do upstream (não herda o
    loop sem pausa)."""
    import pydualsense

    assert (
        bp._PinnedPyDualSense.sendReport is not pydualsense.pydualsense.sendReport
    )


def test_sendreport_throttla_e_faz_flush(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cada ciclo lê, escreve o output (flush) e dorme REPORT_THREAD_THROTTLE_SEC;
    o loop para quando ds_thread vira False."""
    inst = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    inst.input_report_length = 64
    inst.connected = True
    inst.ds_thread = True

    calls = {"read": 0, "write": 0, "sleep": 0}

    class _FakeDev:
        def read(self, _n: int) -> bytes:
            calls["read"] += 1
            return bytes(_n)

    inst.device = _FakeDev()

    def _count_write(_r: object) -> None:
        calls["write"] += 1

    monkeypatch.setattr(inst, "readInput", lambda _r: None)
    monkeypatch.setattr(inst, "prepareReport", lambda: [0] * 64)
    monkeypatch.setattr(inst, "writeReport", _count_write)

    def _fake_sleep(secs: float) -> None:
        assert secs == bp.REPORT_THREAD_THROTTLE_SEC
        calls["sleep"] += 1
        if calls["sleep"] >= 3:
            inst.ds_thread = False  # encerra o loop após 3 ciclos

    monkeypatch.setattr(bp.time, "sleep", _fake_sleep)

    inst.sendReport()

    assert calls["sleep"] == 3
    assert calls["read"] >= 3  # leu a cada ciclo
    assert calls["write"] >= 3  # E fez flush do output a cada ciclo (broadcast vivo)


def test_sendreport_encerra_em_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    """OSError (device sumiu) marca desconectado e sai do loop sem vazar a thread."""
    inst = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    inst.input_report_length = 64
    inst.connected = True
    inst.ds_thread = True

    class _BoomDev:
        def read(self, _n: int) -> bytes:
            raise OSError("device foi embora")

    inst.device = _BoomDev()
    inst.sendReport()

    assert inst.connected is False
