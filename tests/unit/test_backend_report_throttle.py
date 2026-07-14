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


def _make_inst() -> bp._PinnedPyDualSense:
    inst = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    inst.input_report_length = 64
    inst.connected = True
    inst.ds_thread = True
    # Campos que o __init__ real inicializa (PERF-MULTI-CONTROLLER-01 +
    # FEAT-NATIVE-OUTPUT-MUTE-01).
    inst._throttle_sec = bp.REPORT_THREAD_THROTTLE_SEC
    inst._last_out_report = None
    inst._last_write_at = 0.0
    inst._output_muted = False
    return inst


def test_sendreport_throttla_e_escreve_so_quando_muda(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cada ciclo lê e dorme `_throttle_sec`; o write OUT só acontece quando o
    report MUDA (dirty-flag) — report idêntico repetido não vai ao barramento
    (PERF-MULTI-CONTROLLER-01)."""
    inst = _make_inst()

    calls = {"read": 0, "write": 0, "sleep": 0}
    reports = [[0] * 64, [0] * 64, [1] + [0] * 63]  # muda só no 3º ciclo

    class _FakeDev:
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
            inst.ds_thread = False  # encerra o loop após 3 ciclos

    monkeypatch.setattr(bp.time, "sleep", _fake_sleep)

    inst.sendReport()

    assert calls["sleep"] == 3
    assert calls["read"] >= 3  # leu a cada ciclo
    assert calls["write"] == 2  # 1º (novo) + 3º (mudou); o idêntico foi pulado


def test_sendreport_keepalive_reescreve_report_identico(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem mudança no report, o write ainda acontece a cada
    OUT_REPORT_KEEPALIVE_SEC (cobre perda de report/glitch de link)."""
    inst = _make_inst()

    calls = {"write": 0, "sleep": 0}
    now = {"t": 100.0}

    class _FakeDev:
        def read(self, _n: int) -> bytes:
            return bytes(_n)

    inst.device = _FakeDev()
    monkeypatch.setattr(inst, "readInput", lambda _r: None)
    monkeypatch.setattr(inst, "prepareReport", lambda: [0] * 64)
    def _count_write(_r: object) -> None:
        calls["write"] += 1

    monkeypatch.setattr(inst, "writeReport", _count_write)
    monkeypatch.setattr(bp.time, "monotonic", lambda: now["t"])

    def _fake_sleep(_secs: float) -> None:
        calls["sleep"] += 1
        now["t"] += bp.OUT_REPORT_KEEPALIVE_SEC + 0.01  # cada ciclo "passa" 0.51s
        if calls["sleep"] >= 3:
            inst.ds_thread = False

    monkeypatch.setattr(bp.time, "sleep", _fake_sleep)

    inst.sendReport()

    assert calls["write"] == 3  # report nunca mudou, mas o keepalive reescreveu


def test_sendreport_mutado_nao_escreve_nem_keepalive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FEAT-NATIVE-OUTPUT-MUTE-01: mutado (Modo Nativo), ZERO writes — nem o
    keepalive (que pisoteava o rumble que o jogo escrevia no hidraw)."""
    inst = _make_inst()
    inst._output_muted = True

    calls = {"write": 0, "sleep": 0}
    now = {"t": 100.0}

    class _FakeDev:
        def read(self, _n: int) -> bytes:
            return bytes(_n)

    inst.device = _FakeDev()
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

    assert calls["write"] == 0  # release total: o jogo é o dono do output
    assert calls["sleep"] == 3  # a leitura de input/bateria continuou viva


def test_set_output_mute_propaga_e_forca_reassert_ao_desmutar() -> None:
    """Backend propaga o mute a todos os handles; desmutar limpa o dirty-flag
    (o estado desejado do hefesto é re-escrito no próximo ciclo)."""
    ctl = bp.PyDualSenseController()

    class _FakeHandle:
        def __init__(self) -> None:
            self._output_muted = False
            self._last_out_report: list[int] | None = [1, 2, 3]

    h1, h2 = _FakeHandle(), _FakeHandle()
    ctl._handles = {"aa": h1, "bb": h2}  # type: ignore[dict-item]

    ctl.set_output_mute(True)
    assert h1._output_muted and h2._output_muted
    assert h1._last_out_report == [1, 2, 3]  # mute não mexe no dirty

    ctl.set_output_mute(False)
    assert not h1._output_muted and not h2._output_muted
    assert h1._last_out_report is None  # próximo ciclo re-escreve tudo
    assert h2._last_out_report is None


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
