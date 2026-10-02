"""BUG-MULTI-CONTROLLER-BT-CRC-CONTENTION-01 — o loop sendReport da pydualsense
roda sem pausa (na taxa do controle), e com 2+ controles as threads saturam o
controlador USB compartilhado, degradando o link Bluetooth (CRC fails → output do
BT morre). `_PinnedPyDualSense` sobrescreve sendReport para throttlar o ciclo
read+write a ~125Hz (REPORT_THREAD_THROTTLE_SEC), o que basta para o output e
elimina a contenção.

O throttle marca a SAÍDA. A entrada (o botão do microfone e o bit de mudo, que
só chegam por este laço) não envelhece com ele porque a volta esvazia a fila do
hidraw (O-BOTAO-DO-MIC-CHEGA-NA-HORA-01, 29/09/2026; a régua da idade é
`test_o_botao_do_mic_chega_na_hora.py`). Esta linha dizia que a entrada vinha do
evdev e que throttlar não custava nada: com UMA leitura por volta, custava 63
voltas de idade (2,1 s com os quatro no rádio).

Estes testes garantem que o throttle não regrida (o flush de output continua
acontecendo, o sleep usa a constante, e o loop encerra ao baixar ds_thread).
"""
from __future__ import annotations

import types

import hidapi
import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as bp


class _HidDevice:
    """O `hid_device` do C: só o modo do `hid_read` (nasce bloqueante)."""

    def __init__(self) -> None:
        self.bloqueante = True


def _trocar_o_modo(dev: _HidDevice, nonblock: int) -> int:
    dev.bloqueante = not nonblock
    return 0


@pytest.fixture(autouse=True)
def _o_c_do_hidapi(monkeypatch: pytest.MonkeyPatch) -> None:
    """O lado C do `hidapi`: o laço troca o modo do handle na primeira volta."""
    monkeypatch.setattr(
        hidapi, "hidapi", types.SimpleNamespace(hid_set_nonblocking=_trocar_o_modo)
    )


class _DevComFila:
    """Um `hidapi.Device` com a fila sempre cheia: todo `read` tem report."""

    def __init__(self) -> None:
        self._device = _HidDevice()

    def read(self, _n: int) -> bytes:
        return bytes(_n)


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


def _make_inst() -> bp._PinnedPyDualSense:
    inst = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    inst.input_report_length = 64
    inst.connected = True
    inst.ds_thread = True
    inst._throttle_sec = bp.REPORT_THREAD_THROTTLE_SEC
    inst._last_out_report = None
    inst._last_write_at = 0.0
    inst._last_change_at = float("-inf")
    inst._output_muted = False
    inst._rumble_active = False
    inst._rumble_stop_pending = False
    return inst


def test_sendreport_throttla_e_escreve_so_quando_muda(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cada ciclo lê e dorme `_throttle_sec`; o write OUT só acontece quando o"""
    inst = _make_inst()

    calls = {"read": 0, "write": 0, "sleep": 0}
    reports = [[0] * 64, [0] * 64, [1] + [0] * 63]

    class _FakeDev(_DevComFila):
        def read(self, _n: int) -> bytes:
            calls["read"] += 1
            return bytes(_n)

    inst.device = _FakeDev()

    def _count_write(_r: object) -> None:
        calls["write"] += 1

    monkeypatch.setattr(inst, "readInput", lambda _r: None)
    monkeypatch.setattr(inst, "prepareReport", lambda: reports[min(calls["sleep"], 2)])
    monkeypatch.setattr(inst, "writeReport", _count_write)

    def _fake_sleep(secs: float) -> None:
        assert secs == bp.REPORT_THREAD_THROTTLE_SEC
        calls["sleep"] += 1
        if calls["sleep"] >= 3:
            inst.ds_thread = False

    monkeypatch.setattr(bp.time, "sleep", _fake_sleep)

    inst.sendReport()

    assert calls["sleep"] == 3
    assert calls["read"] >= 3
    assert calls["write"] == 2


def test_sendreport_keepalive_reescreve_report_identico(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem mudança no report, o write ainda acontece a cada"""
    inst = _make_inst()

    calls = {"write": 0, "sleep": 0}
    now = {"t": 100.0}

    inst.device = _DevComFila()
    monkeypatch.setattr(inst, "readInput", lambda _r: None)
    monkeypatch.setattr(inst, "prepareReport", lambda: [0] * 64)
    def _count_write(_r: object) -> None:
        calls["write"] += 1

    monkeypatch.setattr(inst, "writeReport", _count_write)
    monkeypatch.setattr(bp.time, "monotonic", lambda: now["t"])

    def _fake_sleep(_secs: float) -> None:
        calls["sleep"] += 1
        now["t"] += bp.OUT_REPORT_KEEPALIVE_SEC + 0.01
        if calls["sleep"] >= 3:
            inst.ds_thread = False

    monkeypatch.setattr(bp.time, "sleep", _fake_sleep)

    inst.sendReport()

    assert calls["write"] == 3


def test_sendreport_mutado_nao_escreve_nem_keepalive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FEAT-NATIVE-OUTPUT-MUTE-01: mutado (Modo Nativo), ZERO writes — nem o"""
    inst = _make_inst()
    inst._output_muted = True

    calls = {"write": 0, "sleep": 0}
    now = {"t": 100.0}

    inst.device = _DevComFila()
    monkeypatch.setattr(inst, "readInput", lambda _r: None)
    monkeypatch.setattr(inst, "prepareReport", lambda: [0] * 64)

    def _count_write(_r: object) -> None:
        calls["write"] += 1

    monkeypatch.setattr(inst, "writeReport", _count_write)
    monkeypatch.setattr(bp.time, "monotonic", lambda: now["t"])

    def _fake_sleep(_secs: float) -> None:
        calls["sleep"] += 1
        now["t"] += bp.OUT_REPORT_KEEPALIVE_SEC + 0.01
        if calls["sleep"] >= 3:
            inst.ds_thread = False

    monkeypatch.setattr(bp.time, "sleep", _fake_sleep)

    inst.sendReport()

    assert calls["write"] == 0
    assert calls["sleep"] == 3


def test_set_output_mute_propaga_e_forca_reassert_ao_desmutar() -> None:
    """Backend propaga o mute a todos os handles; desmutar limpa o dirty-flag"""
    ctl = bp.PyDualSenseController()

    class _FakeHandle:
        def __init__(self) -> None:
            self._output_muted = False
            self._last_out_report: list[int] | None = [1, 2, 3]

    h1, h2 = _FakeHandle(), _FakeHandle()
    ctl._handles = {"aa": h1, "bb": h2}  # type: ignore[dict-item]

    ctl.set_output_mute(True)
    assert h1._output_muted and h2._output_muted
    assert h1._last_out_report == [1, 2, 3]

    ctl.set_output_mute(False)
    assert not h1._output_muted and not h2._output_muted
    assert h1._last_out_report is None
    assert h2._last_out_report is None


def test_sendreport_encerra_em_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    """OSError (device sumiu) marca desconectado e sai do loop sem vazar a thread."""
    inst = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    inst.input_report_length = 64
    inst.connected = True
    inst.ds_thread = True

    class _BoomDev(_DevComFila):
        def read(self, _n: int) -> bytes:
            raise OSError("device foi embora")

    inst.device = _BoomDev()
    inst.sendReport()

    assert inst.connected is False
    assert inst.device._device.bloqueante is False, "saiu antes de chegar ao `read`"
