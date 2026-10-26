"""O Off do gatilho não é desfeito pelo report que a volta montou antes dele.

Item 57 das pendências de 16/10 (o conferente do `f2-controle`): a volta do `sendReport`
(`_girar_a_volta`) monta o `prepareReport()` sem trava. Um report com o gatilho Rígido montado
um instante antes de o `soltar_os_gatilhos` armar o Off tomava o `_write_lock` logo depois do
quadro de Off; com o mudo do Nativo ou o `disconnect` em seguida, o Rígido ficava no firmware.
A cura: a volta lê a `_geracao_da_saida` antes de montar, o soltar a sobe depois de armar o Off,
e o `writeReport` descarta o quadro de geração velha.

A MORDIDA: tire o `geracao=geracao` da escrita da volta e
:func:`test_o_report_montado_antes_do_off_nao_sai_depois_dele` reprova; tire a subida da geração
do `soltar_os_gatilhos` e :func:`test_o_soltar_sobe_a_geracao_de_cada_handle` reprova.
"""
from __future__ import annotations

import contextlib
import threading
from types import SimpleNamespace
from typing import Any

import pytest
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp

RIGIDO = [0x02, 0xAA]
OFF = [0x02, 0x00]


class _Fio:
    def __init__(self) -> None:
        self.quadros: list[bytes] = []

    def write(self, quadro: bytes) -> int:
        self.quadros.append(bytes(quadro))
        return len(quadro)


def _volta_com_o_soltar_no_meio(monkeypatch: pytest.MonkeyPatch) -> _Fio:
    """Uma passada da volta em que o soltar arma o Off e escreve ENTRE o montar e o escrever."""
    monkeypatch.setattr(bp, "_hid_set_nonblocking", lambda _d: None)
    ds: Any = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    fio = _Fio()
    ds.device = fio
    ds._write_lock = threading.Lock()
    ds.ds_thread = True
    ds._acordar = None
    ds._output_muted = False
    ds._rumble_active = False
    ds._rumble_stop_pending = False
    ds._last_out_report = None
    ds._last_change_at = 0.0
    ds._last_write_at = 0.0
    ds._no_c = contextlib.nullcontext
    ds._esvaziar_a_fila = list
    ds._registrar_leitura_vazia = lambda: None
    ds._a_saida_espera_a_entrada = lambda _agora: False

    def _parar(_acordar: Any, *, lidos: bool) -> None:
        ds.ds_thread = False

    ds._dormir_a_volta = _parar

    def _montar() -> list[int]:
        montado = list(RIGIDO)
        ds._geracao_da_saida += 1
        ds.writeReport(list(OFF))
        return montado

    ds.prepareReport = _montar
    ds._girar_a_volta()
    return fio


def test_o_report_montado_antes_do_off_nao_sai_depois_dele(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fio = _volta_com_o_soltar_no_meio(monkeypatch)
    assert fio.quadros, "nem o Off saiu"
    assert fio.quadros[-1] == bytes(OFF), "o Rígido montado antes saiu por cima do Off"


def test_o_soltar_sobe_a_geracao_de_cada_handle() -> None:
    def _handle(transporte: str) -> SimpleNamespace:
        h = SimpleNamespace(
            conType=SimpleNamespace(name="BT_31" if transporte == "bt" else "USB_01"),
            triggerL=DSTrigger(), triggerR=DSTrigger(), light=DSLight(), audio=DSAudio(),
            _raw_trigger_left=None, _raw_trigger_right=None, _geracao_da_saida=3)
        h.writeReport = lambda report: len(report)
        return h

    ctl = bp.PyDualSenseController()
    handles = {"AA:BB:CC:00:00:01": _handle("usb"), "AA:BB:CC:00:00:03": _handle("bt")}
    ctl._handles = dict(handles)
    assert all(ctl.soltar_os_gatilhos().values())
    assert [h._geracao_da_saida for h in handles.values()] == [4, 4]


def test_a_escrita_sem_geracao_sai_sempre() -> None:
    ds: Any = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    ds.device = _Fio()
    ds._write_lock = threading.Lock()
    ds._no_c = contextlib.nullcontext
    ds._geracao_da_saida = 7
    assert ds.writeReport(list(OFF)) == len(OFF)
    assert ds.writeReport(list(RIGIDO), geracao=6) == 0
    assert ds.device.quadros == [bytes(OFF)]
